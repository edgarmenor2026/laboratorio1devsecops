pipeline {
    agent any
    
    environment {
        // Variables de entorno para el clúster
        DOCKER_IMAGE = "mi-app-nlp:latest"
        // Este ID debe coincidir con la credencial de tu kubeconfig en Jenkins
        KUBECONFIG_ID = 'k8s-credentials' 
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
                # Al estar dentro del clúster, kubectl se autentica automáticamente sin kubeconfig
                kubectl apply -f k8s/deployment.yaml
            '''
        }
    }        
    stage('Verify Deployment') {
            steps {
                withCredentials([file(credentialsId: env.KUBECONFIG_ID, variable: 'KUBECONFIG')]) {
                    sh 'kubectl rollout status deployment/nlp-app-deployment'
                    sh 'kubectl get pods -l app=nlp-app'
                }
            }
        }
    }
}