"""
Blog business logic — pure Python, no Flask imports.

Provides CRUD operations for blog posts used by The Observatory.
"""

import re
import html
import sqlite3
from typing import Optional


def _slugify(title: str) -> str:
    """Convert a title to a URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:120]


def _render_markdown(md_text: str) -> str:
    """Convert markdown to HTML.

    Uses the ``markdown`` library when available, falling back to a
    lightweight regex-based converter for basic formatting.
    """
    try:
        import markdown
        return markdown.markdown(
            md_text,
            extensions=['fenced_code', 'tables', 'nl2br'],
        )
    except ImportError:
        pass

    # Lightweight fallback — handles headers, bold, italic, links, code
    lines = md_text.split('\n')
    out = []
    in_code = False
    for line in lines:
        if line.startswith('```'):
            if in_code:
                out.append('</code></pre>')
                in_code = False
            else:
                out.append('<pre><code>')
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue

        # Headers
        if line.startswith('### '):
            out.append(f'<h3>{html.escape(line[4:])}</h3>')
            continue
        if line.startswith('## '):
            out.append(f'<h2>{html.escape(line[3:])}</h2>')
            continue
        if line.startswith('# '):
            out.append(f'<h1>{html.escape(line[2:])}</h1>')
            continue

        # Inline formatting
        escaped = html.escape(line)
        escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
        escaped = re.sub(r'\*(.+?)\*', r'<em>\1</em>', escaped)
        escaped = re.sub(r'`(.+?)`', r'<code>\1</code>', escaped)
        escaped = re.sub(
            r'\[(.+?)\]\((.+?)\)',
            r'<a href="\2">\1</a>',
            escaped,
        )

        if escaped.strip():
            out.append(f'<p>{escaped}</p>')
        else:
            out.append('')

    if in_code:
        out.append('</code></pre>')

    return '\n'.join(out)


def create_post(
    conn: sqlite3.Connection,
    title: str,
    content_md: str,
    author_id: int,
    excerpt: str = '',
    published: bool = False,
) -> int:
    """Create a new blog post. Returns the post ID."""
    slug = _slugify(title)
    # Ensure slug uniqueness
    base_slug = slug
    counter = 1
    while conn.execute(
        "SELECT 1 FROM blog_posts WHERE slug = ?", (slug,)
    ).fetchone():
        slug = f"{base_slug}-{counter}"
        counter += 1

    content_html = _render_markdown(content_md)
    cur = conn.execute(
        """INSERT INTO blog_posts
           (title, slug, content_md, content_html, excerpt, author_id, published)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, slug, content_md, content_html, excerpt, author_id, int(published)),
    )
    conn.commit()
    return cur.lastrowid


def update_post(conn: sqlite3.Connection, post_id: int, **fields) -> bool:
    """Partial update of a blog post. Re-renders HTML if content_md changes."""
    allowed = {'title', 'content_md', 'excerpt', 'published', 'pinned', 'slug'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    if 'content_md' in updates:
        updates['content_html'] = _render_markdown(updates['content_md'])

    if 'title' in updates and 'slug' not in updates:
        updates['slug'] = _slugify(updates['title'])

    if 'published' in updates:
        updates['published'] = int(updates['published'])
    if 'pinned' in updates:
        updates['pinned'] = int(updates['pinned'])

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    set_clause += ", updated_at = datetime('now')"
    values = list(updates.values()) + [post_id]

    conn.execute(
        f"UPDATE blog_posts SET {set_clause} WHERE id = ?",
        values,
    )
    conn.commit()
    return True


def delete_post(conn: sqlite3.Connection, post_id: int) -> bool:
    """Delete a blog post."""
    cur = conn.execute("DELETE FROM blog_posts WHERE id = ?", (post_id,))
    conn.commit()
    return cur.rowcount > 0


def get_post(
    conn: sqlite3.Connection,
    post_id: Optional[int] = None,
    slug: Optional[str] = None,
) -> Optional[sqlite3.Row]:
    """Get a single post by ID or slug."""
    if post_id is not None:
        return conn.execute(
            """SELECT bp.*, u.display_name as author_name
               FROM blog_posts bp
               LEFT JOIN users u ON u.id = bp.author_id
               WHERE bp.id = ?""",
            (post_id,),
        ).fetchone()
    if slug is not None:
        return conn.execute(
            """SELECT bp.*, u.display_name as author_name
               FROM blog_posts bp
               LEFT JOIN users u ON u.id = bp.author_id
               WHERE bp.slug = ?""",
            (slug,),
        ).fetchone()
    return None


def list_posts(
    conn: sqlite3.Connection,
    published_only: bool = True,
    limit: int = 50,
) -> list:
    """List posts ordered by pinned desc, created_at desc."""
    where = "WHERE bp.published = 1" if published_only else ""
    return conn.execute(
        f"""SELECT bp.*, u.display_name as author_name
            FROM blog_posts bp
            LEFT JOIN users u ON u.id = bp.author_id
            {where}
            ORDER BY bp.pinned DESC, bp.created_at DESC
            LIMIT ?""",
        (limit,),
    ).fetchall()
