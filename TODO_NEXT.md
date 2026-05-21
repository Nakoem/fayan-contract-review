# 下一步改动

## 1. 多Agent协作改造 ✅ 已完成
- 5个Agent节点：extraction_agent / regulation_agent / assessment_agent / reflection_agent / report_agent
- Supervisor路由 + 新图结构
- 对外接口 review_contract_langgraph() 适配完成
- 遗留代码已清理

## 2. Agent 调用失败 · State 断点恢复 ✅ 已完成
- **文件**：`agent_langgraph.py`
- **方案**：LangGraph SqliteSaver Checkpointer 机制
  - 编译图时注入 `SqliteSaver`，每个节点执行完自动 checkpoint → `checkpoints.db`
  - State 全量快照到 SQLite
  - `review_contract_langgraph()` 新增 `thread_id` 参数
  - 中断后用同 `thread_id` 重新 invoke，LangGraph 自动从最近 checkpoint 恢复
  - 已完成的节点不会重复执行
- **新增**：`resume_review(thread_id)` 独立恢复入口

## 3. 跨会话记忆系统
- **文件**：涉及 Chroma 存储层
- **改法**：
  - 向量库加 session_id 字段
  - 会话结束时提取关键信息（用户偏好、历史高风险条款）写入向量库
  - 新会话开始时检索历史记忆
  - 短期：滑动窗口上下文；长期：跨会话偏好存储
- **目标**：用户第二次审查同类型合同，Agent记得上次关注过什么
