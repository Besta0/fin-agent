# Multi-Agent Research MVP

一个基于 **Chainlit + LangGraph** 的中文多 Agent 投研助手 MVP。

项目目标：用户输入一句股票分析问题，系统模拟一个小型投研团队，完成任务解析、行情分析、技术指标计算、新闻/风险整理，并生成中文投研报告。

> 免责声明：本项目仅用于学习和研究 Agent 架构，不构成投资建议。

## 为什么这个项目有价值

普通投资研究通常需要在行情网站、新闻网站、财报页面和图表工具之间来回切换。这个项目把流程收敛成一个可解释的 Agent 工作流：

- **Coordinator Agent**：识别股票、市场、分析周期和任务目标
- **Market Agent**：获取价格、涨跌幅、成交量和区间表现
- **Technical Agent**：计算 MA、RSI、MACD 等技术指标
- **News & Risk Agent**：整理近期新闻和主要风险
- **Report Agent**：生成结构化中文投研报告

它吸引人的地方不是“让 AI 猜涨跌”，而是把投研流程变成可追踪、可扩展、可展示的系统。

## 技术栈

- Frontend: Chainlit
- Agent Orchestration: LangGraph
- Data: yfinance
- Indicators: pandas
- Charts: Plotly
- LLM: OpenAI-compatible via `langchain-openai`

## 项目结构

```text
.
├── app.py
├── financial_agent
│   ├── agents
│   ├── graph
│   ├── tools
│   ├── cli.py
│   ├── llm.py
│   └── settings.py
├── outputs
│   └── reports
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

如果要使用 LLM 报告生成，在 `.env` 中设置一个 OpenAI-compatible provider。

OpenAI:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=
```

DeepSeek:

```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=your_deepseek_api_key
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
```

MiniMax:

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your_minimax_api_key
LLM_MODEL=MiniMax-M2.7
LLM_BASE_URL=https://api.minimax.io/v1
```

启动 Chainlit：

```bash
chainlit run app.py
```

命令行测试：

```bash
python -m financial_agent.cli "帮我分析一下 NVDA 未来一个月走势"
```

## MVP 范围

第一版重点是跑通完整闭环：

```text
用户问题
  ↓
Coordinator Agent
  ↓
Market Agent
  ↓
Technical Agent
  ↓
News & Risk Agent
  ↓
Report Agent
  ↓
中文投研报告
```

## 后续升级方向

- 加入 Bull Agent / Bear Agent 多空辩论
- 接入 SEC filings、财报电话会 transcript 和研报 RAG
- 用 MCP 统一封装行情、新闻、财报和报告导出工具
- 增加 watchlist、历史报告、定时日报
- 从 Chainlit 升级到 Next.js / FastAPI 产品化前端
