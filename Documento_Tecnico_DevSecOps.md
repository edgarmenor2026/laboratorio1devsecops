# Documento Técnico: Implementación de Pipeline CI/CD DevSecOps y MLOps

**Fecha:** Agosto 2026

## 1. Descripción del Flujo CI/CD

El pipeline diseñado sigue una arquitectura DevSecOps orientada a una aplicación de Inteligencia Artificial. El flujo se divide en dos fases principales integradas de manera fluida:

1.  **Integración Continua (CI) con GitHub Actions:**
    *   Se activa automáticamente con cada `push` a la rama principal del repositorio.
    *   Configura el entorno de Python e instala las dependencias necesarias.
    *   **SonarQube (Análisis Estático):** Evalúa la calidad del código (`app.py`), identificando *code smells*, bugs y vulnerabilidades lógicas.
    *   **Snyk (Análisis de Dependencias):** Escanea el archivo `requirements.txt` y el contenedor en busca de vulnerabilidades conocidas en librerías de terceros.
    *   Finaliza con la construcción (Build) de la imagen de Docker, validando que el empaquetado sea correcto.

2.  **Despliegue Continuo (CD) con Jenkins:**
    *   Se encarga de la orquestación hacia el entorno de ejecución.
    *   Aplica los manifiestos declarativos de Kubernetes (`deployment.yaml` y `service.yaml`) para desplegar los pods en el clúster.
    *   Verifica el estado del despliegue asegurando que la aplicación esté levantada y lista para recibir tráfico.

## 2. Herramientas Utilizadas y Justificación

*   **GitHub Actions:** Seleccionado por su proximidad al código fuente, lo que permite un *feedback* inmediato al desarrollador tras cada *commit*.
*   **Jenkins:** Utilizado como orquestador de despliegue por su flexibilidad y capacidad nativa para conectarse y administrar clústeres de Kubernetes mediante credenciales seguras.
*   **SonarQube:** Vital para mantener altos estándares de calidad de software y reducir la deuda técnica, algo crítico en el ciclo de vida del software.
*   **Snyk:** Herramienta líder para implementar el concepto de *Shift-Left Security*, detectando brechas de seguridad antes de que el código llegue al clúster.
*   **Kubernetes (K8s):** Estándar de la industria para la orquestación de contenedores, garantizando escalabilidad, resiliencia y auto-recuperación de la aplicación.
*   **Prometheus y Grafana:** Conforman el *stack* de observabilidad. Prometheus actúa como motor de recolección de métricas temporales (Time Series) y Grafana proporciona la capa de visualización para monitorear CPU, Memoria y estado de los Pods.

## 3. Evidencia de Seguridad y Monitoreo

*(Instrucción: Reemplaza este bloque con capturas de pantalla)*
*   [ ] Captura de los resultados de Snyk (vulnerabilidades detectadas o mitigadas).
*   [ ] Captura del informe de SonarQube (Quality Gate superado).
*   [ ] Captura del dashboard de Grafana mostrando el uso de recursos de los pods de la aplicación.

## 4. Reflexión sobre Eficiencia Operativa

La automatización de las pruebas de seguridad y el despliegue iterativo transforma significativamente el ciclo de vida del desarrollo. Al integrar SonarQube y Snyk directamente en GitHub Actions, logramos detectar vulnerabilidades en la fase más temprana de codificación, evitando el despliegue de configuraciones inseguras en el clúster. Asimismo, contar con observabilidad continua mediante Grafana y Prometheus asegura que cualquier anomalía en el rendimiento de la aplicación se detecte y mitigue de forma proactiva, garantizando la estabilidad operativa requerida.
