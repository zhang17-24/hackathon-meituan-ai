# NailFlow 实现计划（基于 DeerFlow）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 DeerFlow 基础上扩展，3 天内交付 NailFlow——含三端鉴权（user/ops/dev）、视觉试戴链路、运营 Agent、开发评估面板的完整 AI 美甲系统。

**Architecture:** Fork DeerFlow，在其 `config.yaml` 中注册 nail 工具组（`nail`/`nail_ops`/`nail_dev`），通过向 LangGraph `configurable` 注入 `nail_role` 实现角色级工具过滤；User 模型新增 `nail_role` 字段，前端按角色路由守卫；所有新工具均为标准 LangChain `BaseTool`，零侵入 DeerFlow 核心。

**Tech Stack:** DeerFlow (LangGraph + FastAPI + Next.js) / Python 3.12 / MediaPipe / ChromaDB / SQLite / APScheduler / ByteDance 生图 API

---

## 文件变更地图

**项目根：** `hackathon-meituan-ai/`（下文称 `ROOT`）

| 操作 | 路径 | 说明 |
|------|------|------|
| 复制 | `ROOT/backend/` | DeerFlow backend 完整复制 |
| 复制 | `ROOT/frontend/` | DeerFlow frontend 完整复制 |
| 复制 | `ROOT/config.yaml` | DeerFlow config.example.yaml 改名 |
| 修改 | `backend/app/gateway/auth/models.py` | 新增 `nail_role` 字段 |
| 修改 | `backend/app/gateway/authz.py` | 角色权限过滤 |
| 修改 | `backend/packages/harness/deerflow/agents/lead_agent/agent.py` | 注入 nail_role → 工具过滤 |
| 修改 | `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` | 美甲专属 system prompt |
| 修改 | `config.yaml` | 注册 nail 工具组 |
| 新建 | `backend/packages/harness/deerflow/tools/nail/` | 所有 nail 工具 |
| 新建 | `backend/packages/harness/deerflow/persistence/nail_tables.py` | nail DB 表 |
| 新建 | `backend/app/gateway/routers/nail_ops.py` | ActionProposal 确认接口 |
| 新建 | `backend/nail_scheduler.py` | APScheduler 运营定时任务 |
| 修改 | `frontend/src/app/` | 三端路由 + 角色守卫 |
| 新建 | `frontend/src/components/tryon-canvas/` | 试戴画布组件 |
| 新建 | `frontend/src/components/ops-dashboard/` | 运营看板组件 |

---

## Phase 0：Fork DeerFlow + 环境初始化

### Task 0: 复制 DeerFlow，初始化项目

**Files:**
- Create: `ROOT/backend/` (from research/sources/deer-flow-main/backend)
- Create: `ROOT/frontend/` (from research/sources/deer-flow-main/frontend)
- Create: `ROOT/config.yaml`
- Create: `ROOT/.env`

- [ ] **Step 1: 复制 DeerFlow 代码**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
SRC=research/sources/deer-flow-main

cp -r $SRC/backend ./backend
cp -r $SRC/frontend ./frontend
cp $SRC/config.example.yaml ./config.yaml
cp $SRC/.env.example ./.env
```

- [ ] **Step 2: 配置 .env（填入真实 Key）**

编辑 `ROOT/.env`，添加：

```bash
# LLM（字节系 / OpenAI 兼容接口）
OPENAI_API_KEY=your_llm_api_key
OPENAI_BASE_URL=https://your-bytedance-llm-endpoint/v1

# 字节生图 API
NAIL_IMAGE_API_KEY=your_bytedance_image_api_key
NAIL_IMAGE_API_URL=https://your-bytedance-image-api/inpaint

# JWT
JWT_SECRET_KEY=nailflow-hackathon-secret-2026

# ChromaDB（进程内，无需额外配置）
CHROMA_PERSIST_DIR=./data/chroma
```

- [ ] **Step 3: 安装后端依赖**

```bash
cd backend
pip install uv
uv sync
uv pip install mediapipe chromadb apscheduler pillow httpx
```

- [ ] **Step 4: 安装前端依赖**

```bash
cd ../frontend
pnpm install
```

- [ ] **Step 5: 验证 DeerFlow 原版可以启动**

```bash
# 终端 1
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload

# 终端 2
cd frontend && pnpm dev
```

浏览器打开 `http://localhost:3000`，确认 DeerFlow 原版界面正常。

- [ ] **Step 6: 建 data 目录**

```bash
mkdir -p data/{chroma,uploads,results,mock}
```

- [ ] **Step 7: Commit 基线**

```bash
git add backend frontend config.yaml .env.example
git commit -m "chore: fork DeerFlow as NailFlow base"
```

---

## Phase 1（Day 1）：视觉工具链 + TryOnAgent

### Task 1: 新增 nail_role 到 User 模型

**Files:**
- Modify: `backend/app/gateway/auth/models.py`

- [ ] **Step 1: 修改 User 模型**

找到 `backend/app/gateway/auth/models.py`，在 `system_role` 字段下方添加 `nail_role`：

```python
# 原有
system_role: Literal["admin", "user"] = Field(default="user")

# 新增（在 system_role 下方）
nail_role: Literal["user", "ops", "dev"] = Field(
    default="user",
    description="NailFlow role: user=trial, ops=operator, dev=developer"
)
```

同样在 `UserResponse` 中暴露该字段：

```python
class UserResponse(BaseModel):
    id: str
    email: str
    system_role: Literal["admin", "user"]
    nail_role: Literal["user", "ops", "dev"] = "user"   # 新增
    needs_setup: bool = False
```

- [ ] **Step 2: 在 SQLite 用户表添加 nail_role 列**

找到 `backend/app/gateway/auth/repositories/sqlite.py`，搜索 CREATE TABLE 语句，添加列：

```sql
-- 原有
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    system_role TEXT DEFAULT 'user',
    ...
)

-- 新增列（在 system_role 后）
nail_role TEXT DEFAULT 'user',
```

如果表已存在，添加迁移（在文件底部 init 函数中）：

```python
# 在数据库初始化函数中添加
async def _migrate_add_nail_role(self) -> None:
    try:
        await self._db.execute(
            "ALTER TABLE users ADD COLUMN nail_role TEXT DEFAULT 'user'"
        )
        await self._db.commit()
    except Exception:
        pass  # 列已存在则忽略
```

- [ ] **Step 3: 验证 User 模型可以序列化**

```bash
cd backend
python -c "from app.gateway.auth.models import User; u = User(email='test@test.com'); print(u.nail_role)"
```

预期输出：`user`

- [ ] **Step 4: 创建 3 个测试账号（nail_role 各不同）**

在 `backend/scripts/` 下新建 `seed_nail_users.py`：

```python
"""创建 NailFlow 三端测试账号"""
import asyncio
import sys
sys.path.insert(0, ".")

from app.gateway.auth.password import hash_password
from app.gateway.auth.repositories.sqlite import SqliteUserRepository

USERS = [
    {"email": "user@nailflow.dev", "password": "nail123", "nail_role": "user"},
    {"email": "ops@nailflow.dev",  "password": "nail123", "nail_role": "ops"},
    {"email": "dev@nailflow.dev",  "password": "nail123", "nail_role": "dev"},
]

async def main():
    repo = SqliteUserRepository()
    await repo.initialize()
    for u in USERS:
        existing = await repo.find_by_email(u["email"])
        if not existing:
            from app.gateway.auth.models import User
            user = User(email=u["email"], password_hash=hash_password(u["password"]), nail_role=u["nail_role"])
            await repo.create(user)
            print(f"Created: {u['email']} (nail_role={u['nail_role']})")
        else:
            print(f"Already exists: {u['email']}")

asyncio.run(main())
```

```bash
cd backend && uv run python scripts/seed_nail_users.py
```

预期输出：
```
Created: user@nailflow.dev (nail_role=user)
Created: ops@nailflow.dev (nail_role=ops)
Created: dev@nailflow.dev (nail_role=dev)
```

- [ ] **Step 5: 在 JWT payload 中注入 nail_role**

找到 `backend/app/gateway/auth/jwt.py`，在创建 JWT payload 的函数中（通常叫 `create_access_token` 或类似），在写入 `sub`/`email` 之后加：

```python
# 找到类似这段代码：
payload = {
    "sub": str(user.id),
    "email": user.email,
    "system_role": user.system_role,
    # 新增：
    "nail_role": getattr(user, "nail_role", "user"),
}
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/gateway/auth/models.py backend/app/gateway/auth/repositories/sqlite.py backend/app/gateway/auth/jwt.py backend/scripts/seed_nail_users.py
git commit -m "feat(auth): add nail_role to User model, JWT payload, seed test accounts"
```

---

### Task 2: nail 工具包目录结构

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/__init__.py`
- Create: `backend/packages/harness/deerflow/tools/nail/base.py`

- [ ] **Step 1: 创建包目录**

```bash
mkdir -p backend/packages/harness/deerflow/tools/nail
```

- [ ] **Step 2: 创建 `__init__.py`**

```python
# backend/packages/harness/deerflow/tools/nail/__init__.py
"""NailFlow tool package — nail art try-on and ops tools."""
```

- [ ] **Step 3: 创建 `base.py`（公共工具基类和 DB helper）**

```python
# backend/packages/harness/deerflow/tools/nail/base.py
"""Shared utilities for NailFlow tools."""
import os
import sqlite3
from pathlib import Path

