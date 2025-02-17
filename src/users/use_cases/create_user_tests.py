import json
import uuid
from collections.abc import Generator

import pytest
from clickhouse_connect.driver import Client
from django.conf import settings

from event_logs.models import LogEntry, LogEntryStatus
from event_logs.tasks import process_outbox_events
from users.use_cases import CreateUser, CreateUserRequest

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def f_use_case() -> CreateUser:
    return CreateUser()


@pytest.fixture(autouse=True)
def f_clean_up_event_log(f_ch_client: Client) -> Generator:
    f_ch_client.query(f'TRUNCATE TABLE {settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}')
    yield


def test_user_created(f_use_case: CreateUser) -> None:
    request = CreateUserRequest(
        email='test@email.com', first_name='Test', last_name='Testovich',
    )

    response = f_use_case.execute(request)

    assert response.result.email == 'test@email.com'
    assert response.error == ''


def test_emails_are_unique(f_use_case: CreateUser) -> None:
    request = CreateUserRequest(
        email='test@email.com', first_name='Test', last_name='Testovich',
    )

    f_use_case.execute(request)
    response = f_use_case.execute(request)

    assert response.result is None
    assert response.error == 'User with this email already exists'


def test_event_inserted_to_outbox(f_use_case: CreateUser) -> None:
    email = 'test@email.com'
    request = CreateUserRequest(
        email=email, first_name='Test', last_name='Testovich',
    )

    f_use_case.execute(request)

    event = LogEntry.objects.first()

    assert event.event_type == 'user_created'
    assert event.status == LogEntryStatus.SCHEDULED


def test_event_outbox_processed(f_use_case: CreateUser, f_ch_client: Client) -> None:
    email = f'test_{uuid.uuid4()}@example.com'
    first_name = 'Test'
    last_name = 'Testovich'
    request = CreateUserRequest(
        email=email, first_name=first_name, last_name=last_name,
    )

    f_use_case.execute(request)

    process_outbox_events()

    log = f_ch_client.query("SELECT * FROM default.event_log WHERE event_type = 'user_created'")
    assert len(log.result_rows) == 1

    row = log.result_rows[0]
    assert row[0] == 'user_created'

    context = json.loads(row[3])
    assert context == {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
    }

    event = LogEntry.objects.first()
    assert event.status == LogEntryStatus.SUCCEEDED
