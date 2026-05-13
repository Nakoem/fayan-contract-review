# 简历 — AI 应用工程师

> 投递方向：AI 应用工程师（实用主义派 · 价值导向 · 全栈构建能力）

## 个人信息

- **GitHub**：github.com/pppppgy
- **求职状态**：随时到岗
- **所在地**：（你自己填）
- **电话/邮箱**：（你自己填）

---

## 关于我

转行进入 AI 应用开发。无传统 CS 背景，但 4 个月内从零独立交付了一个产品级 AI Agent 项目——从需求分析、模型选型、Agent 架构设计，到 RAG 检索、API 封装、Docker 部署，全链路自己走通。

我相信"够用就好"的工程哲学：90% 的问题可以用现有技术解决，关键不在于造轮子，而在于把合适的轮子组装成能跑的车。我用法眼项目证明了这一点。

日常使用 Claude Code 作为主要开发工具，深刻理解 AI 辅助编程的效率提升和边界——知道什么时候信任 AI 的生成，什么时候需要自己判断。

---

## 技能矩阵

| 类别 | 技术 | 熟练度 |
|------|------|:--:|
| **AI/Agent** | ReAct Agent、Function Calling、RAG、Prompt 工程、MCP 协议、LLM-as-Judge | 项目实战 |
| **后端 & API** | Python、FastAPI、REST API、异步任务 | 项目实战 |
| **向量检索** | Chroma、DashScope Embedding、混合检索 | 项目实战 |
| **工程化** | Docker、docker-compose、loguru、YAML 配置管理 | 项目实战 |
| **AI 开发工具** | Claude Code（主力）、OpenAI 兼容 SDK | 日常使用 |
| **前端** | Streamlit | 项目使用 |

---

## 项目经历

### 法眼 · AI 合同审查 Agent（4个月，独立全栈开发）

> GitHub: github.com/pppppgy/fayan-contract-review
> 从真实合同审查痛点出发，用 AI Agent 替代人工"读合同 → 查法规 → 写报告"流程。

#### 我做了什么

**Agent 工作流设计**
- 用 ReAct 模式（思考→行动→观察循环）设计了 10 工具 Agent，自动走完"提取条款→查法规→逐条分析→完整性检查→生成报告"全流程
- 把合同审查这个复杂业务流程抽象成了 6 步结构化 Agent 工作流，每步可独立执行、可单独调试

**RAG 检索增强**
- 66 条法规/判例/政策/税务知识 → Chroma 向量库（216 chunks），语义检索替代关键词匹配
- 实际效果："押金不退"能命中"押金退还"条目（关键词匹配命中率 0% → 语义检索 91%）
- 选 Chroma 而不是 Milvus：数据量小（~23K 字符），嵌入式方案够用，不引入额外服务复杂度

**Prompt 工程**
- 15 个提示词 YAML 外部化 + 版本管理，支持热切换和回退
- 每个合同类型配备了法条级法定红线标准，确保 LLM 判断有据可依
- 分析了 4 个模型的"指令跟随"表现（qwen-plus / qwen-max / qwen3.6-plus / deepseek-v3.2），最终选 qwen-plus——不是最强但最"听话"

**FastAPI + Docker 部署**
- Streamlit 单体 → FastAPI REST 服务（同步/异步审查 + Swagger 文档 + Health Check）
- Docker 多阶段构建 + docker-compose 编排，一键启动

**MCP 协议标准化**
- 将 5 个法律搜索工具封装为 MCP Server（Anthropic 2024 年发布的 Agent 工具互操作协议）
- Claude Code 和 Cursor 可直接调用法眼的法规/判例搜索能力

#### 实用主义决策（面试可展开）

| 决策 | 为什么这么选 |
|------|------|
| Chroma 而不是 Milvus | 23K 数据量，够用就好；数据量大了可升级 |
| 6 种合同类型而不是 13 种 | 扩展后 JSON 错误暴增 → 果断回退，宁可少而精 |
| qwen-plus 而不是 deepseek | deepseek 法律判断好但顽固输出 Markdown → 选了"听话"的 |
| 先工程化后 RAG | 没评估体系就上 RAG，改完不知道好坏 |
| MCP 放最后 | 工具先稳定再暴露接口，否则下游频繁适配 |

#### 技术栈

```
Python | FastAPI | Streamlit | Docker | Chroma | MCP SDK
阿里云百炼 DashScope | 日常使用 Claude Code 开发
```

---

## 自我评价

- **实用主义**："够用就好"不是偷懒，是知道瓶颈在哪。67 条数据不用 Milvus、6 种合同做到极致而不是追求 20 种
- **全栈交付**：能从需求分析一路做到 Docker 部署，不是只会调 API 的 Demo 工程师
- **快速学习**：转行 4 个月，从不会写 Agent 到交付完整项目——靠的是 AI 工具辅助 + 快速试错 + 不懂就查
- **客户思维**：法眼不是"我想做一个 AI 项目"，而是"合同审查确实有痛点"——从需求出发，而非技术出发

---

## 附录

- **法眼技术复盘文章**：《从零到一：我用 ReAct Agent 做了一个合同审查工具，踩了 5 个深坑》（待发布）
- **语言**：普通话、英语（读写）
- **学历**：（你自己填）
