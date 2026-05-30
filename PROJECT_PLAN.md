# Multi-Agent 投研系统项目计划

## 1. 项目定位

本项目是一个面向中文用户的多 Agent 投研助手，使用 LangGraph 编排多个专业 Agent，并通过 Chainlit 展示 Agent 的执行过程。

一句话介绍：

> 输入一句股票分析问题，系统自动拆解任务，调用行情和技术指标工具，由多个 Agent 分工分析，最终生成结构化中文投研报告。

## 2. 项目为什么吸引人

普通股票研究流程非常碎片化：用户需要查行情、看新闻、算指标、找风险、整理报告。这个项目把这些步骤组织成一个“AI 投研团队”，让用户看到每个 Agent 的分工和中间结论。

核心吸引力：

- **多 Agent 分工直观**：不是一个黑盒聊天机器人，而是一个投研团队。
- **流程可解释**：用户能看到 Coordinator、Market、Review、Technical、Fundamental、Risk、Bull、Bear、Committee、Portfolio、Report、Verifier、History 各自做了什么。
- **新手友好**：用户问“你能做什么 / 怎么用 / 帮助”时，系统直接返回能力说明和示例问题，不会误进入投研流程。
- **数据和推理结合**：行情数据、技术指标和 LLM 总结形成闭环。
- **适合展示工程能力**：覆盖 LangGraph、工具调用、结构化状态、Chainlit UI 和后续 RAG/MCP 扩展。
- **可产品化**：观察池、历史复盘、日报、PDF 报告、财报 RAG 和 Next.js 工作台都可以沿着同一套状态流继续扩展。

## 3. MVP 目标

第一版只解决一个清晰问题：

> 用户输入美股 ticker 或自然语言问题，系统在一个 Chainlit 会话中生成中文短线投研报告。

示例输入：

```text
帮我分析一下 NVDA 未来一个月走势
```

示例输出：

```text
结论：中性偏多
置信度：62%

核心理由：
1. 近一个月走势偏强。
2. 价格仍在关键均线附近或上方。
3. RSI 和 MACD 显示短线动能状态。
4. 风险主要来自估值、财报预期和宏观风险。
```

## 4. MVP Agent 设计

### Coordinator Agent

职责：

- 解析用户输入
- 识别 ticker
- 识别分析周期
- 设定分析模块

当前实现：

- 支持常见中文公司名映射，例如英伟达、苹果、特斯拉、微软。
- 支持直接输入美股 ticker，例如 NVDA、AAPL、TSLA。
- 如果问题不是股票投研请求，直接返回范围说明，不启动后续 Agent。
- 如果问题像投研请求但缺少明确 ticker，直接请用户补充标的，不启动后续 Agent。

### Market Agent

职责：

- 使用 yfinance 获取历史行情
- 计算最新价格、成交量、52 周区间和阶段涨跌幅

当前实现：

- 近 1 日、5 日、1 月、3 月、6 月涨跌幅
- 最近 180 个交易日价格序列

### Memory Agent

职责：

- 读取和更新用户偏好记忆
- 按用户隔离检索历史语义记忆
- 为后续 Agent 提供个性化上下文

当前实现：

- 使用 `outputs/users/{user_id}/memory/preferences.json` 保存偏好
- 使用 `outputs/users/{user_id}/memory/semantic_memory.jsonl` 保存历史报告摘要
- 使用 `outputs/users/{user_id}/memory/vector_memory.sqlite` 保存 Hash/TF-IDF 向量记忆
- 支持“记住我偏好短线，只看科技股”
- 支持“以前分析过 NVDA 吗 / 查一下历史报告”
- 优先使用 SQLite + 本地 TF-IDF/Hash Embedding 检索，JSONL 作为兼容备份
- 自动生成 `memory_context`：
  - `ticker_history`：同标的历史观点
  - `semantic_memories`：语义相似历史报告
  - `report_references`：可进入报告正文的可追溯引用
  - `memory_guidance`：关注点、延续风险、历史 thesis、上次评级和旧报告路径
