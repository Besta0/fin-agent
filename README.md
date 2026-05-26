# Fin Agent

一个基于 **Chainlit + LangGraph** 的中文多 Agent 投研助手。用户输入一句股票分析问题，系统会模拟一个小型投研团队，自动识别 ticker、拉取行情和基本面数据、计算技术指标、整理新闻线索、形成多空观点、给出投委会结论，并生成带质量检查和观察池跟踪的中文投研报告。

> 免责声明：本项目仅用于学习、研究和 Agent 架构演示，不构成任何投资建议。

## 项目价值

普通股票研究通常需要在行情网站、新闻网站、财报数据、图表工具和文档之间来回切换。这个项目把流程收敛成一个可解释的 Agent 工作流：

- 数据层负责获取行情、新闻、基本面和技术指标
- 分析层负责拆解任务、生成风险、多空观点和投委会结论
- 写作层负责生成中文报告
- 质检层负责检查报告是否和结构化数据矛盾

它的核心不是“让 AI 猜涨跌”，而是把投研流程做成一个可追踪、可复盘、可扩展、可展示的系统。随着 Review、Portfolio、History 这些 Agent 接入，系统会逐渐从“一次性报告生成器”进化成“持续跟踪的研究工作台”。

## 技术栈

- **Frontend**: Chainlit
- **Workflow**: LangGraph
- **LLM Adapter**: `langchain-openai`
- **LLM Provider**: OpenAI / DeepSeek / MiniMax / OpenAI-compatible endpoint
- **Market Data**: yfinance
- **Indicators**: pandas
- **Charts**: Plotly
- **Language**: Python

## 总体架构

```text
User
  ↓
Chainlit UI
  ↓
Intent Router
  ├─ Help Intent → Capability Guide
  ├─ Watchlist Intent → Watchlist Table
  ↓
LangGraph Workflow
  ↓
Coordinator Agent
  ├─ Missing ticker / non-research → Direct Response
  ↓
Market Agent
  ↓
Review Agent
  ↓
Technical Agent
  ↓
Fundamental Agent
  ↓
News & Risk Agent
  ↓
Bull Agent
  ↓
Bear Agent
  ↓
Committee Agent
  ↓
Portfolio Agent
  ↓
Report Agent
  ↓
Verifier Agent
  ↓
History Agent
  ↓
Final Report + Plotly Chart
```

## Agent 设计

### Coordinator Agent

文件：`financial_agent/agents/coordinator.py`

职责：

- 解析用户自然语言问题
- 识别股票代码、公司名、市场和分析周期
- 先用规则识别常见 ticker 和中文别名
- 规则失败后调用 LLM fallback 自动识别 ticker
- 如果 LLM 置信度不足，则提示用户输入明确 ticker
- 如果问题不是股票投研请求，直接返回说明并停止后续 Agent
- 如果问题像投研请求但没有明确 ticker，直接请用户补充标的并停止后续 Agent

输出字段：

```python
intent
should_continue
direct_response
ticker
company_name
market
horizon
ticker_resolution
```

### Market Agent

文件：`financial_agent/agents/market_agent.py`

工具：`financial_agent/tools/market_data.py`

职责：

- 使用 yfinance 获取历史行情
- 计算当前收盘价、成交量、52 周高低点
- 计算 1 日、5 日、1 月、3 月、6 月涨跌幅
- 输出最近 180 个交易日价格序列，供图表和技术指标使用

输出字段：

```python
market_data
```

### Review Agent

文件：`financial_agent/agents/review_agent.py`

工具：`financial_agent/tools/history.py`

职责：

- 读取同 ticker 最近一次历史记录
- 对比上次价格和当前价格
- 判断上次评级是否基本兑现
- 给本次分析提供复盘提醒

输出字段：

```python
review
```

### Technical Agent

文件：`financial_agent/agents/technical_agent.py`

工具：`financial_agent/tools/indicators.py`

职责：

- 基于价格序列计算技术指标
- 计算 MA5、MA20、MA60
- 计算 RSI(14)
- 计算 MACD、Signal、Histogram
- 给出趋势标签和动能标签

输出字段：

```python
technicals
```

### Fundamental Agent

文件：`financial_agent/agents/fundamental_agent.py`

工具：`financial_agent/tools/fundamentals.py`

职责：

- 使用 yfinance `info` 和 `fast_info` 获取基本面数据
- 整理估值、增长、盈利能力、分红和分析师预期
- 生成基本面亮点和风险
- 支持 partial fallback：`info` 失败时尽量使用 `fast_info`

输出字段：

```python
fundamentals
```

