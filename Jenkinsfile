pipeline {
    agent any

    environment {
        IMAGE_NAME = 'feeling-palette-api'
        CONTAINER_NAME = 'feeling-palette-api'
        CLAUDE_API_KEY = credentials('claude-api-key')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:latest .'
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker stop ${CONTAINER_NAME} || true'
                sh 'docker rm ${CONTAINER_NAME} || true'
                sh '''
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart unless-stopped \
                        -p 8100:8080 \
                        -e CLAUDE_API_KEY=${CLAUDE_API_KEY} \
                        ${IMAGE_NAME}:latest
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    for i in 1 2 3 4 5; do
                        sleep 3
                        docker exec ${CONTAINER_NAME} python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/docs')" && echo "Health check passed" && exit 0
                        echo "Attempt $i failed, retrying..."
                    done
                    echo "Health check failed after 5 attempts"
                    exit 1
                '''
            }
        }

        stage('Cleanup') {
            steps {
                sh 'docker image prune -f'
            }
        }
    }

    post {
        failure {
            sh 'docker logs ${CONTAINER_NAME} || true'
        }
    }
}
