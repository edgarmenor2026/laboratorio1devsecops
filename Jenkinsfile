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
                        echo "Verificando e instalando dependencias (kubectl y auth-plugin)..."
                        
                        # 1. Instalar kubectl si no existe
                        if ! command -v kubectl &> /dev/null; then
                            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                            chmod +x kubectl
                            mkdir -p ~/.local/bin
                            mv kubectl ~/.local/bin/
                        fi
        
                        # 2. Instalar el plugin de autenticación de GKE si no existe
                        if ! command -v gke-gcloud-auth-plugin &> /dev/null; then
                            echo "Descargando Google Cloud SDK para obtener gke-gcloud-auth-plugin..."
                            curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz
                            tar -xf google-cloud-cli-linux-x86_64.tar.gz
                            mkdir -p ~/.local/google-cloud-sdk
                            ./google-cloud-sdk/install.sh --quiet --path-update=false
                            mv google-cloud-sdk ~/.local/
                        fi
        
                        # 3. Configurar el PATH para incluir las herramientas
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