主要指标：

- 市值
- Trailing PE / Forward PE
- PS / PB
- EPS
- 营收增长
- 毛利率 / 净利率 / 经营利润率
- 分红率
- 分析师目标价
- 分析师一致预期
- 财报日期与 past/future 上下文

### News & Risk Agent

文件：`financial_agent/agents/news_risk_agent.py`

工具：`financial_agent/tools/news.py`

职责：

- 使用 yfinance 新闻数据获取近期新闻线索
- 提取标题、来源、日期和链接
- 根据技术面、行情和基本面风险生成风险清单

输出字段：

```python
news
risks
```

### Bull Agent

文件：`financial_agent/agents/bull_agent.py`

职责：

- 构建看多论据
- 使用行情、趋势、RSI、MACD、新闻热度和基本面亮点
- 输出看多置信度和看多观点薄弱点

输出字段：

```python
bull_case
```

### Bear Agent

文件：`financial_agent/agents/bear_agent.py`

职责：

- 构建看空论据
- 使用短线回撤、MACD 转弱、估值压力、增长承压、目标价下行和风险清单
- 输出看空置信度和看空观点反驳点

输出字段：

```python
bear_case
```

### Committee Agent

文件：`financial_agent/agents/committee_agent.py`

职责：

- 比较 Bull Agent 与 Bear Agent 的置信度和核心论据
- 给出最终评级
- 给出最终置信度
- 总结最大不确定性

评级范围：

```text
偏多 / 中性偏多 / 中性 / 中性偏空 / 偏空
```

输出字段：

```python
committee_view
```

### Portfolio Agent

文件：`financial_agent/agents/portfolio_agent.py`

工具：`financial_agent/tools/watchlist.py`

职责：

- 维护本地观察池 `outputs/watchlist/watchlist.json`
- 根据投委会评级、置信度、近期涨跌幅、风险数量、新闻数量和历史复盘结果计算跟踪优先级
- 给当前标的打上组合角色，例如进攻观察、趋势跟踪、中性跟踪、防守观察、风险警戒
- 检查观察池里是否已有同板块标的，提示赛道集中度
- 输出观察池 Top 5，帮助用户知道下一步优先复盘哪些股票

输出字段：

```python
portfolio
```

### Report Agent

文件：`financial_agent/agents/report_agent.py`

职责：

- 汇总所有结构化状态
- 生成中文短线投研报告
- 如果配置了 LLM，则使用模型生成报告
- 如果没有配置 LLM，则使用规则模板兜底
- 保存 Markdown 报告到 `outputs/reports/`

报告包含：

- 投资结论
- 投委会综合判断
- 历史复盘
- 组合观察池
- 行情摘要
- 技术面判断
- 基本面与估值
- 多空观点对比
- 新闻与催化
- 主要风险
- 后续观察指标
- 资料线索

### Verifier Agent

文件：`financial_agent/agents/verifier_agent.py`

职责：

- 对最终报告做本地规则质检
- 不额外调用 LLM，避免质检阶段产生新幻觉
- 检查评级一致性、关键数字、财报日期语义、投资建议措辞和资料线索
- 在报告末尾追加质量检查结果
- 保存质检版报告到 `outputs/reports/*_verified_*.md`

输出字段：

```python
verification
```

质量状态：

```text
pass / warning / fail
```

### History Agent

文件：`financial_agent/agents/history_agent.py`

工具：`financial_agent/tools/history.py`

职责：

- 在 Verifier Agent 之后保存本次分析记录
- 使用本地 JSONL 文件作为轻量历史库
- 每个 ticker 一个文件：`outputs/history/{ticker}.jsonl`

保存字段：

```python
timestamp
ticker
company_name
horizon
price
rating
confidence
portfolio_priority
portfolio_score
portfolio_role
verification_status
report_path
```

## 状态对象

LangGraph 中的核心状态定义在 `financial_agent/graph/state.py`。

```python
class ResearchState(TypedDict, total=False):
    user_query: str
    ticker: str
    company_name: str
    market: str
    horizon: str
    ticker_resolution: dict[str, Any]
    analysis_modules: list[str]
    market_data: dict[str, Any]
    review: dict[str, Any]
    technicals: dict[str, Any]
    fundamentals: dict[str, Any]
    news: list[dict[str, Any]]
    risks: list[str]
    bull_case: dict[str, Any]
    bear_case: dict[str, Any]
    committee_view: dict[str, Any]
    portfolio: dict[str, Any]
    verification: dict[str, Any]
    history_record: dict[str, Any]
    agent_notes: list[dict[str, str]]
    final_report: str
    errors: list[str]
```

