# NailOps PDF Report — 运营日报 PDF 导出设计

> 日期: 2026-06-07
> 状态: 设计完成，待实施
> 依赖: NailOps Channel (2026-06-04-nailops-channel-design.md)

## 一、目标

在 NailOps Channel 日报推送基础上，增加 PDF 文件生成链路：把运营分析结果（趋势数据、排行榜、分析图表、策略建议）生成专业 PDF 文档，运营同学可下载分享。

## 二、技术选型

**方案 A：matplotlib + ReportLab（纯 Python）**

- 图表：matplotlib + seaborn 渲染 PNG
- PDF 拼装：ReportLab Platypus 流式布局
- 字体：PingFang SC / Noto Sans CJK（降级 DejaVu Sans）
- 新增依赖：`matplotlib seaborn reportlab`

比选理由：纯 Python 无外部进程，cron job 不会因浏览器超时失败；依赖最小，CI/docker/本地统一。

## 三、PDF 内容布局（A4竖版，3页）

| 页码 | 内容块 | 数据类型 | 渲染方式 |
|------|--------|---------|---------|
| P1 | 封面标题 + 日期 | 元数据 | ReportLab Paragraph |
| P1 | 核心指标卡片（4列） | SQL 聚合 | ReportLab Table |
| P1 | 7日趋势面积图 | 时序数据 | matplotlib fill_between |
| P1 | 爆款 TOP5 表格 | 排名数据 | ReportLab Table |
| P2 | 风格分布环形图 | 分类占比 | matplotlib pie(donut) |
| P2 | 用户行为柱状图 | 分类对比 | matplotlib barh |
| P2 | 冷门预警表格 | 列表数据 | ReportLab Table |
| P3 | 运营策略建议 | LLM 文本 | ReportLab Paragraph |
| P3 | 数据来源 | 元数据 | ReportLab Paragraph |

配色方案：品牌粉 `#EC4899` / 蓝色 `#3B82F6` / 绿色 `#10B981` / 琥珀 `#F59E0B` / 红色 `#EF4444`

## 四、模块划分

### 新增文件（ops_channel/ 包内）

```
ops_channel/
├── delivery/
│   ├── adapters/
│   │   └── file_adapter.py           # 文件输出适配器
│   └── messages/
│       └── base.py                    # 修改: 新增 FileMessage
└── formatters/
    └── pdf_report/                    # 新增 PDF 报告子包
        ├── __init__.py
        ├── charts.py                  # matplotlib 图表渲染 (3个函数)
        ├── builder.py                 # ReportLab PDF 拼装
        └── report_data.py             # 数据聚合 (ReportData + SQL查询)
```

### 修改文件

| 文件 | 改动 |
|------|------|
| `delivery/messages/base.py` | 新增 `FileMessage` 类型 |
| `ops_runner.py` | `_run_daily_report` 增加 PDF 生成步骤 |
| `ops_scheduler.py` | delivery loop 支持 file 通道 |
| `app.py` lifespan | daily_job 增加 file delivery target |
| `nail_ops.py` | 新增 `/ops/reports/latest` 下载 + `/ops/reports` 列表 |
| `config.yaml` | 新增 `file` channel + pdf_report 配置段 |

## 五、核心接口

### 5.1 数据聚合层

```python
@dataclass
class ReportData:
    date: str; days: int
    metrics: Metrics                   # total_signals/hot_count/cold_count/active_users
    trend_series: list[TrendPoint]     # date_label/signal_count/save_count
    top_styles: list[StyleRank]        # rank/style_id/signal_count/change_pct
    cold_styles: list[StyleRank]
    style_distribution: list[CategoryPct]   # label/count/percentage
    behavior_distribution: list[BehaviorPct] # label/count
    strategy_text: str                 # LLM 生成
    data_source: str; generated_at: str; model_used: str

def gather_report_data(days: int = 7) -> ReportData
```

数据来源：ops_signals 表 SQL 聚合 + trend_discovery_tool + ops_analysis_tool（复用已有）

### 5.2 图表渲染层

```python
def render_trend_chart(series: list[TrendPoint]) -> BytesIO | None   # 面积图
def render_style_donut(dist: list[CategoryPct]) -> BytesIO | None    # 环形图
def render_behavior_bar(dist: list[BehaviorPct]) -> BytesIO | None   # 柱状图
```

全局设置：`matplotlib.use("Agg")` + seaborn whitegrid + 中文字体

### 5.3 PDF 拼装层

```python
def build_daily_report_pdf(report: ReportData, charts: dict[str, BytesIO|None]) -> bytes
```

ReportLab Platypus 流式排版，自动分页。字体注册降级链：PingFang → Noto Sans CJK → DejaVu Sans → Helvetica。

### 5.4 File Adapter

```python
class FileAdapter(AbstractChannelAdapter):
    channel_id = "file"
    capabilities = ChannelCapability.FILE
    async def send(target, message: FileMessage) -> DeliveryResult
```

### 5.5 FileMessage

```python
@dataclass
class FileMessage(AbstractMessage):
    content: bytes
    filename: str
    mime_type: str = "application/pdf"
```

## 六、数据流

```
09:00 cron 触发 daily_report
  → trend_discovery_tool + ops_analysis_tool  (已有)
  → gather_report_data() → SQL聚合 + 结构化   (新增)
  → render_*() → 3个 PNG 图表                  (新增)
  → build_daily_report_pdf() → PDF bytes       (新增)
  → CardMessage (已有) + FileMessage (新增)
  →
  ├─ web_push adapter  → Web 看板卡片
  ├─ feishu adapter    → 飞书群卡片
  └─ file adapter      → data/reports/daily_report_YYYY-MM-DD.pdf
```

## 七、API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/nail/ops/reports/latest` | 下载最新 PDF 日报 |
| GET | `/api/nail/ops/reports` | 列出所有 PDF 日报 |

## 八、降级策略

- charts.py: 每个 render 函数失败时返回 None，PDF 中显示 "图表生成失败"
- builder.py: report_data 为空时生成纯文本降级 PDF（至少包含策略文本）
- 文件写入失败时 file_adapter 返回 DeliveryResult(ok=False)，不影响飞书/WebPush 投递
- SQL 查询失败时 ReportData 各字段返回空值/空列表，单个查询失败不影响其他

## 九、依赖

新增 pip 包：`matplotlib seaborn reportlab`（均为纯 Python，零系统依赖）
