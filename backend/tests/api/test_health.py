import json

from fastapi.testclient import TestClient

from quantcore.api.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "QuantCore",
    }


def test_health_live_returns_ok():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "QuantCore",
    }


def test_health_ready_checks_database_and_configuration(monkeypatch):
    class FakeScalarResult:
        def scalars(self):
            return self

        def all(self):
            return ["current-revision"]

    class FakeSession:
        def execute(self, statement):
            if "alembic_version" in str(statement):
                return FakeScalarResult()
            return None

        def close(self):
            pass

    monkeypatch.setattr(
        "quantcore.api.endpoints.health.SessionLocal",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        "quantcore.api.endpoints.health.ProductionDataPolicy.validate_all",
        lambda: None,
    )
    monkeypatch.setattr(
        "quantcore.api.endpoints.health._expected_schema_revisions",
        lambda: {"current-revision"},
    )

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"] == {
        "configuration": "ok",
        "database": "ok",
        "schema": "ok",
    }


def test_health_ready_fails_when_database_is_unavailable(monkeypatch):
    class FakeSession:
        def execute(self, _statement):
            raise RuntimeError("database unavailable")

        def close(self):
            pass

    monkeypatch.setattr(
        "quantcore.api.endpoints.health.SessionLocal",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        "quantcore.api.endpoints.health.ProductionDataPolicy.validate_all",
        lambda: None,
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {
        "configuration": "ok",
        "database": "failed",
    }


def test_health_ready_fails_when_production_configuration_is_invalid(monkeypatch):
    from quantcore.core.exceptions import ConfigurationError

    monkeypatch.setattr(
        "quantcore.api.endpoints.health.ProductionDataPolicy.validate_all",
        lambda: (_ for _ in ()).throw(
            ConfigurationError("invalid production source")
        ),
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {"configuration": "failed"}



def test_health_ready_requires_current_alembic_schema(monkeypatch):
    from quantcore.api.endpoints import health

    class FakeScalarResult:
        def all(self):
            return ["stale-revision"]

        def scalars(self):
            return self

    class FakeDb:
        def execute(self, statement):
            if "alembic_version" in str(statement):
                return FakeScalarResult()
            return None

        def close(self):
            pass

    monkeypatch.setattr(health, "SessionLocal", lambda: FakeDb())
    monkeypatch.setattr(health, "_expected_schema_revisions", lambda: {"current-revision"})
    monkeypatch.setattr(
        health.ProductionDataPolicy,
        "validate_all",
        classmethod(lambda cls: None),
    )

    response = health.health_ready()

    assert response.status_code == 503
    payload = json.loads(response.body)
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["schema"] == "failed"
