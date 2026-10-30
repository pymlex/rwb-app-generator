CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS documents(kind text NOT NULL, id text NOT NULL, body jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(kind,id));
CREATE INDEX IF NOT EXISTS ix_documents_body ON documents USING gin(body);
CREATE TABLE IF NOT EXISTS idempotency(key text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS outbox(id bigserial PRIMARY KEY, aggregate_id text NOT NULL, event_type text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz);
CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox(id) WHERE published_at IS NULL;
INSERT INTO schema_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;
