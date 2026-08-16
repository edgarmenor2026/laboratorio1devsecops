# Guía de implementación DevSecOps

Esta guía corrige la arquitectura actual y deja dos responsabilidades separadas:

1. **GitHub Actions (CI):** valida, ejecuta SonarQube Cloud y Snyk, construye la imagen y la publica en Artifact Registry con la etiqueta inmutable del commit.
2. **Jenkins (CD):** recibe la etiqueta publicada y despliega esa imagen en Kubernetes. Jenkins no ejecuta Docker ni administra credenciales de Google Cloud.

## 0. Hallazgos que se deben corregir

- El agente dinámico de Jenkins es `jenkins/inbound-agent`; contiene Git y Java, pero no el binario ni el daemon de Docker. Por eso `docker build` termina con código 127.
- La aplicación escucha en `7860`, mientras Deployment y Service estaban configurados en `5000`.
- El Jenkinsfile aplicaba únicamente `deployment.yaml`; el Service no quedaba garantizado.
- La aplicación entrenaba el MLP y leía el CSV completo durante cada arranque del pod.
- El límite de `512Mi` no es realista para Python, PyTorch/SentenceTransformer y dos modelos spaCy.
- `Snyk monitor` registraba el proyecto, pero no actuaba como compuerta de seguridad del pipeline.
- `kubeconfig.yaml`, el ZIP y el dataset completo no deben permanecer en el árbol activo del repositorio.

## 1. Copiar el parche al repositorio

Copia el contenido de este paquete sobre la raíz del repositorio y revisa el diff antes de confirmar:

```bash
rsync -av --exclude GUIA_IMPLEMENTACION.md ./devsecops_patch/ ./laboratorio1devsecops/
cd laboratorio1devsecops
git status
git diff -- . ':!data/muestra_nlp_sample.jsonl'
```

Elimina del repositorio los artefactos que no deben versionarse:

```bash
git rm --cached kubeconfig.yaml 2>/dev/null || true
git rm --cached Aplicacion.zip 2>/dev/null || true
git rm --cached muestra_nlp_limpia.csv 2>/dev/null || true
rm -f kubeconfig.yaml Aplicacion.zip muestra_nlp_limpia.csv
git add .
git commit -m "Implement CI security gates, immutable image delivery and Kubernetes monitoring"
git push origin main
```

Eliminar el archivo actual no elimina copias antiguas del historial. Si el kubeconfig alguna vez incluyó tokens, claves o certificados cliente, rota esas credenciales y limpia el historial con `git filter-repo`.

## 2. Preparar Google Artifact Registry y Workload Identity Federation

Ejecuta estos comandos desde una terminal con `gcloud` autenticado y permisos de administración del proyecto. Ajusta nombres solo si tu infraestructura es diferente.

```bash
export PROJECT_ID="laboratorio1devsecops"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export REGION="us-central1"
export GAR_REPOSITORY="repo-nlp"
export GITHUB_REPOSITORY="edgarmenor2026/laboratorio1devsecops"
export CI_SERVICE_ACCOUNT="github-ci@${PROJECT_ID}.iam.gserviceaccount.com"
export WIF_POOL="github-actions"
export WIF_PROVIDER="laboratorio1devsecops"

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com

gcloud artifacts repositories describe "$GAR_REPOSITORY" --location "$REGION" >/dev/null 2>&1 || \
gcloud artifacts repositories create "$GAR_REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Images for the DevSecOps laboratory"

gcloud iam service-accounts describe "$CI_SERVICE_ACCOUNT" >/dev/null 2>&1 || \
gcloud iam service-accounts create github-ci \
  --display-name="GitHub Actions CI publisher"

gcloud artifacts repositories add-iam-policy-binding "$GAR_REPOSITORY" \
  --location="$REGION" \
  --member="serviceAccount:${CI_SERVICE_ACCOUNT}" \
  --role="roles/artifactregistry.writer"

gcloud iam workload-identity-pools describe "$WIF_POOL" --location=global >/dev/null 2>&1 || \
gcloud iam workload-identity-pools create "$WIF_POOL" \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
  --workload-identity-pool="$WIF_POOL" --location=global >/dev/null 2>&1 || \
gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
  --workload-identity-pool="$WIF_POOL" \
  --location=global \
  --display-name="laboratorio1devsecops GitHub provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='${GITHUB_REPOSITORY}' && assertion.ref=='refs/heads/main'"

gcloud iam service-accounts add-iam-policy-binding "$CI_SERVICE_ACCOUNT" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPOSITORY}"

export PROVIDER_RESOURCE="$(gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
  --workload-identity-pool="$WIF_POOL" \
  --location=global \
  --format='value(name)')"

printf 'GCP_WORKLOAD_IDENTITY_PROVIDER=%s\n' "$PROVIDER_RESOURCE"
printf 'GCP_SERVICE_ACCOUNT=%s\n' "$CI_SERVICE_ACCOUNT"
```

