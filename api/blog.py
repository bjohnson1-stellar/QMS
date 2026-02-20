"""
Blog blueprint — The Observatory.

Public routes for viewing posts, admin API for CRUD.
"""

from flask import Blueprint, abort, jsonify, render_template, request, session

bp = Blueprint("blog", __name__, url_prefix="/blog")


@bp.route("/")
def blog_list():
    """All published posts (auto-publishes scheduled posts on visit)."""
    from qms.blog.db import list_posts
    from qms.core import get_db

    with get_db() as conn:
        posts = list_posts(conn, published_only=True)
    return render_template("blog/list.html", posts=posts)


@bp.route("/<slug>")
def blog_detail(slug):
    """Single post by slug."""
    from qms.blog.db import get_post
    from qms.core import get_db

    with get_db(readonly=True) as conn:
        post = get_post(conn, slug=slug)
    if not post or (not post["published"] and session.get("user", {}).get("role") != "admin"):
        abort(404)
    return render_template("blog/detail.html", post=post)


# ── Admin API ──────────────────────────────────────────────────────────


def _require_admin():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        abort(403)
    return user


@bp.route("/api/posts", methods=["GET"])
def api_list_posts():
    """List all posts (admin sees drafts too)."""
    _require_admin()
    from qms.blog.db import list_posts
    from qms.core import get_db

    with get_db() as conn:
        posts = list_posts(conn, published_only=False)
    return jsonify([dict(p) for p in posts])


@bp.route("/api/posts", methods=["POST"])
def api_create_post():
    """Create a new post."""
    user = _require_admin()
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    from qms.blog.db import create_post, get_post
    from qms.core import get_db

    publish_at = (data.get("publish_at") or "").strip() or None

    with get_db() as conn:
        post_id = create_post(
            conn,
            title=title,
            content_md=data.get("content_md", ""),
            author_id=user["id"],
            excerpt=data.get("excerpt", ""),
            published=data.get("published", False),
            publish_at=publish_at,
        )
        post = get_post(conn, post_id=post_id)
    return jsonify(dict(post)), 201


@bp.route("/api/posts/<int:post_id>", methods=["PUT"])
def api_update_post(post_id):
    """Update a post."""
    _require_admin()
    data = request.get_json(force=True)

    from qms.blog.db import get_post, update_post
    from qms.core import get_db

    # Normalize empty publish_at to None
    if "publish_at" in data:
        data["publish_at"] = (data["publish_at"] or "").strip() or None

    with get_db() as conn:
        if not get_post(conn, post_id=post_id):
            abort(404)
        update_post(conn, post_id, **data)
        post = get_post(conn, post_id=post_id)
    return jsonify(dict(post))


@bp.route("/api/posts/<int:post_id>", methods=["DELETE"])
def api_delete_post(post_id):
    """Delete a post."""
    _require_admin()
    from qms.blog.db import delete_post
    from qms.core import get_db

    with get_db() as conn:
        deleted = delete_post(conn, post_id)
    if not deleted:
        abort(404)
    return jsonify({"ok": True})
