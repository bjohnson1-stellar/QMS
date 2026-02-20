-- Blog posts for "The Observatory"
CREATE TABLE IF NOT EXISTS blog_posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    slug          TEXT NOT NULL UNIQUE,
    content_md    TEXT NOT NULL DEFAULT '',
    content_html  TEXT NOT NULL DEFAULT '',
    excerpt       TEXT DEFAULT '',
    author_id     INTEGER REFERENCES users(id),
    published     INTEGER NOT NULL DEFAULT 0,
    pinned        INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
