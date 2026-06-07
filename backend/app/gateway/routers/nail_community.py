"""nailflow 美甲社区 — 帖子发布、浏览、点赞、评论。"""
import json
import logging
import shutil
import uuid
from datetime import datetime, UTC
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Query
from pydantic import BaseModel

from app.gateway.authz import require_auth
from packages.harness.nailflow.tools.nail.base import get_db, STYLES_DIR, UPLOADS_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/community", tags=["nail-community"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
COMMUNITY_IMAGES_DIR = UPLOADS_DIR / "community"
COMMUNITY_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

_PAGE_SIZE_MAX = 100


def _save_upload(file: UploadFile) -> tuple[str, str, str]:
    ext = Path(file.filename or "image.jpg").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}")
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}{ext}"
    dest = COMMUNITY_IMAGES_DIR / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return file_id, str(dest), safe_name


# ─── 响应模型 ────────────────────────────────────────────

class PostImageOut(BaseModel):
    id: str
    url: str
    sort_order: int

class CommentOut(BaseModel):
    id: str
    user_id: str
    content: str
    parent_id: str | None = None
    created_at: str

class PostOut(BaseModel):
    id: str
    user_id: str
    content: str
    tags: list[str]
    style_refs: list[dict]
    images: list[PostImageOut]
    like_count: int
    comment_count: int
    is_liked: bool
    created_at: str
    updated_at: str

class PostListOut(BaseModel):
    posts: list[PostOut]
    page: int
    size: int
    total: int
    has_more: bool


# ═══════════════════════════════════════════════════════════
# 帖子列表
# ═══════════════════════════════════════════════════════════

@router.get("/posts")
@require_auth
async def list_posts(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=_PAGE_SIZE_MAX),
):
    user_id = str(request.state.user.id)
    offset = (page - 1) * size

    with get_db() as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM community_posts WHERE is_active = 1"
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        rows = conn.execute(
            "SELECT id, user_id, content, tags, style_refs, like_count, comment_count, "
            "created_at, updated_at FROM community_posts "
            "WHERE is_active = 1 ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (size, offset),
        ).fetchall()

    posts = []
    for r in rows:
        with get_db() as conn:
            img_rows = conn.execute(
                "SELECT id, file_path, sort_order FROM post_images "
                "WHERE post_id = ? ORDER BY sort_order",
                (r["id"],),
            ).fetchall()
            liked = conn.execute(
                "SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?",
                (r["id"], user_id),
            ).fetchone()

        posts.append(PostOut(
            id=r["id"],
            user_id=r["user_id"],
            content=r["content"] or "",
            tags=json.loads(r["tags"]) if r["tags"] else [],
            style_refs=json.loads(r["style_refs"]) if r["style_refs"] else [],
            images=[PostImageOut(
                id=ir["id"],
                url=f"/api/nail/image?path={ir['file_path']}",
                sort_order=ir["sort_order"] or 0,
            ) for ir in img_rows],
            like_count=r["like_count"] or 0,
            comment_count=r["comment_count"] or 0,
            is_liked=liked is not None,
            created_at=r["created_at"] or "",
            updated_at=r["updated_at"] or "",
        ))

    return PostListOut(
        posts=posts, page=page, size=size, total=total,
        has_more=offset + size < total,
    ).model_dump()


# ═══════════════════════════════════════════════════════════
# 帖子详情
# ═══════════════════════════════════════════════════════════

