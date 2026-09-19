import datetime
import sys

from sqlalchemy.exc import SQLAlchemyError

from core.database import get_db
from core.logging import setup_logging
from core.settings import settings
from models.event import Event
from seed_data import REFERENCE_EVENTS

logger = setup_logging(
    service_name=settings.SERVICE_NAME,
    log_level=settings.LOG_LEVEL,
    use_colors=settings.LOG_FORMAT == "colored"
)

DAYS_UNTIL_FIRST_EVENT = 3


def _shifted_dates(now: datetime.datetime) -> list[datetime.datetime]:
    earliest_reference = min(event["reference_date"] for event in REFERENCE_EVENTS)
    offset = (now + datetime.timedelta(days=DAYS_UNTIL_FIRST_EVENT)) - earliest_reference
    return [event["reference_date"] + offset for event in REFERENCE_EVENTS]


def main() -> int:
    logger.info("Iniciando semeadura de eventos de demonstração")

    with get_db() as db:
        try:
            already_has_events = db.query(Event).first() is not None
        except SQLAlchemyError:
            logger.exception("Falha ao consultar o armazenamento de eventos")
            return 1

        if already_has_events:
            logger.info("Catálogo já contém eventos — semeadura não é necessária")
            return 0

        shifted_dates = _shifted_dates(datetime.datetime.utcnow())
        events = [
            Event(
                title=reference["title"],
                description=reference["description"],
                date=date,
                location=reference["location"],
            )
            for reference, date in zip(REFERENCE_EVENTS, shifted_dates)
        ]

        try:
            db.add_all(events)
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Falha ao criar os eventos de demonstração")
            return 1

    logger.info(f"Semeadura concluída: {len(events)} eventos criados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
