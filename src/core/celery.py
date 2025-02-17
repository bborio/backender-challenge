import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'process-outbox-every-5min': {
        'task': 'event_logs.tasks.process_outbox_events',
        'schedule': 300.0,
        'options': {
            'expires': 60,
            'priority': 5
        }
    },
}