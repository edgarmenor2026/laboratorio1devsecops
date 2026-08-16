# Implementación de pipeline CI/CD con seguridad y monitoreo

## 1. Resumen ejecutivo

El proyecto implementa una cadena DevSecOps dividida en dos controles: GitHub Actions ejecuta integración continua, análisis de seguridad y publicación de imágenes; Jenkins ejecuta la promoción controlada de una imagen inmutable hacia Kubernetes. Prometheus y Grafana cubren observabilidad de infraestructura y aplicación.

La separación evita otorgar acceso al daemon Docker al agente Jenkins. También mejora la trazabilidad porque el artefacto promovido se identifica mediante el SHA del commit y el digest generado durante la construcción.

## 2. Arquitectura y flujo

```text
Developer -> GitHub push/PR
              |
              v
       GitHub Actions CI
       - syntax/tests
       - SonarQube Cloud
       - Snyk test
       - Docker Buildx
              |
              v
       Artifact Registry
       image:<commit-sha> + digest
              |
              v
       Jenkins CD (IMAGE_TAG + IMAGE_DIGEST)
       - in-cluster ServiceAccount
       - namespace-scoped RBAC
       - kubectl apply/rollout/smoke test
              |
              v
       GKE namespace devsecops
              |
              +--> Prometheus scrape
              +--> Grafana dashboards
              +--> PrometheusRule alerts
```

## 3. Herramientas y justificación

| Herramienta | Uso | Justificación |
|---|---|---|
| GitHub Actions | CI, pruebas, SAST/SCA, build y push | Ejecuta controles cerca del repositorio y emite una imagen trazable. |
| SonarQube Cloud | Análisis estático y Quality Gate | Detecta bugs, vulnerabilidades y deuda de mantenibilidad antes de publicar. |
| Snyk | Análisis de dependencias | Bloquea dependencias con vulnerabilidades high/critical según la política definida. |
| Artifact Registry | Registro de imágenes | Conserva imágenes etiquetadas por SHA y sus digests. |
| Jenkins | Promoción y despliegue | Implementa CD separado, auditado y con parámetros explícitos. |
| Kubernetes/GKE | Ejecución | Proporciona rollout, probes, aislamiento por namespace y control RBAC. |
| Prometheus | Métricas y alertas | Recolecta métricas de pods, nodos, despliegues y endpoint `/metrics`. |
| Grafana | Visualización | Consolida señales operativas en dashboards de infraestructura y aplicación. |

## 4. Controles de seguridad implementados

- OIDC/Workload Identity Federation para GitHub Actions; no se almacenan claves JSON de Google Cloud.
- Cuenta de servicio CI con permiso `artifactregistry.writer` limitado al repositorio.
- ServiceAccount de Jenkins con Role y RoleBinding limitados al namespace `devsecops`.
- Jenkins no usa Docker socket, modo privilegiado ni credenciales permanentes de GCP.
- Snyk `test` actúa como compuerta ante severidad high/critical.
- SonarQube Cloud espera el resultado de Quality Gate.
- Contenedor no root, sin escalamiento de privilegios, capacidades Linux eliminadas, filesystem de solo lectura y token de ServiceAccount deshabilitado.
- Imagen etiquetada por SHA y desplegada por digest; `latest` se conserva solo como referencia humana y nunca se usa para promover.

## 5. Evidencias de seguridad

### SonarQube Cloud

- URL o proyecto: `edgarmenor2026_laboratorio1devsecops`
- Fecha de análisis: **[completar]**
- Estado del Quality Gate: **[completar]**
- Issues principales y correcciones: **[completar]**
- Evidencia: `evidencias/sonar-quality-gate.png`

### Snyk

| Dependencia | Severidad | Hallazgo | Acción | Estado |
|---|---:|---|---|---|
| **[completar]** | **[completar]** | **[completar]** | Actualizar, reemplazar, mitigar o aceptar con justificación | **[completar]** |

Artefacto del pipeline: `snyk-open-source-report`.

## 6. Implementación de CI

Archivo: `.github/workflows/ci.yml`.

Controles:

1. Checkout completo para que Sonar analice historial.
2. Instalación y verificación de dependencias.
3. Compilación de sintaxis y tests.
4. SonarQube Cloud con espera de Quality Gate.
5. Snyk con reporte JSON y compuerta high/critical.
6. Autenticación federada a Google Cloud.
7. Buildx con cache, SBOM y provenance.
8. Publicación por SHA y digest.

Evidencia: `evidencias/github-actions-ci.png`.

## 7. Implementación de CD

Archivo: `Jenkinsfile`.

El operador suministra el SHA y el digest producidos por CI. Jenkins despliega por digest, valida RBAC, aplica Service y Deployment, espera el rollout y ejecuta una prueba sobre `/health/ready`. Ante fallo recopila estado, eventos, descripción y logs.

Evidencia: `evidencias/jenkins-cd.png`.

Imagen desplegada: **[completar URI@sha256:digest]**  
Digest: **[completar sha256]**

## 8. Kubernetes

- Namespace: `devsecops`.
- Deployment inicial: una réplica por el costo de memoria de modelos NLP.
- Puerto: `7860`, expuesto por Service interno en `80`.
- Probes: startup, readiness y liveness.
- Recursos iniciales: request `500m/1Gi`, límite `2 CPU/3Gi`; deben ajustarse con medición.
- Rollout: `maxUnavailable=0`, `maxSurge=1`.

## 9. Monitoreo y alertas

`kube-prometheus-stack` instala Prometheus, Grafana, kube-state-metrics, node exporter y componentes del operador. La aplicación expone métricas Prometheus en `/metrics` y un ServiceMonitor configura el descubrimiento.

Dashboard: **NLP Application - DevSecOps**.

Métricas clave:

- `nlp_http_requests_total`;
- `nlp_http_request_duration_seconds`;
- `nlp_model_ready`;
- `nlp_model_load_seconds`;
- `nlp_analyses_total`;
- CPU y memoria del contenedor;
- réplicas disponibles y reinicios.

Alertas:

- `NlpAppUnavailable`;
- `NlpAppRestarting`.

Evidencia: `evidencias/grafana-dashboard.png` y `evidencias/prometheus-target.png`.

## 10. Reflexión sobre eficiencia operativa

La principal mejora no es acelerar un comando aislado, sino reducir retrabajo y ambigüedad. CI produce una única imagen verificada; CD despliega exactamente ese artefacto sin reconstruirlo. Esto elimina diferencias entre entornos, permite rollback a un SHA anterior y concentra diagnósticos en el pipeline.

La autenticación federada reduce la gestión de secretos. RBAC limita el impacto de una credencial comprometida. Las probes y métricas acortan el tiempo para distinguir un error de imagen, permisos, capacidad, enrutamiento o salud de la aplicación.

Persisten oportunidades de mejora: mover el entrenamiento a un pipeline MLOps independiente, firmar y verificar imágenes, generar un lockfile reproducible, agregar pruebas funcionales y de carga, definir SLOs, configurar notificaciones reales de Alertmanager y usar Ingress con TLS y autenticación si la API se expone externamente.

## 11. Conclusión

La solución cubre CI, CD, seguridad y monitoreo con trazabilidad de extremo a extremo. El criterio central es que un commit solo puede llegar a Kubernetes después de superar pruebas, Quality Gate, análisis de dependencias y publicación de una imagen identificable; posteriormente, Jenkins verifica el rollout y Prometheus/Grafana mantienen visibilidad operativa continua.
