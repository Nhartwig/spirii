# The envelope: fields every event has, whatever its type. JSON is camelCase.
from datetime import datetime, timedelta, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.event_types import REGISTRY

# allowance for charger clock drift
MAX_FUTURE_SKEW = timedelta(minutes=5)


class Envelope(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    event_type: str
    charge_point_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    connector_id: int | None = Field(default=None, ge=0)
    payload: dict

    @field_validator("event_type")
    @classmethod
    def known_event_type(cls, value: str) -> str:
        if value not in REGISTRY:
            raise ValueError(f"unknown eventType, expected one of {sorted(REGISTRY)}")
        return value

    @field_validator("timestamp")
    @classmethod
    def not_in_future(cls, value: datetime) -> datetime:
        # a future timestamp would block every later update to that field
        if value > datetime.now(timezone.utc) + MAX_FUTURE_SKEW:
            raise ValueError("timestamp is too far in the future")
        return value
