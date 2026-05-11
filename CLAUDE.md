# 法眼 · 合同审查 Agent

## 启动方式
- Web 界面：`streamlit run app.py`
- 终端审查：`python main.py <合同文件> <合同类型>`

## 项目文件
| 文件 | 作用 |
|:---|:---|
| `app.py` | Streamlit Web 界面 |
| `main.py` | Agent ReAct 主循环（20 轮迭代） |
| `llm_client.py` | LLM 客户端（qwen-plus，OpenAI 兼容 API） |
| `prompts.py` | 系统提示词 + 工具提示词 + 完整性检查清单 |
| `tools.py` | 10 个工具 + 6 合同类型法规库 |

## 技术栈
- 模型：阿里云百炼 qwen-plus
- API：OpenAI SDK → `https://dashscope.aliyuncs.com/compatible-mode/v1`
- API Key：在 `.env` 文件中（`DASHSCOPE_API_KEY`）
- OCR：qwen-vl-plus 多模态模型

## 支持的合同类型
房屋租赁合同、劳动合同、买卖合同、服务合同、合作协议、借款合同

## UI 风格
Legal Editorial：深蓝(#1a1f36) + 香槟金(#c9a96e)，Cormorant Garamond + DM Sans 字体

## 已知问题
- qwen-turbo 不支持 function calling（JSON 参数格式频繁出错），别用它
- 进度条通过后台线程轮询实现，不是实时 streaming
