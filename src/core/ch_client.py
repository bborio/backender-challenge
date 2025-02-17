from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import clickhouse_connect
import structlog
from clickhouse_connect.driver.exceptions import DatabaseError
from django.conf import settings

logger = structlog.get_logger(__name__)


class ClickHouseClient:
    def __init__(self, client: clickhouse_connect.driver.Client) -> None:
        self._client = client

    @classmethod
    @contextmanager
    def init(cls) -> Generator['ClickHouseClient']:
        client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            query_retries=2,
            connect_timeout=30,
            send_receive_timeout=10,
        )
        try:
            yield cls(client)
        except Exception as e:
            logger.error('error while executing clickhouse query', error=str(e))
        finally:
            client.close()

    def insert(
        self,
        data: list[tuple[Any]],
        columns: list[str],
    ) -> None:
        try:
            self._client.insert(
                data=data,
                column_names=columns,
                database=settings.CLICKHOUSE_SCHEMA,
                table=settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME,
            )
        except DatabaseError as e:
            logger.error('unable to insert data to clickhouse', error=str(e))

    def query(self, query: str) -> Any:  # noqa: ANN401
        logger.debug('executing clickhouse query', query=query)

        try:
            return self._client.query(query).result_rows
        except DatabaseError as e:
            logger.error('failed to execute clickhouse query', error=str(e))
            return