UPLOADS_DIR = Path(os.getenv("NAIL_UPLOADS_DIR", "data/uploads"))
RESULTS_DIR = Path(os.getenv("NAIL_RESULTS_DIR", "data/results"))
DB_PATH = Path(os.getenv("NAIL_DB_PATH", "data/nailflow.db"))

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with row_factory set."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_nail_tables() -> None:
    """Create NailFlow tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS nail_runs (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            nail_role TEXT,
            intent TEXT,
            status TEXT DEFAULT 'running',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS nail_assets (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            asset_type TEXT,
            file_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ops_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            style_id TEXT,
            signal_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS action_proposals (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            title TEXT,
            content TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            confirmed_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS evaluation_results (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            total_score INTEGER,
            rubric_scores TEXT,
            blocking_issues TEXT,
            next_dev_tasks TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ops_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 4: 验证表创建**

```bash
cd backend
python -c "from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables(); print('OK')"
```

预期输出：`OK`

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/
git commit -m "feat(nail): create nail tools package and DB schema"
```

---

### Task 3: HandDetectTool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/hand_detect.py`

- [ ] **Step 1: 实现 HandDetectTool**

```python
# backend/packages/harness/deerflow/tools/nail/hand_detect.py
"""检测手部姿态，返回指尖坐标和甲床 bounding box。"""
import base64
import json
import logging
from pathlib import Path

import mediapipe as mp
import numpy as np
from langchain.tools import tool
from PIL import Image
import io

logger = logging.getLogger(__name__)

mp_hands = mp.solutions.hands


def _decode_image(image_path_or_b64: str) -> np.ndarray:
    """接受文件路径或 base64 字符串，返回 numpy RGB 数组。"""
    p = Path(image_path_or_b64)
    if p.exists():
        img = Image.open(p).convert("RGB")
    else:
        data = base64.b64decode(image_path_or_b64)
        img = Image.open(io.BytesIO(data)).convert("RGB")
    return np.array(img)


@tool
def hand_detect_tool(image_path: str) -> str:
    """检测手部姿态，返回指尖坐标和甲床候选 bounding box。

    Args:
        image_path: 本地文件路径或 base64 编码字符串。

    Returns:
        JSON 字符串，包含 detected(bool)、landmarks、nail_bboxes、image_size。
    """
    try:
        img_array = _decode_image(image_path)
        h, w = img_array.shape[:2]

        with mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            min_detection_confidence=0.5,
        ) as hands:
            results = hands.process(img_array)

        if not results.multi_hand_landmarks:
            return json.dumps({
                "detected": False,
                "message": "未检测到手部，请正面拍摄手背，确保光线充足",
                "image_size": {"width": w, "height": h},
            })

        # 提取指尖 (4,8,12,16,20) 和甲床区域 bbox
        FINGERTIP_IDS = [4, 8, 12, 16, 20]
        KNUCKLE_IDS   = [3, 7, 11, 15, 19]

        nail_bboxes = []
        all_landmarks = []

        for hand_lm in results.multi_hand_landmarks:
            lms = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lm.landmark]
            all_landmarks.extend(lms)

            for tip_id, knuckle_id in zip(FINGERTIP_IDS, KNUCKLE_IDS):
                tx, ty = lms[tip_id]
                kx, ky = lms[knuckle_id]
                nail_w = max(abs(tx - kx), 20)
                nail_h = max(abs(ty - ky) // 2, 15)
                x1 = max(tx - nail_w // 2, 0)
                y1 = max(min(ty, ky) - nail_h // 4, 0)
                x2 = min(tx + nail_w // 2, w)
                y2 = min(max(ty, ky) + nail_h // 4, h)
                nail_bboxes.append({
                    "finger_id": tip_id,
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "center_x": tx, "center_y": ty,
                })

        return json.dumps({
            "detected": True,
            "landmarks_count": len(all_landmarks),
            "nail_bboxes": nail_bboxes,
            "image_size": {"width": w, "height": h},
        })

    except Exception as e:
        logger.error(f"HandDetect error: {e}")
        return json.dumps({
            "detected": False,
            "message": f"手部检测失败: {e}，请检查图片格式",
        })
```

- [ ] **Step 2: 手动测试 HandDetectTool**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.hand_detect import hand_detect_tool
# 用项目里的手图测试
result = hand_detect_tool.run('../微信图片_20260523173957_29_463.jpg')
import json; d = json.loads(result); print('detected:', d['detected'])
if d['detected']: print('nail_bboxes count:', len(d['nail_bboxes']))
"
```

预期：`detected: True`，`nail_bboxes count: 10`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/hand_detect.py
git commit -m "feat(nail): implement HandDetectTool with MediaPipe"
```

---

### Task 4: NailMaskTool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/nail_mask.py`

- [ ] **Step 1: 实现 NailMaskTool（bbox 生成 mask）**

```python
# backend/packages/harness/deerflow/tools/nail/nail_mask.py
"""根据甲床 bbox 生成 PNG mask 文件。白色=甲面，黑色=其余。"""
import json
import uuid
from pathlib import Path

import numpy as np
from langchain.tools import tool
from PIL import Image, ImageDraw

from .base import RESULTS_DIR


@tool
def nail_mask_tool(image_path: str, nail_bboxes_json: str) -> str:
    """根据 HandDetectTool 返回的 nail_bboxes 生成甲面 mask PNG。

    Args:
        image_path: 原始手图路径。
        nail_bboxes_json: hand_detect_tool 返回的 nail_bboxes JSON 字符串
                          或 {"nail_bboxes": [...], "image_size": {...}} JSON。

    Returns:
        JSON 包含 mask_path（mask 文件本地路径）和 nail_count。
    """
    try:
        data = json.loads(nail_bboxes_json)
        # 兼容直接传 detect 结果或只传 bboxes
        bboxes = data.get("nail_bboxes", data) if isinstance(data, dict) else data
        img_size = data.get("image_size") if isinstance(data, dict) else None

        # 确定图像尺寸
        if img_size:
            w, h = img_size["width"], img_size["height"]
        else:
            with Image.open(image_path) as img:
                w, h = img.size

        # 创建黑色 mask，白色区域=甲面
        mask = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(mask)

        if isinstance(bboxes, list):
            for bbox in bboxes:
                # 扩展 bbox 略微放大甲面区域
                pad = 4
                x1 = max(bbox["x1"] - pad, 0)
                y1 = max(bbox["y1"] - pad, 0)
                x2 = min(bbox["x2"] + pad, w)
                y2 = min(bbox["y2"] + pad, h)
                draw.ellipse([x1, y1, x2, y2], fill=(255, 255, 255))

        mask_path = RESULTS_DIR / f"mask_{uuid.uuid4().hex[:8]}.png"
        mask.save(str(mask_path))

        return json.dumps({
            "mask_path": str(mask_path),
            "nail_count": len(bboxes) if isinstance(bboxes, list) else 0,
            "image_size": {"width": w, "height": h},
        })

    except Exception as e:
        return json.dumps({"error": f"Mask 生成失败: {e}"})
```

- [ ] **Step 2: 测试 NailMaskTool**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.hand_detect import hand_detect_tool
from packages.harness.deerflow.tools.nail.nail_mask import nail_mask_tool
detect = hand_detect_tool.run('../微信图片_20260523173957_29_463.jpg')
mask = nail_mask_tool.run({'image_path': '../微信图片_20260523173957_29_463.jpg', 'nail_bboxes_json': detect})
import json; d = json.loads(mask); print('mask_path:', d.get('mask_path'), 'nails:', d.get('nail_count'))
"
```

预期：输出 mask 文件路径，`nails: 10`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/nail_mask.py
git commit -m "feat(nail): implement NailMaskTool using bbox ellipse"
```

---

### Task 5: StyleUnderstandingTool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/style_understanding.py`

- [ ] **Step 1: 实现 StyleUnderstandingTool**

```python
# backend/packages/harness/deerflow/tools/nail/style_understanding.py
"""用 LLM Vision 解析款式图，提取颜色/纹理/甲型/饰品标签。"""
import json
import logging
import base64
from pathlib import Path

from langchain.tools import tool
from deerflow.models import create_chat_model
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


def _encode_image_b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@tool
def style_understanding_tool(style_image_path: str, user_description: str = "") -> str:
    """解析美甲款式图，提取风格标签。

    Args:
        style_image_path: 款式参考图的本地路径。
        user_description: 用户对想要款式的文字描述（可选）。

    Returns:
        JSON 包含 colors, texture, nail_shape, decorations, style_tags, style_description_en。
    """
    try:
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)

        img_b64 = _encode_image_b64(style_image_path)

        prompt = f"""你是美甲风格分析师。请分析这张美甲款式图，提取以下信息并以 JSON 格式返回：

{{
  "colors": ["主色1", "主色2"],      // 甲面主要颜色，英文颜色名
  "texture": "glitter|matte|glossy|gradient|marble|solid",
  "nail_shape": "round|square|almond|coffin|stiletto|oval",
  "decorations": ["rhinestone", "foil", "3d_art"] // 或空数组
  "style_tags": ["cat_eye", "french_tip", "ombre", "solid", "nail_art"],
  "style_description_en": "一句话英文款式描述，用于生图提示词"
}}

用户补充描述：{user_description or "无"}

