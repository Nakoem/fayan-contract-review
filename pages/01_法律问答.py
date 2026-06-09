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
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --primary: #5c1d5e;
    --canvas: #f4ede4;
    --canvas-lavender: #f9f0ff;
    --surface: #ffffff;
    --surface-aubergine: #5c1d5e;
    --hairline: #e6e6e6;
    --ink: #1d1d1d;
    --body: #454545;
    --body-mid: #888888;
    --link-blue: #1264a3;
    --on-primary: #ffffff;
    --on-aubergine-mute: #d9bdde;
}

html, body, [class*="css"] { font-family: 'Inter', system-ui, -apple-system, 'Noto Sans SC', sans-serif; color: var(--body); }
h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 600; color: var(--ink); }

[data-testid="stAppViewContainer"] { background: var(--canvas); }
[data-testid="stHeader"] { background: rgba(244,237,228,0.94); backdrop-filter: blur(10px); border-bottom: 1px solid var(--hairline); }

[data-testid="stSidebar"] { background: var(--surface-aubergine); border-right: 1px solid rgba(255,255,255,0.08); }
[data-testid="stSidebar"] * { color: var(--on-aubergine-mute) !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label { color: var(--on-primary) !important; font-family: 'Inter', sans-serif !important; font-weight: 600; }
[data-testid="stSidebar"] input {
    background: rgba(255,255,255,0.08) !important; border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 8px !important; color: var(--on-primary) !important;
}
[data-testid="stSidebar"] input:hover { border-color: rgba(255,255,255,0.3) !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1) !important; }

.sidebar-brand { font-family: 'Inter', sans-serif !important; font-size: 1.1rem !important; font-weight: 600 !important; color: var(--on-primary) !important; }
.sidebar-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; }
.sidebar-dot.online { background: var(--link-blue); animation: pulse-dot 2.5s infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.4} }

.main-title { font-family: 'Inter', sans-serif !important; font-size: 2.4rem !important; font-weight: 600 !important; color: var(--ink) !important; }
.main-subtitle { color: var(--body-mid); font-size: 0.9rem; }

[data-testid="stChatMessage"] { background: transparent !important; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { font-size: 0.95rem; line-height: 1.8; color: var(--body); }

.contract-bar { background: var(--surface); border: 1px solid var(--hairline); border-radius: 8px; padding: 8px 14px; margin-bottom: 12px; font-size: 0.82rem; color: var(--body); }

[data-testid="stChatInput"] textarea {
    border: 1px solid var(--hairline) !important; border-radius: 8px !important;
    background: var(--canvas) !important; color: var(--ink) !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stChatInput"] textarea:focus { border-color: var(--primary) !important; box-shadow: none !important; }

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
""",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════
# 标题
# ═══════════════════════════════════════════════════════
st.markdown('<div class="main-title">💬 法律问答</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-subtitle">基于法规库 + 判例库 + 地方政策 + 税务规则四重知识库的 AI 法律助手</div>',
    unsafe_allow_html=True,
)

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
        "上传 .txt 合同文件",
        type=["txt"],
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
# 合同状态提示 + 指纹匹配
# ═══════════════════════════════════════════════════════
if contract_text:
    # 计算合同指纹，检查是否审过
    match_hint = ""
    try:
        from cache import contract_cache_key as compute_fingerprint

        fp = compute_fingerprint(contract_text, "未知")
        # review:{hash16} → 取 hash16 部分
        fingerprint = fp.replace("review:", "")
        from tools import query_review_history

        match_result = query_review_history(action="match", fingerprint=fingerprint)
        if "已找到" in match_result:
            match_hint = f" · {match_result.strip()}"
    except Exception:
        pass

    bar_text = f"📎 已加载合同（{len(contract_text)}字）{match_hint} · 你可以针对这份合同提问"
    st.markdown(
        f'<div class="contract-bar">{bar_text}</div>',
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════
# 聊天消息
# ═══════════════════════════════════════════════════════
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "你好！我是法眼法律助手。\n\n"
            "你可以直接问我法律问题，比如：\n"
            "- 租房押金一般多久退？\n"
            "- 劳动合同试用期最长几个月？\n"
            "- 民间借贷利率超过多少不合法？\n\n"
            "也可以先在侧边栏上传一份合同，然后针对合同条款提问。",
        }
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
                    enable_tools=True,
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
