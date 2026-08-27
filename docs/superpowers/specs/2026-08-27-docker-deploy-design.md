# nailflow Docker 部署设计

日期：2026-08-27
状态：已确认（方案 A：docker-compose 单机部署）

## 背景与目标

hackathon-meituan-ai（美甲 AI 试戴）需要部署到**国内云服务器 VPS**（待购买，阿里云/腾讯云轻量，2核4G，Ubuntu 24.04）。仓库已有未经验证的 docker-compose.yml、backend/frontend Dockerfile、nginx.conf、render.yaml。目标：修复现有配置中的部署坑，**本机容器化验证通过后**，在服务器上一键 `docker compose up -d --build` 部署。

## 部署架构

```
Internet → :3000 frontend (Next.js) ── /api/* 代理 ──→ backend:8001 (FastAPI + LangGraph)
                                                     └─ 挂载 nailflow_data → /app/backend/data（SQLite + ChromaDB + uploads + results）
                                                     └─ 挂载 nailflow_nailflow → /app/backend/.nail-flow（checkpoint/thread 数据）
                                                     └─ 只读挂载 ./config.yaml → /app/backend/config.yaml
```

- backend 容器：uvicorn :8001（GATEWAY_HOST=0.0.0.0），healthcheck `GET /health`
- frontend 容器：`pnpm start` :3000，`DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://backend:8001` 代理 /api/*
- 两个 named volume 持久化；`restart: unless-stopped`

## 修复清单

| # | 问题 | 修复 |
|---|------|------|
| 1 | 容器内无 `.mp-venv`，hand_detect_tool subprocess 找不到 `backend/.mp-venv/bin/python`，手部检测必失败 | backend/Dockerfile builder 阶段 `python -m venv .mp-venv && .mp-venv/bin/pip install mediapipe`，runtime 阶段 COPY 保留 |
| 2 | compose environment 缺 `MINIMAX_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`NAIL_IMAGE_MODEL`，config.yaml 解析 `$VAR` 时 raise ValueError 启动崩溃 | environment 补齐全部 config.yaml 引用 + 代码读取的变量（`${VAR:-}` 形式） |
| 3 | `nailflow_data` 卷首次挂载为空，styles（40 款式）/knowledge/seed_images/hand_landmarker.task 系统资产缺失 | Dockerfile COPY 资产副本到 `/app/backend-data-seed/`，entrypoint 脚本（backend/scripts/docker_entrypoint.sh）检测卷中缺失则复制 |
| 4 | `.env.example` 缺失（compose 注释要求 `cp .env.example .env`） | 创建 `.env.example`（只含键名，不含值） |
| 5 | torch>=2.12 依赖使镜像约 3GB，构建内存压力大 | 服务器 4G 内存 + 2G swap；国内镜像加速（APT_MIRROR=mirrors.aliyun.com、UV_INDEX_URL=清华 pypi、NPM_REGISTRY=npmmirror） |

## 验证流程（本机 OrbStack，全部通过后才上服务器）

1. 启动 OrbStack docker daemon
2. `docker compose build`（验证 Dockerfile 修复、.mp-venv 创建）
3. `docker compose up -d`（验证 entrypoint seed、健康检查）
4. 浏览器实测（chrome-devtools/web-devhandler 访问 localhost:3000）：
   - 登录（user@nailflow.dev / nail123456，需先 seed 用户或注册）
   - 试戴全流程：上传手图+款式图 → hand_detect（.mp-venv 真实执行）→ mask → style_understanding → prompt_builder → 生图（mock 模式）→ quality_check → 结果图可访问
   - 对话流式 SSE 正常
5. 验证通过后提交修复，交付服务器部署步骤

### 验证结果（2026-08-27 完成 ✅）

**构建**：backend/frontend 镜像构建成功（CPU torch，`[tool.uv.sources]` 指向 pytorch-cpu 源）。

**运行时**：
- 两个容器 healthy，数据卷 seed 成功（styles 41 项、knowledge、seed_images、hand_landmarker.task）
- `.mp-venv` 手部检测容器内真实执行：`detected: true`，5 个甲面 bbox；mask 生成成功（与本地行为一致）
- 登录 API 链路通（`/api/v1/auth/login/local` form 编码；用户 seed 后有效）
- 前端页面完整渲染（登录页、工作区、试戴页 40 款样式）

**端到端试戴（浏览器实测）**：
- 上传手图+选款式 → thread 创建 → Agent（minimax-m2，LLM 200 OK）调用 unified_tryon_tool → 手检测 → 款式理解 → **Seedream 真实生图成功**（`ark.cn-beijing.volces.com 200 OK`，结果图 result_62407178.jpg 291KB，浏览器可访问）→ 质量评分 → 对话页展示试戴结果图 + 建议按钮

**验证期间额外修复**：
- `frontend/Dockerfile`：builder 阶段声明 `ARG/ENV DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`（next.config.js rewrites 构建时求值，缺 ARG 导致产物编译成 127.0.0.1:8001）
- compose frontend：补 `NAILFLOW_INTERNAL_GATEWAY_BASE_URL`（SSR auth 模块 gateway-config.ts 读的 env 名与 next.config.js 不同）
- `backend/scripts/seed_nail_users.py`：改为读 config.yaml 的 database 配置（原默认 `./nail-flow.db` 与运行时 `.nail-flow/data/nailflow.db` 不一致，seed 用户登录失败）

**注意**：`unified_tryon_tool` 的生图凭据解析优先级为 env → DB ModelRouter → config；容器内即使 `NAIL_IMAGE_API_KEY` 置空，若 DB/配置存在 IMAGE_GEN 模型仍会真实调用生图（部署服务器时 .env 配好真实 key 即可，无需特殊处理）。

## 服务器部署步骤（用户购买后执行）

```bash
# 1. 安装 Docker（国内源）
curl -fsSL https://get.docker.com | bash -s -- --mirror Aliyun
systemctl enable --now docker
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile

# 2. 拉代码 + 配置
git clone https://github.com/zhang17-24/hackathon-meituan-ai.git
cd hackathon-meituan-ai && cp .env.example .env && vim .env  # 填真实密钥

# 3. 构建 + 启动（国内加速）
docker compose up -d --build   # 首次构建 15-25 分钟
docker compose logs -f         # 查看日志
```

安全组开放：22、3000。

## 风险与降级

- 生图 API 未配置 → image_generation_tool 自动 mock 模式（复制原图），已有降级路径
- 服务器 Docker 构建 OOM → swap 兜底；仍 OOM 则本机构建后 `docker save/load` 传输镜像
- 国内网络访问 ghcr.io（uv 镜像）失败 → 构建参数换镜像源或直接 `COPY --from` 本地 uv
- hand_landmarker.task 已 git 跟踪（7.5MB），无需额外下载
