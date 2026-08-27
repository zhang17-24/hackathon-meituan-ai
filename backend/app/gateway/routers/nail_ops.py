# backend/app/gateway/routers/nail_ops.py
"""nailflow 运营端接口：ActionProposal 确认/拒绝，运营看板，图片服务。"""
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

    from packages.harness.nailflow.tools.nail.base import get_db

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
    from packages.harness.nailflow.tools.nail.base import get_db

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
    from packages.harness.nailflow.tools.nail.base import get_db

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


# ─── 款式图库 ───────────────────────────────────────────────

_STYLE_CACHE: list[dict] = []
_STYLE_CACHE_MTIME: float = 0.0


@router.get("/styles")
async def list_styles():
    """列出 data/styles/ 目录下所有可试戴的美甲款式图。"""
    import os as _os
    global _STYLE_CACHE, _STYLE_CACHE_MTIME

    styles_dir = Path("data/styles")
    if not styles_dir.exists():
        return {"styles": [], "count": 0}

    try:
        mtime = _os.path.getmtime(styles_dir)
    except OSError:
        mtime = 0

    if _STYLE_CACHE and mtime == _STYLE_CACHE_MTIME:
        return {"styles": _STYLE_CACHE, "count": len(_STYLE_CACHE)}

    _STYLE_CACHE = []
    for f in sorted(styles_dir.glob("*.jpg")):
        _STYLE_CACHE.append({
            "id": f.stem,
            "name": f"款式 {f.stem}",
            "url": f"/api/nail/image?path=data/styles/{f.name}",
            "filename": f.name,
        })
    _STYLE_CACHE_MTIME = mtime
    return {"styles": _STYLE_CACHE, "count": len(_STYLE_CACHE)}


# ─── 款式收藏 ───────────────────────────────────────────────

class SaveStyleRequest(BaseModel):
    signal_type: str = "save"  # "save" 或 "search"


@router.post("/styles/{style_id}/save")
@require_auth
async def save_style(style_id: str, body: SaveStyleRequest, request: Request):
    """用户收藏款式：更新用户偏好向量 + 写入 ops_signals。"""
    from packages.harness.nailflow.tools.nail.base import update_user_pref_vector, get_db
    user = request.state.user
    user_id = str(user.id)

    signal_type = body.signal_type if body.signal_type in ("save", "search") else "save"
    update_user_pref_vector(user_id, style_id, signal_type)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO ops_signals (user_id, style_id, signal_type) VALUES (?,?,?)",
            (user_id, style_id, signal_type)
        )
        conn.commit()
    return {"saved": True, "style_id": style_id, "signal_type": signal_type}


# ─── 分析看板 ───────────────────────────────────────────────

@router.get("/analytics/pref-distribution")
@require_auth
async def get_pref_distribution(request: Request):
    """返回全体用户偏好风格分布（供运营看板饼图使用）。"""
    from packages.harness.nailflow.tools.nail.base import get_db
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
    from packages.harness.nailflow.tools.nail.base import get_db
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


# ─── Job 触发 ──────────────────────────────────────────────────


class OpsTriggerBody(BaseModel):
    context: dict = {}


@router.post("/ops/trigger/{job_id}")
@require_auth
async def trigger_ops_job(job_id: str, body: OpsTriggerBody, request: Request):
    """手动触发运营定时任务（daily_report / trend_alert / proactive_chat）。"""
    from nailflow.tools.nail.ops_channel.ops_runner import run_job
    from nailflow.tools.nail.ops_channel.job_store import OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec
    import asyncio as _asyncio

    job = OpsJob(
        job_id=job_id,
        trigger=Trigger(type=TriggerType.MANUAL),
        task=TaskSpec(type=job_id),
        delivery=DeliverySpec(targets=[]),
    )
    try:
        result = await _asyncio.wait_for(
            run_job(job, trigger_context=body.context or {}),
            timeout=300,
        )
        return {"job_id": job_id, "status": "completed", "result": result}
    except _asyncio.TimeoutError:
        return {"job_id": job_id, "status": "timeout", "result": {}}
    except Exception as exc:
        logger.exception("Trigger job %s failed", job_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── AI 运营分析 ──────────────────────────────────────────────


@router.get("/dashboard/ai-analysis")
@require_auth
async def get_ai_analysis(request: Request, days: int = 7):
    """基于近N天运营数据，调用千问模型生成 AI 分析报告。"""
    from nailflow.tools.nail.base import get_db

    with get_db() as conn:
        signals = conn.execute("""
            SELECT s.style_id, s.signal_type, COUNT(*) AS count, c.description as style_name
            FROM ops_signals s
            LEFT JOIN nail_style_catalog c ON s.style_id = c.style_id
            WHERE s.created_at >= datetime('now', ?)
            GROUP BY s.style_id, s.signal_type
            ORDER BY count DESC
            LIMIT 50
        """, (f"-{days} day",)).fetchall()

        proposals = conn.execute(
            "SELECT status, COUNT(*) as count FROM action_proposals GROUP BY status"
        ).fetchall()

        top5 = conn.execute("""
            SELECT s.style_id, COUNT(*) as total,
                   SUM(CASE WHEN s.signal_type='save' THEN 1 ELSE 0 END) as saves,
                   c.description as style_name
            FROM ops_signals s
            LEFT JOIN nail_style_catalog c ON s.style_id = c.style_id
            WHERE s.created_at >= datetime('now', ? || ' days')
            GROUP BY s.style_id ORDER BY total DESC LIMIT 5
        """, (f"-{days}",)).fetchall()

    signal_list = [dict(s) for s in signals]
    proposal_stats = {r["status"]: r["count"] for r in proposals}
    top5_list = [dict(r) for r in top5]

    if not signal_list:
        return {"analysis": "暂无足够运营数据，AI 分析将在积累数据后自动生成。", "days": days}

    # 用千问简单总结
    from nailflow.models import create_chat_model
    from langchain_core.messages import HumanMessage, SystemMessage

    prompt = f"""你是美甲运营分析专家。基于以下数据生成一段 200 字以内的运营速报：

近 {days} 天信号总数：{len(signal_list)} 条
热门款式 TOP5：{top5_list}
方案状态分布：{proposal_stats}

请用中文给出：1) 趋势总结 2) 热门款式 3) 运营建议"""
    try:
        model = create_chat_model(name="qwen3.7-max", thinking_enabled=False, attach_tracing=False)
        resp = await model.ainvoke([
            SystemMessage(content="你是美甲运营分析助手，回复简洁专业。"),
            HumanMessage(content=prompt),
        ])
        content = resp.content
        if isinstance(content, list):
            content = "".join(d.get("text", "") if isinstance(d, dict) else str(d) for d in content)
        return {"analysis": str(content)[:1000], "days": days, "data": {"signals": len(signal_list), "top5": top5_list, "proposals": proposal_stats}}
    except Exception:
        return {"analysis": f"近 {days} 天共有 {len(signal_list)} 条运营信号，热门款式：{', '.join(s['style_name'] or s['style_id'] for s in top5_list[:3])}。", "days": days}
