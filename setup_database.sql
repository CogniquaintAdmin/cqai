PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- ==========================================================
-- Latest Messages Table
-- ==========================================================

CREATE TABLE IF NOT EXISTS messages_new (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    group_id TEXT,
    sender TEXT,
    body TEXT,

    message_type TEXT,

    media_path TEXT,
    media_type TEXT,
    media_filename TEXT,

    timestamp INTEGER,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    normalized_content TEXT,

    enrichment_status TEXT DEFAULT 'pending',

    ai_content TEXT,

    ai_metadata TEXT,

    enriched_at DATETIME
);

-- ==========================================================
-- Copy old data (if old table exists)
-- ==========================================================

INSERT INTO messages_new (

    id,
    group_id,
    sender,
    body,
    message_type,
    media_path,
    media_type,
    media_filename,
    timestamp,
    created_at

)
SELECT

    id,
    group_id,
    sender,
    body,
    message_type,
    media_path,
    media_type,
    media_filename,
    timestamp,
    created_at

FROM messages
WHERE EXISTS (
    SELECT 1
    FROM sqlite_master
    WHERE type='table'
      AND name='messages'
);

DROP TABLE IF EXISTS messages;

ALTER TABLE messages_new
RENAME TO messages;

CREATE INDEX IF NOT EXISTS idx_messages_timestamp
ON messages(timestamp);

CREATE INDEX IF NOT EXISTS idx_messages_group
ON messages(group_id);

CREATE INDEX IF NOT EXISTS idx_messages_status
ON messages(enrichment_status);

COMMIT;

PRAGMA foreign_keys = ON;
