# 法眼 · 合同审查 Agent

AI 驱动的合同审查工具，基于 ReAct Agent 模式，支持 5 种合同类型的自动审查。

## 功能

- **10 工具 ReAct Agent**：AI 自主决策审查步骤，法规 × 判例 × 地方政策三重交叉验证
- **Streamlit Web 界面**：粘贴合同文本或上传照片 OCR，一键审查
- **5 种合同类型**：房屋租赁、劳动、买卖、服务、合作协议
- **生成专业审查报告**：按风险等级标注，可下载 PDF/TXT

## 快速开始（本地运行）

```bash
# 1. 克隆项目
git clone <your-repo-url> && cd contract_review

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DashScope API Key（从 dashscope.console.aliyun.com 获取）

# 4. 启动
streamlit run app.py
```

浏览器打开 http://localhost:8501 即可使用。

## 部署到 Streamlit Cloud

1. 将项目推送到 GitHub 仓库
2. 登录 [share.streamlit.io](https://share.streamlit.io)
3. 点击 "New app"，选择你的仓库和分支
4. 在 App Settings → Secrets 中添加：

```
DASHSCOPE_API_KEY = "sk-your-api-key"
```

5. 点击 Deploy，几分钟后即可通过公开链接访问

> **注意**：API Key 存储在 Streamlit Secrets 中，不会暴露给前端用户。每个审查请求由服务端调用阿里云百炼 API。

## 命令行用法

```bash
python main.py sample_lease.txt "房屋租赁合同"
python main.py sample_employment.txt "劳动合同" --output report.txt
```

## 项目结构

| 文件 | 作用 |
|------|------|
| `app.py` | Streamlit Web 界面 |
| `main.py` | Agent ReAct 主循环 |
| `llm_client.py` | LLM 客户端（OpenAI 兼容 API） |
| `prompts.py` | 系统提示词 + 工具提示词 |
| `tools.py` | 10 个工具 + 法规库 |
| `ocr_utils.py` | 合同照片 OCR |

## 依赖

- Python ≥ 3.10
- [阿里云百炼 DashScope API Key](https://dashscope.console.aliyun.com/)
- Qwen-Plus / Qwen-VL-Plus 模型
