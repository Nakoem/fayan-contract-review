"""
法眼 · 法律助手 — 聊天界面
用法：streamlit run chat.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="法眼 · 法律助手", page_icon="⚖️", layout="wide")

# ═══════════════════════════════════
# 样式（复用主界面风格）
# ═══════════════════════════════════
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,600&display=swap');

:root {
    --navy: #1a1f36; --gold: #c9a96e; --cream: #faf8f5;
    --ink: #2c2416; --border: #e0d8c8;
}

html, body, [class*="css"] { font-family: 'DM Sans', 'Noto Sans SC', sans-serif; }
h1, h2, h3 { font-family: 'Cormorant Garamond', 'Noto Serif SC', serif; }

[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #faf8f5 0%, #f0ece4 100%);
}

.main-title {
    font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
    font-size: 2rem !important; font-weight: 700 !important;
    color: var(--navy) !important;
}

/* 聊天消息 */
.user-msg {
    background: var(--navy); color: #e0cc9a; padding: 12px 18px;
    border-radius: 12px 12px 2px 12px; margin: 8px 0 8px 60px;
    font-size: 0.95rem; line-height: 1.7;
}
.assistant-msg {
    background: white; color: var(--ink); padding: 14px 18px;
    border-radius: 2px 12px 12px 12px; margin: 8px 60px 8px 0;
    border: 1px solid var(--border); font-size: 0.95rem; line-height: 1.8;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.assistant-msg .reference {
    font-size: 0.78rem; color: #888; margin-top: 8px;
    padding-top: 8px; border-top: 1px solid var(--border);
}

/* 合同状态栏 */
.contract-bar {
    background: rgba(201,169,110,0.08); border: 1px solid rgba(201,169,110,0.2);
    border-radius: 6px; padding: 8px 14px; margin-bottom: 12px;
    font-size: 0.82rem; color: #8a7a50;
}

[data-testid="stChatInput"] textarea {
    border: 1px solid var(--border) !important; border-radius: 8px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════
# 标题
# ═══════════════════════════════════
st.markdown('<div class="main-title">⚖ 法眼 · 法律助手</div>', unsafe_allow_html=True)
st.caption("基于法规库 + 判例库 + 地方政策 + 税务规则四重知识库的 AI 法律问答")

# ═══════════════════════════════════
# 侧边栏设置
# ═══════════════════════════════════
with st.sidebar:
    st.markdown("### 📄 合同模式（可选）")
    st.caption("上传合同后，可针对该合同提问")

    uploaded_file = st.file_uploader(
        "上传合同 (.txt)",
        type=["txt"],
        label_visibility="collapsed",
    )

    contract_text = ""
    if uploaded_file:
        contract_text = uploaded_file.read().decode("utf-8")
        st.success(f"已加载合同：{uploaded_file.name}（{len(contract_text)}字）")

    st.divider()

    # API Key
    try:
        api_key = st.secrets["DASHSCOPE_API_KEY"]
    except (KeyError, FileNotFoundError):
        api_key = os.getenv("DASHSCOPE_API_KEY", "")

    if not api_key:
        api_key = st.text_input("DashScope API Key", type="password", placeholder="sk-...")

    st.divider()
    st.caption("© 2026 法眼 · Powered by Qwen-Plus + RAG")

# ═══════════════════════════════════
# 合同状态提示
# ═══════════════════════════════════
if contract_text:
    st.markdown(
        '<div class="contract-bar">📎 已加载合同 · 你可以针对这份合同提问，如"第四条合法吗？"、"这份合同的违约金合理吗？"</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"合同预览（前200字）：{contract_text[:200]}...")

# ═══════════════════════════════════
# 聊天消息显示
# ═══════════════════════════════════
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "你好！我是法眼法律助手。\n\n"
            "你可以直接问我法律问题，比如：\n"
            "- 租房押金一般多久退？\n"
            "- 劳动合同试用期最长几个月？\n"
            "- 民间借贷利率超过多少不合法？\n\n"
            "也可以先上传一份合同，然后针对合同条款提问。",
        }
    ]
    st.session_state.chat_history = []

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ═══════════════════════════════════
# 输入框
# ═══════════════════════════════════
if prompt := st.chat_input("输入你的法律问题..."):
    if not api_key:
        st.error("请在侧边栏填写 API Key")
        st.stop()

    # 显示用户消息
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用对话引擎
    with st.chat_message("assistant"):
        with st.spinner(""):
            placeholder = st.empty()
            full_response = ""

            try:
                from chat_engine import chat_stream

                for chunk in chat_stream(
                    query=prompt,
                    history=st.session_state.chat_history,
                    contract_text=contract_text,
                    api_key=api_key,
                ):
                    full_response += chunk
                    placeholder.markdown(full_response + "▌")
            except Exception as e:
                full_response = f"抱歉，回答问题出错了：{e}"
                placeholder.markdown(full_response)

            placeholder.markdown(full_response)

    # 保存
    st.session_state.chat_messages.append({"role": "assistant", "content": full_response})
    st.session_state.chat_history.append({"user": prompt, "assistant": full_response})

    # 最多保留20轮对话
    if len(st.session_state.chat_history) > 20:
        st.session_state.chat_history = st.session_state.chat_history[-20:]
