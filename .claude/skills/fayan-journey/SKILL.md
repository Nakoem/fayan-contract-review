---
name: fayan-journey
description: 法眼合同审查项目从0到1的完整历程记录，含 LangGraph 改写经验。当用户询问项目历程、开发步骤、技术演进或遇到类似问题时使用。
---

# 法眼 · 从 0 到 1 完整历程

## 项目概述

AI 合同审查 Agent，替代人工"读合同→查法规→写风控报告"。6种合同类型，10个工具，4重知识库（法规/判例/政策/税务），Web/CLI/API/MCP 四种使用方式。

**技术栈**：qwen-plus · ReAct Agent · LangGraph · RAG(ChromaDB) · Streamlit · FastAPI · Docker · MCP

---

## 开发历程

### Step 1：Coze 原型 → Python 迁移
- 最开始在 Coze 上搭固定工作流验证可行性
- 发现 Coze 灵活性不够 → 迁移到 Python + Streamlit
- 建立了第一个 Web 界面

### Step 2：Agent 架构
- 从三步流水线（提取→分析→报告）重构为 ReAct Agent
- LLM 自主决定每一步调哪个工具，20轮迭代上限
- 10个工具：extract_clauses / search_regulation / search_case_law / check_local_policy / lookup_tax_rule / web_search / analyze_single_clause / check_completeness / switch_perspective / generate_final_report

### Step 3：RAG 全链路
- 66条知识 → Chroma 向量库（216 chunks）
- DashScope Embedding 语义检索 + 关键词匹配兜底 + 去重融合
- 效果："押金不退"命中"押金退还"（关键词0%→语义91%）

### Step 4：模型选型
- 对比测试 4 个模型（qwen-plus / max / 3.6-plus / deepseek-v3.2）
- 定义 4 维评测标准，最终选 qwen-plus（性价比 + 指令遵循）
- 关键教训：选模型不是看跑分，是看在你具体任务上的"听话程度"

### Step 5：工程化 + 部署
- FastAPI REST + Docker 容器化
- loguru 日志 + Prompt YAML 版本管理
- 三维度自动化评估（格式/召回率/LLM裁判）
- MCP 协议：5 个法律搜索工具封装为 MCP Server

### Step 6：LangGraph 改写（新增）
- 用自定义 StateGraph 重构 Agent 循环
- 流程编排代码从 ~200 行缩减到 ~50 行
- 保留了所有 qwen 专有修复（JSON修复/文本模式兜底/API重试）
- 两版输出完全一致（temperature=0.0）验证改写不改质量
- 关键认知：框架省流程编排（~60%），省不掉模型特有问题（~40%）

---

## 核心踩坑

| 坑 | 教训 |
|---|---|
| qwen-plus JSON 参数格式错误 | 文本模式兜底（<<TOOL:name>>标签）绕过 Function Calling 校验 |
| DeepSeek Markdown 执念 | 选模型看"听话程度"不看能力参数 |
| 提示词铁律污染报告 | System Prompt 和 User Prompt 作用域是两回事 |
| Agent 总结覆盖工具结果 | last_report 无条件优先，工具结果 > 模型回复 |
| 13种合同回退到6种 | 少即是多：提示词越短，格式出错越少 |

---

## 关键文件

| 文件 | 作用 |
|---|---|
| `main.py` | 原版 ReAct Agent 循环（手写） |
| `agent_langgraph.py` | LangGraph 自定义 StateGraph 版（新增） |
| `llm_client.py` | LLM 客户端（temperature=0.0，qwen 专有修复） |
| `tools.py` | 10个工具函数 + AGENT_TOOLS schema |
| `prompts.py` | 系统提示词 + 风险评分锚点 + 防重复规则 |
| `app.py` | Streamlit Web 界面 |
| `chat.py` / `chat_engine.py` | 法律问答 Bot |

---

## 相关输出

- 知乎发布版技术复盘：`知乎发布版-法眼项目技术复盘.md`
- Agent 决策拓扑图：`screenshots/agent-graph.png`
- GitHub 仓库：https://github.com/Nakoem/fayan-contract-review