- 在用户未明确周期时，使用偏好记忆补全默认 horizon
- 为 Committee Agent 提供观点变化依据，为 Report Agent 提供历史记忆参考

### Review Agent

职责：

- 读取同 ticker 最近一次历史记录
- 对比上次评级、上次价格和当前价格
- 判断上次观点是否兑现
- 给本次分析提供复盘提醒

当前实现：

- 使用本地 `outputs/history/{ticker}.jsonl`
- 如果没有历史记录，输出“本次为首条记录”
- 如果有历史记录，输出上次评级、上次价格、当前价格、期间涨跌幅和兑现情况

### Technical Agent

职责：

- 基于价格序列计算技术指标
- 输出趋势状态

当前实现：

- MA5 / MA20 / MA60
- RSI(14)
- MACD / Signal / Histogram
- 趋势标签

### News & Risk Agent

职责：

- 获取近期新闻线索
- 根据行情和技术面生成风险点

当前实现：

- 优先使用 yfinance 新闻
- 如果新闻不可用，报告中明确说明暂无数据
- 根据 RSI、近 1 月涨跌幅、基本面风险和通用金融风险生成风险清单

### Fundamental Agent

职责：

- 获取估值、盈利能力、增长、分红和分析师预期
- 生成基本面亮点和风险
- 为 Bull / Bear / Committee 提供基本面信号

当前实现：

- 使用 `yfinance.Ticker(ticker).info` 和 `fast_info`
- 输出市值、PE、Forward PE、PS、PB、EPS、营收增长、利润率、目标价、分析师一致预期等指标
- 基于增长、利润率、估值和目标价生成结构化亮点与风险

### Bull Agent

职责：

- 从行情、趋势、技术指标和新闻中提取看多论据
- 说明看多观点的薄弱点
- 输出看多置信度

当前实现：

- 基于近 5 日 / 1 月涨跌幅、均线趋势、RSI、MACD、新闻热度和基本面亮点生成规则型看多观点
- 即使 LLM 不可用，也能稳定输出结构化观点

### Bear Agent

职责：

- 从回撤、过热、动能转弱和风险清单中提取看空论据
- 说明看空观点可能被反驳的地方
- 输出看空置信度

当前实现：

- 基于近 1 日 / 5 日回撤、近 1 月涨幅、RSI、MACD、估值压力和风险清单生成规则型看空观点

### Committee Agent

职责：

- 比较 Bull Agent 和 Bear Agent 的论据强度
- 给出最终评级和置信度
- 总结最大不确定性

当前实现：

- 根据多空置信度差值输出 偏多 / 中性偏多 / 中性 / 中性偏空 / 偏空
- Report Agent 会优先使用投委会结论作为最终评级

### Portfolio Agent

职责：

- 维护本地观察池
- 根据本次分析结果给标的排序
- 判断当前标的在组合中的角色
- 提醒同板块标的集中度

当前实现：

- 使用 `outputs/watchlist/watchlist.json` 保存观察池
- 根据投委会评级、置信度、近 1 日 / 近 1 月涨跌幅、风险数量、新闻数量和历史复盘结果计算 `priority_score`
- 输出 核心跟踪 / 高优先级 / 常规观察 / 低优先级 / 风险警戒
- 输出 进攻观察 / 趋势跟踪 / 中性跟踪 / 防守观察 / 风险警戒 等组合角色
- 在 Chainlit 中展示观察池 Top 5

### Dashboard

职责：

- 把观察池、记忆库和最近报告聚合成投研工作台
- 给用户一个从“聊天”进入“产品界面”的入口
- 输出下一步可复制动作，降低用户不知道该问什么的成本

当前实现：

