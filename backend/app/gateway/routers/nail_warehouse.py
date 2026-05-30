# backend/app/gateway/routers/nail_warehouse.py
"""NailFlow 美甲仓库 — 手图管理与款式图库。"""
import json
import logging
import shutil
import uuid
from datetime import datetime, UTC
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.gateway.authz import require_auth
from packages.harness.deerflow.tools.nail.base import get_db, HANDS_DIR, STYLES_DIR, UPLOADS_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nail/warehouse", tags=["nail-warehouse"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _save_upload(file: UploadFile, target_dir: Path) -> tuple[str, str]:
    """Save uploaded file, returns (file_id, physical_path)."""
    ext = Path(file.filename or "image.jpg").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}，仅支持 jpg/png/webp/bmp")
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}{ext}"
    dest = target_dir / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return file_id, str(dest)


# ─── 响应模型 ────────────────────────────────────────────

class HandPhotoOut(BaseModel):
    id: str
    filename: str
    url: str
    created_at: str


class StyleImageOut(BaseModel):
    id: str
    filename: str
    url: str
    category: str
    source: str
    tags: list[str]
    created_at: str


# ═══════════════════════════════════════════════════════════
# 手图管理
# ═══════════════════════════════════════════════════════════

@router.get("/hands")
@require_auth
async def list_hands(request: Request):
    """列出当前用户的所有手图。"""
    user_id = str(request.state.user.id)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, filename, file_path, created_at FROM nail_hand_photos "
            "WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return {
        "hands": [
            HandPhotoOut(
                id=r["id"],
                filename=r["filename"],
                url=f"/api/nail/image?path={r['file_path']}",
                created_at=r["created_at"],
            )
            for r in rows
        ]
    }


@router.post("/hands", status_code=201)
@require_auth
async def upload_hand(request: Request, file: UploadFile = File(...)):
    """上传一张手图到仓库。"""
    user_id = str(request.state.user.id)
    file_id, dest = _save_upload(file, HANDS_DIR)
    now = datetime.now(UTC).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO nail_hand_photos (id, user_id, filename, file_path, created_at) "
            "VALUES (?,?,?,?,?)",
            (file_id, user_id, file.filename, dest, now),
        )
        conn.commit()
    return {"id": file_id, "url": f"/api/nail/image?path={dest}", "filename": file.filename}


@router.delete("/hands/{hand_id}")
@require_auth
async def delete_hand(hand_id: str, request: Request):
    """删除一张手图（软删除）。"""
    user_id = str(request.state.user.id)
    with get_db() as conn:
        result = conn.execute(
            "UPDATE nail_hand_photos SET is_active = 0 WHERE id = ? AND user_id = ?",
            (hand_id, user_id),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(404, detail="手图不存在或无权操作")
    return {"message": "已删除"}


# ═══════════════════════════════════════════════════════════
# 款式图管理
# ═══════════════════════════════════════════════════════════

@router.get("/styles")
@require_auth
async def list_styles(request: Request):
    """列出款式图：系统内置 + 用户上传。"""
    user_id = str(request.state.user.id)
    results: list[StyleImageOut] = []

    # 系统内置款式（data/styles/ 目录下的 .jpg）
    sys_dir = Path("data/styles")
    if sys_dir.exists():
        for f in sorted(sys_dir.glob("*.jpg")):
            results.append(StyleImageOut(
                id=f"sys-{f.stem}",
                filename=f.name,
                url=f"/api/nail/image?path=data/styles/{f.name}",
                category="system",
                source="system",
                tags=[],
                created_at="",
            ))

    # 用户上传的款式
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, filename, file_path, category, source, tags, created_at "
            "FROM nail_style_images "
            "WHERE (user_id = ? OR source = 'system') AND is_active = 1 "
            "ORDER BY source DESC, created_at DESC",
            (user_id,),
        ).fetchall()
    for r in rows:
        tags = json.loads(r["tags"]) if r["tags"] else []
        results.append(StyleImageOut(
            id=r["id"],
            filename=r["filename"],
            url=f"/api/nail/image?path={r['file_path']}",
            category=r["category"] or "user",
            source=r["source"] or "user",
            tags=tags,
            created_at=r["created_at"] or "",
        ))

    return {"styles": results, "count": len(results)}


@router.post("/styles", status_code=201)
@require_auth
async def upload_style(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(default="user"),
    tags: str = Form(default="[]"),
):
    """上传一张自定义款式图到仓库。"""
    user_id = str(request.state.user.id)
    file_id, dest = _save_upload(file, STYLES_DIR)
    now = datetime.now(UTC).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO nail_style_images (id, user_id, filename, file_path, category, tags, source, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (file_id, user_id, file.filename, dest, category, tags, "user", now),
        )
        conn.commit()
    return {"id": file_id, "url": f"/api/nail/image?path={dest}", "filename": file.filename}


@router.delete("/styles/{style_id}")
@require_auth
async def delete_style(style_id: str, request: Request):
    """删除用户上传的款式图（系统款式不可删）。"""
    if style_id.startswith("sys-"):
        raise HTTPException(400, detail="系统款式不可删除")
    user_id = str(request.state.user.id)
    with get_db() as conn:
        result = conn.execute(
            "UPDATE nail_style_images SET is_active = 0 WHERE id = ? AND user_id = ?",
            (style_id, user_id),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(404, detail="款式不存在或无权操作")
    return {"message": "已删除"}
