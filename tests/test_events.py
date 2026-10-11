# Behaviour tests: duplicates, out-of-order events, validation, concurrency.
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import get_args

import psycopg
import pytest
from pydantic import BaseModel

from app.db import get_connection
from app.envelope import Envelope
from app.event_types import REGISTRY, status_notification
from app.processing import process_event

CP = "CP-1"
T_1003 = "2026-10-01T10:03:00Z"
T_1005 = "2026-10-01T10:05:00Z"


def event(event_type, message_id, timestamp, payload):
    return {
        "eventType": event_type,
        "chargePointId": CP,
        "messageId": message_id,
        "timestamp": timestamp,
        "payload": payload,
    }


def status(message_id, timestamp, value):
    return event("StatusNotification", message_id, timestamp, {"status": value})


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def latest_state(client):
    return client.get(f"/chargers/{CP}").json()


def test_valid_status_is_stored(client):
    response = client.post("/events", json=status("m-1", T_1005, "Charging"))

    assert response.status_code == 202
    assert response.json() == {"result": "stored"}
    assert latest_state(client)["status"] == "Charging"


def test_duplicate_is_stored_once(client, conn):
    body = status("m-1", T_1005, "Charging")
    client.post("/events", json=body)
    before = latest_state(client)

    response = client.post("/events", json=body)

    assert response.status_code == 202
    assert response.json() == {"result": "duplicate"}
    assert count(conn, "events") == 1
    assert latest_state(client) == before


def test_older_status_does_not_overwrite_newer(client, conn):
    client.post("/events", json=status("m-1", T_1005, "Charging"))
    client.post("/events", json=status("m-2", T_1003, "Available"))

    assert latest_state(client)["status"] == "Charging"
    assert count(conn, "events") == 2


def test_status_and_power_update_independently(client):
    client.post("/events", json=event("MeterValues", "m-1", T_1005, {"powerW": 7200}))
    client.post("/events", json=status("m-2", T_1003, "Available"))

    state = latest_state(client)
    assert state["powerW"] == 7200
    assert state["status"] == "Available"


@pytest.mark.parametrize("order", [("m-1", "m-2"), ("m-2", "m-1")])
def test_same_timestamp_higher_message_id_wins(client, order):
    statuses = {"m-1": "Available", "m-2": "Charging"}
    for message_id in order:
        client.post("/events", json=status(message_id, T_1005, statuses[message_id]))

    assert latest_state(client)["status"] == "Charging"


def test_same_message_id_different_timestamp_is_a_new_event(client, conn):
    first = client.post("/events", json=status("m-1", T_1003, "Available"))
    second = client.post("/events", json=status("m-1", T_1005, "Charging"))

    assert first.json() == second.json() == {"result": "stored"}
    assert count(conn, "events") == 2


def test_unknown_status_is_rejected(client, conn):
    response = client.post("/events", json=status("m-1", T_1005, "Exploded"))

    assert response.status_code == 422
    assert count(conn, "events") == 0
    assert count(conn, "charger_state") == 0


def test_concurrent_same_event_is_stored_once(conn):
    envelope = Envelope(
        event_type="StatusNotification",
        charge_point_id=CP,
        message_id="m-1",
        timestamp=datetime(2026, 10, 1, 10, 5, tzinfo=timezone.utc),
        payload={"status": "Charging"},
    )
    threads = 4
    barrier = threading.Barrier(threads)

    def worker():
        with get_connection() as own_conn:
            barrier.wait()  # release all threads at once
            return process_event(own_conn, envelope)

    with ThreadPoolExecutor(threads) as pool:
        futures = [pool.submit(worker) for _ in range(threads)]
        results = [f.result() for f in futures]

    assert sorted(results) == ["duplicate"] * (threads - 1) + ["stored"]
    assert count(conn, "events") == 1


def test_status_literal_matches_db_check(conn):
    insert = "INSERT INTO charger_state (charge_point_id, status) VALUES (%s, %s)"
    allowed = get_args(status_notification.Payload.model_fields["status"].annotation)

    for value in allowed:
        conn.execute(insert, (f"cp-{value}", value))
    assert count(conn, "charger_state") == len(allowed)

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(insert, ("cp-bad", "Exploded"))


def test_future_timestamp_is_rejected(client, conn):
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    response = client.post("/events", json=status("m-1", future, "Charging"))

    assert response.status_code == 422
    assert count(conn, "events") == 0
    assert count(conn, "charger_state") == 0


def test_naive_timestamp_is_rejected(client):
    response = client.post("/events", json=status("m-1", "2026-10-01T10:05:00", "Charging"))

    assert response.status_code == 422


def test_history_only_event_type(client, conn, monkeypatch):
    class Payload(BaseModel):
        ok: bool

    # a module with a Payload but no apply()
    monkeypatch.setitem(REGISTRY, "Heartbeat", SimpleNamespace(EVENT_TYPE="Heartbeat", Payload=Payload))

    response = client.post("/events", json=event("Heartbeat", "m-1", T_1005, {"ok": True}))

    assert response.status_code == 202
    assert response.json() == {"result": "stored"}
    assert count(conn, "events") == 1
    assert count(conn, "charger_state") == 0


def test_list_chargers_is_ordered_and_paged(client):
    for cp in ("CP-2", "CP-1", "CP-3"):
        client.post("/events", json={**status("m-1", T_1005, "Charging"), "chargePointId": cp})

    def ids(url):
        return [charger["chargePointId"] for charger in client.get(url).json()]

    assert ids("/chargers") == ["CP-1", "CP-2", "CP-3"]
    assert ids("/chargers?limit=2") == ["CP-1", "CP-2"]
    assert ids("/chargers?limit=2&after=CP-2") == ["CP-3"]