@router.get("/posts/{post_id}")
@require_auth
async def get_post(post_id: str, request: Request):
    user_id = str(request.state.user.id)

    with get_db() as conn:
        r = conn.execute(
            "SELECT id, user_id, content, tags, style_refs, like_count, comment_count, "
            "created_at, updated_at FROM community_posts "
            "WHERE id = ? AND is_active = 1", (post_id,)
        ).fetchone()

    if not r:
        raise HTTPException(404, detail="帖子不存在")

    with get_db() as conn:
        img_rows = conn.execute(
            "SELECT id, file_path, sort_order FROM post_images "
            "WHERE post_id = ? ORDER BY sort_order", (post_id,)
        ).fetchall()
        liked = conn.execute(
            "SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()

    return PostOut(
        id=r["id"],
        user_id=r["user_id"],
        content=r["content"] or "",
        tags=json.loads(r["tags"]) if r["tags"] else [],
        style_refs=json.loads(r["style_refs"]) if r["style_refs"] else [],
        images=[PostImageOut(
            id=ir["id"],
            url=f"/api/nail/image?path={ir['file_path']}",
            sort_order=ir["sort_order"] or 0,
        ) for ir in img_rows],
        like_count=r["like_count"] or 0,
        comment_count=r["comment_count"] or 0,
        is_liked=liked is not None,
        created_at=r["created_at"] or "",
        updated_at=r["updated_at"] or "",
    ).model_dump()


# ═══════════════════════════════════════════════════════════
# 发帖
# ═══════════════════════════════════════════════════════════

@router.post("/posts", status_code=201)
@require_auth
async def create_post(
    request: Request,
    content: str = Form(default=""),
    tags: str = Form(default="[]"),
    style_refs: str = Form(default="[]"),
    files: list[UploadFile] = File(default_factory=list),
):
    user_id = str(request.state.user.id)

    try:
        tags_list = json.loads(tags)
        if not isinstance(tags_list, list):
            tags_list = []
    except (json.JSONDecodeError, TypeError):
        tags_list = []

    try:
        refs = json.loads(style_refs)
        if not isinstance(refs, list):
            refs = []
    except (json.JSONDecodeError, TypeError):
        refs = []

    post_id = uuid.uuid4().hex[:16]
    now = datetime.now(UTC).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO community_posts (id, user_id, content, tags, style_refs, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (post_id, user_id, content, json.dumps(tags_list, ensure_ascii=False),
             json.dumps(refs, ensure_ascii=False), now, now),
        )

        for idx, f in enumerate(files):
            if not f.filename:
                continue
            img_id, dest, safe_name = _save_upload(f)
            conn.execute(
                "INSERT INTO post_images (id, post_id, file_path, filename, sort_order, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (img_id, post_id, dest, safe_name, idx, now),
            )
        conn.commit()

    return {"id": post_id, "message": "发布成功"}


# ═══════════════════════════════════════════════════════════
# 删除帖子
# ═══════════════════════════════════════════════════════════

@router.delete("/posts/{post_id}")
@require_auth
async def delete_post(post_id: str, request: Request):
    user_id = str(request.state.user.id)

    with get_db() as conn:
        r = conn.execute(
            "SELECT user_id FROM community_posts WHERE id = ? AND is_active = 1",
            (post_id,),
        ).fetchone()
        if not r:
            raise HTTPException(404, detail="帖子不存在")
        if r["user_id"] != user_id:
            raise HTTPException(403, detail="只能删除自己的帖子")
        conn.execute(
            "UPDATE community_posts SET is_active = 0 WHERE id = ?", (post_id,)
        )
        conn.commit()
    return {"message": "已删除"}


# ═══════════════════════════════════════════════════════════
# 点赞/取消点赞
# ═══════════════════════════════════════════════════════════

@router.post("/posts/{post_id}/like")
@require_auth
async def toggle_like(post_id: str, request: Request):
    user_id = str(request.state.user.id)
    now = datetime.now(UTC).isoformat()

    with get_db() as conn:
        post = conn.execute(
            "SELECT id FROM community_posts WHERE id = ? AND is_active = 1",
            (post_id,),
        ).fetchone()
        if not post:
            raise HTTPException(404, detail="帖子不存在")

        existing = conn.execute(
            "SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()

        if existing:
            conn.execute("DELETE FROM post_likes WHERE post_id = ? AND user_id = ?",
                         (post_id, user_id))
            conn.execute(
                "UPDATE community_posts SET like_count = MAX(0, like_count - 1) WHERE id = ?",
                (post_id,),
            )
            conn.commit()
            return {"liked": False, "like_count": post["like_count"] - 1 if post["like_count"] > 0 else 0}
        else:
            like_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO post_likes (id, post_id, user_id, created_at) VALUES (?,?,?,?)",
                (like_id, post_id, user_id, now),
            )
            conn.execute(
                "UPDATE community_posts SET like_count = like_count + 1 WHERE id = ?",
                (post_id,),
            )
            conn.commit()
            with get_db() as conn2:
                updated = conn2.execute(
                    "SELECT like_count FROM community_posts WHERE id = ?", (post_id,)
                ).fetchone()
            return {"liked": True, "like_count": updated["like_count"] if updated else 1}


# ═══════════════════════════════════════════════════════════
# 评论列表
# ═══════════════════════════════════════════════════════════

@router.get("/posts/{post_id}/comments")
@require_auth
async def list_comments(
    post_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=_PAGE_SIZE_MAX),
):
    offset = (page - 1) * size
    with get_db() as conn:
        post = conn.execute(
            "SELECT id FROM community_posts WHERE id = ? AND is_active = 1",
            (post_id,),
        ).fetchone()
        if not post:
            raise HTTPException(404, detail="帖子不存在")

        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM post_comments WHERE post_id = ? AND is_active = 1",
            (post_id,),
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        rows = conn.execute(
            "SELECT id, post_id, user_id, content, parent_id, created_at "
            "FROM post_comments WHERE post_id = ? AND is_active = 1 "
            "ORDER BY created_at ASC LIMIT ? OFFSET ?",
            (post_id, size, offset),
        ).fetchall()

    comments = [
        CommentOut(
            id=r["id"],
            user_id=r["user_id"],
            content=r["content"],
            parent_id=r["parent_id"],
            created_at=r["created_at"] or "",
        )
        for r in rows
    ]
    return {"comments": [c.model_dump() for c in comments], "page": page, "size": size,
            "total": total, "has_more": offset + size < total}


