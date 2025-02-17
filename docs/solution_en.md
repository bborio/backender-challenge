## Problems

- Logs were lost due to lack of transactional guarantees (a web worker could die between executing business logic and writing to ClickHouse).
- Network errors led to a poor user experience.
- A high number of small inserts negatively impacted ClickHouse performance.

## Solution

### Transactional Outbox Pattern

- Logs are saved in an outbox (using the `LogEntry` model) within the same transaction as business operations, ensuring atomicity.

### Batch Processing

- A dedicated Celery task periodically aggregates events from the outbox and sends them to ClickHouse in batches.
- Batch processing reduces load and improves system stability.

### Error Handling

- Built-in Celery retry mechanisms automatically reattempt sending in case of failures.
- All errors are logged in a structured manner using `structlog`.

### Improvement of the ClickHouse Client

- The class has been renamed to `ClickHouseLogClient` to reflect its specialization.
- The list of columns is now passed as a parameter to the `insert` method (with default settings), making the client more universal.

### Refactoring of the EventLogProcessor

- The `process_events` method has been split into specialized sub-methods: fetching and locking, data preparation, sending to ClickHouse, and status updating.
- Using a Pydantic model (`EventLogRecord`) instead of unstructured tuples has improved type safety and code readability.
- The logic for updating record statuses has been extracted into separate methods to simplify maintenance.
