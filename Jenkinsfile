pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 25, unit: 'MINUTES')
    }

    parameters {
        string(
            name: 'IMAGE_TAG',
            defaultValue: '',
            description: 'SHA completo de 40 caracteres publicado por el job build-and-push de GitHub Actions.'
        )
        string(
            name: 'IMAGE_DIGEST',
            defaultValue: '',
            description: 'Digest sha256 publicado en deployment-metadata.txt; Jenkins despliega por digest, no por latest.'
        )
        string(
            name: 'KUBECTL_VERSION',
            defaultValue: 'v1.30.0',
            description: 'Versión de kubectl compatible con el clúster. Manténgala dentro de +/- 1 minor del API server.'
        )
    }

    environment {
        IMAGE_REPOSITORY = 'us-central1-docker.pkg.dev/laboratorio1devsecops/repo-nlp/mi-app-nlp'
        K8S_NAMESPACE = 'devsecops'
        DEPLOYMENT_NAME = 'nlp-app-deployment'
        CONTAINER_NAME = 'nlp-app-container'
        SERVICE_NAME = 'nlp-app-service'
        KUBECTL = "${WORKSPACE}/.tools/kubectl"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install kubectl') {
            steps {
                sh '''
                    set -eu
                    mkdir -p "$(dirname "$KUBECTL")"
                    curl -fsSLo "$KUBECTL" \
                      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
                    curl -fsSLo "${KUBECTL}.sha256" \
                      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl.sha256"
                    echo "$(cat "${KUBECTL}.sha256")  ${KUBECTL}" | sha256sum -c -
                    chmod 0755 "$KUBECTL"
                    "$KUBECTL" version --client=true
                '''
            }
        }

        stage('Validate deployment input and RBAC') {
            steps {
                sh '''
                    set -eu
                    if ! printf '%s' "$IMAGE_TAG" | grep -Eq '^[0-9a-f]{40}$'; then
                      echo "IMAGE_TAG debe ser el SHA completo de 40 caracteres generado por CI: $IMAGE_TAG" >&2
                      exit 2
                    fi
                    if ! printf '%s' "$IMAGE_DIGEST" | grep -Eq '^sha256:[0-9a-f]{64}$'; then
                      echo "IMAGE_DIGEST debe tener el formato sha256:<64 hex>: $IMAGE_DIGEST" >&2
                      exit 2
                    fi

                    echo "Identity visible from this agent:"
                    "$KUBECTL" auth whoami || true

                    for CHECK in \
                      "get deployments.apps" \
                      "create deployments.apps" \
                      "patch deployments.apps" \
                      "get services" \
                      "create services" \
                      "patch services"; do
                        VERB=$(printf '%s' "$CHECK" | cut -d' ' -f1)
                        RESOURCE=$(printf '%s' "$CHECK" | cut -d' ' -f2)
                        "$KUBECTL" auth can-i "$VERB" "$RESOURCE" -n "$K8S_NAMESPACE" | grep -qx yes
                    done
                '''
            }
        }

        stage('Deploy immutable image') {
            steps {
                sh '''
                    set -eu
                    IMAGE="${IMAGE_REPOSITORY}@${IMAGE_DIGEST}"
                    echo "Deploying ${IMAGE} into namespace ${K8S_NAMESPACE}"

                    "$KUBECTL" apply -n "$K8S_NAMESPACE" -f k8s/service.yaml

                    "$KUBECTL" set image \
                      -f k8s/deployment.yaml \
                      "${CONTAINER_NAME}=${IMAGE}" \
                      --local -o yaml \
                    | "$KUBECTL" apply -n "$K8S_NAMESPACE" -f -

                    "$KUBECTL" annotate deployment "$DEPLOYMENT_NAME" \
                      -n "$K8S_NAMESPACE" \
                      devsecops/image-tag="$IMAGE_TAG" \
                      devsecops/image-digest="$IMAGE_DIGEST" \
                      devsecops/jenkins-build="${BUILD_URL:-unknown}" \
                      --overwrite
                '''
            }
        }

        stage('Verify rollout and smoke test') {
            steps {
                sh '''
                    set -eu
                    "$KUBECTL" rollout status deployment/"$DEPLOYMENT_NAME" \
                      -n "$K8S_NAMESPACE" --timeout=15m

                    "$KUBECTL" get deployment,pods,service,endpoints \
                      -n "$K8S_NAMESPACE" -o wide

                    SERVICE_URL="http://${SERVICE_NAME}.${K8S_NAMESPACE}.svc.cluster.local/health/ready"
                    curl -fsS --retry 12 --retry-delay 5 --retry-all-errors "$SERVICE_URL"
                    echo
                '''
            }
        }
    }

    post {
        success {
            echo "Deployment completed: ${IMAGE_REPOSITORY}@${params.IMAGE_DIGEST} (commit ${params.IMAGE_TAG})"
        }
        failure {
            sh '''
                set +e
                if [ -x "$KUBECTL" ]; then
                  "$KUBECTL" get all -n "$K8S_NAMESPACE" -o wide
                  "$KUBECTL" describe deployment "$DEPLOYMENT_NAME" -n "$K8S_NAMESPACE"
                  "$KUBECTL" get events -n "$K8S_NAMESPACE" \
                    --sort-by='.lastTimestamp' | tail -n 80
                  for POD in $("$KUBECTL" get pods -n "$K8S_NAMESPACE" \
                    -l app=nlp-app -o name); do
                    "$KUBECTL" describe "$POD" -n "$K8S_NAMESPACE"
                    "$KUBECTL" logs "$POD" -n "$K8S_NAMESPACE" \
                      -c "$CONTAINER_NAME" --tail=200
                  done
                fi
            '''
        }
        always {
            deleteDir()
        }
    }
}
