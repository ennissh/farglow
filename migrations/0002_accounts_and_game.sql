-- PoC 1: accounts, the order queue, the Dispatch and the advisor log.

-- Orders are numbered by one sequence, so the tick applies them in the order they were queued.
CREATE SEQUENCE orders_seq;
ALTER TABLE orders ADD COLUMN user_id bigint;
CREATE INDEX orders_for_tick_idx ON orders (for_tick, seq);

CREATE TABLE users (
    id                 bigserial PRIMARY KEY,
    email              text        NOT NULL,
    email_lower        text        NOT NULL UNIQUE,
    display_name       text        NOT NULL,
    password_hash      text        NOT NULL,
    birth_year         integer     NOT NULL,
    birth_month        integer     NOT NULL CHECK (birth_month BETWEEN 1 AND 12),
    is_admin           boolean     NOT NULL DEFAULT false,
    email_verified_at  timestamptz,
    dispatch_email     boolean     NOT NULL DEFAULT true,
    session_version    integer     NOT NULL DEFAULT 1,
    walkthrough        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    last_seen_at       timestamptz
);

-- The Dispatch: what happened to a civilization, one row per event, rendered by templates (T0).
CREATE TABLE dispatch_items (
    id          bigserial PRIMARY KEY,
    user_id     bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    civ_id      text        NOT NULL,
    tick        bigint      NOT NULL,
    kind        text        NOT NULL,
    data        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    emailed     boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX dispatch_user_idx ON dispatch_items (user_id, id DESC);

-- Everything the advisor said or proposed, and to whom (the AI activity log).
CREATE TABLE advisor_log (
    id          bigserial PRIMARY KEY,
    user_id     bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role        text        NOT NULL CHECK (role IN ('player', 'advisor')),
    text        text        NOT NULL,
    tier        text,
    fallback    boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX advisor_log_user_idx ON advisor_log (user_id, id DESC);
