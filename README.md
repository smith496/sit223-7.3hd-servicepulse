# ServicePulse

ServicePulse is a small incident tracking API created to demonstrate a complete DevOps lifecycle in Jenkins. It contains testable business rules, a repeatable package and container build, automated quality and security gates, staging and production deployments, and live monitoring with an exercised alert.

## Main endpoints

- `GET /health` checks the application and database.
- `GET /metrics` exposes Prometheus metrics.
- `GET /api/incidents` lists incidents.
- `POST /api/incidents` creates an incident when a valid `X-API-Key` is supplied.
- `PATCH /api/incidents/<id>` changes the incident status.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest --cov=servicepulse
.venv/bin/flask --app servicepulse run
```

The default local API key is `local-demo-key`. Production and staging keys are injected as environment variables by Jenkins.

## Jenkins pipeline

The `Jenkinsfile` implements all seven stages required by SIT223 Task 7.3HD:

1. Build
2. Test
3. Code Quality
4. Security
5. Deploy
6. Release
7. Monitoring and Alerting

The separate Checkout stage prepares a clean workspace and is not counted as one of the seven assessed stages.

