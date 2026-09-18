from flask import Blueprint, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.database import engine
from core.logging import get_logger
from main import metrics

logger = get_logger("health_router")
bp = Blueprint('health', __name__)


@bp.route("/health", methods=['GET'])
@metrics.do_not_track()
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/ready", methods=['GET'])
@metrics.do_not_track()
def ready():
    try:
        connection = engine.connect()
    except SQLAlchemyError as e:
        logger.warning(f"Não pronto - banco de dados inalcançável: {str(e)}")
        return jsonify({"status": "not ready"}), 503

    try:
        connection.execute(text("SELECT 1 FROM events LIMIT 1"))
    except SQLAlchemyError as e:
        logger.warning(f"Não pronto - armazenamento de eventos ausente ou não legível: {str(e)}")
        return jsonify({"status": "not ready"}), 503
    finally:
        connection.close()

    return jsonify({"status": "ok"}), 200
