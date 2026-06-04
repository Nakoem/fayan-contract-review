"""
法眼 —— 合同审查 Agent Web 版
用法：streamlit run app.py
"""

import os
import sys
import time
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from cache import warmup_from_reports
from logger import init_logger
from service import (
    CONTRACT_TYPES,
    StreamingReviewRunner,
    extract_summary,
    read_uploaded_contract,
    save_report_file,
    save_to_history,
)

load_dotenv()
init_logger(mode="web")

# Windows 控制台 GBK 编码下 emoji 会炸，强制 UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 启动时 Redis 缓存预热 ──
_warmup_result = warmup_from_reports()
print(f"[缓存预热] {_warmup_result}")

st.set_page_config(page_title="法眼 · 合同审查", page_icon="⚖️", layout="wide")

# ═══════════════════════════════════════════════════════
# 自定义 CSS
# ═══════════════════════════════════════════════════════
st.markdown(
    """
<script>
(function() {
    if (document.querySelector('link[href*="Newsreader"]')) return;
    var links = [
        'https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;700;900&display=swap',
        'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap',
        'https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;1,400&display=swap'
    ];
    links.forEach(function(url) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        document.head.appendChild(link);
    });
})();
</script>
<script>
(function() {
    var cleanTips = setInterval(function() {
        document.querySelectorAll('[data-testid="stSidebar"] button[title]').forEach(function(el) {
            el.removeAttribute('title');
        });
        document.querySelectorAll('[data-testid="stSidebar"] button[aria-label]').forEach(function(el) {
            var a = el.getAttribute('aria-label') || '';
            if (a.indexOf('keyboard') !== -1) el.removeAttribute('aria-label');
        });
    }, 500);
    setTimeout(function() { clearInterval(cleanTips); }, 8000);
})();
</script>
<script>
(function() {
    var tries = 0;
    var apply = function() {
        tries++;
        var blocks = document.querySelectorAll('[data-testid="stHorizontalBlock"]');
        var found = false;
        blocks.forEach(function(b) {
            if (b.children.length !== 2) return;
            if (!b.closest('[data-testid="stAppViewBlockContainer"]')) return;
            if (b.querySelector('[data-testid="stHorizontalBlock"]')) return;
            if (b.children[0].dataset._eline === '1') return;
            b.children[0].dataset._eline = '1';
            b.children[0].style.borderRight = '1px solid #d4cec4';
            b.children[0].style.paddingRight = '28px';
            b.children[0].style.background = '#ffffff';
            b.children[1].style.background = '#ffffff';
            found = true;
        });
        if (!found && tries < 20) setTimeout(apply, 400);
    };
    apply();
})();
</script>
<style>
/* ═══════════════════════════════════════════════
   Editorial Ink & Paper — 纸媒编辑风
   墨黑纸白 + Noto Serif SC + 新闻规则线
   ═══════════════════════════════════════════════ */

:root {
    --paper: #fbf9f6;
    --ink-black: #1c1c1c;
    --ink-blue: #1a365d;
    --ink-red: #9b2c2c;
    --ink-amber: #8b6914;
    --ink-green: #2d6a4f;
    --border: #d4cec4;
    --subtle: #e8e3da;
    --muted: #8a8378;
    --surface: #ffffff;
    --surface-warm: #f4f1ea;
    --red-bg: rgba(155,44,44,0.06);
    --amber-bg: rgba(139,105,20,0.06);
    --green-bg: rgba(45,106,79,0.06);
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
[data-testid="stMarkdownContainer"], [data-testid="stSidebarContent"] {
    font-family: 'Newsreader', 'Noto Serif SC', serif !important;
    color: var(--ink-black);
}
/* 排除所有图标/按钮元素，保留原生 icon font */
.material-icons, .material-symbols-outlined,
[data-testid="collapsedControl"], [data-testid="collapsedControl"] *,
[data-testid="baseButton-header"], [data-testid="baseButton-header"] *,
button[kind="header"], button[kind="headerNoPadding"],
button[aria-label*="arrow"], button[aria-label*="Collapse"],
button[aria-label*="Close"], button[aria-label*="close"],
.st-emotion-cache-1h9us95, .st-emotion-cache-1qg05tj {
    font-family: 'Material Icons', 'Material Symbols Outlined', system-ui, sans-serif !important;
}
[data-testid="stTextArea"] textarea {
    font-family: 'Newsreader', 'Noto Serif SC', serif !important;
    font-size: 1rem !important; line-height: 2 !important;
    color: #1c1c1c !important;
    background: #ffffff !important;
    min-height: 380px !important;
}
[data-testid="stTextArea"] textarea::placeholder {
    font-family: 'Newsreader', 'Noto Serif SC', serif !important;
    font-style: italic !important;
    color: #c5bfb0 !important;
}
h1, h2, h3, h4, h5, h6, [data-testid="stHeading"] {
    font-family: 'DM Sans', 'Noto Serif SC', sans-serif !important;
    font-weight: 700 !important; color: var(--ink-black) !important; letter-spacing: -0.01em;
}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] span {
    font-family: 'Newsreader', 'Noto Serif SC', serif !important;
}

[data-testid="stAppViewContainer"] {
    background: #fbf9f6 !important;
}
[data-testid="stAppViewContainer"] > div {
    background: #ffffff !important;
}
[data-testid="stAppViewBlockContainer"],
[data-testid="stAppViewBlockContainer"] > div,
[data-testid="stAppViewBlockContainer"] > div > div {
    background: #ffffff !important;
}
/* 主内容区两列 */
[data-testid="stAppViewBlockContainer"] [data-testid="stHorizontalBlock"] {
    background: #ffffff !important;
}
[data-testid="stAppViewBlockContainer"] [data-testid="stHorizontalBlock"] > div {
    background: #ffffff !important;
}
[data-testid="stHorizontalBlock"] {
    column-gap: 0 !important;
    gap: 0 !important;
}
[data-testid="stHorizontalBlock"] > *:first-child {
    border-right: 1px solid #d4cec4 !important;
    padding-right: 28px !important;
    margin-right: 0 !important;
}
[data-testid="stHorizontalBlock"] > *:last-child {
    padding-left: 28px !important;
}

[data-testid="stHeader"] {
    background: rgba(251,249,246,0.94);
    backdrop-filter: blur(10px);
    border-bottom: 3px double var(--ink-black);
}

/* ── 标题 ── */
.main-title {
    font-family: 'Noto Serif SC', serif !important;
    font-size: 2.8rem !important; font-weight: 900 !important;
    color: var(--ink-black) !important; letter-spacing: 10px !important;
}
.main-subtitle {
    color: var(--muted); font-size: 0.95rem; font-weight: 400;
    font-style: italic; font-family: 'Newsreader', 'Noto Serif SC', serif;
}

/* ── 侧边栏：暖纸色 ── */
[data-testid="stSidebar"] {
    background: var(--surface-warm);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * {
    color: var(--ink-black) !important;
    font-family: 'DM Sans', 'Noto Serif SC', sans-serif !important;
    pointer-events: auto !important;
}
[data-testid="stSidebar"] button,
[data-testid="stSidebar"] [data-testid="collapsedControl"],
[data-testid="stSidebar"] [data-testid="collapsedControl"] * {
    font-family: 'Material Icons', 'Material Symbols Outlined', 'DM Sans', system-ui, sans-serif !important;
}
[data-testid="stSidebar"] [title] {
    pointer-events: auto !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    font-weight: 700 !important; letter-spacing: 1px !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--ink-black) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:hover,
[data-testid="stSidebar"] input:hover { border-color: var(--muted) !important; }
[data-testid="stSidebar"] hr { border-color: var(--border) !important; }

.sidebar-brand {
    font-family: 'Noto Serif SC', serif !important;
    font-size: 1.2rem !important; font-weight: 900 !important;
    color: var(--ink-black) !important; letter-spacing: 4px !important;
}
.sidebar-dot { display: inline-block; width: 5px; height: 5px; margin-right: 6px; }
.sidebar-dot.online { background: var(--ink-blue); animation: ed-pulse 3s ease-in-out infinite; }
@keyframes ed-pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── 合同输入区 ── */
.contract-wrapper {
    background: #ffffff;
    border: 1px solid var(--border);
}
.contract-wrapper:focus-within { border-color: var(--ink-black); }
.contract-wrapper textarea,
.contract-wrapper [data-testid="stTextArea"] textarea,
[data-testid="stTextArea"] .contract-wrapper textarea {
    background: #ffffff !important;
    font-family: 'Newsreader', 'Noto Serif SC', serif !important;
    font-size: 1rem !important; line-height: 2 !important;
    color: #1c1c1c !important; border: none !important; box-shadow: none !important;
    background-image: repeating-linear-gradient(0deg,
        transparent, transparent 31px,
        rgba(0,0,0,0.02) 31px, rgba(0,0,0,0.02) 32px) !important;
}
.contract-wrapper textarea::placeholder,
.contract-wrapper [data-testid="stTextArea"] textarea::placeholder {
    color: #c5bfb0 !important;
    font-family: 'Newsreader', 'Noto Serif SC', serif !important;
    font-style: italic !important;
}

/* ── 按钮（墨黑矩形）── */
[data-testid="stButton"] button,
div[data-testid="stButton"] > button,
button[kind="primary"],
button[kind="secondary"] {
    background: #1c1c1c !important;
    color: #ffffff !important;
    border: none !important; border-radius: 0 !important;
    font-weight: 600 !important; letter-spacing: 2px !important;
    font-family: 'Noto Sans SC', 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important; padding: 12px 28px !important;
    text-transform: none !important;
}
[data-testid="stButton"] button *,
div[data-testid="stButton"] > button *,
[data-testid="stButton"] p,
[data-testid="stButton"] span {
    color: #ffffff !important;
    font-family: 'Noto Sans SC', 'DM Sans', sans-serif !important;
}
[data-testid="stButton"] button:hover,
div[data-testid="stButton"] > button:hover {
    background: #000 !important;
    transform: none !important; box-shadow: none !important;
    color: #ffffff !important;
}
[data-testid="stButton"] button[kind="primary"],
button[kind="primary"] {
    border-bottom: 2px solid #9b2c2c !important;
}

/* ── 文件上传器 ── */
[data-testid="stFileUploader"] label {
    display: none !important;
}
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] [data-testid="stFileDropzone"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    padding: 12px !important;
}
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] div {
    font-family: 'DM Sans', 'Noto Sans SC', sans-serif !important;
    font-size: 0.65rem !important;
    color: var(--muted) !important;
    letter-spacing: 1px !important;
}
[data-testid="stFileUploader"] button {
    font-family: 'Noto Sans SC', 'DM Sans', sans-serif !important;
    font-size: 0.7rem !important;
}

/* ── 链接 ── */
a, a:visited { color: var(--ink-blue) !important; }
[data-testid="stProgress"] > div > div { background: var(--ink-black) !important; }

.timeline-round {
    background: var(--surface); border-left: 3px solid var(--ink-black);
    padding: 6px 12px; margin: 4px 0;
    font-family: 'DM Sans', sans-serif; font-size: 0.72rem; color: var(--muted);
    letter-spacing: 0.5px;
}

.report-card {
    background: var(--paper); padding: 28px 32px; margin: 16px 0;
    border: 1px solid var(--border);
}

.risk-high, .risk-medium, .risk-low {
    display:inline-block; padding:2px 10px; font-weight:500; font-size:0.72rem;
    letter-spacing: 1px; font-family: 'DM Sans', sans-serif;
}
.risk-high   { background:var(--red-bg); color:var(--ink-red); border-bottom: 1px solid var(--ink-red); }
.risk-medium { background:var(--amber-bg); color:var(--ink-amber); border-bottom: 1px solid var(--ink-amber); }
.risk-low    { background:var(--green-bg); color:var(--ink-green); border-bottom: 1px solid var(--ink-green); }

.stat-grid {
    display: grid !important;
    grid-template-columns: 1fr 1fr 1fr !important;
    gap: 0 !important;
    border-top: 1px solid var(--border) !important;
    border-left: 1px solid var(--border) !important;
}
.stat-cell {
    padding: 24px 12px !important;
    text-align: center !important;
    border-right: 1px solid var(--border) !important;
    border-bottom: 1px solid var(--border) !important;
    background: #ffffff !important;
}
.stat-num {
    font-family: 'Noto Serif SC', serif !important;
    font-size: 2rem !important; font-weight: 900 !important;
    display: block; line-height: 1;
}
.stat-num.high { color: #9b2c2c !important; }
.stat-num.mid { color: #8b6914 !important; }
.stat-num.rounds { color: #1c1c1c !important; }
.stat-lbl {
    font-size: 0.55rem !important; color: #8a8378 !important;
    text-transform: uppercase !important; letter-spacing: 2px !important;
    font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important;
    margin-top: 8px !important; display: block;
}

[data-testid="stExpander"] details {
    border: 1px solid var(--border) !important;
    background: var(--surface) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important; color: var(--ink-black) !important;
    padding: 10px 14px !important; font-family: 'DM Sans', sans-serif !important;
    font-size: 0.65rem !important; letter-spacing: 2px !important;
    text-transform: uppercase !important;
}
[data-testid="stInfo"],
[data-testid="stNotification"],
[data-testid="stAlert"],
[data-testid="stCallout"],
div[data-baseweb="notification"] {
    background: #ffffff !important;
    border: 1px solid #d4cec4 !important;
}
[data-testid="stInfo"] *,
[data-testid="stNotification"] * {
    background: transparent !important;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: var(--border); }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── 尺寸: 侧边栏260 / 主flex / 右380 ── */
[data-testid="stSidebar"] { width: 260px !important; flex-shrink: 0 !important; }
[data-testid="stSidebarContent"] { width: 260px !important; }
[data-testid="stAppViewBlockContainer"] {
    padding: 40px 38px 0 38px !important;
    max-width: 100%;
    background: #ffffff !important;
}

/* ── 主内容区白色底色 ── */
section[data-testid="stAppViewBlockContainer"] {
    background: #ffffff !important;
}

/* ── 去掉侧边栏折叠按钮的提示文字 ── */
button[data-testid="baseButton-header"] [data-testid="stTooltipIcon"],
button[data-testid="baseButton-headerNoPadding"] [data-testid="stTooltipIcon"] {
    display: none !important;
}

/* ── checkbox 字体 ── */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] span {
    font-size: 0.7rem !important;
    font-family: 'DM Sans', 'Noto Sans SC', sans-serif !important;
}

/* ── 下载/复制 白色按钮 ── */
[data-testid="stDownloadButton"] button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #ffffff !important;
    color: #1c1c1c !important;
    border: 1px solid #d4cec4 !important;
    padding: 0.25rem 0.75rem !important;
    margin: 0 !important;
    border-radius: 0 !important;
    line-height: 1.6 !important;
    width: 100% !important;
    min-height: 2.5rem !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: #f4f1ea !important;
}
[data-testid="stDownloadButton"] {
    margin: 0 !important;
    padding: 0 !important;
}

/* ── 移动端 ── */
@media (max-width: 768px) {
    .main-title { font-size: 1.8rem !important; letter-spacing: 4px !important; }
    div[data-testid="column"] { min-width: 100% !important; }
    .report-card { padding: 18px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════
for key, default in [
    ("report", ""),
    ("log", ""),
    ("summary", {}),
    ("report_history", []),
    ("last_thread_id", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ═══════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sidebar-brand">⚖ 法眼 · 合同审查 Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<span class="sidebar-dot online"></span>'
        '<span style="font-size:0.75rem;color:#8a8fa0;letter-spacing:0.5px;">REACT AGENT · QWEN-PLUS</span>',
        unsafe_allow_html=True,
    )
    st.divider()

    try:
        api_key = st.secrets["DASHSCOPE_API_KEY"]
    except (KeyError, FileNotFoundError):
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        api_key = st.text_input(
            "DashScope API Key",
            type="password",
            placeholder="sk-...",
            help="去 dashscope.console.aliyun.com 获取",
        )

    st.markdown("**合同类型**")
    # 记住上次选择的合同类型
    if "last_contract_type" not in st.session_state:
        st.session_state.last_contract_type = "房屋租赁合同"
    contract_types = CONTRACT_TYPES
    default_idx = 0
    if st.session_state.last_contract_type in contract_types:
        default_idx = contract_types.index(st.session_state.last_contract_type)
    contract_type = st.selectbox(
        "合同类型",
        contract_types,
        index=default_idx,
        label_visibility="collapsed",
    )
    if contract_type == "自定义":
        contract_type = st.text_input(
            "输入合同类型", placeholder="如：软件开发合同", label_visibility="collapsed"
        )

    st.markdown("**上传合同**")
    uploaded_file = st.file_uploader(
        "上传合同文件",
        type=["txt", "pdf", "docx", "jpg", "jpeg", "png", "bmp", "webp"],
        label_visibility="collapsed",
    )

    # Self-Reflection 开关
    if "enable_reflection" not in st.session_state:
        st.session_state.enable_reflection = False
    st.session_state.enable_reflection = st.checkbox(
        "Self-Reflection 反思审查",
        value=st.session_state.enable_reflection,
    )

    st.divider()

    # 审查统计
    if st.session_state.summary:
        s = st.session_state.summary
        st.markdown("**Statistics**")
        st.markdown(
            f"""<div style="display:flex;flex-direction:column;gap:6px;font-family:'DM Sans',sans-serif;">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;">
                <span style="display:flex;align-items:center;gap:6px;font-size:0.72rem;color:#8a8378;">
                    <span style="display:inline-block;width:8px;height:8px;background:#9b2c2c;"></span> High Risk
                </span>
                <span style="font-weight:700;font-size:1rem;color:#9b2c2c;">{s.get("high", 0)}</span>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;">
                <span style="display:flex;align-items:center;gap:6px;font-size:0.72rem;color:#8a8378;">
                    <span style="display:inline-block;width:8px;height:8px;background:#8b6914;"></span> Medium Risk
                </span>
                <span style="font-weight:700;font-size:1rem;color:#8b6914;">{s.get("medium", 0)}</span>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;">
                <span style="display:flex;align-items:center;gap:6px;font-size:0.72rem;color:#8a8378;">
                    <span style="display:inline-block;width:8px;height:8px;background:#1c1c1c;"></span> Rounds
                </span>
                <span style="font-weight:700;font-size:1rem;color:#1c1c1c;">{s.get("rounds", 0)}</span>
            </div>
        </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── 历史报告 ──
    if st.session_state.report_history:
        st.markdown("**📂 历史报告**")
        items_per_row = 3
        for row_start in range(0, len(st.session_state.report_history), items_per_row):
            row_items = st.session_state.report_history[row_start : row_start + items_per_row]
            cols = st.columns(items_per_row)
            for j, h in enumerate(row_items):
                i = row_start + j
                with cols[j]:
                    safe_type = h["type"].replace("/", "_")
                    st.download_button(
                        f"⬇ {h['time']}",
                        h["report"],
                        file_name=f"审查报告_{safe_type}_{h['time'].replace(':', '').replace(' ', '_')}.txt",
                        mime="text/plain",
                        key=f"hist_dl_{i}",
                        help=f"{h['type']} · 🔴{h['summary'].get('high', '-')} 🟡{h['summary'].get('medium', '-')}",
                        use_container_width=True,
                    )
                    st.caption(
                        f"{h['type']} · 🔴{h['summary'].get('high', '-')} 🟡{h['summary'].get('medium', '-')}"
                    )

    if st.session_state.report_history:
        if "show_clear_confirm" not in st.session_state:
            st.session_state.show_clear_confirm = False
        if not st.session_state.show_clear_confirm:
            if st.button("🗑 清空历史", use_container_width=True):
                st.session_state.show_clear_confirm = True
                st.rerun()
        else:
            st.warning(f"确定清空 {len(st.session_state.report_history)} 条历史报告？")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确认清空", use_container_width=True):
                    st.session_state.report_history = []
                    st.session_state.show_clear_confirm = False
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.show_clear_confirm = False
                    st.rerun()

    st.caption("© 2026 法眼 · Powered by Qwen-Plus")

# ═══════════════════════════════════════════════════════
# 页面标题
# ═══════════════════════════════════════════════════════
st.markdown('<div class="main-title">法眼</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-subtitle">合同审查 Agent · 法规 × 判例 × 地方政策 · 三重交叉验证</div>',
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════
# 读取上传文件（纯文本直接读，图片走 OCR）
# ═══════════════════════════════════════════════════════
if uploaded_file:
    contract_text, ocr_error = read_uploaded_contract(uploaded_file, api_key)
    if ocr_error:
        st.error(ocr_error)
        contract_text = ""
    elif Path(uploaded_file.name).suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        st.sidebar.success(f"已从照片提取 {len(contract_text)} 字")
else:
    contract_text = ""

# ═══════════════════════════════════════════════════════
# 两栏布局
# ═══════════════════════════════════════════════════════
col_left, col_right = st.columns([7, 2], gap="small")

with col_left:
    # 标题 + 按钮同一行
    col_t, col_b = st.columns([3, 1], gap="small")
    with col_t:
        st.markdown("#### Contract Source")
    with col_b:
        start_review = st.button("开始审查", type="primary", use_container_width=True)

    # 纸张质感容器
    st.markdown('<div class="contract-wrapper">', unsafe_allow_html=True)
    contract_text = st.text_area(
        "合同原文",
        value=contract_text,
        placeholder="在此粘贴合同全文，或从左侧上传文件...\n\n按 Enter 开始审查",
        height=380,
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="key-hint" style="font-family:\'DM Sans\',sans-serif;font-size:0.65rem;'
        'color:var(--muted);letter-spacing:0.5px;margin-top:8px;">'
        "<kbd style=\"font-family:'DM Sans',sans-serif;font-weight:600;color:var(--ink-black);"
        "background:var(--paper);border:1px solid var(--border);padding:2px 6px;font-size:0.6rem;"
        'letter-spacing:1px;">Enter</kbd> 开始审查 &nbsp; '
        "<kbd style=\"font-family:'DM Sans',sans-serif;font-weight:600;color:var(--ink-black);"
        "background:var(--paper);border:1px solid var(--border);padding:2px 6px;font-size:0.6rem;"
        'letter-spacing:1px;">Shift</kbd> + '
        "<kbd style=\"font-family:'DM Sans',sans-serif;font-weight:600;color:var(--ink-black);"
        "background:var(--paper);border:1px solid var(--border);padding:2px 6px;font-size:0.6rem;"
        'letter-spacing:1px;">Enter</kbd> 换行'
        "</div>",
        unsafe_allow_html=True,
    )

    # 功能概览卡片
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Capabilities", expanded=False):
        st.markdown(
            """<div style="display:grid;grid-template-columns:1fr 1fr;gap:0;margin-top:4px;border-top:1px solid var(--border);border-left:1px solid var(--border);">
            <div style="padding:14px 16px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);">
                <div style="font-weight:600;color:var(--ink-black);font-size:0.75rem;font-family:'DM Sans',sans-serif;">11-Tool ReAct Agent</div>
                <div style="font-size:0.7rem;color:var(--muted);margin-top:4px;">自主决策审查步骤 + 反思</div>
            </div>
            <div style="padding:14px 16px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);">
                <div style="font-weight:600;color:var(--ink-black);font-size:0.75rem;font-family:'DM Sans',sans-serif;">Five Knowledge Bases</div>
                <div style="font-size:0.7rem;color:var(--muted);margin-top:4px;">法规·判例·政策·税务·动态</div>
            </div>
            <div style="padding:14px 16px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);">
                <div style="font-weight:600;color:var(--ink-black);font-size:0.75rem;font-family:'DM Sans',sans-serif;">Six Contract Types</div>
                <div style="font-size:0.7rem;color:var(--muted);margin-top:4px;">每种配备法定红线标准</div>
            </div>
            <div style="padding:14px 16px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);">
                <div style="font-weight:600;color:var(--ink-black);font-size:0.75rem;font-family:'DM Sans',sans-serif;">Multi-Interface</div>
                <div style="font-size:0.7rem;color:var(--muted);margin-top:4px;">CLI·Web·API·MCP·Docker</div>
            </div>
        </div>""",
            unsafe_allow_html=True,
        )

    # Enter 快捷键触发审查
    st.markdown(
        """
    <script>
    (function() {
        const checkAndBind = function() {
            const textareas = document.querySelectorAll('.contract-wrapper textarea');
            if (textareas.length === 0) { setTimeout(checkAndBind, 300); return; }
            textareas.forEach(function(ta) {
                if (ta.dataset.enterBound) return;
                ta.dataset.enterBound = '1';
                ta.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            if (btn.innerText.includes('开始审查')) {
                                btn.click();
                                break;
                            }
                        }
                    }
                });
            });
        };
        checkAndBind();
    })();
    </script>
    """,
        unsafe_allow_html=True,
    )

    if start_review:
        if not contract_text.strip():
            st.error("请粘贴或上传合同文本")
        elif not api_key:
            st.error("请在侧边栏填写 API Key")
        else:
            # 新审查前保存旧报告到历史
            if st.session_state.report:
                st.session_state.report_history = save_to_history(
                    st.session_state.report_history,
                    st.session_state.report,
                    st.session_state.log,
                    st.session_state.get("last_contract_type", "未知"),
                    st.session_state.summary,
                )
                save_report_file(
                    st.session_state.report, st.session_state.get("last_contract_type", "未知")
                )

            st.session_state["last_contract_type"] = contract_type
            st.session_state.last_contract_type = contract_type

            progress_bar = st.progress(0, "准备审查...")
            thinking_placeholder = st.empty()
            tool_placeholder = st.empty()

            def render_tool_log(lines):
                """内联渲染工具日志为 HTML。"""
                parts = [
                    '<div style="font-family:DM Sans,sans-serif;font-size:0.72rem;'
                    "color:#8a8378;max-height:360px;overflow-y:auto;padding:8px;"
                    "background:var(--paper);border-left:3px solid var(--ink-black);"
                    'border-radius:0 4px 4px 0;">'
                ]
                for tl in lines:
                    if "轮" in tl:
                        tag = (
                            f'<div style="border-left-color:#1c1c1c;font-weight:600;'
                            f'padding:4px 0 4px 10px;margin:2px 0;">{tl}</div>'
                        )
                    else:
                        tag = f'<div style="padding:2px 0 2px 10px;margin:1px 0;">{tl}</div>'
                    parts.append(tag)
                parts.append("</div>")
                return "".join(parts)

            runner = StreamingReviewRunner(
                api_key=api_key,
                enable_reflection=st.session_state.enable_reflection,
            )
            runner.start(contract_text, contract_type)

            thinking_text = ""
            tool_lines = []
            round_num = 0

            for event in runner.events():
                if event["type"] == "thinking_delta":
                    thinking_text += event["content"]
                    display = thinking_text[-800:]
                    thinking_placeholder.markdown(
                        f'<div style="font-family:DM Sans,sans-serif;font-size:0.72rem;'
                        f"color:#8a8378;max-height:200px;overflow-y:auto;padding:10px 14px;"
                        f"background:var(--paper);border-left:3px solid var(--ink-black);"
                        f'border-radius:0 4px 4px 0;white-space:pre-wrap;">{display}</div>',
                        unsafe_allow_html=True,
                    )

                elif event["type"] == "round_start":
                    round_num = event["round"]
                    pct = min(0.88, round_num / 20)
                    progress_bar.progress(pct, f"第 {round_num} 轮 · {int(pct * 100)}%")
                    tool_lines.append(f"第 {round_num} 轮")
                    tool_placeholder.markdown(render_tool_log(tool_lines), unsafe_allow_html=True)

                elif event["type"] == "tool_start":
                    tool_lines.append(f"🔧 {event['name']}()")
                    tool_placeholder.markdown(render_tool_log(tool_lines), unsafe_allow_html=True)

                elif event["type"] == "tool_result":
                    tool_lines.append(f"📋 {event['name']} → {event['result_len']} 字符")
                    tool_placeholder.markdown(render_tool_log(tool_lines), unsafe_allow_html=True)

                elif event["type"] == "tool_error":
                    tool_lines.append(f"⚠️ {event['name']}: {event.get('message', '失败')}")
                    tool_placeholder.markdown(render_tool_log(tool_lines), unsafe_allow_html=True)

                elif event["type"] == "retry":
                    tool_lines.append(f"🔄 API重试 {event['attempt']}/3")
                    tool_placeholder.markdown(render_tool_log(tool_lines), unsafe_allow_html=True)

                elif event["type"] == "error":
                    st.error(f"审查出错：{event['message']}")
                    st.stop()

                elif event["type"] == "done":
                    progress_bar.progress(0.92, "生成报告中...")
                    thread_id = event.get("thread_id", "")
                    if thread_id:
                        st.session_state.last_thread_id = thread_id
                    break

            progress_bar.progress(1.0, "审查完成 ✅")
            time.sleep(0.3)
            progress_bar.empty()
            thinking_placeholder.empty()
            tool_placeholder.empty()

            st.session_state.report = runner.report
            st.session_state.log = runner.log
            st.session_state.summary = extract_summary(runner.report, runner.log)
            st.rerun()

# ═══════════════════════════════════════════════════════
# 右栏：审查结果
# ═══════════════════════════════════════════════════════
with col_right:
    st.markdown("#### Inspection Results")

    if st.session_state.report:
        # 统计卡片
        s = st.session_state.summary
        if s:
            st.markdown(
                f"""<div class="stat-grid">
                <div class="stat-cell">
                    <span class="stat-num high">{s.get("high", "-")}</span>
                    <span class="stat-lbl">High Risk</span>
                </div>
                <div class="stat-cell">
                    <span class="stat-num mid">{s.get("medium", "-")}</span>
                    <span class="stat-lbl">Medium Risk</span>
                </div>
                <div class="stat-cell">
                    <span class="stat-num rounds">{s.get("rounds", "-")}</span>
                    <span class="stat-lbl">Rounds</span>
                </div>
            </div>""",
                unsafe_allow_html=True,
            )

        # 审查过程（时间线折叠）
        with st.expander("Review Process", expanded=False):
            log = st.session_state.log
            for line in log.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "🔧" in line or "📋" in line:
                    st.markdown(f'<div class="timeline-round">{line}</div>', unsafe_allow_html=True)
                elif "第" in line and "轮" in line:
                    st.markdown(
                        f'<div class="timeline-round" style="border-left-color:#1c1c1c;font-weight:600;">{line}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.text(line)

        st.divider()

        # 报告卡片（默认折叠）
        with st.expander("Full Report", expanded=False):
            st.markdown('<div class="report-card">', unsafe_allow_html=True)
            st.markdown(st.session_state.report)
            st.markdown("</div>", unsafe_allow_html=True)

        col_dl, col_cp = st.columns([1, 1])
        with col_dl:
            st.download_button(
                "下载报告",
                st.session_state.report,
                file_name=f"审查报告_{contract_type}_{date.today().isoformat()}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_cp:
            st.markdown(
                """<button id="copy-btn" onclick="
                    var text = document.querySelector('.report-card').innerText;
                    navigator.clipboard.writeText(text).then(function(){
                        var btn=document.getElementById('copy-btn');
                        btn.innerText='已复制';
                        setTimeout(function(){btn.innerText='复制报告';},2000);
                    });
                " style="
                    display:inline-flex; align-items:center; justify-content:center;
                    width:100%; min-height:2.5rem;
                    padding:0.25rem 0.75rem; margin:0;
                    border:1px solid #d4cec4;
                    background:#ffffff; color:#1c1c1c;
                    cursor:pointer;
                    border-radius:0; line-height:1.6;
                ">复制报告</button>""",
                unsafe_allow_html=True,
            )
    else:
        st.info('Paste contract and click "开始审查" to launch review')
