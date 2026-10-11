# Registry of event types. To add one: new module in this folder + one line in REGISTRY.
from app.event_types import meter_values, status_notification

REGISTRY = {
    status_notification.EVENT_TYPE: status_notification,
    meter_values.EVENT_TYPE: meter_values,
}


def validate_payload(envelope):
    # raises pydantic.ValidationError if the payload doesn't fit the type's model
    return REGISTRY[envelope.event_type].Payload.model_validate(envelope.payload)
