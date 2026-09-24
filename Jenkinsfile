pipeline {
    agent any

    options {
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
        skipDefaultCheckout()
    }

    environment {
        SOURCE_REPOSITORY = '/Users/smith/Documents/SIT223_7_3HD_DevOps/servicepulse'
        IMAGE_NAME = 'servicepulse'
        STAGING_CONTAINER = 'servicepulse-staging'
        PRODUCTION_CONTAINER = 'servicepulse-prod'
        MONITORING_NETWORK = 'servicepulse-monitoring'
        PROMETHEUS_CONTAINER = 'servicepulse-prometheus'
        ALERTMANAGER_CONTAINER = 'servicepulse-alertmanager'
    }

    stages {
        stage('Checkout') {
            steps {
                deleteDir()
                sh 'git clone "$SOURCE_REPOSITORY" .'
                sh 'git log -1 --pretty=format:%h > source-commit.txt'
            }
        }

        stage('1. Build') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/python -m pip install --upgrade pip
                    .venv/bin/pip install --requirement requirements-dev.txt
                    .venv/bin/python -m build --no-isolation
                    docker build --tag "$IMAGE_NAME:build-$BUILD_NUMBER" .
                '''
            }
        }

        stage('2. Test') {
            steps {
                sh '''
                    mkdir -p artifacts
                    .venv/bin/pytest --junitxml=artifacts/junit.xml \
                        --cov=servicepulse --cov-report=term-missing \
                        --cov-report=xml:artifacts/coverage.xml
                '''
            }
        }

        stage('3. Code Quality') {
            steps {
                sh '''
                    .venv/bin/ruff check src tests | tee artifacts/ruff.txt
                    .venv/bin/radon cc src -s -a | tee artifacts/radon.txt
                    ! grep -E ' - [F] ' artifacts/radon.txt
                '''
            }
        }

        stage('4. Security') {
            steps {
                sh '''
                    .venv/bin/bandit -r src -ll -ii -f json -o artifacts/bandit.json
                    .venv/bin/pip-audit --requirement requirements.txt \
                        --format json --output artifacts/pip-audit.json
                '''
            }
        }

        stage('5. Deploy') {
            steps {
                retry(2) {
                    sh '''
                        docker rm -f "$STAGING_CONTAINER" >/dev/null 2>&1 || true
                        docker run --detach --name "$STAGING_CONTAINER" \
                            --publish 18081:8000 \
                            --env SERVICEPULSE_API_KEY=staging-demo-key \
                            "$IMAGE_NAME:build-$BUILD_NUMBER"
                        for attempt in $(seq 1 20); do
                            curl --fail --silent http://127.0.0.1:18081/health && break
                            if [ "$attempt" -eq 20 ]; then exit 1; fi
                            sleep 1
                        done
                        curl --fail --silent http://127.0.0.1:18081/metrics \
                            | grep servicepulse_http_requests_total
                    '''
                }
            }
        }

        stage('6. Release') {
            steps {
                sh '''
                    RELEASE_TAG="1.0.${BUILD_NUMBER}"
                    docker tag "$IMAGE_NAME:build-$BUILD_NUMBER" "$IMAGE_NAME:$RELEASE_TAG"
                    docker tag "$IMAGE_NAME:build-$BUILD_NUMBER" "$IMAGE_NAME:latest"
                    docker rm -f "$PRODUCTION_CONTAINER" >/dev/null 2>&1 || true
                    docker network inspect "$MONITORING_NETWORK" >/dev/null 2>&1 \
                        || docker network create "$MONITORING_NETWORK"
                    docker run --detach --name "$PRODUCTION_CONTAINER" \
                        --network "$MONITORING_NETWORK" \
                        --publish 18082:8000 \
                        --env SERVICEPULSE_API_KEY=production-demo-key \
                        "$IMAGE_NAME:$RELEASE_TAG"
                    for attempt in $(seq 1 20); do
                        curl --fail --silent http://127.0.0.1:18082/health && break
                        if [ "$attempt" -eq 20 ]; then exit 1; fi
                        sleep 1
                    done
                    printf 'version=%s\nimage=%s\ncommit=%s\n' \
                        "$RELEASE_TAG" "$IMAGE_NAME:$RELEASE_TAG" "$(cat source-commit.txt)" \
                        > artifacts/release-manifest.txt
                '''
            }
        }

        stage('7. Monitoring and Alerting') {
            steps {
                sh '''
                    docker rm -f "$PROMETHEUS_CONTAINER" "$ALERTMANAGER_CONTAINER" \
                        >/dev/null 2>&1 || true
                    docker run --detach --name "$ALERTMANAGER_CONTAINER" \
                        --network "$MONITORING_NETWORK" --publish 19093:9093 \
                        --volume "$WORKSPACE/monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro" \
                        prom/alertmanager:v0.28.1
                    docker run --detach --name "$PROMETHEUS_CONTAINER" \
                        --network "$MONITORING_NETWORK" --publish 19090:9090 \
                        --volume "$WORKSPACE/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
                        --volume "$WORKSPACE/monitoring/alerts.yml:/etc/prometheus/alerts.yml:ro" \
                        prom/prometheus:v3.5.0
                    chmod +x scripts/monitoring-check.sh
                    scripts/monitoring-check.sh
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts allowEmptyArchive: true, artifacts: 'artifacts/**, dist/**, source-commit.txt'
            sh 'docker rm -f "$STAGING_CONTAINER" >/dev/null 2>&1 || true'
        }
        success {
            echo 'All seven DevOps stages completed successfully.'
        }
        failure {
            echo 'The pipeline stopped because a quality gate or automation step failed.'
        }
    }
}
