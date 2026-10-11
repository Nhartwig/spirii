#Spirii Takehome

## Running locally

Needs Docker with Compose. Nothing else is installed on the host.

```bash
docker compose up --build -d
```

Check it is up (the first build takes a minute):

```bash
curl -s localhost:8000/healthz
# {"status":"ok"}
```

The API is on http://localhost:8000 (interactive docs at http://localhost:8000/docs).
Postgres is not published to the host.

### Tests

```bash
docker compose run --rm app pytest
```

The tests run against the same Postgres as the app and truncate both tables first, so
they wipe anything you have posted by hand.

### Try it

Write a status:

```bash
curl -s -X POST localhost:8000/events -H 'Content-Type: application/json' -d '{
  "eventType": "StatusNotification", "chargePointId": "CP-1", "messageId": "m-1",
  "timestamp": "2026-10-10T10:05:00Z", "payload": {"status": "Charging"}}'
# {"result":"stored"}
```

Send the same event again (duplicate):

```bash
curl -s -X POST localhost:8000/events -H 'Content-Type: application/json' -d '{
  "eventType": "StatusNotification", "chargePointId": "CP-1", "messageId": "m-1",
  "timestamp": "2026-10-10T10:05:00Z", "payload": {"status": "Charging"}}'
# {"result":"duplicate"}
```

Send an older event (out of order). It goes into history but does not change the latest
state:

```bash
curl -s -X POST localhost:8000/events -H 'Content-Type: application/json' -d '{
  "eventType": "StatusNotification", "chargePointId": "CP-1", "messageId": "m-2",
  "timestamp": "2026-10-10T10:03:00Z", "payload": {"status": "Available"}}'
# {"result":"stored"}
```

Write a meter value:

```bash
curl -s -X POST localhost:8000/events -H 'Content-Type: application/json' -d '{
  "eventType": "MeterValues", "chargePointId": "CP-1", "messageId": "m-3",
  "timestamp": "2026-10-10T10:04:00Z", "connectorId": 1, "payload": {"powerW": 7200}}'
# {"result":"stored"}
```

Read latest state:

```bash
curl -s localhost:8000/chargers/CP-1
# {"chargePointId":"CP-1","status":"Charging","statusAt":"2026-10-10T10:05:00Z",
#  "powerW":7200.0,"powerAt":"2026-10-10T10:04:00Z"}
```

Read history (newest first, three events, `?limit=` defaults to 50):

```bash
curl -s localhost:8000/chargers/CP-1/events
```

List all chargers (ordered by id; page with `?limit=` and `?after=<last id>`):

```bash
curl -s localhost:8000/chargers
```

### Reset

```bash
docker compose down -v
```

This deletes the database volume. `db/schema.sql` only runs on an empty volume, so this is
also needed after changing the schema.

To look at the tables directly:

```bash
docker compose exec db psql -U postgres telemetry
```

To follow the app logs:

```bash
docker compose logs -f app
```
