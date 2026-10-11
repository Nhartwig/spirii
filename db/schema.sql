-- Database schema. Postgres runs this once, on first start with an
-- empty data directory (it is mounted into /docker-entrypoint-initdb.d).
-- To re-run it after an edit: docker compose down -v

-- History: every accepted event, exactly once. The primary key is what makes a re-sent
-- event a duplicate (INSERT ... ON CONFLICT DO NOTHING).
CREATE TABLE events (
  charge_point_id text        NOT NULL CHECK (charge_point_id <> ''),
  message_id      text        NOT NULL CHECK (message_id <> ''),
  event_ts        timestamptz NOT NULL,
  event_type      text        NOT NULL,
  connector_id    int         CHECK (connector_id >= 0),
  payload         jsonb       NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  received_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (charge_point_id, message_id, event_ts)
);
CREATE INDEX events_by_charger ON events (charge_point_id, event_ts DESC);

-- Latest state: one row per charger. Each field keeps its own timestamp and message id,
-- so an old status event cannot overwrite a newer status, but can sit next to a newer
-- meter value.
CREATE TABLE charger_state (
  charge_point_id text PRIMARY KEY,
  status          text CHECK (status IN ('Available', 'Charging', 'Faulted')),
  status_at       timestamptz,
  status_msg_id   text,
  power_w         numeric,
  power_at        timestamptz,
  power_msg_id    text
);
