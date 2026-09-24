from sqlalchemy import inspect


def test_postgresql_pooler_disables_prepared_statements(monkeypatch):
    from backend.app import database

    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    database.make_engine("postgresql://user:password@example.com:5432/app")

    assert captured["connect_args"]["prepare_threshold"] is None


def test_postgresql_url_defaults_to_psycopg_driver():
    from backend.app.database import make_engine

    engine = make_engine("postgresql://user:password@example.com:5432/app")

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_schema_contains_all_business_tables(app):
    expected = {
        "users",
        "menus",
        "menu_items",
        "uploads",
        "recognition_runs",
        "samples",
        "sample_images",
        "recognition_fields",
        "disposals",
        "audit_events",
        "idempotency_keys",
        "reports",
    }

    assert expected.issubset(set(inspect(app.state.engine).get_table_names()))


def test_health_endpoint_reports_database_ready(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ready",
        "database_engine": "sqlite",
    }
