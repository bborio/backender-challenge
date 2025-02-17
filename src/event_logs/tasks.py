import structlog
from celery import shared_task

from event_logs.processor import event_log_processor

logger = structlog.get_logger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_outbox_events(self) -> None:  # noqa: ANN001
    try:
        event_log_processor.process_events()
    except Exception as e:
        self.retry(exc=e, countdown=10)
