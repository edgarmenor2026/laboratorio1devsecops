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
                        echo "Verificando o instalando kubectl..."
                        if ! command -v kubectl &> /dev/null; then
                            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                            chmod +x kubectl
                            mkdir -p ~/.local/bin
                            mv kubectl ~/.local/bin/
                            export PATH=$PATH:~/.local/bin/
                        fi
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