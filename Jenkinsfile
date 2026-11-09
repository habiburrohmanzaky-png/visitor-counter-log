pipeline {
    agent any

    environment {
        APP_VERSION = '1.0.0'
        COMPOSE_PROJECT_NAME = 'tugasbesar'
    }

    stages {
        stage('1. Checkout Code') {
            steps {
                echo 'Mengambil source code dari GitHub'
                checkout scm
            }
        }

        stage('2. Syntax Check') {
            steps {
                echo 'Memeriksa sintaks Python backend'
                sh '''
                    python3 -m py_compile backend/app.py
                    echo "Python syntax check berhasil"
                '''
            }
        }

        stage('3. Build Image') {
            steps {
                echo 'Membangun Docker image backend dan frontend'
                sh 'docker compose build'
            }
        }

        stage('4. Automated Deployment') {
            steps {
                echo 'Melakukan deployment aplikasi'
                sh 'docker compose up -d --remove-orphans'
            }
        }

        stage('5. Health Check') {
            steps {
                echo 'Memeriksa kesehatan backend dan frontend'
                sh '''
                    echo "Menunggu backend healthy..."

                    STATUS="unknown"

                    for i in $(seq 1 20); do
                        STATUS=$(docker inspect \
                            --format='{{.State.Health.Status}}' \
                            visitor-backend 2>/dev/null || echo "missing")

                        if [ "$STATUS" = "healthy" ]; then
                            break
                        fi

                        echo "Backend belum healthy: $STATUS ($i/20)"
                        sleep 3
                    done

                    if [ "$STATUS" != "healthy" ]; then
                        echo "Backend health check gagal"
                        docker compose logs --tail=50
                        exit 1
                    fi

                    echo "Backend healthy"
                    echo "Memeriksa API melalui frontend..."

                    docker exec visitor-frontend \
                        wget -qO- http://127.0.0.1/api/health

                    echo ""
                    echo "Semua health check berhasil"
                '''
            }
        }
    }

    post {
        success {
            echo 'CI/CD berhasil! Aplikasi telah berhasil di-deploy.'
        }

        failure {
            echo 'CI/CD gagal. Periksa Console Output untuk detail error.'
        }

        always {
            echo 'Pipeline selesai dijalankan.'
        }
    }
}