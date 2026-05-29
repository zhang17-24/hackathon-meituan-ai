# backend/app/gateway/routers/nail_ops.py
"""NailFlow 运营端接口：ActionProposal 确认/拒绝，运营看板，图片服务。"""
import logging
from datetime import datetime, UTC
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.gateway.authz import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nail", tags=["nail-ops"])


# ─── ActionProposal 接口 ──────────────────────────────────────

class ProposalActionBody(BaseModel):
    status: str  # "approved" | "rejected"


@router.post("/proposals/{proposal_id}/confirm")
@require_auth
async def confirm_proposal(proposal_id: str, body: ProposalActionBody, request: Request):
    """运营人员确认或拒绝 ActionProposal。"""
    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status 必须是 'approved' 或 'rejected'")

    from packages.harness.deerflow.tools.nail.base import get_db

    with get_db() as conn:
        row = conn.execute("SELECT id FROM action_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} 不存在")

        conn.execute(
            "UPDATE action_proposals SET status = ?, confirmed_at = ? WHERE id = ?",
            (body.status, datetime.now(UTC).isoformat(), proposal_id)
        )
        conn.commit()

    return {"proposal_id": proposal_id, "status": body.status, "updated_at": datetime.now(UTC).isoformat()}


@router.get("/proposals")
@require_auth
async def list_proposals(request: Request, status: str = "pending", limit: int = 20):
    """查询 ActionProposal 列表。"""
    from packages.harness.deerflow.tools.nail.base import get_db

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM action_proposals WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    return {"proposals": [dict(r) for r in rows], "count": len(rows)}


# ─── 运营看板 ───────────────────────────────────────────────

@router.get("/dashboard")
@require_auth
async def get_dashboard(request: Request, days: int = 7):
    """运营看板：趋势信号聚合 + ActionProposal 状态汇总。"""
    from packages.harness.deerflow.tools.nail.base import get_db

    with get_db() as conn:
        signals = conn.execute("""
            SELECT style_id, signal_type, COUNT(*) AS count
            FROM ops_signals
            WHERE created_at >= datetime('now', ?)
            GROUP BY style_id, signal_type
            ORDER BY count DESC
            LIMIT 30
        """, (f"-{days} day",)).fetchall()

        proposal_summary = conn.execute(
            "SELECT status, COUNT(*) AS count FROM action_proposals GROUP BY status"
        ).fetchall()

    return {
        "signals": [dict(s) for s in signals],
        "proposal_summary": {r["status"]: r["count"] for r in proposal_summary},
        "days": days,
    }


# ─── 图片服务（结果图 / 上传图） ──────────────────────────────

@router.get("/image")
@require_auth
async def serve_image(path: str, request: Request):
    """提供本地生成/上传图片的 HTTP 访问。"""
    safe = Path(path).resolve()
    # 安全检查：只允许读取 data/ 目录下的文件
    data_dir = Path("data").resolve()
    if not str(safe).startswith(str(data_dir)):
        raise HTTPException(status_code=403, detail="Access denied: path outside data directory")
    if not safe.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {path}")
    return FileResponse(str(safe))