En **GitHub > Settings > Secrets and variables > Actions** crea:

- Variables: `GCP_WORKLOAD_IDENTITY_PROVIDER` y `GCP_SERVICE_ACCOUNT`.
- Secrets: `SONAR_TOKEN` y `SNYK_TOKEN`.

No crees una clave JSON de cuenta de servicio. El workflow usa OIDC y credenciales temporales.

## 3. Ejecutar y verificar CI

Haz push a `main` o ejecuta `workflow_dispatch`. La ejecución debe mostrar, en este orden:

1. Tests y validación de sintaxis.
2. SonarQube Cloud con resultado de Quality Gate.
3. Snyk `test` con umbral `high`.
4. Build y push a Artifact Registry.
5. Artefacto `deployment-metadata` con el SHA y el digest que se usarán en Jenkins.

Obtén el SHA del commit:

```bash
git rev-parse HEAD
```

Comprueba la imagen:

```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/laboratorio1devsecops/repo-nlp/mi-app-nlp \
  --include-tags
```

No continúes con CD si `validate-and-scan` falla. Corregir la vulnerabilidad o la condición del Quality Gate es parte de la actividad; desactivar la compuerta solo produce un pipeline verde sin control de seguridad.

## 4. Crear el namespace y RBAC de Jenkins

Estos manifiestos son de bootstrap y deben aplicarse una sola vez con una identidad administradora del clúster:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac-jenkins.yaml
```

Los manifiestos anteriores no tenían `namespace`, por lo que probablemente dejaron recursos en `default`. Elimínalos después de confirmar que no contienen otra carga válida:

```bash
kubectl delete deployment nlp-app-deployment -n default --ignore-not-found
kubectl delete service nlp-app-service -n default --ignore-not-found
```

Después, en Jenkins:

1. Abre **Manage Jenkins > Clouds > Kubernetes > Pod Templates > default**.
2. En el campo **Service Account** escribe `jenkins-deployer`.
3. Guarda la configuración.
4. Lanza una nueva ejecución; un pod ya creado no cambia de identidad retroactivamente.

Verifica desde un agente nuevo:

```bash
kubectl auth can-i patch deployments.apps -n devsecops
kubectl auth can-i create services -n devsecops
```

Ambos comandos deben responder `yes`. El Jenkinsfile hace estas comprobaciones y falla antes del despliegue si el RBAC es insuficiente.

## 5. Verificar que GKE puede descargar la imagen

Los nodos o la identidad administrada por GKE necesitan permiso de lectura sobre el repositorio. Identifica la cuenta de servicio de nodos configurada en tu clúster y concédele, si aún no lo tiene, `roles/artifactregistry.reader` en el repositorio:

```bash
export NODE_SERVICE_ACCOUNT="$(gcloud container clusters describe laboratorio1devsecops \
  --region us-central1 \
  --format='value(nodeConfig.serviceAccount)')"

echo "$NODE_SERVICE_ACCOUNT"
```

Si el resultado es `default`, consulta la cuenta Compute Engine predeterminada:

```bash
export NODE_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

Concede lectura:

```bash
gcloud artifacts repositories add-iam-policy-binding repo-nlp \
  --location=us-central1 \
  --member="serviceAccount:${NODE_SERVICE_ACCOUNT}" \
  --role="roles/artifactregistry.reader"
```

## 6. Ejecutar CD en Jenkins

Crea o actualiza el Pipeline para que lea `Jenkinsfile` desde `main`. Usa **Build with Parameters**:

- `IMAGE_TAG`: SHA completo publicado por GitHub Actions.
- `IMAGE_DIGEST`: valor `sha256:...` publicado en `deployment-metadata.txt`.
- `KUBECTL_VERSION`: usa una versión compatible con el API server del clúster. El valor inicial conserva `v1.30.0`, pero debes ajustarlo si GKE ya está en otro minor.

El pipeline:

1. Descarga y verifica `kubectl`.
2. Valida la etiqueta y los permisos RBAC.
3. Aplica el Service.
4. sustituye localmente la imagen del Deployment por `IMAGE_REPOSITORY@IMAGE_DIGEST` y conserva el SHA como anotación trazable.
5. espera el rollout.
6. ejecuta `/health/ready` por DNS interno.
7. muestra eventos y logs automáticamente cuando hay fallo.

