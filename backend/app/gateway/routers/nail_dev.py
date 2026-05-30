# backend/app/gateway/routers/nail_dev.py
"""开发工具：直接调用单个 nail tool 进行测试。"""
import json
import logging
import traceback

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.gateway.authz import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nail/dev", tags=["nail-dev"])


class ToolTestRequest(BaseModel):
    tool_name: str
    args: dict = {}


# 工具名 → Python 导入路径映射
_TOOL_REGISTRY = {
    "unified_tryon_tool":      "deerflow.tools.nail.unified_tryon:unified_tryon_tool",
    "hand_detect_tool":        "deerflow.tools.nail.hand_detect:hand_detect_tool",
    "nail_mask_tool":          "deerflow.tools.nail.nail_mask:nail_mask_tool",
    "style_understanding_tool":"deerflow.tools.nail.style_understanding:style_understanding_tool",
    "prompt_builder_tool":     "deerflow.tools.nail.prompt_builder:prompt_builder_tool",
    "image_generation_tool":   "deerflow.tools.nail.image_generation:image_generation_tool",
    "quality_check_tool":      "deerflow.tools.nail.quality_check:quality_check_tool",
    "trend_query_tool":        "deerflow.tools.nail.trend_query:trend_query_tool",
    "trend_discovery_tool":    "deerflow.tools.nail.trend_discovery:trend_discovery_tool",
    "ops_analysis_tool":       "deerflow.tools.nail.ops_analysis:ops_analysis_tool",
    "customer_service_tool":   "deerflow.tools.nail.customer_service:customer_service_tool",
    "action_proposal_tool":    "deerflow.tools.nail.action_proposal:action_proposal_tool",
    "evaluation_tool":         "deerflow.tools.nail.evaluation:evaluation_tool",
    "preference_rag_tool":     "deerflow.tools.nail.preference_rag:preference_rag_tool",
    "nail_style_recommend_tool":"deerflow.tools.nail.nail_style_recommend:nail_style_recommend_tool",
    "nail_run_query_tool":     "deerflow.tools.nail.nail_run_query:nail_run_query_tool",
    "user_pref_analytics_tool":"deerflow.tools.nail.user_pref_analytics:user_pref_analytics_tool",
}

_TOOL_DESCRIPTIONS = {
    "hand_detect_tool": {
        "description": "检测手图中的手部姿态，返回指尖坐标和甲床 bbox",
        "params": {"image_path": "手图文件路径（本地路径或虚拟路径）"},
    },
    "nail_mask_tool": {
        "description": "根据 bbox 生成甲面 mask PNG",
        "params": {"image_path": "手图路径", "nail_bboxes_json": "hand_detect_tool 输出的 JSON"},
    },
    "style_understanding_tool": {
        "description": "用 Vision LLM 解析款式图颜色/纹理/甲型",
        "params": {"style_image_path": "款式图文件路径", "user_description": "（可选）补充文字描述"},
    },
    "prompt_builder_tool": {
        "description": "根据款式分析构建生图 prompt",
        "params": {"style_analysis_json": "style_understanding_tool 输出的 JSON", "user_request": "（可选）用户要求"},
    },
    "image_generation_tool": {
        "description": "调用生图 API 在甲面 mask 区域生成试戴效果图",
        "params": {"hand_image_path": "手图路径", "mask_path": "mask 文件路径", "prompt_json": "prompt_builder_tool 输出的 JSON"},
    },
    "quality_check_tool": {
        "description": "双图对比评估试戴质量",
        "params": {"original_hand_path": "原手图路径", "result_path": "试戴结果图路径", "style_summary_zh": "（可选）款式摘要"},
    },
}


@router.get("/tools")
async def list_testable_tools():
    """列出所有可测试的工具及其参数说明。"""
    return {
        "tools": [
            {
                "name": name,
                "path": path,
                "description": _TOOL_DESCRIPTIONS.get(name, {}).get("description", ""),
                "params": _TOOL_DESCRIPTIONS.get(name, {}).get("params", {}),
            }
            for name, path in _TOOL_REGISTRY.items()
        ]
    }


@router.post("/test-tool")
@require_auth
async def test_tool(body: ToolTestRequest, request: Request):
    """直接调用指定工具并返回结果（开发测试用）。"""
    user = request.state.user
    nail_role = getattr(user, "nail_role", "user")
    if nail_role not in ("ops", "dev"):
        raise HTTPException(403, "仅 ops/dev 角色可测试工具")

    tool_path = _TOOL_REGISTRY.get(body.tool_name)
    if not tool_path:
        raise HTTPException(404, f"未知工具: {body.tool_name}")

    try:
        from deerflow.reflection import resolve_variable
        from langchain.tools import BaseTool
        tool = resolve_variable(tool_path, BaseTool)
    except Exception as e:
        raise HTTPException(500, f"加载工具失败: {e}")

    try:
        result = tool.invoke(body.args)
        return {
            "tool_name": body.tool_name,
            "success": True,
            "result": result,
        }
    except Exception as e:
        return {
            "tool_name": body.tool_name,
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()[:2000],
        }
