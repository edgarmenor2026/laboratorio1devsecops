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
            withCredentials([file(credentialsId: 'k8s-credentials', variable: 'KUBECONFIG')]) {
                sh '''
                    echo "Instalando kubectl..."
                    curl -LO "https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl"
                    chmod +x kubectl
                    mkdir -p ~/.local/bin
                    mv kubectl ~/.local/bin/

                    echo "Instalando gke-gcloud-auth-plugin de forma ligera (optimizada para almacenamiento)..."
                    curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz

                    # Extraer únicamente el binario y las librerías esenciales para no exceder 1Gi
                    tar -xzf google-cloud-cli-linux-x86_64.tar.gz google-cloud-sdk/bin/gke-gcloud-auth-plugin google-cloud-sdk/lib/

                    mkdir -p ~/.local/google-cloud-sdk/bin
                    mv google-cloud-sdk/bin/gke-gcloud-auth-plugin ~/.local/google-cloud-sdk/bin/

                    # Limpiar inmediatamente los archivos temporales
                    rm -rf google-cloud-cli-linux-x86_64.tar.gz google-cloud-sdk

                    # Configurar el PATH
                    export PATH=$PATH:~/.local/bin:~/.local/google-cloud-sdk/bin

                    echo "Desplegando en Kubernetes..."
                    kubectl apply -f k8s/deployment.yaml
                '''
            }
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