- 使用 `financial_agent/tools/dashboard.py` 渲染 Markdown 工作台
- 支持 `投研工作台`、`dashboard`、`/dashboard`、`仪表盘` 等 direct intent
- 展示观察池 Top 标的、SQLite 向量记忆数量、JSONL 语义备份数量、最近向量记忆和最近报告
- Chainlit 和 CLI 共用同一套 dashboard 渲染逻辑

### Report Browser

职责：

- 把本地 Markdown 报告变成可直接阅读的报告详情页
- 支持从工作台进入最近报告或某个 ticker 的最新报告
- 让用户能快速看到结论、历史记忆引用、质量检查和下一步动作

当前实现：

- 使用 `financial_agent/tools/report_browser.py` 读取 `outputs/users/{user_id}/reports/*.md`
- 支持 `打开最近报告`、`打开 NVDA 报告`、`报告列表`
- 优先打开最新质检版报告
- 渲染产品化报告库：按时间展示最近报告，并显示评级、置信度、分析周期、价格、质检状态和资料链接数量
- 渲染产品化报告阅读页：结论面板、市场与技术、基本面、多空与投委会、风险与观察指标、新闻线索、历史记忆与观察池、质量检查、正文目录和下一步动作
- 自动提取评级、置信度、分析周期、市场、行业、价格、质检状态和资料链接
- 支持中英文公司别名，例如 `打开英伟达报告`、`打开闪迪报告`
- Chainlit 报告库提供操作按钮：打开最近、投研工作台、模型设置、分析 NVDA
- Chainlit 报告页提供操作按钮：重新分析、报告列表、投研工作台、观察池、模型设置
- Chainlit 和 CLI 共用同一套 report browser 渲染逻辑

### Settings Panel

职责：

- 展示当前 LLM provider、model、base_url 和 API key 配置状态
- 隐藏完整 API key，避免把密钥写进聊天记录
- 给用户一个自助排查模型连接的入口
- 提供 OpenAI、DeepSeek、MiniMax、小米 MiMo 配置模板

当前实现：

- 使用 `financial_agent/tools/settings_panel.py` 渲染设置面板
- 支持 `模型设置`、`查看模型配置`、`小米配置`、`测试模型连接`
- Chainlit 首页提供 starter cards 和快捷按钮，侧边栏 Chat Settings 支持用户配置 provider、model、base_url、API key 和 temperature
- Model 下拉选项跟随 provider 动态刷新，Base URL 也会跟随 provider 自动切换默认值
- 用户 API key 只保存在当前 Python 进程的会话内存中，不写入 `.env`、报告或记忆库
- 使用 `contextvars` 为每次请求注入会话级 LLMConfig，避免多用户之间串模型配置
- 内置 provider：OpenAI、DeepSeek、MiniMax、Xiaomi MiMo
- Xiaomi MiMo 支持 `LLM_PROVIDER=xiaomi` 或 `LLM_PROVIDER=mimo`
- Xiaomi MiMo 默认 `LLM_BASE_URL=https://api.xiaomimimo.com/v1`，默认模型 `mimo-v2.5-pro`
- Chainlit 和 CLI 共用同一套 settings panel 渲染逻辑

### Product Home

职责：

- 让用户打开应用后先看到产品化首页，而不是长帮助文本
- 展示当前模型配置、研究资产数量、工作流阶段和可点击动作
- 提供更像投研 SaaS 的默认视觉体验

当前实现：

- `app.py` 中 `_format_product_home()` 渲染 Home
- 首页快捷动作支持分析 NVDA、模型设置、测试连接、最近报告、投研工作台和能力指南
- `public/fin-agent.css` 覆盖 Chainlit 默认样式，优化表格、按钮、输入框和工作台观感
- `.chainlit/config.toml` 启用 wide layout、light theme 和 custom CSS

### Report Agent

职责：

- 汇总所有 Agent 输出
- 生成中文投研报告
- 保存 Markdown 报告

当前实现：

- 有可用 LLM provider API key 时使用模型生成报告
- 没有 API key 时使用规则模板兜底
- 自动保存到 `outputs/reports/`

