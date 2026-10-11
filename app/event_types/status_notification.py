# StatusNotification: updates the charger's latest status.
from typing import Literal

from pydantic import BaseModel

EVENT_TYPE = "StatusNotification"


class Payload(BaseModel):
    # must match the CHECK on charger_state.status
    status: Literal["Available", "Charging", "Faulted"]


# only overwrites if the incoming (timestamp, message id) is newer
UPSERT = """
INSERT INTO charger_state (charge_point_id, status, status_at, status_msg_id)
VALUES (%(cp)s, %(status)s, %(ts)s, %(msg)s)
ON CONFLICT (charge_point_id) DO UPDATE
SET status = EXCLUDED.status, status_at = EXCLUDED.status_at,
    status_msg_id = EXCLUDED.status_msg_id
WHERE charger_state.status_at IS NULL
   OR (charger_state.status_at, charger_state.status_msg_id)
    < (EXCLUDED.status_at, EXCLUDED.status_msg_id);
"""


def apply(conn, envelope, payload: Payload) -> None:
    conn.execute(
        UPSERT,
        {
            "cp": envelope.charge_point_id,
            "status": payload.status,
            "ts": envelope.timestamp,
            "msg": envelope.message_id,
        },
    )