只返回 JSON，不要其他内容。"""

        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": prompt},
        ])

        response = model.invoke([msg])
        raw = response.content.strip()

        # 清理可能的 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"StyleUnderstanding error: {e}")
        # 降级返回基础描述
        return json.dumps({
            "colors": ["pink"],
            "texture": "glossy",
            "nail_shape": "round",
            "decorations": [],
            "style_tags": ["solid"],
            "style_description_en": user_description or "glossy pink nail polish, solid color",
        })
```

- [ ] **Step 2: 测试（需要 LLM 服务运行）**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.style_understanding import style_understanding_tool
# 用美甲图片目录里的图
import os
pics = os.listdir('../美甲图片/')
if pics:
    result = style_understanding_tool.run({'style_image_path': f'../美甲图片/{pics[0]}'})
    import json; print(json.loads(result))
"
```

预期：输出解析后的 JSON 对象，含 `colors`, `style_description_en` 等字段

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/style_understanding.py
git commit -m "feat(nail): implement StyleUnderstandingTool with LLM Vision"
```

---

### Task 6: PromptBuilderTool（关键）

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/prompt_builder.py`

- [ ] **Step 1: 实现 PromptBuilderTool**

```python
# backend/packages/harness/deerflow/tools/nail/prompt_builder.py
"""根据手图描述 + 款式标签 + 用户需求，生成生图模型的 positive/negative prompt。"""
import json
import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)

# 正向 prompt 模板
_POS_TEMPLATE = """\
Edit only the fingernail regions inside the provided nail mask. \
Preserve the original hand skin tone, wrinkles, joints, shadows, \
background, camera angle, and lighting. \
Apply the nail art style: {style_description}. \
Colors: {colors}. Texture: {texture}. Shape: {nail_shape}. \
{decoration_str}\
The manicure should fit the natural nail shape, with clean cuticle edges, \
realistic gloss, and no changes outside the nails. \
Photorealistic commercial beauty retouching, natural hand photo, 4k quality.\
"""

# 反向 prompt（通用，不需要参数化）
_NEG_PROMPT = (
    "do not redraw the hand, do not change skin tone, do not alter fingers, "
    "no extra fingers, no missing fingers, no deformed nails, no floating decorations, "
    "no blurry cuticle, no color bleeding outside nail mask, no background change, "
    "no plastic skin, no overexposure, no cartoon, no painting style"
)


@tool
def prompt_builder_tool(style_analysis_json: str, user_request: str = "") -> str:
    """根据款式分析和用户需求，构建生图正向/反向 prompt。

    Args:
        style_analysis_json: style_understanding_tool 的输出 JSON 字符串。
        user_request: 用户的额外文字要求（如"我想要更亮一点"）。

    Returns:
        JSON 包含 positive_prompt, negative_prompt, style_summary_zh（中文摘要）。
    """
    try:
        style = json.loads(style_analysis_json)

        colors = ", ".join(style.get("colors", ["neutral"]))
        texture = style.get("texture", "glossy")
        nail_shape = style.get("nail_shape", "round")
        decorations = style.get("decorations", [])
        style_desc = style.get("style_description_en", "nail polish")

        decoration_str = ""
        if decorations:
            decoration_str = f"Nail decorations: {', '.join(decorations)}. "

        # 用户请求修正
        user_mod = ""
        if user_request:
            user_mod = f" User request: {user_request}."

        positive = _POS_TEMPLATE.format(
            style_description=style_desc + user_mod,
            colors=colors,
            texture=texture,
            nail_shape=nail_shape,
            decoration_str=decoration_str,
        )

        # 中文摘要（给用户展示）
        style_tags = style.get("style_tags", [])
        summary_zh = (
            f"款式：{style_desc}，"
            f"颜色：{colors}，"
            f"质感：{texture}，"
            f"甲型：{nail_shape}"
        )
        if style_tags:
            summary_zh += f"，风格标签：{'/'.join(style_tags)}"

        return json.dumps({
            "positive_prompt": positive,
            "negative_prompt": _NEG_PROMPT,
            "style_summary_zh": summary_zh,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"PromptBuilder error: {e}")
        # 降级
        return json.dumps({
            "positive_prompt": (
                f"Edit only the fingernail regions inside the mask. "
                f"Apply beautiful nail art: {user_request or 'natural pink glossy nails'}. "
                "Preserve original hand. Photorealistic."
            ),
            "negative_prompt": _NEG_PROMPT,
            "style_summary_zh": user_request or "自然粉色光泽美甲",
        }, ensure_ascii=False)
```

- [ ] **Step 2: 测试 PromptBuilderTool**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.prompt_builder import prompt_builder_tool
import json
style = json.dumps({'colors': ['rose', 'gold'], 'texture': 'glitter', 'nail_shape': 'almond', 'decorations': ['rhinestone'], 'style_tags': ['nail_art'], 'style_description_en': 'rose gold glitter nail art with rhinestone'})
result = prompt_builder_tool.run({'style_analysis_json': style, 'user_request': '我想要暗一点的玫瑰金'})
d = json.loads(result)
print('POS:', d['positive_prompt'][:100])
print('NEG:', d['negative_prompt'][:60])
print('ZH:', d['style_summary_zh'])
"
```

预期：输出正向/反向 prompt 和中文摘要

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/prompt_builder.py
git commit -m "feat(nail): implement PromptBuilderTool for image generation"
```

---

### Task 7: ImageGenerationTool（字节生图 API）

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/image_generation.py`

- [ ] **Step 1: 实现 ImageGenerationTool**

```python
# backend/packages/harness/deerflow/tools/nail/image_generation.py
"""调用字节生图 API，进行 inpaint 试戴生成。"""
import base64
import json
import logging
import os
import uuid
from pathlib import Path

import httpx
from langchain.tools import tool

from .base import RESULTS_DIR

logger = logging.getLogger(__name__)

NAIL_IMAGE_API_KEY = os.getenv("NAIL_IMAGE_API_KEY", "")
NAIL_IMAGE_API_URL = os.getenv("NAIL_IMAGE_API_URL", "")
API_TIMEOUT = int(os.getenv("NAIL_IMAGE_API_TIMEOUT", "60"))


def _load_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@tool
def image_generation_tool(
    hand_image_path: str,
    mask_path: str,
    prompt_json: str,
) -> str:
    """调用字节生图 inpaint API，在甲面 mask 区域生成试戴效果图。

    Args:
        hand_image_path: 原始手图路径。
        mask_path: 甲面 mask PNG 路径（白色=编辑区域）。
        prompt_json: prompt_builder_tool 返回的 JSON 字符串。

    Returns:
        JSON 包含 result_path（生成图本地路径）或 error。
    """
    try:
        prompts = json.loads(prompt_json)
        positive = prompts["positive_prompt"]
        negative = prompts["negative_prompt"]

        hand_b64 = _load_image_b64(hand_image_path)
        mask_b64 = _load_image_b64(mask_path)

        # 字节生图 API 请求体（根据实际 API 文档调整字段名）
        payload = {
            "model": "seedream-inpaint",          # 按实际模型名调整
            "image": hand_b64,
            "mask": mask_b64,
            "prompt": positive,
            "negative_prompt": negative,
            "strength": 0.85,                      # inpaint 强度
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "seed": 42,
        }

        headers = {
            "Authorization": f"Bearer {NAIL_IMAGE_API_KEY}",
            "Content-Type": "application/json",
        }

        if not NAIL_IMAGE_API_KEY or not NAIL_IMAGE_API_URL:
            # 本地 mock：返回原图作为结果（演示用）
            logger.warning("Image API not configured, returning original image as mock result")
            result_path = RESULTS_DIR / f"result_{uuid.uuid4().hex[:8]}.jpg"
            import shutil
            shutil.copy(hand_image_path, str(result_path))
            return json.dumps({
                "result_path": str(result_path),
                "is_mock": True,
                "message": "使用原图作为 mock 结果（未配置生图 API）",
            })

        with httpx.Client(timeout=API_TIMEOUT) as client:
            resp = client.post(NAIL_IMAGE_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 解析响应（根据实际 API 响应格式调整）
        img_b64 = data.get("image") or data.get("data", {}).get("image", "")
        if not img_b64:
            return json.dumps({"error": f"API 未返回图像，响应: {str(data)[:200]}"})

        result_path = RESULTS_DIR / f"result_{uuid.uuid4().hex[:8]}.jpg"
        with open(str(result_path), "wb") as f:
            f.write(base64.b64decode(img_b64))

        return json.dumps({
            "result_path": str(result_path),
            "is_mock": False,
        })

    except httpx.TimeoutException:
        return json.dumps({
            "error": "生图 API 超时（>60s），请重试或使用 mock 模式",
            "retry_suggestion": "降低 strength 参数或减少推理步数",
        })
    except Exception as e:
        logger.error(f"ImageGeneration error: {e}")
        return json.dumps({"error": f"生图失败: {e}"})
```

- [ ] **Step 2: 测试 mock 模式（API 未配置时）**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.image_generation import image_generation_tool
import json
result = image_generation_tool.run({
  'hand_image_path': '../微信图片_20260523173957_29_463.jpg',
  'mask_path': 'data/results/mask_test.png',
  'prompt_json': json.dumps({'positive_prompt': 'test', 'negative_prompt': 'test'})
})
d = json.loads(result)
print('is_mock:', d.get('is_mock'), 'result_path:', d.get('result_path'))
"
```

预期：`is_mock: True`，`result_path: data/results/result_*.jpg`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/image_generation.py
git commit -m "feat(nail): implement ImageGenerationTool with ByteDance inpaint API"
```

---

### Task 8: TryOnQualityTool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/quality_check.py`

- [ ] **Step 1: 实现 TryOnQualityTool**

```python
# backend/packages/harness/deerflow/tools/nail/quality_check.py
"""评估试戴图质量：甲面边界、肤色漂移、款式相似度。"""
import base64
import json
import logging

from langchain.tools import tool
from langchain_core.messages import HumanMessage
from deerflow.models import create_chat_model

logger = logging.getLogger(__name__)


@tool
def quality_check_tool(
    original_hand_path: str,
    result_path: str,
    style_summary_zh: str = "",
) -> str:
    """评估 AI 试戴效果图质量，生成分数和中文解释。

    Args:
        original_hand_path: 原始手图路径。
        result_path: 生成的试戴结果图路径。
        style_summary_zh: 款式中文描述（来自 prompt_builder_tool）。

    Returns:
        JSON 包含 scores（各维度分数）、overall（总分）、explanation_zh（中文解释）、fit_comment。
    """
    try:
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)

        def enc(p: str) -> str:
            with open(p, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        orig_b64 = enc(original_hand_path)
        result_b64 = enc(result_path)

        prompt = f"""你是美甲试戴质量评估专家。请对比原图和生成的试戴图，按以下维度评分（0-10分）：

1. boundary_score: 甲面边界是否干净，有无溢色到皮肤
2. skin_tone_score: 肤色是否保持一致，有无漂移
3. lighting_score: 光照是否与原图一致
4. style_match_score: 试戴款式是否与目标款式相符
5. natural_score: 整体是否自然真实，商业可用

