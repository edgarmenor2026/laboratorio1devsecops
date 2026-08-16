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
                    echo "--- 1. Instalando kubectl ---"
                    curl -LO "https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl"
                    chmod +x kubectl
                    mkdir -p ~/.local/bin
                    mv kubectl ~/.local/bin/
    
                    echo "--- 2. Descargando Google Cloud SDK Base ---"
                    curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz
                    tar -xzf google-cloud-cli-linux-x86_64.tar.gz
                    
                    echo "--- 3. SOLUCIÓN DE RAÍZ: Liberando 100MB inmediatamente ---"
                    # Al borrar el comprimido original evitamos superar el límite de 1GB (1Gi)
                    rm google-cloud-cli-linux-x86_64.tar.gz 
    
                    echo "--- 4. Descargando e instalando el plugin gke-auth-plugin ---"
                    ./google-cloud-sdk/bin/gcloud components install gke-gcloud-auth-plugin --quiet
    
                    echo "--- 5. Limpiando cachés y organizando el sistema ---"
                    # Borramos los archivos residuales de la instalación de Google
                    rm -rf ./google-cloud-sdk/.install/.backup
                    
                    # Movemos el SDK listo a la carpeta del usuario
                    mkdir -p ~/.local
                    rm -rf ~/.local/google-cloud-sdk
                    mv google-cloud-sdk ~/.local/
                    
                    # Configuramos la ruta para que Jenkins encuentre los comandos
                    export PATH=$PATH:~/.local/bin:~/.local/google-cloud-sdk/bin
    
                    echo "--- 6. Desplegando en el Clúster de Kubernetes ---"
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