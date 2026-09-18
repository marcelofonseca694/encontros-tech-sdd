import os
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from main import app
from routers import health_router


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


def test_health_responds_200_without_touching_db(client):
    with patch.object(health_router, "engine") as mock_engine:
        mock_engine.connect.side_effect = AssertionError("/health não deve tocar o banco")
        response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    mock_engine.connect.assert_not_called()


def test_health_responds_200_even_with_db_unavailable(client):
    with patch.object(health_router, "engine") as mock_engine:
        mock_engine.connect.side_effect = SQLAlchemyError("banco fora do ar")
        response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_responds_200_when_db_and_storage_ok(client):
    mock_connection = MagicMock()
    with patch.object(health_router, "engine") as mock_engine:
        mock_engine.connect.return_value = mock_connection
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    mock_connection.execute.assert_called_once()
    mock_connection.close.assert_called_once()


def test_ready_responds_503_when_db_unreachable(client, caplog):
    with patch.object(health_router, "engine") as mock_engine:
        mock_engine.connect.side_effect = SQLAlchemyError("connection refused")
        with caplog.at_level("WARNING", logger="encontros-tech.health_router"):
            response = client.get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {"status": "not ready"}
    assert any(record.levelname == "WARNING" for record in caplog.records)
    assert not any(record.levelname == "ERROR" for record in caplog.records)


def test_ready_responds_503_when_storage_not_readable(client, caplog):
    mock_connection = MagicMock()
    mock_connection.execute.side_effect = SQLAlchemyError("relation events does not exist")
    with patch.object(health_router, "engine") as mock_engine:
        mock_engine.connect.return_value = mock_connection
        with caplog.at_level("WARNING", logger="encontros-tech.health_router"):
            response = client.get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {"status": "not ready"}
    mock_connection.close.assert_called_once()
    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_health_and_ready_require_no_authentication(client):
    with patch.object(health_router, "engine") as mock_engine:
        mock_engine.connect.return_value = MagicMock()
        health_response = client.get("/health")
        ready_response = client.get("/ready")

    assert health_response.status_code != 401
    assert ready_response.status_code != 401


def test_ready_bounds_response_time_when_connection_is_dropped(client):
    # Endereço não roteável (não é um banco real): o TCP nunca recusa nem
    # aceita a conexão, exercitando o connect_timeout de verdade (P13),
    # sem depender de nenhum banco de dados em execução.
    timeout_seconds = 2
    blackhole_engine = create_engine(
        "postgresql://u:p@10.255.255.1:5432/db",
        connect_args={"connect_timeout": timeout_seconds},
    )

    with patch.object(health_router, "engine", blackhole_engine):
        start = time.monotonic()
        response = client.get("/ready")
        elapsed = time.monotonic() - start

    assert response.status_code == 503
    assert elapsed < timeout_seconds + 2