### Verifier Agent

职责：

- 检查最终报告是否和结构化数据矛盾
- 检查投委会评级是否被保留
- 检查财报日期语义、投资建议措辞、资料线索和关键数字
- 在报告末尾追加质量检查结果

当前实现：

- 使用本地规则检查，不额外调用 LLM
- 输出 `pass` / `warning` / `fail`
- 检查历史记忆引用是否包含摘要、相似度、检索后端和旧报告路径
- 将质检后的报告保存为 `outputs/users/{user_id}/reports/*_verified_*.md`

### History Agent

职责：

- 在质检完成后保存本次分析摘要
- 为下一次 Review Agent 复盘提供输入

当前实现：

- 每个用户、每个 ticker 使用一个 JSONL 文件
- 保存 timestamp、ticker、horizon、price、rating、confidence、portfolio_priority、portfolio_score、portfolio_role、verification_status 和 report_path
- 同步写入 JSONL 语义记忆和 SQLite 向量记忆，供后续 RAG 检索

## 5. 当前技术架构

```text
Chainlit UI
  ↓
Intent Router
  ├─ Help Intent → 能力说明和示例问题
  ├─ Dashboard Intent → 投研工作台
  ├─ Report Browser Intent → 报告详情 / 报告列表
  ├─ Settings Intent → 模型设置 / 连接测试
  ├─ Watchlist Intent → 观察池表格
  ├─ Watchlist Detail Intent → 单个标的跟踪理由
  ↓
LangGraph Workflow
  ↓
Coordinator Agent
  ├─ Missing ticker / non-research → 直接回复并结束
  ↓
Memory Agent
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
中文报告 + Plotly 图表
```

## 6. 二期升级

二期目标是把 MVP 从“短线分析助手”升级成“更像投研团队”的系统。

下一批新增 Agent / 能力：

- **Watchlist Dashboard**：支持在前端查看多个股票的优先级和最近复盘状态

新增能力：

- 观察池排序变化和优先级提醒
- SEC filings 检索
- 财报电话会 transcript 检索
- 公司基本面数据
- 多空辩论过程展示
- 报告导出 PDF

## 7. 三期升级：RAG

RAG 适合解决“历史资料和内部知识”问题。

可加入的数据：

- 财报 PDF
- 10-K / 10-Q
- 财报电话会 transcript
- 行业研报摘要
- 用户自己的投资笔记
- 历史报告和历史决策日志

推荐架构：

```text
Document Loader
  ↓
Chunking
  ↓
Embedding
  ↓
Vector DB
  ↓
Fundamental / Risk / Committee Agent
```

向量库选择：

- 本地 MVP：Chroma / FAISS
- 产品化：Qdrant / pgvector

## 8. 四期升级：MCP

MCP 可以作为统一工具层，让 Agent 不直接耦合外部服务。

可拆分 MCP server：

- `market-data-server`：行情、历史价格、估值数据
- `news-server`：新闻搜索、新闻正文抓取
- `filing-server`：SEC filings、财报检索
- `rag-server`：向量检索
- `report-server`：Markdown / PDF / 邮件导出

目标架构：

```text
LangGraph Agents
  ↓
MCP Tool Layer
  ↓
Market / News / Filing / RAG / Report Services
```

## 9. 作品集表达

可以在简历或项目介绍中这样写：

> 构建了一个基于 LangGraph 和 Chainlit 的中文多 Agent 投研系统，模拟真实投研团队的分工协作流程。系统能够自动解析用户投资问题，调用行情和技术指标工具，并由多个专业 Agent 完成市场、技术面、风险审查和报告撰写，最终生成结构化中文投研报告。项目支持 LLM 报告生成、规则兜底、Agent 执行过程可视化，并预留 RAG 与 MCP 扩展接口。

短版：

> 一个能自动完成“识别股票、查行情、算指标、找风险、写报告”的 AI 投研团队。
