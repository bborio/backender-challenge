from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class LogEntryStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED'
    IN_PROGRESS = 'IN_PROGRESS'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'

class LogEntry(TimeStampedModel):
    event_type = models.CharField(max_length=255)
    event_date_time = models.DateTimeField(default=timezone.now)
    environment = models.CharField(max_length=255)
    event_context = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=LogEntryStatus.choices,
        default=LogEntryStatus.SCHEDULED,
    )
