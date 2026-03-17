import logging
from datetime import datetime


logger = logging.getLogger(__name__)


def send_notification(document_id: int, user_name: str, version_number: int) -> None:
    timestamp = datetime.now().strftime("%I:%M %p")
    logger.info(
        "Document %s updated by %s at %s (version %s).",
        document_id,
        user_name,
        timestamp,
        version_number,
    )
