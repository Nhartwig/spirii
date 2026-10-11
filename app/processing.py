# Stores one event: history row first, then the latest-state update, in one transaction.
from typing import Literal

from psycopg.types.json import Jsonb

from app.event_types import REGISTRY, validate_payload

INSERT_EVENT = """
INSERT INTO events (charge_point_id, message_id, event_ts, event_type, connector_id, payload)
VALUES (%(cp)s, %(msg)s, %(ts)s, %(type)s, %(connector)s, %(payload)s)
ON CONFLICT DO NOTHING;
"""


def insert_into_events(conn, envelope) -> bool:
    cur = conn.execute(
        INSERT_EVENT,
        {
            "cp": envelope.charge_point_id,
            "msg": envelope.message_id,
            "ts": envelope.timestamp,
            "type": envelope.event_type,
            "connector": envelope.connector_id,
            "payload": Jsonb(envelope.payload),
        },
    )
    # 0 rows means the primary key already existed
    return cur.rowcount == 1


def process_event(conn, envelope) -> Literal["stored", "duplicate"]:
    with conn.transaction():
        if not insert_into_events(conn, envelope):
            return "duplicate"
        # modules without apply() are history-only
        apply = getattr(REGISTRY[envelope.event_type], "apply", None)
        if apply:
            apply(conn, envelope, validate_payload(envelope))
    return "stored"