目标款式：{style_summary_zh or "未指定"}

以 JSON 格式返回，加上中文解释：
{{
  "scores": {{
    "boundary_score": 8,
    "skin_tone_score": 9,
    "lighting_score": 8,
    "style_match_score": 7,
    "natural_score": 8
  }},
  "overall": 8,
  "fit_comment": "该款式很适合您的手型",
  "risk_comment": "若有饰品可能偏大，建议到店确认",
  "adjustments": "可以调整颜色深浅",
  "explanation_zh": "我保留了原图的肤色、手纹和光照，只在甲面区域试戴了该款式。..."
}}

只返回 JSON。"""

        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{orig_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{result_b64}"}},
            {"type": "text", "text": prompt},
        ])

        response = model.invoke([msg])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return json.loads(raw) if raw.startswith("{") else json.dumps({
            "scores": {"boundary_score": 7, "skin_tone_score": 7, "lighting_score": 7, "style_match_score": 7, "natural_score": 7},
            "overall": 7,
            "fit_comment": "效果较好",
            "risk_comment": "建议到店确认",
            "adjustments": "可调整颜色",
            "explanation_zh": raw,
        })

    except Exception as e:
        logger.error(f"QualityCheck error: {e}")
        return json.dumps({
            "scores": {"boundary_score": 5, "skin_tone_score": 5, "lighting_score": 5, "style_match_score": 5, "natural_score": 5},
            "overall": 5,
            "fit_comment": "质量评估失败，请重试",
            "risk_comment": f"错误: {e}",
            "adjustments": "",
            "explanation_zh": "质量评估暂时不可用",
        })
```

- [ ] **Step 2: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/quality_check.py
git commit -m "feat(nail): implement TryOnQualityTool with dual-image LLM scoring"
```

---

### Task 9: 注册 nail 工具到 config.yaml + 注入 nail_role 到 lead_agent

**Files:**
- Modify: `ROOT/config.yaml`
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

- [ ] **Step 1: 在 config.yaml 添加 nail 工具组**

在 `ROOT/config.yaml` 的 `tools:` 列表末尾追加：

```yaml
  # ─── NailFlow Tools ───────────────────────────────────────
  # group: nail  (user + ops + dev 都可用)
  - name: hand_detect
    group: nail
    use: deerflow.tools.nail.hand_detect:hand_detect_tool

  - name: nail_mask
    group: nail
    use: deerflow.tools.nail.nail_mask:nail_mask_tool

  - name: style_understanding
    group: nail
    use: deerflow.tools.nail.style_understanding:style_understanding_tool

  - name: prompt_builder
    group: nail
    use: deerflow.tools.nail.prompt_builder:prompt_builder_tool

  - name: image_generation
    group: nail
    use: deerflow.tools.nail.image_generation:image_generation_tool

  - name: quality_check
    group: nail
    use: deerflow.tools.nail.quality_check:quality_check_tool

  - name: preference_rag
    group: nail
    use: deerflow.tools.nail.preference_rag:preference_rag_tool

  - name: trend_query
    group: nail
    use: deerflow.tools.nail.trend_query:trend_query_tool

  # group: nail_ops  (ops + dev 才可用)
  - name: ops_analysis
    group: nail_ops
    use: deerflow.tools.nail.ops_analysis:ops_analysis_tool

  - name: customer_service
    group: nail_ops
    use: deerflow.tools.nail.customer_service:customer_service_tool

  - name: action_proposal
    group: nail_ops
    use: deerflow.tools.nail.action_proposal:action_proposal_tool

  - name: trend_discovery
    group: nail_ops
    use: deerflow.tools.nail.trend_discovery:trend_discovery_tool

  # group: nail_dev  (dev only)
  - name: evaluation
    group: nail_dev
    use: deerflow.tools.nail.evaluation:evaluation_tool
```

- [ ] **Step 2: 在 lead_agent/agent.py 中注入 nail_role 并过滤工具**

找到 `_make_lead_agent` 函数（或等效函数），在读取 `cfg` 之后，在调用 `get_available_tools` 之前，添加：

```python
# 读取 nail_role，默认 user
nail_role = cfg.get("nail_role", "user")

# 按角色决定工具组
ROLE_TOOL_GROUPS = {
    "user": ["nail"],
    "ops":  ["nail", "nail_ops"],
    "dev":  ["nail", "nail_ops", "nail_dev"],
}
nail_groups = ROLE_TOOL_GROUPS.get(nail_role, ["nail"])

# 调用 get_available_tools 时传入 groups
tools = get_available_tools(
    groups=nail_groups,          # ← 只加这一行参数
    model_name=model_name,
    subagent_enabled=subagent_enabled,
    app_config=app_config,
)
```

- [ ] **Step 3: 在 lead_agent/prompt.py 添加美甲专属 system prompt**

找到 `apply_prompt_template` 函数，在其调用的模板中添加角色专属前缀。在文件末尾添加：

```python
# NailFlow 角色 system prompt 前缀
NAIL_ROLE_PROMPTS = {
    "user": """你是 NailFlow 的美甲 AI 顾问。你的目标是帮助用户进行 AI 美甲试戴、发现爆款款式、获取个性化推荐。
当用户上传手图和款式图时，依次调用：hand_detect → nail_mask → style_understanding → prompt_builder → image_generation → quality_check。
用中文回复，语气亲切、专业。""",

    "ops": """你是 NailFlow 的智能运营助手。除了能帮用户试戴，你还能分析运营数据、发现爆款趋势、生成营销方案、处理客服咨询。
所有会影响价格、库存、预约、退款的操作，必须先生成 ActionProposal 待人工确认后再执行。
数据来源必须在回复中标注（来自趋势分析 / 用户偏好 / 门店 SOP）。""",

    "dev": """你是 NailFlow 开发版 AI，拥有所有工具权限。除了用户和运营能力，你还能调用 evaluation_tool 对本次运行进行赛题评分。
