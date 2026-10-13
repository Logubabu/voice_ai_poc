import pytest
from starlette.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_simple_get_request(client):
    origin = "http://localhost:5173"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_devtunnels_origin(client):
    origin = "https://skp54pvx-8000.inc1.devtunnels.ms"
    response = client.get("/api/config/status", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_aws_elb_origin(client):
    origin = "http://voice-ai-fe-2010978805.ap-southeast-2.elb.amazonaws.com:8000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_preflight_post_request(client):
    origin = "http://localhost:5173"
    response = client.options(
        "/api/start",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_patch_request(client):
    origin = "https://skp54pvx-5173.inc1.devtunnels.ms"
    response = client.options(
        "/api/webrtc/patch",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "PATCH" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_custom_headers(client):
    origin = "http://192.168.1.4:5173"
    response = client.options(
        "/api/v1/knowledge-bases",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-tenant-id,authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "x-tenant-id" in response.headers.get("access-control-allow-headers", "").lower()