# ═══════════════════════════════════════════════════════════
# 发表评论
# ═══════════════════════════════════════════════════════════

class CreateCommentBody(BaseModel):
    content: str
    parent_id: str | None = None


@router.post("/posts/{post_id}/comments", status_code=201)
@require_auth
async def create_comment(post_id: str, body: CreateCommentBody, request: Request):
    if not body.content or not body.content.strip():
        raise HTTPException(400, detail="评论内容不能为空")
    user_id = str(request.state.user.id)
    comment_id = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()

    with get_db() as conn:
        post = conn.execute(
            "SELECT id FROM community_posts WHERE id = ? AND is_active = 1",
            (post_id,),
        ).fetchone()
        if not post:
            raise HTTPException(404, detail="帖子不存在")

        conn.execute(
            "INSERT INTO post_comments (id, post_id, user_id, content, parent_id, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (comment_id, post_id, user_id, body.content.strip(), body.parent_id, now),
        )
        conn.execute(
            "UPDATE community_posts SET comment_count = comment_count + 1 WHERE id = ?",
            (post_id,),
        )
        conn.commit()

    return {
        "id": comment_id,
        "user_id": user_id,
        "content": body.content.strip(),
        "parent_id": body.parent_id,
        "created_at": now,
    }


# ═══════════════════════════════════════════════════════════
# 点赞用户列表
# ═══════════════════════════════════════════════════════════

@router.get("/posts/{post_id}/likes")
@require_auth
async def list_likes(post_id: str, request: Request):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT user_id, created_at FROM post_likes WHERE post_id = ? ORDER BY created_at DESC LIMIT 50",
            (post_id,),
        ).fetchall()
    return {"likes": [{"user_id": r["user_id"], "created_at": r["created_at"]} for r in rows]}
