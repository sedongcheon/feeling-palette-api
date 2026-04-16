pipeline {
    agent any

    environment {
        COMPOSE_PROJECT = 'feeling-palette'
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
                sh 'docker compose build --no-cache'
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker compose down || true'
                sh 'docker compose up -d'
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    sleep 3
                    curl -sf http://feeling-palette-api:8080/docs > /dev/null && echo "Health check passed" || curl -sf http://localhost:8080/docs > /dev/null && echo "Health check passed (localhost)" || (echo "Health check failed" && exit 1)
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
            sh 'docker compose logs feeling-palette-api || true'
        }
    }
}
