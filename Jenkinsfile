pipeline {
    agent any
    
    environment {
        // Variables de entorno para el clúster
        DOCKER_IMAGE = "mi-app-nlp:latest"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    echo "--- 1. Instalando kubectl (Ligero, sin saturar la RAM) ---"
                    curl -LO "https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl"
                    chmod +x kubectl
                    mkdir -p ~/.local/bin
                    mv kubectl ~/.local/bin/
                    export PATH=$PATH:~/.local/bin/

                    echo "--- 2. Desplegando en Kubernetes de forma nativa ---"
                    kubectl apply -f k8s/deployment.yaml
                '''
            }
        }
        stage('Verify Deployment') {
            steps {
                sh '''
                echo "--- 3. Verificando el estado del despliegue ---"
                export PATH=/opt/java/openjdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/jenkins/.local/bin/

                # Intentar verificar el rollout. Si falla, ejecutar comandos de debug.
                if ! kubectl rollout status deployment/nlp-app-deployment --timeout=3m; then
                    echo "El despliegue falló. Obteniendo información de los pods para depurar:"
                    echo "--- ESTADO DE LOS PODS ---"
                    kubectl get pods
                    echo "--- EVENTOS DEL DESPLIEGUE ---"
                    kubectl describe deployment nlp-app-deployment
                    echo "--- EVENTOS DE LOS PODS FALLIDOS ---"
                    # Describe los pods que no están en estado Running
                    kubectl get pods --field-selector=status.phase!=Running -o name | xargs -r kubectl describe
                    exit 1 # Forzar la falla del pipeline de nuevo
                fi
                '''
            }
        }        
    }
}