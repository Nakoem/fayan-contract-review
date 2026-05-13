# 法眼 · 合同审查 Agent

## 用户上下文
- 项目定位：AI 项目应用工程师面试展示材料，非商用
- 所有 Step（1-5 + 法律问答Bot + LangGraph 改写）已完成
- 知乎已发布技术复盘文章（待更新最新改动）
- 在线 Demo：https://fayan-contract-review-777.streamlit.app/

## 启动方式
- Web 界面：`streamlit run app.py`
- 终端审查：`python main.py <合同文件> <合同类型> [--output report.txt]`
- API 服务：`uvicorn api:app --host 0.0.0.0 --port 8000`
- 全部服务：`docker compose up -d`

## 测试
- 冒烟测试：`pytest tests/test_smoke.py -v`（22 个单元 + 3 个集成）
- 仅单元：`pytest tests/test_smoke.py -k "not Integration"`
- 集成测试会调真实 LLM，约 4-5 分钟，需设置 DASHSCOPE_API_KEY

## 项目文件（完整）
| 文件 | 作用 |
|:---|:---|
| `app.py` | Streamlit Web 界面（SSE 流式，434 行） |
| `main.py` | Agent ReAct 主循环（20 轮 + Self-Reflection） |
| `agent_langgraph.py` | LangGraph 自定义 StateGraph 版 Agent |
| `llm_client.py` | LLM 客户端（含 `stream_chat()` 流式） |
| `prompts.py` | 系统提示词 + 工具提示词 + 反思提示词 |
| `tools.py` | 11 个工具 + 6 合同类型法规库（~1460 行） |
| `utils.py` | 共享工具：JSON 修复 + 文本解析 + 报告后处理 |
| `service.py` | Web 业务逻辑层（文件读取/审查执行/报告管理） |
| `api.py` | FastAPI REST 接口 |
| `mcp_server.py` | MCP 协议工具封装 |
| `chat_engine.py` | 法律问答 RAG 引擎 |
| `logger.py` | Loguru 日志配置 |
| `prompt_manager.py` | YAML 驱动提示词版本管理 |
| `rag/` | RAG 管线：embedder / indexer / retriever / vector_store |
| `tests/test_smoke.py` | 22 冒烟测试 |
| `tests/benchmark_consistency.py` | 双版本一致性基准 |

## 技术栈
- 模型：阿里云百炼 qwen-plus（temperature=0.0）
- API：OpenAI SDK → `https://dashscope.aliyuncs.com/compatible-mode/v1`
- API Key：`.env` 中 `DASHSCOPE_API_KEY`
- OCR：qwen-vl-plus 多模态模型
- RAG：ChromaDB 向量检索 + 关键词全文扫描 + RRF 融合
- 部署：Docker + docker-compose
- 质量：pre-commit (ruff format + lint)

## 核心特性
- **SSE 流式输出**：LLMClient.stream_chat() → Agent.run_stream() → StreamingReviewRunner(Queue) → for-event-loop
- **PDF/DOCX 解析**：pypdf + python-docx 原生文本提取，扫描件走 OCR
- **RAG 混合检索**：向量语义 + 关键词全文扫描 + RRF 融合去重
- **Self-Reflection 反思**：生成报告前全局质量审核（一致性/覆盖性/评分合规），最多 3 轮
- **11 个工具**：extract_clauses / search_regulation / search_case_law / check_local_policy / lookup_tax_rule / web_search / analyze_single_clause / check_completeness / self_reflection / switch_perspective / generate_final_report
- **双版本 Agent**：手写 ReAct（main.py）+ LangGraph StateGraph（agent_langgraph.py），互补对比
- **MCP 协议**：5 个查询工具暴露给外部 AI
- **FastAPI REST**：`/api/v1/review` 同步审查接口

## 支持的合同类型
房屋租赁合同、劳动合同、买卖合同、服务合同、合作协议、借款合同、自定义

## 已知问题
- qwen-turbo 不支持 function calling，别用
- qwen-plus 偶尔生成非法 JSON（function.arguments），已有多级兜底：
  1. `utils.repair_json()` 自动修复尾部逗号/单引号/前后说明文字
  2. 文本模式 <<TOOL::name>> <<ARGS::{}>> 标签绕过 Function Calling 校验
  3. `json_error_count >= 3` 时强制纯文本输出报告，防止死循环
- self_reflection 工具因为参数较长，更容易触发 qwen-plus JSON 错误 → 参数已截断 + 兜底策略可保底
- ENTER 快捷键依赖前端 JS 注入，首次加载可能需点一次按钮激活

## 审查质量保障
- temperature=0.0 消除随机性
- 评分锚点：三维度（公平性/明确性/风险敞口）强制映射
- 防重复：同条款只在最高风险级出现一次
- check_completeness 缺失项强制反映到报告
- self_reflection 交叉验证分析质量
- clean_report() 后处理清理占位文字 + 硬编码兜底检查