每次试戴或运营分析结束后，主动调用 evaluation_tool 生成评分和改进建议。
详细展示每个工具的调用参数和返回结果，方便调试。""",
}
```

在 `apply_prompt_template` 中，从 config/state 读取 `nail_role`，在 system prompt 头部插入对应前缀：

```python
def apply_prompt_template(state, config, ...) -> str:
    nail_role = (config.get("configurable") or {}).get("nail_role", "user")
    role_prefix = NAIL_ROLE_PROMPTS.get(nail_role, NAIL_ROLE_PROMPTS["user"])
    # 在原有 system prompt 前加前缀
    original_prompt = ...  # 原有逻辑
    return role_prefix + "\n\n" + original_prompt
```

- [ ] **Step 4: 验证工具可以按组加载**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.tools import get_available_tools
tools_user = get_available_tools(groups=['nail'])
tools_ops  = get_available_tools(groups=['nail', 'nail_ops'])
tools_dev  = get_available_tools(groups=['nail', 'nail_ops', 'nail_dev'])
print('user tools:', [t.name for t in tools_user if 'nail' in t.name or t.name in ['hand_detect','prompt_builder','image_generation']])
print('ops extra:', [t.name for t in tools_ops if t.name not in [t2.name for t2 in tools_user]])
print('dev extra:', [t.name for t in tools_dev if t.name not in [t2.name for t2 in tools_ops]])
"
```

预期：
```
user tools: ['hand_detect', 'nail_mask', 'style_understanding', 'prompt_builder', 'image_generation', 'quality_check', 'preference_rag', 'trend_query']
ops extra: ['ops_analysis', 'customer_service', 'action_proposal', 'trend_discovery']
dev extra: ['evaluation']
```

- [ ] **Step 5: Commit**

```bash
git add config.yaml backend/packages/harness/deerflow/agents/lead_agent/
git commit -m "feat(nail): register nail tool groups in config.yaml, inject nail_role into lead_agent"
```

---

### Task 10: 端到端 TryOn 测试（Day 1 验收）

- [ ] **Step 1: 启动后端服务**

```bash
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload
```

- [ ] **Step 2: 用 user@nailflow.dev 登录获取 JWT**

```bash
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@nailflow.dev","password":"nail123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: $TOKEN"
```

- [ ] **Step 3: 创建 thread，发送试戴请求（含 nail_role）**

```bash
# 创建 thread
THREAD=$(curl -s -X POST http://localhost:8001/api/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | python -c "import sys,json; print(json.load(sys.stdin)['thread_id'])")

# 上传手图
HAND_URL=$(curl -s -X POST http://localhost:8001/api/uploads \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@../微信图片_20260523173957_29_463.jpg" \
  | python -c "import sys,json; print(json.load(sys.stdin)['url'])")

# 发送试戴消息（传入 nail_role=user）
curl -s -X POST http://localhost:8001/api/threads/$THREAD/runs/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {\"messages\": [{\"role\": \"user\", \"content\": \"请帮我试戴猫眼款式，手图：$HAND_URL\"}]},
    \"config\": {\"configurable\": {\"nail_role\": \"user\"}}
  }" --no-buffer | head -50
```

预期：看到 SSE 流式输出，包含 `hand_detect` → `nail_mask` → `style_understanding` → `prompt_builder` → `image_generation` 的调用过程

- [ ] **Step 4: Commit Day 1 基线**

```bash
git add -A && git commit -m "feat: Day 1 complete — TryOn vision pipeline end-to-end"
```

---

## Phase 2（Day 2）：用户链路完善 + 运营 Agent

### Task 11: PreferenceRAGTool（ChromaDB）

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/preference_rag.py`

- [ ] **Step 1: 实现 PreferenceRAGTool**

```python
# backend/packages/harness/deerflow/tools/nail/preference_rag.py
"""用户偏好 RAG：存储和检索用户喜好款式，返回个性化推荐。"""
import json
import logging
import os
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions
from langchain.tools import tool

logger = logging.getLogger(__name__)

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")

_client: Optional[chromadb.PersistentClient] = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        ef = embedding_functions.DefaultEmbeddingFunction()
        _collection = _client.get_or_create_collection(
            name="user_preferences",
            embedding_function=ef,
        )
    return _collection


@tool
def preference_rag_tool(action: str, user_id: str, data: str = "") -> str:
    """管理用户偏好 RAG：保存喜好或查询推荐。

    Args:
        action: "save"（保存偏好）或 "query"（查询推荐）。
        user_id: 当前用户 ID。
        data: action=save 时为款式描述 JSON；action=query 时为查询词。

    Returns:
        action=save: {"saved": true}
        action=query: {"recommendations": [...top5款式描述...]}
    """
    try:
        col = _get_collection()

        if action == "save":
            style_data = json.loads(data) if data.startswith("{") else {"description": data}
            doc_id = f"{user_id}_{len(col.get(where={'user_id': user_id}).get('ids', []))}"
            col.add(
                documents=[json.dumps(style_data, ensure_ascii=False)],
                metadatas=[{"user_id": user_id, **{k: str(v) for k, v in style_data.items() if k != "description"}}],
                ids=[doc_id],
            )
            return json.dumps({"saved": True, "doc_id": doc_id})

        elif action == "query":
            query_text = data or "美甲推荐"
            results = col.query(
                query_texts=[query_text],
                n_results=min(5, col.count()),
                where={"user_id": user_id} if col.count() > 0 else None,
            )
            docs = results.get("documents", [[]])[0]
            return json.dumps({
                "recommendations": docs,
                "count": len(docs),
                "message": "基于您的历史偏好推荐" if docs else "暂无偏好记录，推荐热门款式",
            }, ensure_ascii=False)

        else:
            return json.dumps({"error": f"unknown action: {action}"})

    except Exception as e:
        logger.error(f"PreferenceRAG error: {e}")
        return json.dumps({"error": str(e), "recommendations": []})
```

- [ ] **Step 2: 测试 PreferenceRAGTool**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.preference_rag import preference_rag_tool
import json
# 保存偏好
r1 = preference_rag_tool.run({'action': 'save', 'user_id': 'test_user', 'data': json.dumps({'colors': ['rose', 'pink'], 'texture': 'glitter', 'style_description_en': 'rose glitter nail art'})})
print('save:', r1)
# 查询推荐
r2 = preference_rag_tool.run({'action': 'query', 'user_id': 'test_user', 'data': '闪亮玫瑰色'})
print('query:', r2)
"
```

预期：save 返回 `{"saved": true}`，query 返回包含保存内容的推荐

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/preference_rag.py
git commit -m "feat(nail): implement PreferenceRAGTool with ChromaDB"
```

---

### Task 12: TrendQueryTool + mock 运营数据

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/trend_query.py`
- Create: `data/mock/ops_signals.sql`

- [ ] **Step 1: 创建 mock 运营数据**

新建 `data/mock/ops_signals.sql`：

```sql
INSERT INTO ops_signals (user_id, style_id, signal_type, created_at) VALUES
('u001', 'cat_eye_purple', 'save',  datetime('now', '-1 day')),
('u002', 'cat_eye_purple', 'save',  datetime('now', '-2 day')),
('u003', 'cat_eye_purple', 'order', datetime('now', '-1 day')),
('u001', 'french_tip_gold','save',  datetime('now', '-3 day')),
('u004', 'french_tip_gold','click', datetime('now', '-1 day')),
('u002', 'ombre_pink',     'save',  datetime('now', '-2 day')),
('u005', 'ombre_pink',     'order', datetime('now', '-4 day')),
('u003', 'ombre_pink',     'save',  datetime('now', '-1 day')),
('u001', 'nail_art_floral','click', datetime('now', '-5 day')),
('u006', 'solid_nude',     'order', datetime('now', '-1 day')),
('u007', 'solid_nude',     'order', datetime('now', '-2 day')),
('u008', 'solid_nude',     'save',  datetime('now', '-1 day'));
```

导入数据：

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.base import init_nail_tables, get_db, DB_PATH
init_nail_tables()
conn = get_db()
with open('../data/mock/ops_signals.sql') as f:
    conn.executescript(f.read())
conn.commit()
conn.close()
print('Mock data imported to', DB_PATH)
"
```

- [ ] **Step 2: 实现 TrendQueryTool**

```python
# backend/packages/harness/deerflow/tools/nail/trend_query.py
"""查询 7/30 天内的款式热度信号，返回爆款榜。"""
import json
from langchain.tools import tool
from .base import get_db


@tool
def trend_query_tool(days: int = 7, top_n: int = 10) -> str:
    """查询近期爆款美甲款式。

    Args:
        days: 统计天数，默认 7 天。
        top_n: 返回排名前 N 名，默认 10。

    Returns:
        JSON 包含 trending_styles 列表（style_id, total_signals, saves, orders, clicks）。
    """
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT
                style_id,
                COUNT(*) as total_signals,
                SUM(CASE WHEN signal_type='save'  THEN 1 ELSE 0 END) as saves,
                SUM(CASE WHEN signal_type='order' THEN 1 ELSE 0 END) as orders,
                SUM(CASE WHEN signal_type='click' THEN 1 ELSE 0 END) as clicks
            FROM ops_signals
            WHERE created_at >= datetime('now', ? )
            GROUP BY style_id
            ORDER BY total_signals DESC
            LIMIT ?
        """, (f"-{days} day", top_n)).fetchall()
        conn.close()

        trending = [dict(r) for r in rows]
        return json.dumps({
            "days": days,
            "trending_styles": trending,
            "total_styles_tracked": len(trending),
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "trending_styles": []})
```

- [ ] **Step 3: 测试 TrendQueryTool**

```bash
cd backend
python -c "
from packages.harness.deerflow.tools.nail.trend_query import trend_query_tool
import json
result = trend_query_tool.run({'days': 7, 'top_n': 5})
d = json.loads(result)
print('trending:', [s['style_id'] for s in d['trending_styles']])
"
```

预期：输出 `['solid_nude', 'cat_eye_purple', 'ombre_pink', ...]` 等按热度排序的款式列表

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/trend_query.py data/mock/
git commit -m "feat(nail): implement TrendQueryTool, add mock ops_signals data"
```

---

### Task 13: 运营端四个工具

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/trend_discovery.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_analysis.py`
- Create: `backend/packages/harness/deerflow/tools/nail/customer_service.py`
- Create: `backend/packages/harness/deerflow/tools/nail/action_proposal.py`

- [ ] **Step 1: 实现 TrendDiscoveryTool（OpenClaw 检索模式）**

```python
# backend/packages/harness/deerflow/tools/nail/trend_discovery.py
"""综合分析爆款趋势，输出可执行的趋势洞察报告。"""
import json
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from deerflow.models import create_chat_model
from .trend_query import trend_query_tool
from .base import get_db


@tool
def trend_discovery_tool(days: int = 7) -> str:
    """分析近期美甲趋势，返回爆款榜 + 滞销预警 + 运营建议。

    Args:
        days: 分析窗口天数，默认 7。

    Returns:
        JSON 包含 hot_styles, cold_styles, trend_summary, action_hints。
    """
    try:
        # 获取趋势数据
        trend_raw = trend_query_tool.run({"days": days, "top_n": 20})
        trend_data = json.loads(trend_raw)
        trending = trend_data.get("trending_styles", [])

        hot = [s for s in trending if s["total_signals"] >= 3]
        cold = [s for s in trending if s["total_signals"] <= 1]

        # 用 LLM 生成洞察（OpenClaw 模式：检索 + LLM 分析）
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)

        prompt = f"""你是美甲门店运营分析师。根据以下 {days} 天内的款式数据，生成运营洞察报告。

热门款式（信号数≥3）：{json.dumps(hot, ensure_ascii=False)}
冷门款式（信号数≤1）：{json.dumps(cold, ensure_ascii=False)}

返回 JSON：
{{
  "hot_styles": [{{"style_id": "...", "reason": "...", "suggested_action": "..."}}],
  "cold_styles": [{{"style_id": "...", "reason": "...", "suggested_action": "..."}}],
  "trend_summary": "一段话总结本周趋势",
  "action_hints": ["具体运营建议1", "具体运营建议2"]
}}
只返回 JSON。"""

        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw) if raw.startswith("{") else {
            "hot_styles": hot[:3],
            "cold_styles": cold[:3],
            "trend_summary": f"本周共追踪 {len(trending)} 个款式",
            "action_hints": ["对热门款式做限时套餐", "对冷门款式降价或换封面"],
        }
        result["data_source"] = "来自近 7 日收藏/订单/点击信号"
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)})
```

- [ ] **Step 2: 实现 OpsAnalysisTool**

```python
# backend/packages/harness/deerflow/tools/nail/ops_analysis.py
"""生成运营建议并写入 ops_memory（OpenClaw 长期记忆模式）。"""
import json
import uuid
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from deerflow.models import create_chat_model
from .base import get_db

MARKETING_TEMPLATES = [
    {"type": "限时套餐", "desc": "把高收藏款做成 3 折限时套餐，刺激转化"},
    {"type": "复购召回", "desc": "按上次美甲时间生成提醒消息，附推荐款式"},
    {"type": "换封面", "desc": "对低转化款换主图，突出显白/耐脱落卖点"},
    {"type": "节日主题", "desc": "结合节日（520/七夕/毕业季）做主题组合"},
]


