# 法眼 · Fayan — AI Contract Review Agent

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b.svg)](https://streamlit.io/)
[![Model](https://img.shields.io/badge/Model-Qwen--Plus-6c47ff.svg)](https://dashscope.console.aliyun.com/)
[![MCP](https://img.shields.io/badge/Protocol-MCP-orange.svg)](https://modelcontextprotocol.io/)

> 不只是"把合同丢给 GPT"——一个真正会查法规、找判例、逐条分析、自主决策审查步骤的 ReAct Agent。

> Not just "throw a contract at GPT" — a ReAct Agent that actually searches regulations, finds case law, analyzes clause by clause, and decides its own review strategy.

---

## 为什么是法眼 / Why Fayan

把合同丢给 ChatGPT，你会得到一份"看起来不错"但不知道引用了什么法条、有没有幻觉的分析。

法眼做的不一样：

```
裸调 LLM：    合同全文 → GPT → 审查报告（一次性，不可验证）
法眼 Agent：  合同全文 → 提取条款 → 查法规 → 查判例 → 查地方政策
                        → 查税务 → 逐条三维评分 → 完整性检查
                        → 视角切换 → 汇总报告（12-15 轮，每轮可追溯）
```

## 架构 / Architecture

```
                        ┌─────────────────────┐
                        │   ReAct Agent 主循环  │
                        │   思考 → 行动 → 观察   │
                        │   （20 轮迭代上限）    │
                        └──────────┬──────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
     ┌──────▼──────┐       ┌──────▼──────┐       ┌──────▼──────┐
     │   合同处理    │       │   知识检索    │       │   分析生成    │
     │ extract_clauses│     │ search_regulation│   │ analyze_single_clause│
     │ (OCR 照片→文本)│      │ search_case_law │    │ check_completeness│
     │              │       │ check_local_policy│  │ switch_perspective│
     │              │       │ lookup_tax_rule │    │ generate_final_report│
     │              │       │ web_search      │       │              │
     └──────────────┘       └──────┬──────────┘       └──────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
             ┌──────▼──────┐ ┌────▼────┐ ┌──────▼──────┐
             │  法规原文库   │ │ 判例库  │ │ 地方政策+税务│
             │ 民法典+司法解释│ │ 52个判例│ │ 5城×税务主题 │
             │  + 行政法规   │ │         │ │              │
             └──────────────┘ └─────────┘ └──────────────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │  RAG 混合检索引擎   │
                         │  向量语义 + 关键词兜底 │
                         │  + 去重融合          │
                         └───────────────────┘
```

## 能查出什么 / What It Finds

用附件里的 `sample_cooperation.txt`（合作协议）跑一次，法眼会告诉你：

| 风险等级 | 发现 |
|---------|------|
| 高风险 | 分成比例可单方调整——对方可随时改规则 |
| 高风险 | "扣除直接成本后分成"——成本定义不明确，无审计上限 |
| 高风险 | 争议解决条款缺失——出了纠纷不知道去哪告 |
| 中风险 | 知识产权归属模糊——合作产出归谁没说清 |
| 中风险 | 无效力存续条款——如果一方公司注销，合同怎么办 |
| ... | 共 3 高风险 + 8 中风险，审查耗时 13 轮 |

## vs. 裸调 GPT 的真实差距 / Not Just Another GPT Wrapper

| | 裸调 GPT | 法眼 |
|---|---|---|
| 审查过程 | 黑盒，不可追溯 | 每轮工具调用可见，可审计 |
| 法规引用 | 可能幻觉/编造 | 内置法规原文检索，引用真实条文 |
| 地方差异 | 不知道 | 北京/上海/深圳/广州/成都政策分城检索 |
| 税务影响 | 基本不覆盖 | 增值税/个税/印花税/契税专项检索 |
| 对立视角 | 单视角 | `switch_perspective` 切换对方视角再审查一次 |
| 报告一致性 | 每次跑结果不同 | 五段式模板 + 去重逻辑 + 评分自洽约束 |
| 审查深度 | 1 轮完成 | 12-15 轮逐步深入 |

## 快速开始 / Quick Start

```bash
git clone https://github.com/pppppgy/fayan-contract-review.git
cd fayan-contract-review

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY（从 dashscope.console.aliyun.com 获取）

# Web 界面
streamlit run app.py

# 或命令行
python main.py sample_cooperation.txt "合作协议"
```

浏览器打开 http://localhost:8501

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

## MCP 协议支持 / MCP Protocol

法眼的 5 个搜索工具已封装为 MCP Server，可被 Claude Code、Cursor 等 AI 工具直接调用：

```bash
python mcp_server.py
```

在 Claude Code 的 `.mcp.json` 中配置：

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

## 支持的合同类型 / Supported Types

房屋租赁 · 劳动合同 · 买卖合同 · 服务合同 · 合作协议 · 借款合同

## 审查报告格式 / Report Format

```
1. 总体风险概览 — 高/中/低风险计数 + 综合评分（1-10）
2. 高风险条款详解 — 原文 + 风险说明 + 法条依据 + 修改建议
3. 需关注的中风险条款 — 同上格式
4. 修改优先级建议 — P0 / P1 / P2 分级
5. 签约建议 — 可签 / 修改后签 / 不建议签
```

## 项目结构 / Project Structure

```
contract_review/
├── app.py                # Streamlit Web 界面
├── main.py               # Agent ReAct 主循环（20 轮迭代）
├── llm_client.py         # LLM 客户端（OpenAI 兼容 API）
├── prompts.py            # 全部提示词（Agent/分析/报告/完整性）
├── tools.py              # 10 个工具 + 4 大知识库
├── mcp_server.py         # MCP 协议 Server
├── ocr_utils.py          # 合同照片 OCR（qwen-vl-plus）
├── rag/
│   ├── indexer.py        # 知识库构建（分块→嵌入→索引）
│   ├── embedder.py       # 向量嵌入
│   ├── vector_store.py   # ChromaDB 向量存储
│   └── retriever.py      # 混合检索（向量+关键词+去重）
├── sample_cooperation.txt
├── sample_lease.txt
├── sample_employment.txt
├── sample_sales.txt
├── sample_service.txt
├── sample_loan.txt
└── .env.example
```

## 部署 / Deploy

```bash
# Docker
docker build -t fayan .
docker run -p 8501:8501 -e DASHSCOPE_API_KEY=sk-xxx fayan
```

## 技术栈 / Tech Stack

- **模型**: 阿里云百炼 Qwen-Plus + Qwen-VL-Plus（OpenAI 兼容 API）
- **Agent**: ReAct 模式（思考 → 行动 → 观察循环）
- **RAG**: 向量语义检索 + 关键词兜底 + 去重融合（ChromaDB）
- **UI**: Streamlit（Legal Editorial 设计风格）
- **协议**: MCP（Model Context Protocol）标准化工具接口
- **部署**: Docker + Streamlit Cloud

## 踩坑实录 / Lessons Learned

这个项目经历了 5 个让我怀疑人生的 Bug，完整复盘见：[博客草稿-法眼项目技术复盘.md](./博客草稿-法眼项目技术复盘.md)

1. **qwen-plus 的 JSON 地狱**（8 轮迭代 → 文本格式工具调用绕过）
2. **DeepSeek 的 Markdown 执念**（JSON 完美但死也要输出 Markdown）
3. **提示词"铁律"污染报告**（内部约束被逐字输出给用户）
4. **Agent 自我总结覆盖工具结果**（`last_report` 无条件优先）
5. **13 种合同类型回退到 6 种**（少即是多：提示词越短，格式越稳）

## License

MIT
