# 法眼 · 合同审查 Agent

AI 驱动的合同审查工具，基于 ReAct Agent 模式，支持 6 种合同类型的自动审查，内置法规库、判例库、地方政策库、税务规则库四重知识体系。

## 功能

- **ReAct Agent 自主审查**：10 个工具，AI 自主决策审查步骤 —— 提取条款 → 法规检索 → 逐条分析 → 完整性检查 → 视角切换 → 生成报告
- **四重知识库**：法规原文 × 法院判例 × 地方政策 × 税务规则，交叉验证
- **6 种合同类型**：房屋租赁、劳动、买卖、服务、合作、借款
- **Streamlit Web 界面**：Legal Editorial 法务精致风，支持合同照片 OCR
- **命令行模式**：`python main.py <合同文件> <合同类型>` 终端直接出报告

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/pppppgy/fayan-contract-review.git
cd fayan-contract-review

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY（从 dashscope.console.aliyun.com 获取）

# 4. 启动 Web 界面
streamlit run app.py

# 或命令行审查
python main.py sample_cooperation.txt "合作协议"
```

浏览器打开 http://localhost:8501 即可使用。

## Agent 工具集

| 工具 | 功能 |
|------|------|
| `extract_clauses` | 从合同全文提取结构化条款（10个类别） |
| `search_regulation` | 检索内置法规库（民法典 + 司法解释 + 行政法规） |
| `search_case_law` | 检索法院判例，了解类似纠纷的裁判倾向 |
| `check_local_policy` | 查询北京/上海/深圳/广州/成都地方政策 |
| `lookup_tax_rule` | 查询税务规则（增值税/个税/印花税/契税） |
| `web_search` | 联网搜索最新法规动态 |
| `analyze_single_clause` | 逐条深度分析，三维评分（公平性/明确性/风险敞口） |
| `check_completeness` | 检查合同条款完整性，找出缺失项 |
| `switch_perspective` | 切换视角（出租方↔承租方，用人单位↔劳动者） |
| `generate_final_report` | 汇总生成五段式审查报告 |

## 审查报告格式

五段式纯文本报告：
1. **总体风险概览** — 高/中/低风险计数 + 综合评分
2. **高风险条款详解** — 原文 + 风险说明 + 修改建议
3. **需关注的中风险条款** — 同上格式
4. **修改优先级建议** — P0/P1/P2 分级
5. **签约建议** — 可签/修改后签/不建议签

## 项目结构

```
contract_review/
├── app.py              # Streamlit Web 界面
├── main.py             # Agent ReAct 主循环（20轮迭代上限）
├── llm_client.py       # LLM 客户端（OpenAI 兼容 API）
├── prompts.py          # 全部提示词（Agent / 分析 / 报告 / 完整性）
├── tools.py            # 10个工具 + 4大知识库（法规/判例/政策/税务）
├── ocr_utils.py        # 合同照片 OCR（qwen-vl-plus）
├── sample_lease.txt    # 房屋租赁合同样本
├── sample_employment.txt
├── sample_sales.txt
├── sample_service.txt
├── sample_cooperation.txt
├── sample_loan.txt
└── .env.example        # API Key 配置模板
```

## 部署到 Streamlit Cloud

1. 将项目推送到 GitHub 仓库
2. 登录 [share.streamlit.io](https://share.streamlit.io)
3. 点击 "New app"，选择仓库和分支
4. 在 App Settings → Secrets 中添加：

```
DASHSCOPE_API_KEY = "sk-your-api-key"
```

5. 点击 Deploy

> API Key 存储在 Streamlit Secrets 中，不会暴露给前端。每个审查请求由服务端调用阿里云百炼 API。

## 技术栈

- **模型**：阿里云百炼 qwen-plus（OpenAI 兼容 API）
- **OCR**：qwen-vl-plus 多模态模型
- **框架**：Streamlit + OpenAI SDK
- **模式**：ReAct Agent（思考 → 行动 → 观察 循环）
- **兜底**：JSON 解析失败时自动切换文本格式工具调用（`<<TOOL>>` 标签）

## 依赖

- Python ≥ 3.10
- [阿里云百炼 DashScope API Key](https://dashscope.console.aliyun.com/)
- Qwen-Plus / Qwen-VL-Plus 模型

## License

MIT
