# 法眼 · Fayan — AI Contract Review Agent

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b.svg)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/Agent-LangGraph-6c47ff.svg)](https://langchain.com/langgraph)
[![Redis](https://img.shields.io/badge/Cache-Redis-red.svg)](https://redis.io/)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue.svg)](https://github.com/Nakoem/fayan-contract-review/actions)
[![MCP](https://img.shields.io/badge/Protocol-MCP-orange.svg)](https://modelcontextprotocol.io/)

> 不只是"把合同丢给 GPT"——Supervisor 协调 5 个专业 Agent，真正会查法规、找判例、逐条分析的多 Agent 审查引擎。
>
> Not just "throw a contract at GPT" — a Supervisor-coordinated multi-agent pipeline that searches regulations, finds case law, analyzes clause by clause, and decides its own review strategy.

---

## 为什么是法眼 / Why Fayan

```
裸调 LLM：    合同全文 → GPT → 审查报告（一次性，不可验证）
法眼 Agent：  合同全文 → 提取条款 → 查法规 → 查判例 → 查地方政策
                        → 查税务 → 逐条三维评分 → 完整性检查
                        → 视角切换 → 汇总报告（12-15 轮，每轮可追溯）
```

法眼做的不一样：每一步工具调用都可见，每条法规引用都真实可查，每个风险判断都有法条依据。

---

## 新特性 / What's New

- **Redis 缓存层** — 同合同不重复审查，15份历史报告预热69条法规热点，秒级返回
- **LangGraph 引擎** — `agent_langgraph.py` 自定义 StateGraph，替代 `create_react_agent`
- **流式审查** — `StreamingReviewRunner` 实时输出思考过程，不再黑盒等待
- **CI/CD** — GitHub Actions 自动 Ruff 检查
- **FastAPI 接口** — `api.py` 提供 REST API，告别纯命令行
- **代码重构** — 业务逻辑抽离至 `service.py`，工具函数收拢至 `utils.py`

---

## 架构 / Architecture

Supervisor 协调 5 个专业 Agent 的流水线，支持 SqliteSaver 断点恢复。

```
                         ┌──────────────────┐
                         │   🧭 Supervisor   │
                         │   质量判断 + 路由   │
                         └────────┬─────────┘
                                  │
        ┌─────────────┬───────────┼───────────┬──────────┐
        │             │           │           │          │
   ┌────▼────┐  ┌─────▼────┐ ┌───▼───┐ ┌─────▼────┐ ┌───▼───┐
   │📄 提取   │  │📚 法规   │ │⚖️ 评估 │ │🪞 反思   │ │📝 报告 │
   │ Agent   │→│ Agent    │→│ Agent  │→│ Agent    │→│ Agent  │
   │ 条款结构化│  │ 法条+判例 │ │ 三维评分│ │ 视角切换  │ │ 汇总输出│
   └─────────┘  └──────────┘ └───┬───┘ └────┬────┘ └───┬───┘
                                 │          │          │
                                 │   ┌──────┘          │
                                 │   │ 质量不通过→回退   │
                                 │   ▼                 │
                                 │ 🧭 Supervisor       │
                                 │ 通过 → 继续          │
                                 └─────────────────────┘
```

| 阶段 | Agent | 职责 |
|------|-------|------|
| 1. 提取 | `extraction_agent` | 从合同全文提取结构化条款 |
| 2. 法规 | `regulation_agent` | 按合同类型检索法规+判例+政策 |
| 3. 评估 | `assessment_agent` | 逐条三维评分（公平性/明确性/风险敞口） |
| 4. 反思 | `reflection_agent` | 视角切换 + 质量检查，不通过回退到评估 |
| 5. 报告 | `report_agent` | 汇总生成五段式审查报告 |

---

## 支持的合同类型 / Supported Types

房屋租赁 · 劳动合同 · 买卖合同 · 服务合同 · 合作协议 · 借款合同 · 自定义

---

## 审查报告格式 / Report Format

```
1. 总体风险概览 — 高/中/低风险计数 + 综合评分（1-100）
2. 高风险条款详解 — 原文 + 风险说明 + 法条依据 + 修改建议
3. 需关注的中风险条款 — 同上格式
4. 修改优先级建议 — P0 / P1 / P2 分级
5. 签约建议 — 可签 / 修改后签 / 不建议签
```

---

## 快速开始 / Quick Start

```bash
git clone https://github.com/Nakoem/fayan-contract-review.git
cd fayan-contract-review

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY（从 dashscope.console.aliyun.com 获取）
# 可选：配置 REDIS_HOST 等 Redis 参数（不配置则自动降级为无缓存）

# Web 界面
streamlit run app.py

# 或命令行
python main.py sample_lease.txt "房屋租赁合同"
```

浏览器打开 http://localhost:8501

### Redis 缓存（可选）

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
# 启动 app.py 时自动从 15 份历史报告预热缓存
```

---

## Agent 工具集 / 10 Tools

| 工具 | 功能 |
|------|------|
| `extract_clauses` | 从合同全文提取结构化条款（10 个类别） |
| `search_regulation` | 检索内置法规库（民法典 + 司法解释 + 行政法规） |
| `search_case_law` | 检索法院判例（52 个真实判例要点） |
| `check_local_policy` | 查询 5 城地方政策（北京/上海/深圳/广州/成都） |
| `lookup_tax_rule` | 查询税务规则（增值税/个税/印花税/租金专票等） |
| `web_search` | 联网搜索最新法规动态 |
| `analyze_single_clause` | 逐条三维评分（公平性/明确性/风险敞口） |
| `check_completeness` | 检查合同条款完整性，找出缺失项 |
| `switch_perspective` | 切换视角（出租方↔承租方，用人单位↔劳动者） |
| `generate_final_report` | 汇总生成五段式审查报告 |

---

## MCP 协议支持 / MCP Protocol

法眼的 5 个搜索工具已封装为 MCP Server，可被 Claude Code、Cursor 等 AI 工具直接调用：

```bash
python mcp_server.py
```

在 `.mcp.json` 中配置：

```json
{
  "mcpServers": {
    "fayan": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/contract_review"
    }
  }
}
```

---

## 项目结构 / Project Structure

```
contract_review/
├── app.py                  # Streamlit Web 界面
├── main.py                 # CLI 入口（调用 LangGraph 多Agent 引擎）
├── agent_langgraph.py      # LangGraph 自定义 StateGraph 引擎
├── api.py                  # FastAPI REST 接口
├── service.py              # 业务逻辑层（审查执行器、文件处理、报告统计）
├── llm_client.py           # LLM 客户端（OpenAI 兼容 API）
├── prompts.py              # 全部提示词（Agent/分析/报告/完整性）
├── tools.py                # 10 个工具 + 4 大知识库
├── cache.py                # Redis 缓存层 + 历史报告预热
├── utils.py                # 工具函数（报告清洗、格式校验）
├── logger.py               # 日志输出管理
├── chat_engine.py          # 对话引擎
├── evaluate.py             # 评估脚本
├── evaluate_helpers.py     # 评估辅助函数
├── mcp_server.py           # MCP 协议 Server
├── ocr_utils.py            # 合同照片 OCR（qwen-vl-plus）
├── rag/
│   ├── indexer.py          # 知识库构建（分块→嵌入→索引）
│   ├── embedder.py         # 向量嵌入
│   ├── vector_store.py     # ChromaDB 向量存储
│   └── retriever.py        # 混合检索（向量+关键词+去重）
├── scripts/               # 评估与基准测试脚本
│   ├── evaluate.py
│   ├── evaluate_helpers.py
│   ├── benchmark_consistency.py
│   └── known_risks/
├── tests/
│   └── test_smoke.py       # 冒烟测试
├── .github/workflows/
│   └── ci.yml              # GitHub Actions CI
├── 审查报告/               # 15份历史审查报告（预热数据源）
├── sample_lease.txt        # 样本合同 × 6
├── requirements.txt
└── .env.example
```

---

## 技术栈 / Tech Stack

- **模型**: 阿里云百炼 Qwen-Plus / DeepSeek V4（OpenAI 兼容 API）
- **Agent**: LangGraph Supervisor 多 Agent 流水线
- **RAG**: ChromaDB 向量语义检索 + 关键词兜底 + 去重融合
- **缓存**: Redis（自动降级，15份历史报告预热）
- **UI**: Streamlit（流式审查 + 历史管理）
- **API**: FastAPI REST 接口
- **协议**: MCP（Model Context Protocol）标准化工具接口
- **CI/CD**: GitHub Actions
- **部署**: Docker + Streamlit Cloud

---

## 踩坑实录 / Lessons Learned

完整复盘见：[知乎发布版-法眼项目技术复盘.md](./知乎发布版-法眼项目技术复盘.md)

1. **qwen-plus 的 JSON 地狱**（8 轮迭代 → 文本格式工具调用绕过）
2. **DeepSeek 的 Markdown 执念**（JSON 完美但死也要输出 Markdown）
3. **提示词"铁律"污染报告**（内部约束被逐字输出给用户）
4. **Agent 自我总结覆盖工具结果**（`last_report` 无条件优先）
5. **13 种合同类型回退到 6 种**（少即是多：提示词越短，格式越稳）

---

## License

MIT