Comandos de verificación manual:

```bash
kubectl get deployment,pods,service,endpoints -n devsecops -o wide
kubectl rollout status deployment/nlp-app-deployment -n devsecops --timeout=15m
kubectl get deployment nlp-app-deployment -n devsecops \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Para probar la API desde tu equipo sin abrir un LoadBalancer público:

```bash
kubectl port-forward -n devsecops service/nlp-app-service 7860:80
./scripts/smoke-test.sh http://127.0.0.1:7860
```

## 7. Instalar Prometheus y Grafana

Instala `kube-prometheus-stack`, que incluye Prometheus Operator, Grafana, kube-state-metrics, node exporter, reglas y dashboards base:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values monitoring/values-kube-prometheus-stack.yaml \
  --wait \
  --timeout 15m

kubectl apply -f monitoring/servicemonitor.yaml
kubectl apply -f monitoring/prometheusrule.yaml
kubectl apply -f monitoring/grafana-dashboard-nlp.yaml
```

Verifica que Prometheus descubrió la aplicación:

```bash
kubectl get servicemonitor,prometheusrule -n devsecops
kubectl get pods -n monitoring
kubectl port-forward -n monitoring service/monitoring-kube-prometheus-prometheus 9090:9090
```

En Prometheus consulta:

```promql
nlp_model_ready
sum(rate(nlp_http_requests_total[5m]))
kube_deployment_status_replicas_available{namespace="devsecops",deployment="nlp-app-deployment"}
```

Accede a Grafana:

```bash
kubectl get secret -n monitoring monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl port-forward -n monitoring service/monitoring-grafana 3000:80
```

Usuario: `admin`. Abre el dashboard **NLP Application - DevSecOps** y también los dashboards Kubernetes incluidos para CPU, memoria y estado de pods.

## 8. Evidencias de seguridad

Captura y conserva:

- GitHub Actions con `validate-and-scan` y `build-and-push` en verde.
- Quality Gate y principales issues en SonarQube Cloud.
- Artifact `snyk-open-source-report` y la tabla de vulnerabilidades corregidas, aceptadas o pendientes.
- URI y digest de la imagen publicada.
- Jenkins mostrando el SHA, el digest desplegado, rollout y smoke test.

Para cada vulnerabilidad documenta: dependencia, versión afectada, severidad, vector, corrección propuesta, decisión y evidencia de reescaneo.

## 9. Evidencias de monitoreo

Genera tráfico con varias llamadas al endpoint y captura:

- request rate;
- latencia p95;
- errores 5xx;
- `nlp_model_ready`;
- CPU y memoria del contenedor;
- réplicas disponibles y reinicios;
- reglas de alerta activas o en estado normal.

## 10. Problemas frecuentes

### `docker: not found`

Esperado con el Jenkinsfile antiguo. El nuevo Jenkinsfile no usa Docker.

### `Forbidden` al ejecutar kubectl

El pod agente sigue usando `serviceAccountName: default`, el RoleBinding no existe o el namespace no coincide. Crea un agente nuevo después de cambiar el template.

### `ImagePullBackOff`

La etiqueta no existe o la identidad de nodos no tiene `artifactregistry.reader`. Comprueba la URI exacta y los eventos del pod.

### `CrashLoopBackOff` u `OOMKilled`

Inspecciona `kubectl describe pod` y métricas. El parche empieza con un límite de `3Gi`, no con `512Mi`. Ajusta tras medir; no reduzcas por intuición.

### `connection refused` en el Service

Comprueba que el contenedor, Service y probes usan `7860`/puerto nombrado `http`. El manifiesto anterior dirigía tráfico a `5000`.

### Prometheus no ve `/metrics`

Revisa que el Service tenga la etiqueta `app: nlp-app`, el puerto se llame `http`, exista el ServiceMonitor y Prometheus seleccione su namespace.

## 11. Criterio de terminación

La actividad está terminada cuando se cumplen simultáneamente estas condiciones:

- CI bloquea fallos de tests, Quality Gate y vulnerabilidades high/critical.
- La imagen desplegada corresponde al digest emitido por CI, está asociada a un SHA trazable y existe en Artifact Registry.
- Jenkins no posee Docker socket ni credenciales estáticas de Google.
- Deployment, Service, probes y puertos son coherentes.
- Prometheus recolecta métricas de infraestructura y aplicación.
- Grafana muestra el dashboard y existen al menos dos reglas de alerta.
- El documento técnico enlaza las evidencias y explica decisiones, riesgos y mejoras pendientes.
