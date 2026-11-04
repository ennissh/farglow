-- Phase 0 foundations: engine clock, restore points, job queue, signed links, heartbeats.
-- Shipped migrations are never edited (farglow.migrate checks a SHA-256); add a new file.

-- The single engine row. tick 0 is genesis.
CREATE TABLE engine_state (
    id            smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    galaxy_seed   bigint      NOT NULL,
    tick          bigint      NOT NULL DEFAULT 0,
    state_hash    text        NOT NULL,
    paused        boolean     NOT NULL DEFAULT false,
    pause_reason  text,
    tick_seconds  integer     NOT NULL,
    last_tick_at  timestamptz,
    next_tick_at  timestamptz NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- One row per completed tick: the hash chain that determinism tests and replays check.
CREATE TABLE ticks (
    tick         bigint PRIMARY KEY,
    state_hash   text        NOT NULL,
    prev_hash    text        NOT NULL,
    orders_hash  text        NOT NULL,
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz NOT NULL DEFAULT now(),
    duration_ms  integer     NOT NULL
);

-- Full engine state after a tick; the newest N are kept (FARGLOW_RESTORE_POINTS_KEEP, 72).
CREATE TABLE restore_points (
    tick        bigint PRIMARY KEY,
    state_hash  text        NOT NULL,
    snapshot    jsonb       NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Player orders queued for a future tick (empty in Phase 0; the replay contract needs the table).
CREATE TABLE orders (
    id          bigserial PRIMARY KEY,
    for_tick    bigint      NOT NULL,
    seq         integer     NOT NULL,
    body        jsonb       NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (for_tick, seq)
);

-- Postgres-native job queue (no Redis). Claimed with FOR UPDATE SKIP LOCKED.
CREATE TABLE jobs (
    id            bigserial PRIMARY KEY,
    queue         text        NOT NULL,
    kind          text        NOT NULL,
    payload       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    status        text        NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'running', 'done', 'dead')),
    priority      integer     NOT NULL DEFAULT 0,
    attempts      integer     NOT NULL DEFAULT 0,
    max_attempts  integer     NOT NULL DEFAULT 5,
    run_at        timestamptz NOT NULL DEFAULT now(),
    locked_at     timestamptz,
    locked_by     text,
    last_error    text,
    dedupe_key    text UNIQUE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz
);
CREATE INDEX jobs_ready_idx ON jobs (queue, priority DESC, run_at, id) WHERE status = 'queued';
CREATE INDEX jobs_running_idx ON jobs (locked_at) WHERE status = 'running';

CREATE FUNCTION jobs_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('farglow_jobs', NEW.queue);
    RETURN NEW;
END;
$$;
CREATE TRIGGER jobs_notify_insert AFTER INSERT ON jobs
    FOR EACH ROW EXECUTE FUNCTION jobs_notify();

-- Signed, single-use links (email actions). Only the nonce is stored; the token is HMAC-signed.
CREATE TABLE link_tokens (
    nonce       text PRIMARY KEY,
    purpose     text        NOT NULL,
    subject     text        NOT NULL,
    expires_at  timestamptz NOT NULL,
    issued_tick bigint,
    used_at     timestamptz,
    revoked_at  timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Engine audit trail: pause/resume/restore and similar operator actions.
CREATE TABLE engine_events (
    id          bigserial PRIMARY KEY,
    tick        bigint,
    kind        text        NOT NULL,
    detail      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE service_heartbeats (
    service   text        NOT NULL,
    instance  text        NOT NULL,
    version   text        NOT NULL,
    seen_at   timestamptz NOT NULL DEFAULT now(),
    detail    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (service, instance)
);
