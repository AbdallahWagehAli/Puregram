-- ============================================================================
-- Puregram — LEGACY device tables kept alive for pre-12.9 clients.
--
-- Clients built before ADR-001 (2026-09-03) still report their chat list and
-- poll a per-account whitelist. Until every handset has updated, the server
-- answers that old protocol by filtering the reported chats through the global
-- policy (see routes/telegram_device.py). These are the columns/tables that
-- answer needs. Once the old builds are gone from the logs, this file and the
-- legacy endpoints can be dropped together (owner's call).
--
-- Every statement is idempotent; applied on every boot after schema.sql.
-- ============================================================================

-- Which Telegram accounts are logged in on a device (the multi-account roster).
CREATE TABLE IF NOT EXISTS customer_accounts (
    customer_id  TEXT   NOT NULL,
    tg_user_id   BIGINT NOT NULL,
    username     TEXT,
    display_name TEXT,
    created_at   TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
    updated_at   TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'utc','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
    PRIMARY KEY (customer_id, tg_user_id),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_customer_accounts_tg ON customer_accounts(tg_user_id);
ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS username     TEXT;
ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS display_name TEXT;

-- Known chats are keyed per ACCOUNT, not per device.
ALTER TABLE telegram_known_chats ADD COLUMN IF NOT EXISTS tg_user_id BIGINT;
UPDATE telegram_known_chats k
   SET tg_user_id = c.tg_user_id
  FROM customers c
 WHERE c.id = k.customer_id
   AND k.tg_user_id IS NULL
   AND c.tg_user_id IS NOT NULL;
UPDATE telegram_known_chats SET tg_user_id = 0 WHERE tg_user_id IS NULL;
ALTER TABLE telegram_known_chats ALTER COLUMN tg_user_id SET DEFAULT 0;
ALTER TABLE telegram_known_chats ALTER COLUMN tg_user_id SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'telegram_known_chats_pkey'
           AND array_length(conkey, 1) = 2
    ) THEN
        ALTER TABLE telegram_known_chats DROP CONSTRAINT telegram_known_chats_pkey;
        ALTER TABLE telegram_known_chats
            ADD CONSTRAINT telegram_known_chats_pkey
            PRIMARY KEY (customer_id, tg_user_id, chat_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tg_known_account
    ON telegram_known_chats (tg_user_id, last_seen_at);
