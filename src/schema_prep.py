import sys

from core.database import engine
from core.logging import setup_logging
from core.settings import settings
from models.event import Base

logger = setup_logging(
    service_name=settings.SERVICE_NAME,
    log_level=settings.LOG_LEVEL,
    use_colors=settings.LOG_FORMAT == "colored"
)


def main() -> int:
    logger.info("Iniciando preparação de schema")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        logger.exception("Falha ao preparar o schema do banco de dados")
        return 1
    logger.info("Preparação de schema concluída")
    return 0


if __name__ == "__main__":
    sys.exit(main())
