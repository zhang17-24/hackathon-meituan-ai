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

        top_styles = conn.execute("""
            SELECT style_id, COUNT(*) as total,
                   SUM(CASE WHEN signal_type='save' THEN 1 ELSE 0 END) as saves
            FROM ops_signals
            WHERE created_at >= datetime('now', ? || ' days')
            GROUP BY style_id
            ORDER BY total DESC
            LIMIT 10
        """, (f"-{days}",)).fetchall()

    return {
        "signals": [dict(s) for s in signals],
        "proposal_summary": {r["status"]: r["count"] for r in proposal_summary},
        "top_styles": [dict(r) for r in top_styles],
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


# ─── 款式收藏 ───────────────────────────────────────────────

class SaveStyleRequest(BaseModel):
    signal_type: str = "save"  # "save" 或 "search"


@router.post("/styles/{style_id}/save")
@require_auth
async def save_style(style_id: str, body: SaveStyleRequest, request: Request):
    """用户收藏款式：更新用户偏好向量 + 写入 ops_signals。"""
    from packages.harness.deerflow.tools.nail.base import update_user_pref_vector, get_db
    user = request.state.user
    user_id = str(user.id)

    signal_type = body.signal_type if body.signal_type in ("save", "search") else "save"
    update_user_pref_vector(user_id, style_id, signal_type)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO ops_signals (user_id, style_id, signal_type) VALUES (?,?,?)",
            (user_id, style_id, signal_type)
        )
    return {"saved": True, "style_id": style_id, "signal_type": signal_type}


# ─── 分析看板 ───────────────────────────────────────────────

@router.get("/analytics/pref-distribution")
@require_auth
async def get_pref_distribution(request: Request):
    """返回全体用户偏好风格分布（供运营看板饼图使用）。"""
    from packages.harness.deerflow.tools.nail.base import get_db
    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.style_id,
                   COALESCE(c.category, '其他') as category,
                   SUM(CASE WHEN s.signal_type='save'  THEN 3 ELSE 1 END) as score
            FROM ops_signals s
            LEFT JOIN nail_style_catalog c ON s.style_id = c.style_id
            GROUP BY s.style_id, c.category
            ORDER BY score DESC
        """).fetchall()

    cat_scores: dict[str, int] = {}
    for r in rows:
        cat = r["category"] or "其他"
        cat_scores[cat] = cat_scores.get(cat, 0) + r["score"]

    total = sum(cat_scores.values()) or 1
    distribution = [
        {"category": k, "score": v, "percentage": round(v / total * 100, 1)}
        for k, v in sorted(cat_scores.items(), key=lambda x: -x[1])
    ]
    return {"distribution": distribution, "total_signals": sum(cat_scores.values())}


@router.get("/analytics/latest-run")
@require_auth
async def get_latest_run(request: Request):
    """返回当前用户最近一次 nail_run 的工具调用链数据，供前端 ToolTimeline 展示。"""
    from packages.harness.deerflow.tools.nail.base import get_db
    user = request.state.user
    user_id = str(user.id)

    with get_db() as conn:
        run = conn.execute(
            "SELECT id, nail_role, status, created_at FROM nail_runs "
            "WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if run is None:
            return {"run": None}
        calls = conn.execute(
            "SELECT tool_name, call_index, duration_ms FROM tool_call_log "
            "WHERE run_id=? ORDER BY call_index ASC",
            (run["id"],)
        ).fetchall()

    tool_chain = [
        {
            "tool":        c["tool_name"],
            "call_index":  c["call_index"],
            "duration_ms": c["duration_ms"] or 0,
            "success":     (c["duration_ms"] or 0) >= 0,
        }
        for c in calls
    ]
    total_ms = sum(max(0, c["duration_ms"] or 0) for c in calls)
    return {
        "run": {
            "run_id":            run["id"],
            "tool_chain":        tool_chain,
            "total_duration_ms": total_ms,
        }
    }