## 数据流

```text
user_query
  ↓
Intent Router: help intent or research intent
  ├─ Help Intent: capability guide / examples
  ↓
Coordinator: ticker / horizon
  ├─ Missing ticker: ask user for ticker and stop
  ├─ Non-research: explain scope and stop
  ↓
Market: price series / returns
  ↓
Review: previous rating / price performance
  ↓
Technical: MA / RSI / MACD
  ↓
Fundamental: valuation / growth / margins / analyst view
  ↓
News & Risk: news links / risk list
  ↓
Bull: bullish arguments
  ↓
Bear: bearish arguments
  ↓
Committee: final rating
  ↓
Portfolio: watchlist priority / portfolio role
  ↓
Report: markdown report
  ↓
Verifier: quality check
  ↓
History: append JSONL record
```

## 目录结构

```text
.
├── app.py
├── financial_agent
│   ├── agents
│   │   ├── bear_agent.py
│   │   ├── bull_agent.py
│   │   ├── committee_agent.py
│   │   ├── coordinator.py
│   │   ├── fundamental_agent.py
│   │   ├── market_agent.py
│   │   ├── news_risk_agent.py
│   │   ├── portfolio_agent.py
│   │   ├── report_agent.py
│   │   ├── review_agent.py
│   │   ├── technical_agent.py
│   │   ├── verifier_agent.py
│   │   └── history_agent.py
│   ├── graph
│   │   ├── state.py
│   │   └── workflow.py
│   ├── tools
│   │   ├── charting.py
│   │   ├── fundamentals.py
│   │   ├── history.py
│   │   ├── indicators.py
│   │   ├── market_data.py
│   │   ├── news.py
│   │   └── watchlist.py
│   ├── cli.py
│   ├── help.py
│   ├── llm.py
│   └── settings.py
├── outputs
│   ├── history
│   ├── reports
│   └── watchlist
├── PROJECT_PLAN.md
├── requirements.txt
└── .env.example
```

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## LLM 配置

如果要使用 LLM 报告生成，在 `.env` 中设置一个 OpenAI-compatible provider。

同一时间只启用一个 provider。想保留另一个 provider 的配置时，把它前面加 `#` 注释掉。

### OpenAI

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=
```

### DeepSeek

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=high
```

### MiniMax

```bash
LLM_PROVIDER=minimax
MINIMAX_API_KEY=your_minimax_api_key
LLM_MODEL=MiniMax-M2.7
LLM_BASE_URL=https://api.minimax.io/v1
MINIMAX_REASONING_SPLIT=false
```

## 运行

启动 Chainlit：

```bash
chainlit run app.py
```

打开：

```text
http://localhost:8000
```

命令行测试：

```bash
python -m financial_agent.cli "帮我分析一下 NVDA 未来一个月走势"
python -m financial_agent.cli "查看观察池"
```

示例问题：

```text
你能做什么
查看观察池
观察池里优先级最高的是谁
帮我分析一下英伟达未来一个月走势
帮我分析一下闪迪今天走势
帮我看看博通未来一个月是偏多还是偏空
```

## 当前能力

- 中文自然语言输入
- Help Intent：用户问“你能做什么 / 怎么用 / 帮助”时直接返回功能说明
- Watchlist Intent：用户问“查看观察池 / 我的 watchlist / 优先级最高”时直接返回观察池表格
- 早停路由：无法识别 ticker 或问题不是股票投研时，不启动后续分析 Agent
- 规则 + LLM fallback ticker 识别
- 美股行情拉取
- 技术指标计算
- 基本面与估值整理
- 新闻线索和来源链接展示
- 多空观点生成
- 投委会评级
- 本地观察池和组合优先级
- 中文报告生成
- 报告质量检查
- 历史报告复盘
- Plotly 价格图展示
- Markdown 报告保存

## 已知限制

- 数据主要来自 yfinance，数据完整性和稳定性取决于 Yahoo Finance
- 基本面数据可能出现 partial fallback
- 新闻质量取决于 yfinance 返回结果，可能包含相关但不完全聚焦的文章
- Verifier 当前是规则质检，不会自动重写报告
- 历史记录和观察池当前使用本地文件，不支持多用户隔离
- 当前主要面向美股，A 股和港股 ticker 支持有限

## 后续路线

- Watchlist Dashboard：展示观察池、优先级变化和最近复盘结果
- RAG：接入 10-K / 10-Q / earnings call transcript
- MCP：统一封装行情、新闻、财报、RAG 和报告导出工具
- PDF 导出
- FastAPI + Next.js 产品化前端
