# HTTP API: ingest events, read latest state and history.
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.db import get_connection
from app.envelope import Envelope
from app.event_types import validate_payload
from app.processing import process_event

app = FastAPI(title="Charger telemetry")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChargerState(CamelModel):
    charge_point_id: str
    status: str | None
    status_at: datetime | None
    power_w: float | None
    power_at: datetime | None


class EventOut(CamelModel):
    event_type: str
    charge_point_id: str
    message_id: str
    timestamp: datetime
    connector_id: int | None
    payload: dict
    received_at: datetime


@app.post("/events", status_code=202)
def post_event(envelope: Envelope):
    try:
        validate_payload(envelope)
    except ValidationError as e:
        # same 422 shape as envelope errors
        errors = e.errors(include_url=False)
        for error in errors:
            error["loc"] = ("body", "payload", *error["loc"])
        raise RequestValidationError(errors)

    with get_connection() as conn:
        result = process_event(conn, envelope)

    # slice only: in production the API puts the event on a queue and can't know this
    return {"result": result}


@app.get("/chargers", response_model=list[ChargerState])
def list_chargers(limit: int = Query(50, ge=1, le=500), after: str = ""):
    # page by passing the last chargePointId as ?after=
    with get_connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            """
            SELECT * FROM charger_state
            WHERE charge_point_id > %s
            ORDER BY charge_point_id
            LIMIT %s
            """,
            (after, limit),
        ).fetchall()


@app.get("/chargers/{charge_point_id}", response_model=ChargerState)
def get_charger(charge_point_id: str):
    with get_connection() as conn:
        row = conn.cursor(row_factory=dict_row).execute(
            "SELECT * FROM charger_state WHERE charge_point_id = %s",
            (charge_point_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="charger not found")
    return row


@app.get("/chargers/{charge_point_id}/events", response_model=list[EventOut])
def get_charger_events(charge_point_id: str, limit: int = Query(50, ge=1, le=500)):
    with get_connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            """
            SELECT event_type, charge_point_id, message_id, event_ts AS timestamp,
                   connector_id, payload, received_at
            FROM events
            WHERE charge_point_id = %s
            ORDER BY event_ts DESC, message_id DESC
            LIMIT %s
            """,
            (charge_point_id, limit),
        ).fetchall()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