@tool
def ops_analysis_tool(trend_summary: str, query: str = "") -> str:
    """基于趋势数据生成可执行的运营方案（ActionProposal 前置分析）。

    Args:
        trend_summary: trend_discovery_tool 返回的摘要 JSON。
        query: 运营人员的具体问题（可选）。

    Returns:
        JSON 包含 marketing_actions 列表，每条有 title/target/reason/metric/risk/requires_confirm。
    """
    try:
        # 读取历史营销记忆（OpenClaw 长期记忆）
        conn = get_db()
        memory_rows = conn.execute(
            "SELECT content FROM ops_memory WHERE memory_type='marketing' ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        conn.close()
        memory_ctx = "\n".join([r["content"] for r in memory_rows]) if memory_rows else "暂无历史记录"

        model = create_chat_model(thinking_enabled=False, attach_tracing=False)
        prompt = f"""你是美团美甲门店运营专家。根据趋势和历史记录生成 2-3 条可执行的运营方案。

趋势数据：{trend_summary}
历史营销效果：{memory_ctx}
运营提问：{query or "生成本周运营计划"}

可用营销手段：{json.dumps(MARKETING_TEMPLATES, ensure_ascii=False)}

返回 JSON：
{{
  "marketing_actions": [
    {{
      "title": "方案标题",
      "target_user": "目标用户画像",
      "reason": "为什么这样做（数据支撑）",
      "expected_metric": "预期指标提升",
      "risk": "潜在风险",
      "requires_human_confirm": true
    }}
  ]
}}
只返回 JSON。"""

        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw) if raw.startswith("{") else {"marketing_actions": []}
        result["data_source"] = "来自趋势分析 + 历史营销记录"
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "marketing_actions": []})
```

- [ ] **Step 3: 实现 CustomerServiceTool**

```python
# backend/packages/harness/deerflow/tools/nail/customer_service.py
"""美甲客服：处理风格咨询、预约、售后，回答必须标注信息来源。"""
import json
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from deerflow.models import create_chat_model

MOCK_STORE_SOP = """
门店 SOP（来自门店规则）：
- 预约时间：周一至日 10:00-21:00
- 最短提前预约：2 小时
- 退款政策：未开工可全退，开工后不退
- 脱落保修：7 天内免费补色
- 常见问题：猫眼胶需要加钱 30 元，延甲另计
"""


@tool
def customer_service_tool(user_question: str, user_id: str = "") -> str:
    """处理用户美甲相关客服咨询。

    Args:
        user_question: 用户的问题。
        user_id: 用户 ID（用于检索偏好历史，可选）。

    Returns:
        JSON 包含 reply（回复文本）和 source（信息来源标注）。
    """
    try:
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)
        prompt = f"""你是专业美甲门店客服。请根据门店规则和用户问题给出专业回复。

{MOCK_STORE_SOP}

用户问题：{user_question}

要求：
1. 回复简洁、亲切、专业
2. 对于预约/价格/退款问题，必须引用具体规则
3. 回复末尾注明信息来源

返回 JSON：
{{
  "reply": "客服回复内容",
  "source": "来自门店 SOP / 来自近期趋势 / 来自用户偏好",
  "needs_human": false
}}
只返回 JSON。"""

        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return raw if raw.startswith("{") else json.dumps({
            "reply": raw,
            "source": "来自 AI 推断",
            "needs_human": True,
        })

    except Exception as e:
        return json.dumps({
            "reply": f"抱歉，客服系统暂时繁忙，请稍后重试。({e})",
            "source": "系统错误",
            "needs_human": True,
        })
```

- [ ] **Step 4: 实现 ActionProposalTool（写入 DB，等待确认）**

```python
# backend/packages/harness/deerflow/tools/nail/action_proposal.py
"""将运营方案写入 DB，标记 pending，等待人工确认后执行。"""
import json
import uuid
from langchain.tools import tool
from .base import get_db


@tool
def action_proposal_tool(proposal_json: str, run_id: str = "") -> str:
    """将运营方案写入 action_proposals 表，等待人工确认。

    Args:
        proposal_json: ops_analysis_tool 返回的单条 marketing_action JSON 字符串。
        run_id: 关联的 run ID（可选）。

    Returns:
        JSON 包含 proposal_id 和 status=pending。
    """
    try:
        proposal = json.loads(proposal_json) if isinstance(proposal_json, str) else proposal_json
        # 如果传入的是整个 marketing_actions 数组，取第一条
        if "marketing_actions" in proposal:
            proposal = proposal["marketing_actions"][0]

        proposal_id = str(uuid.uuid4())
        conn = get_db()
        conn.execute(
            "INSERT INTO action_proposals (id, run_id, title, content, status) VALUES (?, ?, ?, ?, 'pending')",
            (proposal_id, run_id or "", proposal.get("title", "运营方案"), json.dumps(proposal, ensure_ascii=False))
        )
        conn.commit()
        conn.close()

        return json.dumps({
            "proposal_id": proposal_id,
            "status": "pending",
            "title": proposal.get("title"),
            "message": "方案已生成，等待运营人员确认后执行。请在运营端看板确认。",
            "requires_human_confirm": True,
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)})
```

- [ ] **Step 5: Commit 所有运营工具**

```bash
git add backend/packages/harness/deerflow/tools/nail/
git commit -m "feat(nail): implement ops tools (TrendDiscovery/OpsAnalysis/CustomerService/ActionProposal)"
```

---

### Task 14: EvaluationTool（dev 端专用）

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/evaluation.py`

- [ ] **Step 1: 实现 EvaluationTool**

```python
# backend/packages/harness/deerflow/tools/nail/evaluation.py
"""按赛题评分体系对本次 NailFlow 运行进行自动评分。"""
import json
import uuid
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from deerflow.models import create_chat_model
from .base import get_db

RUBRIC = """
评分标准（总分 100）：
1. 完整性（30分）：用户端/运营端流程覆盖，异常处理
2. 应用效果（25分）：甲面边界、肤色一致、款式相似度、客服命中率
3. 创新性（20分）：多 Agent 编排、评价 Agent 反推、长期记忆
4. 商业价值（15分）：试戴转化、运营建议可执行性
5. 硬约束（10分）：生成<30s、工具响应<3s、至少3类异常处理
"""


@tool
def evaluation_tool(run_summary: str, run_id: str = "") -> str:
    """对本次 NailFlow 运行按赛题评分体系自动打分。

    Args:
        run_summary: 本次运行的简要描述（完成了哪些步骤，结果如何）。
        run_id: 关联的 run ID（可选，用于存储评分结果）。

    Returns:
        JSON 包含 total_score、rubric_scores、blocking_issues、next_dev_tasks、demo_evidence。
    """
    try:
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)
        prompt = f"""你是 NailFlow 系统的自动评测 Agent。请根据以下赛题评分标准，对本次运行进行打分。

{RUBRIC}

本次运行描述：{run_summary}

返回 JSON（严格按格式）：
{{
  "total_score": 75,
  "rubric_scores": {{
    "completeness": 22,
    "application_effect": 18,
    "innovation": 15,
    "business_value": 12,
    "hard_constraints": 8
  }},
  "blocking_issues": ["必须修复的问题1", "必须修复的问题2"],
  "next_dev_tasks": [
    {{"task": "任务描述", "score_gain": 5, "effort": "low|medium|high"}},
  ],
  "demo_evidence": ["答辩时可展示的证据1", "答辩时可展示的证据2"]
}}
只返回 JSON。"""

        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw) if raw.startswith("{") else {
            "total_score": 60,
            "rubric_scores": {},
            "blocking_issues": ["评分解析失败"],
            "next_dev_tasks": [],
            "demo_evidence": [],
        }

        # 持久化评分结果
        if run_id:
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO evaluation_results (id, run_id, total_score, rubric_scores, blocking_issues, next_dev_tasks) VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), run_id, result.get("total_score", 0),
                 json.dumps(result.get("rubric_scores", {})),
                 json.dumps(result.get("blocking_issues", [])),
                 json.dumps(result.get("next_dev_tasks", [])))
            )
            conn.commit()
            conn.close()

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "total_score": 0})
```

- [ ] **Step 2: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/evaluation.py
git commit -m "feat(nail): implement EvaluationTool for dev portal scoring"
```

---

### Task 15: ActionProposal 确认接口 + APScheduler

**Files:**
- Create: `backend/app/gateway/routers/nail_ops.py`
- Create: `backend/nail_scheduler.py`
- Modify: `backend/app/gateway/app.py`

- [ ] **Step 1: 创建 ActionProposal 确认路由**

```python
# backend/app/gateway/routers/nail_ops.py
"""NailFlow 运营端专属接口：ActionProposal 确认/拒绝，看板数据查询。"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.gateway.authz import require_auth, require_permission

# 动态导入以避免循环依赖
def _get_db():
    from packages.harness.deerflow.tools.nail.base import get_db
    return get_db()

router = APIRouter(prefix="/api/nail", tags=["nail-ops"])


class ProposalAction(BaseModel):
    status: str  # "approved" | "rejected"


@router.post("/proposals/{proposal_id}/confirm")
@require_auth
async def confirm_proposal(proposal_id: str, body: ProposalAction, request: Request):
    """运营人员确认或拒绝 ActionProposal。"""
    if body.status not in ("approved", "rejected"):
        raise HTTPException(400, "status must be 'approved' or 'rejected'")

    conn = _get_db()
    row = conn.execute("SELECT * FROM action_proposals WHERE id = ?", (proposal_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Proposal not found")

    conn.execute(
        "UPDATE action_proposals SET status = ?, confirmed_at = ? WHERE id = ?",
        (body.status, datetime.utcnow().isoformat(), proposal_id)
    )
    conn.commit()
    conn.close()
    return {"proposal_id": proposal_id, "status": body.status, "message": "已更新"}


@router.get("/proposals")
@require_auth
async def list_proposals(request: Request, status: str = "pending"):
    """查询 ActionProposal 列表。"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM action_proposals WHERE status = ? ORDER BY created_at DESC LIMIT 20",
        (status,)
    ).fetchall()
    conn.close()
    return {"proposals": [dict(r) for r in rows]}


@router.get("/image")
@require_auth
async def serve_result_image(path: str, request: Request):
    """提供生成结果图的静态文件服务（本地路径 → HTTP）。"""
    from pathlib import Path
    from fastapi.responses import FileResponse
    safe = Path(path).resolve()
    results_dir = Path("data/results").resolve()
    uploads_dir = Path("data/uploads").resolve()
    # 安全检查：只允许读取 results/ 和 uploads/ 目录
    if not (str(safe).startswith(str(results_dir)) or str(safe).startswith(str(uploads_dir))):
        raise HTTPException(403, "Access denied")
    if not safe.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(str(safe))


