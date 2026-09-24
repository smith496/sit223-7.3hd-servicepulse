def incident_payload(**overrides):
    payload = {
        "title": "Checkout latency is elevated",
        "service": "checkout-api",
        "severity": "high",
    }
    payload.update(overrides)
    return payload


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"service": "servicepulse", "status": "healthy"}


def test_metrics_endpoint(client):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"servicepulse_http_requests_total" in response.data


def test_empty_incident_list(client):
    response = client.get("/api/incidents")
    assert response.status_code == 200
    assert response.get_json() == []


def test_create_incident(client, auth_headers):
    response = client.post("/api/incidents", json=incident_payload(), headers=auth_headers)
    assert response.status_code == 201
    assert response.get_json()["status"] == "open"
    assert response.get_json()["severity"] == "high"


def test_create_requires_api_key(client):
    response = client.post("/api/incidents", json=incident_payload())
    assert response.status_code == 401


def test_create_validates_required_fields(client, auth_headers):
    response = client.post(
        "/api/incidents",
        json=incident_payload(title=""),
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "title is required"


def test_create_validates_service(client, auth_headers):
    response = client.post(
        "/api/incidents",
        json=incident_payload(service=" "),
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "service is required"


def test_create_validates_severity(client, auth_headers):
    response = client.post(
        "/api/incidents",
        json=incident_payload(severity="urgent"),
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_create_validates_status(client, auth_headers):
    response = client.post(
        "/api/incidents",
        json=incident_payload(status="closed"),
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_update_incident_status(client, auth_headers):
    created = client.post("/api/incidents", json=incident_payload(), headers=auth_headers)
    incident_id = created.get_json()["id"]
    response = client.patch(
        f"/api/incidents/{incident_id}",
        json={"status": "resolved"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "resolved"


def test_update_rejects_invalid_status(client, auth_headers):
    response = client.patch(
        "/api/incidents/1",
        json={"status": "finished"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_update_returns_not_found(client, auth_headers):
    response = client.patch(
        "/api/incidents/999",
        json={"status": "investigating"},
        headers=auth_headers,
    )
    assert response.status_code == 404

