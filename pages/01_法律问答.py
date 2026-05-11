"""
法眼 · 法律问答 —— 子页面
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="法眼 · 法律问答", page_icon="💬", layout="wide")

# ═══════════════════════════════════════════════════════
# 自定义 CSS（与 app.py 统一 Legal Editorial 风格）
# ═══════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --navy: #1a1f36; --navy-light: #2a3050; --gold: #c9a96e; --gold-light: #e0cc9a;
    --cream: #faf8f5; --paper: #f5f0e8; --ink: #2c2416; --ink-light: #5c5240; --border: #e0d8c8;
}

html, body, [class*="css"] { font-family: 'DM Sans', 'Noto Sans SC', sans-serif; }
h1, h2, h3, h4, h5, h6 { font-family: 'Cormorant Garamond', 'Noto Serif SC', serif; }

/* 背景：纸纹质感 */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 60% 60% at 50% 30%, rgba(201,169,110,0.06) 0%, transparent 70%),
        linear-gradient(180deg, var(--cream) 0%, #f0ece4 100%);
}
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        repeating-linear-gradient(0deg, transparent, transparent 28px, rgba(180,160,120,0.12) 28px, rgba(180,160,120,0.12) 29px);
    pointer-events: none; z-index: -1;
    mask-image: radial-gradient(ellipse 70% 80% at 50% 0%, black 30%, transparent 80%);
    -webkit-mask-image: radial-gradient(ellipse 70% 80% at 50% 0%, black 30%, transparent 80%);
}

/* 顶部栏 */
[data-testid="stHeader"] {
    background: rgba(250,248,245,0.85);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
}

/* 侧边栏：深蓝底 + 金色点缀 */
[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #151a2e 0%, #1a1f36 40%, #1f2545 100%);
    border-right: 1px solid rgba(201,169,110,0.15);
}
[data-testid="stSidebar"] * { color: #b8c0d0 !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label { color: #d8dce6 !important; font-family: 'Cormorant Garamond', serif !important; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(201,169,110,0.2) !important;
    border-radius: 6px !important; color: #d8dce6 !important;
    transition: border-color 0.3s;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:hover,
[data-testid="stSidebar"] input:hover { border-color: rgba(201,169,110,0.5) !important; }
[data-testid="stSidebar"] hr { border-color: rgba(201,169,110,0.15) !important; }

.sidebar-brand {
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 1.5rem !important; font-weight: 700 !important;
    color: var(--gold) !important; letter-spacing: 1px;
}
.sidebar-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }
.sidebar-dot.online { background: #c9a96e; box-shadow: 0 0 6px rgba(201,169,110,0.6); animation: pulse-dot 2.5s infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* 标题 */
.main-title {
    font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
    font-size: 2.4rem !important; font-weight: 700 !important;
    color: var(--navy) !important; letter-spacing: -0.3px;
}
.main-subtitle { color: var(--ink-light); font-size: 0.9rem; letter-spacing: 0.3px; }

/* 聊天消息气泡 */
[data-testid="stChatMessage"] {
    background: transparent !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    font-size: 0.95rem; line-height: 1.8;
}

/* 合同状态栏 */
.contract-bar {
    background: rgba(201,169,110,0.08); border: 1px solid rgba(201,169,110,0.2);
    border-radius: 6px; padding: 8px 14px; margin-bottom: 12px;
    font-size: 0.82rem; color: #8a7a50;
}

/* 聊天输入框 */
[data-testid="stChatInput"] textarea {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: white !important;
    font-family: 'DM Sans', 'Noto Sans SC', sans-serif !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 2px rgba(201,169,110,0.1) !important;
}

/* 滚动条 */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--cream); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--gold-light); }

/* 移动端 */
@media (max-width: 768px) {
    .main-title { font-size: 1.6rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# 标题
# ═══════════════════════════════════════════════════════
st.markdown('<div class="main-title">💬 法律问答</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">基于法规库 + 判例库 + 地方政策 + 税务规则四重知识库的 AI 法律助手</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sidebar-brand">⚖ 法眼 · 法律助手</div>', unsafe_allow_html=True)
    st.markdown(
        '<span class="sidebar-dot online"></span>'
        '<span style="font-size:0.75rem;color:#8a8fa0;letter-spacing:0.5px;">QWEN-PLUS · RAG 检索增强</span>',
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("**📄 上传合同（可选）**")
    st.caption("上传后可针对合同条款定向提问")

    uploaded_file = st.file_uploader(
        "上传 .txt 合同文件", type=["txt"],
        label_visibility="collapsed",
    )

    contract_text = ""
    if uploaded_file:
        contract_text = uploaded_file.read().decode("utf-8")
        st.success(f"已加载（{len(contract_text)}字）")

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

# ═══════════════════════════════════════════════════════
# 合同状态提示
# ═══════════════════════════════════════════════════════
if contract_text:
    st.markdown(
        f'<div class="contract-bar">📎 已加载合同 · 你可以针对这份合同提问，如"第四条合法吗？"、"违约金合理吗？"</div>',
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════
# 聊天消息
# ═══════════════════════════════════════════════════════
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "你好！我是法眼法律助手。\n\n"
         "你可以直接问我法律问题，比如：\n"
         "- 租房押金一般多久退？\n"
         "- 劳动合同试用期最长几个月？\n"
         "- 民间借贷利率超过多少不合法？\n\n"
         "也可以先在侧边栏上传一份合同，然后针对合同条款提问。"}
    ]
    st.session_state.chat_history = []

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ═══════════════════════════════════════════════════════
# 输入框
# ═══════════════════════════════════════════════════════
if prompt := st.chat_input("输入你的法律问题..."):
    if not api_key:
        st.error("请在侧边栏填写 API Key")
        st.stop()

    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

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

    st.session_state.chat_messages.append({"role": "assistant", "content": full_response})
    st.session_state.chat_history.append({"user": prompt, "assistant": full_response})

    if len(st.session_state.chat_history) > 20:
        st.session_state.chat_history = st.session_state.chat_history[-20:]
