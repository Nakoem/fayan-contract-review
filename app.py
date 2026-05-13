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

st.set_page_config(page_title="法眼 · 合同审查", page_icon="⚖️", layout="wide")

# ═══════════════════════════════════════════════════════
# 自定义 CSS
# ═══════════════════════════════════════════════════════
st.markdown(
    """
<style>
/* ═══════════════════════════════════════════════
   Slack-Inspired — 深茄紫 + 奶油薰衣草
   #4a154b茄紫底 + #f4ede4奶油 + 药丸按钮
   ═══════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --primary: #5c1d5e;
    --primary-deep: #4a154b;
    --primary-press: #7a2d7c;
    --on-primary: #ffffff;
    --on-aubergine-mute: #d9bdde;
    --canvas: #f4ede4;
    --canvas-lavender: #f9f0ff;
    --surface: #ffffff;
    --surface-aubergine: #5c1d5e;
    --hairline: #e6e6e6;
    --ink: #1d1d1d;
    --ink-mute: #696969;
    --link-blue: #1264a3;
    --body: #454545;
    --body-mid: #888888;
    --red: #cc4117;
    --red-bg: rgba(204,65,23,0.08);
    --amber: #c37d0d;
    --amber-bg: rgba(195,125,13,0.08);
    --green: #007a5a;
    --green-bg: rgba(0,122,90,0.08);
}

html, body, [class*="css"] { font-family: 'Inter', system-ui, -apple-system, 'Noto Sans SC', sans-serif; color: var(--body); }
h1, h2, h3, h4, h5, h6 { font-family: 'Inter', system-ui, -apple-system, 'Noto Sans SC', sans-serif; font-weight: 600; color: var(--ink); }

[data-testid="stAppViewContainer"] { background: var(--canvas); }

[data-testid="stHeader"] {
    background: rgba(244,237,228,0.94);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--hairline);
}

/* ── 标题 ── */
.main-title {
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 2.4rem !important; font-weight: 600 !important;
    color: var(--ink) !important; letter-spacing: -0.5px;
}
.main-subtitle { color: var(--body-mid); font-size: 0.9rem; font-weight: 400; }

/* ── 侧边栏：深茄紫 ── */
[data-testid="stSidebar"] {
    background: var(--surface-aubergine);
    border-right: 1px solid rgba(255,255,255,0.08);
}
[data-testid="stSidebar"] * { color: var(--on-aubergine-mute) !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label { color: var(--on-primary) !important; font-family: 'Inter', sans-serif !important; font-weight: 600; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] input {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 8px !important; color: var(--on-primary) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:hover,
[data-testid="stSidebar"] input:hover { border-color: rgba(255,255,255,0.3) !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1) !important; }

.sidebar-brand {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.1rem !important; font-weight: 600 !important;
    color: var(--on-primary) !important;
}
.sidebar-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; }
.sidebar-dot.online { background: var(--link-blue); animation: pulse-dot 2.5s infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* ── 合同输入区 ── */
.contract-wrapper {
    background: var(--canvas);
    border: 1px solid var(--hairline);
    border-radius: 8px;
}
.contract-wrapper:focus-within { border-color: var(--primary); }
.contract-wrapper textarea {
    background: transparent !important;
    font-family: 'JetBrains Mono', 'SF Mono', monospace !important;
    font-size: 0.85rem !important; line-height: 1.7 !important;
    color: var(--ink) !important; border: none !important; box-shadow: none !important;
}
.contract-wrapper textarea::placeholder { color: var(--body-mid) !important; }

/* ── 按钮（黑药丸）── */
div[data-testid="stButton"] > button {
    background: var(--primary) !important; color: var(--on-primary) !important;
    border: 1px solid transparent !important;
    border-radius: 9999px !important; font-weight: 600 !important;
    font-size: 0.875rem !important; padding: 10px 24px !important;
    transition: opacity 0.15s !important;
}
div[data-testid="stButton"] > button:hover {
    opacity: 0.85 !important;
    transform: none !important; box-shadow: none !important;
}

/* ── 茄紫强调 ── */
a, a:visited { color: var(--link-blue) !important; }
[data-testid="stProgress"] > div > div { background: var(--primary) !important; }

.timeline-round {
    background: var(--surface); border-left: 2px solid var(--brand-green);
    border-radius: 0 6px 6px 0; padding: 8px 12px; margin: 4px 0;
    font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: var(--body);
}

.report-card {
    background: var(--canvas); border-radius: 12px; padding: 28px 32px; margin: 16px 0;
    border: 1px solid var(--hairline);
}

.risk-high, .risk-medium, .risk-low {
    display:inline-block; padding:2px 10px; border-radius:9999px; font-weight:500; font-size:0.8rem;
}
.risk-high   { background:var(--red-bg); color:var(--red); }
.risk-medium { background:var(--amber-bg); color:var(--amber); }
.risk-low    { background:var(--green-bg); color:var(--green); }

.stat-box {
    background: var(--surface); border-radius: 8px; padding: 18px 20px;
    text-align: center; border: 1px solid var(--hairline);
}
.stat-num { font-family: 'Inter', sans-serif; font-size: 2rem; font-weight: 600; color: var(--ink); }
.stat-label { font-size: 0.75rem; color: var(--body-mid); text-transform: uppercase; letter-spacing: 1px; }

[data-testid="stExpander"] details {
    border-radius: 8px !important; border: 1px solid var(--hairline) !important;
    background: var(--surface) !important;
}
[data-testid="stExpander"] summary { font-weight: 600 !important; color: var(--ink) !important; padding: 10px 14px !important; }
[data-testid="stInfo"] { background: var(--surface) !important; border: 1px solid var(--hairline) !important; border-radius: 8px !important; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--canvas); }
::-webkit-scrollbar-thumb { background: var(--hairline); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--primary); }

/* ── 收紧全局留白 ── */
[data-testid="stAppViewBlockContainer"] {
    padding: 2rem 3rem 0 3rem;
    max-width: 100%;
}

/* ── 移动端 ── */
@media (max-width: 768px) {
    .main-title { font-size: 1.6rem !important; }
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
for key, default in [("report", ""), ("log", ""), ("summary", {}), ("report_history", [])]:
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
        "上传 .txt / .pdf / .docx / .jpg/.png",
        type=["txt", "pdf", "docx", "jpg", "jpeg", "png", "bmp", "webp"],
        label_visibility="collapsed",
    )

    # Self-Reflection 开关
    if "enable_reflection" not in st.session_state:
        st.session_state.enable_reflection = True
    st.session_state.enable_reflection = st.checkbox(
        "Self-Reflection 反思审查",
        value=st.session_state.enable_reflection,
        help="开启后出报告前全局质量审核（稍慢更准）；关闭后跳过直接出报告（更快）",
    )

    st.divider()

    # 审查统计
    if st.session_state.summary:
        s = st.session_state.summary
        st.markdown("**本次统计**")
        col_a, col_b = st.columns(2)
        col_a.metric("🔴 高风险", s.get("high", 0))
        col_b.metric("🟡 中风险", s.get("medium", 0))
        st.metric("⚡ 审查轮次", s.get("rounds", 0))

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
col_left, col_right = st.columns([3, 2])

with col_left:
    # 标题 + 按钮同一行
    col_t, col_b = st.columns([3, 1])
    with col_t:
        st.markdown("#### 📄 合同原文")
    with col_b:
        start_review = st.button("🔍 开始审查", type="primary", use_container_width=True)

    # 纸张质感容器
    st.markdown('<div class="contract-wrapper">', unsafe_allow_html=True)
    contract_text = st.text_area(
        "合同原文",
        value=contract_text,
        placeholder="在此粘贴合同全文，或从左侧上传 .txt 文件...\n\n💡 粘贴后按 Enter 即可开始审查",
        height=600,
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

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
                    '<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                    "color:#5c5240;max-height:360px;overflow-y:auto;padding:8px;"
                    "background:rgba(250,248,245,0.7);border-left:3px solid #c9a96e;"
                    'border-radius:0 4px 4px 0;">'
                ]
                for tl in lines:
                    if "轮" in tl:
                        tag = (
                            f'<div style="border-left-color:#f59e0b;font-weight:600;'
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
                        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.82rem;'
                        f"color:#5c5240;max-height:200px;overflow-y:auto;padding:10px 14px;"
                        f"background:rgba(250,248,245,0.7);border-left:3px solid #c9a96e;"
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
    st.markdown("#### 📊 审查结果")

    if st.session_state.report:
        # 统计卡片
        s = st.session_state.summary
        if s:
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown(
                    f"""<div class="stat-box">
                    <div class="stat-num" style="color:#dc2626;">{s.get("high", "-")}</div>
                    <div class="stat-label">高风险条款</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with sc2:
                st.markdown(
                    f"""<div class="stat-box">
                    <div class="stat-num" style="color:#d97706;">{s.get("medium", "-")}</div>
                    <div class="stat-label">中风险条款</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with sc3:
                st.markdown(
                    f"""<div class="stat-box">
                    <div class="stat-num" style="color:#3b82f6;">{s.get("rounds", "-")}</div>
                    <div class="stat-label">审查轮次</div>
                </div>""",
                    unsafe_allow_html=True,
                )

        # 审查过程（时间线折叠）
        with st.expander("🔎 审查过程（点击展开）", expanded=False):
            log = st.session_state.log
            for line in log.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "🔧" in line or "📋" in line:
                    st.markdown(f'<div class="timeline-round">{line}</div>', unsafe_allow_html=True)
                elif "第" in line and "轮" in line:
                    st.markdown(
                        f'<div class="timeline-round" style="border-left-color:#f59e0b;font-weight:600;">{line}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.text(line)

        st.divider()

        # 报告卡片（默认折叠）
        with st.expander("📋 审查报告全文（点击展开）", expanded=False):
            st.markdown('<div class="report-card">', unsafe_allow_html=True)
            st.markdown(st.session_state.report)
            st.markdown("</div>", unsafe_allow_html=True)

        col_dl, col_cp = st.columns([3, 1])
        with col_dl:
            st.download_button(
                "📥 下载报告 (.txt)",
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
                        btn.innerText='✅ 已复制';
                        setTimeout(function(){btn.innerText='📋 复制报告';},2000);
                    });
                " style="
                    width:100%; padding:10px 0; border-radius:4px;
                    border:1px solid rgba(201,169,110,0.3);
                    background:#1a1f36; color:#e0cc9a;
                    font-weight:500; font-size:0.9rem;
                    cursor:pointer; letter-spacing:0.5px;
                ">📋 复制报告</button>""",
                unsafe_allow_html=True,
            )

    else:
        st.info("👆 粘贴合同后点击「🔍 开始审查」，或上传合同文件")

    # 功能概览卡片（右下角，始终可见）
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📌 法眼 · 能力概览", expanded=True):
        st.markdown(
            """<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px;">
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">⚖ 11工具 ReAct Agent</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">自主决策审查步骤 + 反思</div>
            </div>
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">📚 五重知识库</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">法规·判例·政策·税务·动态</div>
            </div>
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">📋 六种合同类型</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">每种配备法定红线标准</div>
            </div>
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">🚀 多种使用方式</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">CLI·Web·API·MCP·Docker</div>
            </div>
        </div>""",
            unsafe_allow_html=True,
        )
