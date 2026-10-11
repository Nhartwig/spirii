# MeterValues: updates the charger's latest power reading.
from pydantic import BaseModel, Field

EVENT_TYPE = "MeterValues"


class Payload(BaseModel):
    # NaN/Infinity would be rejected by jsonb, so reject them here
    power_w: float = Field(alias="powerW", ge=0, allow_inf_nan=False)


# only overwrites if the incoming (timestamp, message id) is newer
UPSERT = """
INSERT INTO charger_state (charge_point_id, power_w, power_at, power_msg_id)
VALUES (%(cp)s, %(power_w)s, %(ts)s, %(msg)s)
ON CONFLICT (charge_point_id) DO UPDATE
SET power_w = EXCLUDED.power_w, power_at = EXCLUDED.power_at,
    power_msg_id = EXCLUDED.power_msg_id
WHERE charger_state.power_at IS NULL
   OR (charger_state.power_at, charger_state.power_msg_id)
    < (EXCLUDED.power_at, EXCLUDED.power_msg_id);
"""


def apply(conn, envelope, payload: Payload) -> None:
    conn.execute(
        UPSERT,
        {
            "cp": envelope.charge_point_id,
            "power_w": payload.power_w,
            "ts": envelope.timestamp,
            "msg": envelope.message_id,
        },
    )
