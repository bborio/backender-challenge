import re
from datetime import datetime

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel

from core.base_model import Model
from core.ch_client import ClickHouseClient
from event_logs.models import LogEntry, LogEntryStatus

logger = structlog.get_logger(__name__)


class EventLogRecord(BaseModel):
    event_type: str
    event_date_time: datetime
    environment: str
    event_context: str


class EventLogProcessor:
    def __init__(self, batch_size: int) -> None:
        self.batch_size = batch_size

    def process_events(self) -> None:
        events = self._fetch_and_lock_events()
        if not events:
            logger.info("no events to process in outbox")
            return

        event_ids = [event.id for event in events]

        try:
            self._process_batch(events, event_ids)
            logger.info("successfully processed events", extra={"event_count": len(events)})
        except Exception as e:
            self._handle_failure(event_ids, e)
            raise

    def insert_to_outbox(self, data: list[Model]) -> None:
        try:
            converted_data = self._convert_data(data)
            LogEntry.objects.bulk_create([
                LogEntry(
                    **record.model_dump(),
                    status=LogEntryStatus.SCHEDULED,
                )
                for record in converted_data
            ])
        except Exception as e:
            logger.error("unable to insert data to outbox", error=str(e))

    def _process_batch(self, events: list[LogEntry], event_ids: list[int]) -> None:
        batch_data = self._prepare_batch_data(events)
        self._push_to_clickhouse(batch_data)
        self._update_event_status(event_ids, LogEntryStatus.SUCCEEDED)

    def _handle_failure(self, event_ids: list[int], error: Exception) -> None:
        logger.error("failed to process events", error=str(error))
        if event_ids:
            try:
                self._update_event_status(event_ids, LogEntryStatus.FAILED)
            except Exception as update_error:
                logger.error("failed to update status to FAILED", error=str(update_error))

    def _fetch_and_lock_events(self) -> list[LogEntry]:
        with transaction.atomic():
            events: list[LogEntry] = list(
                LogEntry.objects.select_for_update(skip_locked=True)
                .filter(status=LogEntryStatus.SCHEDULED)[:self.batch_size],
            )
            if events:
                ids = [event.id for event in events]
                LogEntry.objects.filter(id__in=ids).update(status=LogEntryStatus.IN_PROGRESS)
            return events

    def _prepare_batch_data(self, events: list[LogEntry]) -> list[EventLogRecord]:
        return [
            EventLogRecord(
                event_type=event.event_type,
                event_date_time=event.event_date_time,
                environment=event.environment,
                event_context=event.event_context,
            )
            for event in events
        ]

    def _push_to_clickhouse(self, data: list[EventLogRecord]) -> None:
        with ClickHouseClient.init() as client:
            if data:
                columns = list(data[0].model_fields.keys())
                data_tuples = [tuple(record.model_dump().values()) for record in data]
            else:
                columns = []
                data_tuples = []
            client.insert(data=data_tuples, columns=columns)

    def _update_event_status(self, event_ids: list[int], status: LogEntryStatus) -> None:
        LogEntry.objects.filter(id__in=event_ids).update(status=status)

    def _convert_data(self, data: list[Model]) -> list[EventLogRecord]:
        return [
            EventLogRecord(
                event_type=self._to_snake_case(event.__class__.__name__),
                event_date_time=timezone.now(),
                environment=settings.ENVIRONMENT,
                event_context=event.model_dump_json(),
            )
            for event in data
        ]

    def _to_snake_case(self, event_name: str) -> str:
        result = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", event_name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", result).lower()


event_log_processor = EventLogProcessor(batch_size=settings.CLICKHOUSE_EVENT_BATCH_SIZE)