@router.get("/dashboard")
@require_auth
async def get_dashboard(request: Request, days: int = 7):
    """运营看板数据：趋势信号、提案状态汇总。"""
    conn = _get_db()
    signals = conn.execute("""
        SELECT style_id, COUNT(*) as count, signal_type
        FROM ops_signals
        WHERE created_at >= datetime('now', ?)
        GROUP BY style_id, signal_type
        ORDER BY count DESC LIMIT 20
    """, (f"-{days} day",)).fetchall()

    proposals = conn.execute("""
        SELECT status, COUNT(*) as count FROM action_proposals GROUP BY status
    """).fetchall()
    conn.close()

    return {
        "signals": [dict(s) for s in signals],
        "proposal_summary": {r["status"]: r["count"] for r in proposals},
        "days": days,
    }
```

- [ ] **Step 2: 注册路由到 app.py**

在 `backend/app/gateway/app.py` 中找到路由注册部分，添加：

```python
from app.gateway.routers.nail_ops import router as nail_ops_router
app.include_router(nail_ops_router)
```

- [ ] **Step 3: 创建 APScheduler 定时任务**

```python
# backend/nail_scheduler.py
"""NailFlow 运营端定时任务：每天 09:00 触发趋势分析。"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def run_daily_trend_report():
    """每天定时生成趋势报告，存入 ops_memory。"""
    try:
        from packages.harness.deerflow.tools.nail.trend_discovery import trend_discovery_tool
        from packages.harness.deerflow.tools.nail.base import get_db
        import json

        result = trend_discovery_tool.run({"days": 7})
        data = json.loads(result)

        conn = get_db()
        conn.execute(
            "INSERT INTO ops_memory (memory_type, content) VALUES ('marketing', ?)",
            (json.dumps({"type": "daily_trend", "summary": data.get("trend_summary", "")}, ensure_ascii=False),)
        )
        conn.commit()
        conn.close()
        logger.info("Daily trend report saved to ops_memory")
    except Exception as e:
        logger.error(f"Daily trend report failed: {e}")


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_trend_report, "cron", hour=9, minute=0)
    scheduler.start()
    logger.info("NailFlow scheduler started (daily trend report at 09:00)")
    return scheduler
```

在 `app.py` 的 lifespan 中启动：

```python
# 在 app startup 事件中添加
from nail_scheduler import start_scheduler
_scheduler = start_scheduler()
```

- [ ] **Step 4: 测试 ActionProposal 接口**

```bash
# 启动服务
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload &

# 登录获取 ops token
OPS_TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@nailflow.dev","password":"nail123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 查询待确认提案
curl -s http://localhost:8001/api/nail/proposals?status=pending \
  -H "Authorization: Bearer $OPS_TOKEN" | python -m json.tool
```

预期：返回 `{"proposals": [...]}`（可能为空，之后通过 Agent 创建）

- [ ] **Step 5: Commit**

```bash
git add backend/app/gateway/routers/nail_ops.py backend/nail_scheduler.py
git commit -m "feat(ops): add ActionProposal confirm API and APScheduler daily report"
```

---

## Phase 3（Day 3）：前端 + 开发端 + 打磨

### Task 16: 前端三端路由守卫

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/app/(user)/layout.tsx`
- Create: `frontend/src/app/(ops)/layout.tsx`
- Create: `frontend/src/app/(dev)/layout.tsx`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: 创建 auth 工具函数（解析 JWT nail_role）**

```typescript
// frontend/src/lib/auth.ts
export type NailRole = "user" | "ops" | "dev";

export function getNailRole(): NailRole {
  if (typeof window === "undefined") return "user";
  const token = localStorage.getItem("access_token");
  if (!token) return "user";
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return (payload.nail_role as NailRole) || "user";
  } catch {
    return "user";
  }
}

export function canAccess(required: NailRole): boolean {
  const role = getNailRole();
  const levels: Record<NailRole, number> = { user: 1, ops: 2, dev: 3 };
  return levels[role] >= levels[required];
}
```

- [ ] **Step 2: 创建三端 Layout（路由守卫）**

```typescript
// frontend/src/app/(user)/layout.tsx
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { canAccess } from "@/lib/auth";

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  useEffect(() => {
    if (!canAccess("user")) router.push("/login");
  }, [router]);
  return <>{children}</>;
}
```

```typescript
// frontend/src/app/(ops)/layout.tsx — 同上，canAccess("ops")
// frontend/src/app/(dev)/layout.tsx — 同上，canAccess("dev")
```

- [ ] **Step 3: 在登录成功后，把 nail_role 存入 localStorage**

找到 DeerFlow 前端的登录逻辑（通常在 `frontend/src/app/(auth)/login/`），在 `localStorage.setItem("access_token", ...)` 之后添加：

```typescript
// 解析 JWT，保存 nail_role
const payload = JSON.parse(atob(token.split(".")[1]));
localStorage.setItem("nail_role", payload.nail_role || "user");
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/auth.ts frontend/src/app/
git commit -m "feat(frontend): add role-based route guards for three portals"
```

---

### Task 17: TryOn Canvas 组件

**Files:**
- Create: `frontend/src/components/tryon-canvas/TryonCanvas.tsx`
- Create: `frontend/src/app/(user)/tryon/page.tsx`

- [ ] **Step 1: 实现 TryonCanvas 组件**

```tsx
// frontend/src/components/tryon-canvas/TryonCanvas.tsx
"use client";
import { useState } from "react";
import { getNailRole } from "@/lib/auth";

interface TryonResult {
  result_path?: string;
  explanation_zh?: string;
  scores?: Record<string, number>;
  is_mock?: boolean;
}

export default function TryonCanvas() {
  const [handFile, setHandFile]   = useState<File | null>(null);
  const [styleFile, setStyleFile] = useState<File | null>(null);
  const [handPreview, setHandPreview]   = useState<string>("");
  const [stylePreview, setStylePreview] = useState<string>("");
  const [result, setResult]       = useState<TryonResult | null>(null);
  const [loading, setLoading]     = useState(false);
  const [agentLog, setAgentLog]   = useState<string[]>([]);

  const handleFile = (file: File, type: "hand" | "style") => {
    const url = URL.createObjectURL(file);
    if (type === "hand") { setHandFile(file); setHandPreview(url); }
    else { setStyleFile(file); setStylePreview(url); }
  };

  const uploadFile = async (file: File): Promise<string> => {
    const form = new FormData();
    form.append("file", file);
    const token = localStorage.getItem("access_token");
    const res = await fetch("/api/uploads", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    const data = await res.json();
    return data.url;
  };

  const startTryon = async () => {
    if (!handFile || !styleFile) return;
    setLoading(true);
    setAgentLog([]);
    setResult(null);

    try {
      const [handUrl, styleUrl] = await Promise.all([
        uploadFile(handFile),
        uploadFile(styleFile),
      ]);

      const token = localStorage.getItem("access_token");
      const role = getNailRole();

      // 创建 thread
      const thread = await fetch("/api/threads", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: "{}",
      }).then(r => r.json());

      // SSE 流式运行
      const response = await fetch(`/api/threads/${thread.thread_id}/runs/stream`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          input: { messages: [{ role: "user", content: `请帮我试戴这个款式。手图：${handUrl}，款式图：${styleUrl}` }] },
          config: { configurable: { nail_role: role } },
        }),
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let resultPath = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter(l => l.startsWith("data: "));
        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "tool_result" && data.tool === "image_generation") {
              const r = JSON.parse(data.content);
              resultPath = r.result_path || "";
            }
            if (data.type === "message" || data.type === "thought") {
              setAgentLog(prev => [...prev, data.content || data.text || ""]);
            }
          } catch { /* ignore parse errors */ }
        }
      }

      if (resultPath) {
        setResult({ result_path: `/api/nail/image?path=${encodeURIComponent(resultPath)}`, is_mock: false });
      }
    } catch (e) {
      setAgentLog(prev => [...prev, `错误: ${e}`]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-3 gap-4 p-6">
      {/* 上传区 */}
      <div className="space-y-4">
        <div className="border-2 border-dashed rounded-lg p-4 text-center cursor-pointer hover:border-pink-400"
          onClick={() => document.getElementById("hand-input")?.click()}>
          {handPreview ? <img src={handPreview} className="max-h-48 mx-auto" alt="手图" /> : <p className="text-gray-400">点击上传手图</p>}
          <input id="hand-input" type="file" hidden accept="image/*" onChange={e => e.target.files?.[0] && handleFile(e.target.files[0], "hand")} />
        </div>
        <div className="border-2 border-dashed rounded-lg p-4 text-center cursor-pointer hover:border-pink-400"
          onClick={() => document.getElementById("style-input")?.click()}>
          {stylePreview ? <img src={stylePreview} className="max-h-48 mx-auto" alt="款式" /> : <p className="text-gray-400">点击上传款式图</p>}
          <input id="style-input" type="file" hidden accept="image/*" onChange={e => e.target.files?.[0] && handleFile(e.target.files[0], "style")} />
        </div>
        <button
          onClick={startTryon}
          disabled={loading || !handFile || !styleFile}
          className="w-full py-2 bg-pink-500 text-white rounded-lg disabled:opacity-50 hover:bg-pink-600"
        >
          {loading ? "AI 试戴中…" : "开始 AI 试戴"}
        </button>
      </div>

      {/* 结果区 */}
      <div className="col-span-2">
        {result?.result_path && (
          <img src={result.result_path} className="max-h-96 mx-auto rounded-lg shadow" alt="试戴结果" />
        )}
        {loading && <div className="text-center text-gray-400 mt-8">AI 正在工作中，请稍候…</div>}
      </div>

      {/* Agent 思考链（在 ops/dev 端可见） */}
      {["ops", "dev"].includes(getNailRole()) && agentLog.length > 0 && (
        <div className="col-span-3 bg-gray-900 rounded-lg p-4 text-xs text-gray-300 max-h-48 overflow-y-auto">
          <p className="text-gray-500 mb-2">Agent 思考链：</p>
          {agentLog.map((log, i) => <p key={i}>{log}</p>)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建用户端试戴页面**

```tsx
// frontend/src/app/(user)/tryon/page.tsx
import TryonCanvas from "@/components/tryon-canvas/TryonCanvas";

export default function TryonPage() {
  return (
    <main>
      <h1 className="text-2xl font-bold p-6 text-pink-600">AI 美甲试戴</h1>
      <TryonCanvas />
    </main>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/tryon-canvas/ frontend/src/app/
git commit -m "feat(frontend): add TryonCanvas component and user tryon page"
```

---

### Task 18: 运营看板 + 开发端评分面板

**Files:**
- Create: `frontend/src/app/(ops)/dashboard/page.tsx`
- Create: `frontend/src/app/(dev)/evaluation/page.tsx`

- [ ] **Step 1: 运营看板页面**

```tsx
// frontend/src/app/(ops)/dashboard/page.tsx
"use client";
import { useEffect, useState } from "react";

export default function OpsDashboard() {
  const [data, setData] = useState<any>(null);
  const [proposals, setProposals] = useState<any[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const headers = { Authorization: `Bearer ${token}` };
    fetch("/api/nail/dashboard?days=7", { headers }).then(r => r.json()).then(setData);
    fetch("/api/nail/proposals?status=pending", { headers }).then(r => r.json()).then(d => setProposals(d.proposals || []));
  }, []);

  const confirm = async (id: string, status: "approved" | "rejected") => {
    const token = localStorage.getItem("access_token");
    await fetch(`/api/nail/proposals/${id}/confirm`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    setProposals(prev => prev.filter(p => p.id !== id));
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">运营看板</h1>

      {/* 趋势信号 */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="font-semibold mb-3">近 7 天爆款款式</h2>
        <div className="grid grid-cols-4 gap-2">
          {data?.signals?.slice(0, 8).map((s: any, i: number) => (
            <div key={i} className="bg-pink-50 rounded p-2 text-sm">
              <p className="font-medium">{s.style_id}</p>
              <p className="text-gray-500">{s.signal_type}: {s.count}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ActionProposal 待确认 */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="font-semibold mb-3">待确认运营方案 ({proposals.length})</h2>
        {proposals.map(p => (
          <div key={p.id} className="border rounded p-3 mb-2">
            <p className="font-medium">{p.title}</p>
            <p className="text-sm text-gray-500 mt-1">{JSON.parse(p.content).reason || ""}</p>
            <div className="flex gap-2 mt-2">
              <button onClick={() => confirm(p.id, "approved")} className="px-3 py-1 bg-green-500 text-white rounded text-sm">确认执行</button>
              <button onClick={() => confirm(p.id, "rejected")} className="px-3 py-1 bg-red-400 text-white rounded text-sm">拒绝</button>
            </div>
          </div>
        ))}
        {proposals.length === 0 && <p className="text-gray-400">暂无待确认方案</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 开发端评分面板**

```tsx
// frontend/src/app/(dev)/evaluation/page.tsx
"use client";
import { useState } from "react";

export default function EvaluationPage() {
  const [summary, setSummary] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runEval = async () => {
    setLoading(true);
    const token = localStorage.getItem("access_token");

    const thread = await fetch("/api/threads", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: "{}",
    }).then(r => r.json());

    const response = await fetch(`/api/threads/${thread.thread_id}/runs/stream`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        input: { messages: [{ role: "user", content: `请用 evaluation_tool 对以下运行进行评分：${summary}` }] },
        config: { configurable: { nail_role: "dev" } },
      }),
    });

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      for (const line of chunk.split("\n").filter(l => l.startsWith("data: "))) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "tool_result" && data.tool === "evaluation") {
            setResult(JSON.parse(data.content));
          }
        } catch { /* ignore */ }
      }
    }
    setLoading(false);
  };

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">EvaluationAgent 评分</h1>
      <textarea
        value={summary}
        onChange={e => setSummary(e.target.value)}
        className="w-full h-32 border rounded p-2"
        placeholder="描述本次运行：完成了哪些步骤、结果如何…"
      />
      <button onClick={runEval} disabled={loading || !summary} className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50">
        {loading ? "评分中…" : "运行 EvaluationAgent"}
      </button>

      {result && (
        <div className="bg-gray-50 rounded-lg p-4 space-y-3">
          <div className="text-3xl font-bold text-center text-blue-600">{result.total_score} / 100</div>
          <div className="grid grid-cols-5 gap-2">
            {Object.entries(result.rubric_scores || {}).map(([k, v]: [string, any]) => (
              <div key={k} className="text-center bg-white rounded p-2 shadow-sm">
                <p className="text-xs text-gray-500">{k}</p>
                <p className="font-bold">{v}</p>
              </div>
            ))}
          </div>
          {result.blocking_issues?.length > 0 && (
            <div>
              <p className="font-semibold text-red-600">必须修复：</p>
              <ul className="list-disc pl-4 text-sm">{result.blocking_issues.map((i: string, idx: number) => <li key={idx}>{i}</li>)}</ul>
            </div>
          )}
          {result.next_dev_tasks?.length > 0 && (
            <div>
              <p className="font-semibold">下一步任务（按评分收益排序）：</p>
              <ul className="list-disc pl-4 text-sm">{result.next_dev_tasks.map((t: any, idx: number) => (
                <li key={idx}>{t.task}（+{t.score_gain}分，{t.effort}）</li>
              ))}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/
git commit -m "feat(frontend): add ops dashboard and dev evaluation panel"
```

---

### Task 19: 异常处理 + 降级策略

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/hand_detect.py`（已有）
- Modify: `backend/packages/harness/deerflow/tools/nail/image_generation.py`（已有）

- [ ] **Step 1: 验证 3 类异常场景的降级**

```bash
# 场景 1：手图检测失败（传一张非手部图片）
python -c "
from packages.harness.deerflow.tools.nail.hand_detect import hand_detect_tool
import json
r = hand_detect_tool.run('config.yaml')  # 非图片文件
d = json.loads(r); print('detected:', d.get('detected'), 'msg:', d.get('message', '')[:50])
"
# 预期：detected: False，含提示重拍的 message

# 场景 2：生图 API 未配置（mock 降级）
python -c "
from packages.harness.deerflow.tools.nail.image_generation import image_generation_tool
import json, os
os.environ['NAIL_IMAGE_API_KEY'] = ''
r = image_generation_tool.run({'hand_image_path': '../微信图片_20260523173957_29_463.jpg', 'mask_path': 'config.yaml', 'prompt_json': '{\"positive_prompt\": \"test\", \"negative_prompt\": \"test\"}'})
d = json.loads(r); print('is_mock:', d.get('is_mock'))
"
# 预期：is_mock: True

# 场景 3：无效 JSON 传入 PromptBuilderTool
python -c "
from packages.harness.deerflow.tools.nail.prompt_builder import prompt_builder_tool
import json
r = prompt_builder_tool.run({'style_analysis_json': 'invalid json', 'user_request': '粉色'})
d = json.loads(r); print('has positive_prompt:', 'positive_prompt' in d)
"
# 预期：has positive_prompt: True（降级到默认 prompt）
```

- [ ] **Step 2: Commit 异常处理确认**

```bash
git commit -m "test: verify 3 fallback scenarios work correctly"
```

---

### Task 20: 全链路 Demo 验收 + EvaluationAgent 自评

- [ ] **Step 1: 启动完整服务**

```bash
# 终端 1：后端
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload

# 终端 2：前端
cd frontend && pnpm dev
```

- [ ] **Step 2: 用 user 角色跑一次完整试戴**

浏览器打开 `http://localhost:3000/tryon`，用 `user@nailflow.dev / nail123` 登录，上传手图 + 款式图，点击"开始 AI 试戴"，等待结果。

- [ ] **Step 3: 用 ops 角色查看看板、创建并确认一个 ActionProposal**

切换到 `ops@nailflow.dev`，访问 `/ops/dashboard`，查看趋势数据，通过 Agent 生成一个运营方案并确认。

- [ ] **Step 4: 用 dev 角色运行 EvaluationAgent**

切换到 `dev@nailflow.dev`，访问 `/dev/evaluation`，描述本次运行，点击评分。

目标：`total_score ≥ 75`，`blocking_issues` 为空。

- [ ] **Step 5: 修复 blocking_issues 中标注的问题**

根据评分结果，按 `score_gain` 从高到低修复。

- [ ] **Step 6: 最终 Commit**

```bash
git add -A
git commit -m "feat: NailFlow v1.0 — Day 3 complete, all three portals working"
```

---

## 快速参考

### 测试账号
| 邮箱 | 密码 | 角色 | 可访问路由 |
|------|------|------|-----------|
| user@nailflow.dev | nail123 | user | /user/tryon, /user/recommend |
| ops@nailflow.dev | nail123 | ops | 以上 + /ops/dashboard, /ops/proposals |
| dev@nailflow.dev | nail123 | dev | 以上 + /dev/evaluation, /dev/trace |

### 工具组权限
| 工具 | group | user | ops | dev |
|------|-------|:---:|:---:|:---:|
| hand_detect, nail_mask, style_understanding, prompt_builder, image_generation, quality_check, preference_rag, trend_query | nail | ✅ | ✅ | ✅ |
| ops_analysis, customer_service, action_proposal, trend_discovery | nail_ops | ❌ | ✅ | ✅ |
| evaluation | nail_dev | ❌ | ❌ | ✅ |

### 关键命令
```bash
# 启动后端
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload

# 启动前端
cd frontend && pnpm dev

# 初始化数据
cd backend && uv run python scripts/seed_nail_users.py

# 重置数据库
rm data/nailflow.db && python -c "from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables()"
```
