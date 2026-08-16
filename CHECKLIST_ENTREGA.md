# Checklist de entrega

## Repositorio

- [ ] Código fuente y tests.
- [ ] `.github/workflows/ci.yml` en `main`.
- [ ] `Jenkinsfile` en `main`.
- [ ] Dockerfile y `.dockerignore`.
- [ ] Manifiestos `k8s/`.
- [ ] Configuración `monitoring/`.
- [ ] Sin kubeconfig, claves, tokens ni ZIP de trabajo.
- [ ] Enlace al repositorio incluido en el documento.

## CI

- [ ] Test y sintaxis en verde.
- [ ] Sonar Quality Gate en verde.
- [ ] Snyk ejecutado y reporte descargado.
- [ ] Imagen publicada con SHA.
- [ ] Digest documentado.
- [ ] Captura de la ejecución completa.

## CD

- [ ] Jenkins agente con ServiceAccount `jenkins-deployer`.
- [ ] RBAC validado.
- [ ] `IMAGE_TAG` corresponde al SHA de CI.
- [ ] `IMAGE_DIGEST` corresponde al digest emitido por Buildx.
- [ ] Rollout exitoso.
- [ ] Smoke test `/health/ready` exitoso.
- [ ] Captura de Jenkins.

## Monitoreo

- [ ] Prometheus target de `nlp-app` en estado UP.
- [ ] Dashboard de aplicación con datos.
- [ ] Dashboard Kubernetes con CPU, memoria y pods.
- [ ] Reglas `NlpAppUnavailable` y `NlpAppRestarting` cargadas.
- [ ] Capturas de Grafana y Prometheus.

## Informe

- [ ] Flujo CI/CD descrito.
- [ ] Herramientas y decisiones justificadas.
- [ ] Vulnerabilidades y remediación documentadas.
- [ ] Evidencia de monitoreo incluida.
- [ ] Reflexión de eficiencia operativa.
- [ ] Riesgos y mejoras pendientes declarados.
