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
                    export PATH=$PATH:~/.local/bin/
                    kubectl rollout status deployment/nlp-app-deployment
                '''
            }
        }
    }
}