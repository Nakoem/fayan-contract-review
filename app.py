"""
法眼 —— 合同审查 Agent Web 版
用法：streamlit run app.py
"""

import io
import re
import sys
import os
import time
import threading
import tempfile
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from main import ContractReviewAgent
from logger import init_logger, attach_web_buffer, detach_web_buffer

load_dotenv()
init_logger(mode="web")

st.set_page_config(page_title="法眼 · 合同审查", page_icon="⚖️", layout="wide")

# ═══════════════════════════════════════════════════════
# 自定义 CSS
# ═══════════════════════════════════════════════════════
st.markdown("""
<style>
/* ═══════════════════════════════════════════════
   Warp-Inspired — 终端即产品
   暖暗色画布 + Inter 字体 + 紧致几何
   ═══════════════════════════════════════════════ */

/* ── 导入字体 ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&family=DM+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&display=swap');

:root {
    --canvas: #2b2622;
    --canvas-soft: #383330;
    --hairline: #3f3a36;
    --ink: #f7f5f0;
    --body-strong: #dad2c1;
    --body: #c9c0ad;
    --mute: #aea69c;
    --primary: #f7f5f0;
    --on-primary: #2b2622;
    --red: #e5484d;
    --red-bg: rgba(229,72,77,0.12);
    --amber: #f5a623;
    --amber-bg: rgba(245,166,35,0.12);
    --green: #30a46c;
    --green-bg: rgba(48,164,108,0.12);
}

html, body, [class*="css"] { font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif; }
h1, h2, h3, h4, h5, h6 { font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif; font-weight: 500; letter-spacing: -0.3px; }

/* ── 背景：暖暗色画布 ── */
[data-testid="stAppViewContainer"] {
    background: var(--canvas);
}

/* ── 顶部栏 ── */
[data-testid="stHeader"] {
    background: rgba(43,38,34,0.92);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--hairline);
}

/* ── 标题 ── */
.main-title {
    font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif !important;
    font-size: 2.4rem !important; font-weight: 400 !important;
    color: var(--ink) !important; letter-spacing: -1.2px;
}
.main-subtitle { color: var(--body); font-size: 0.9rem; font-weight: 400; }

/* ── 侧边栏：暖暗色 + 细线分隔 ── */
[data-testid="stSidebar"] {
    background: var(--canvas);
    border-right: 1px solid var(--hairline);
}
[data-testid="stSidebar"] * { color: var(--body) !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label { color: var(--ink) !important; font-family: 'Inter', system-ui, sans-serif !important; font-weight: 500; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] input {
    background: var(--canvas-soft) !important;
    border: 1px solid var(--hairline) !important;
    border-radius: 3px !important; color: var(--ink) !important;
    transition: border-color 0.2s;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:hover,
[data-testid="stSidebar"] input:hover { border-color: var(--mute) !important; }
[data-testid="stSidebar"] hr { border-color: var(--hairline) !important; }

.sidebar-brand {
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 1.1rem !important; font-weight: 500 !important;
    color: var(--ink) !important; letter-spacing: -0.3px;
}
.sidebar-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; }
.sidebar-dot.online { background: var(--primary); animation: pulse-dot 2.5s infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* ── 合同输入区 ── */
.contract-wrapper {
    background: var(--canvas-soft);
    border: 1px solid var(--hairline);
    border-radius: 4px;
    transition: border-color 0.2s;
}
.contract-wrapper:focus-within { border-color: var(--mute); }
.contract-wrapper textarea {
    background: transparent !important;
    font-family: 'DM Mono', 'SF Mono', monospace !important;
    font-size: 0.85rem !important; line-height: 1.7 !important;
    color: var(--ink) !important; border: none !important; box-shadow: none !important;
}
.contract-wrapper textarea::placeholder { color: var(--mute) !important; }

/* ── 按钮 ── */
div[data-testid="stButton"] > button {
    background: var(--primary) !important; color: var(--on-primary) !important;
    border: 1px solid transparent !important;
    border-radius: 3px !important; font-weight: 500 !important;
    font-size: 0.875rem !important; padding: 8px 16px !important;
    letter-spacing: -0.2px !important;
    transition: opacity 0.15s !important;
}
div[data-testid="stButton"] > button:hover {
    opacity: 0.88 !important;
    transform: none !important;
    box-shadow: none !important;
    border-color: transparent !important;
}

/* ── 时间线 ── */
.timeline-round {
    background: var(--canvas-soft);
    border-left: 2px solid var(--primary);
    border-radius: 0 3px 3px 0; padding: 8px 12px; margin: 4px 0;
    font-family: 'DM Mono', monospace; font-size: 0.78rem;
    color: var(--body); white-space: pre-wrap;
}

/* ── 报告卡片 ── */
.report-card {
    background: var(--canvas-soft); border-radius: 4px; padding: 28px 32px; margin: 16px 0;
    border: 1px solid var(--hairline);
}

/* ── 风险标签 ── */
.risk-high   { display:inline-block; background:var(--red-bg); color:var(--red); padding:2px 12px; border-radius:3px; font-weight:500; font-size:0.8rem; border:1px solid rgba(229,72,77,0.2); }
.risk-medium { display:inline-block; background:var(--amber-bg); color:var(--amber); padding:2px 12px; border-radius:3px; font-weight:500; font-size:0.8rem; border:1px solid rgba(245,166,35,0.2); }
.risk-low    { display:inline-block; background:var(--green-bg); color:var(--green); padding:2px 12px; border-radius:3px; font-weight:500; font-size:0.8rem; border:1px solid rgba(48,164,108,0.2); }

/* ── 统计卡片 ── */
.stat-box {
    background: var(--canvas-soft); border-radius: 4px; padding: 18px 20px; text-align: center;
    border: 1px solid var(--hairline);
}
.stat-num { font-family: 'Inter', system-ui, sans-serif; font-size: 2rem; font-weight: 400; letter-spacing: -0.5px; }
.stat-label { font-size: 0.75rem; color: var(--mute); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* ── 展开器 ── */
[data-testid="stExpander"] details {
    border-radius: 4px !important; border: 1px solid var(--hairline) !important;
    background: var(--canvas-soft) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 500 !important; color: var(--ink) !important;
    padding: 10px 14px !important;
}

/* ── 信息提示 ── */
[data-testid="stInfo"] {
    background: var(--canvas-soft) !important;
    border: 1px solid var(--hairline) !important; border-radius: 4px !important;
}

/* ── 进度条 ── */
[data-testid="stProgress"] > div > div {
    background: var(--primary) !important;
}

/* ── 滚动条 ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--canvas); }
::-webkit-scrollbar-thumb { background: var(--hairline); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--mute); }

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
""", unsafe_allow_html=True)

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
            "DashScope API Key", type="password", placeholder="sk-...",
            help="去 dashscope.console.aliyun.com 获取"
        )

    st.markdown("**合同类型**")
    # 记住上次选择的合同类型
    if "last_contract_type" not in st.session_state:
        st.session_state.last_contract_type = "房屋租赁合同"
    contract_types = [
        "房屋租赁合同", "劳动合同", "买卖合同", "服务合同", "合作协议", "借款合同",
        "自定义",
    ]
    default_idx = 0
    if st.session_state.last_contract_type in contract_types:
        default_idx = contract_types.index(st.session_state.last_contract_type)
    contract_type = st.selectbox(
        "合同类型", contract_types,
        index=default_idx,
        label_visibility="collapsed",
    )
    if contract_type == "自定义":
        contract_type = st.text_input("输入合同类型", placeholder="如：软件开发合同", label_visibility="collapsed")

    st.markdown("**上传合同**")
    uploaded_file = st.file_uploader(
        "上传 .txt 或 .jpg/.png 照片", type=["txt", "jpg", "jpeg", "png", "bmp", "webp"],
        label_visibility="collapsed",
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
            row_items = st.session_state.report_history[row_start:row_start + items_per_row]
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
                    st.caption(f"{h['type']} · 🔴{h['summary'].get('high', '-')} 🟡{h['summary'].get('medium', '-')}")

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
st.markdown('<div class="main-subtitle">合同审查 Agent · 法规 × 判例 × 地方政策 · 三重交叉验证</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# 读取上传文件（纯文本直接读，图片走 OCR）
# ═══════════════════════════════════════════════════════
if uploaded_file:
    ext = Path(uploaded_file.name).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        # 先保存临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        if not api_key:
            st.error("OCR 需要 API Key，请在侧边栏填写或配置到 .env / Streamlit Secrets")
            contract_text = ""
        else:
            with st.spinner("正在 OCR 识别合同照片中的文字..."):
                try:
                    from ocr_utils import ocr_image
                    contract_text = ocr_image(tmp_path, api_key)
                    st.sidebar.success(f"已从照片提取 {len(contract_text)} 字")
                except Exception as e:
                    st.error(f"OCR 失败：{e}")
                    contract_text = ""
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    else:
        contract_text = uploaded_file.read().decode("utf-8")
else:
    contract_text = ""

# ═══════════════════════════════════════════════════════
# 两栏布局
# ═══════════════════════════════════════════════════════
col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown("#### 📄 合同原文")

    # 纸张质感容器
    st.markdown('<div class="contract-wrapper">', unsafe_allow_html=True)
    contract_text = st.text_area(
        "合同原文",
        value=contract_text,
        placeholder="在此粘贴合同全文，或从左侧上传 .txt 文件...\n\n💡 粘贴后按 Enter 即可开始审查",
        height=600,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Enter 快捷键触发审查
    st.markdown("""
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
    """, unsafe_allow_html=True)

    # 开始按钮
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔍 开始审查", type="primary", use_container_width=True):
        if not contract_text.strip():
            st.error("请粘贴或上传合同文本")
        elif not api_key:
            st.error("请在侧边栏填写 API Key")
        else:
            # 开始新审查前，把旧报告存入历史
            if st.session_state.report:
                from datetime import datetime
                st.session_state.report_history.insert(0, {
                    "time": datetime.now().strftime("%m-%d %H:%M"),
                    "type": st.session_state.get("last_contract_type", "未知"),
                    "report": st.session_state.report,
                    "log": st.session_state.log,
                    "summary": st.session_state.summary,
                })
                # 最多保留 20 条
                if len(st.session_state.report_history) > 20:
                    st.session_state.report_history = st.session_state.report_history[:20]

                # 同时自动保存到审查报告文件夹
                report_dir = Path(__file__).parent / "审查报告"
                report_dir.mkdir(exist_ok=True)
                safe_type = st.session_state.get("last_contract_type", "未知").replace("/", "_")
                filename = f"审查报告_{safe_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                try:
                    (report_dir / filename).write_text(st.session_state.report, encoding="utf-8")
                except Exception:
                    pass  # 文件保存失败不影响审查

            st.session_state["last_contract_type"] = contract_type
            st.session_state.last_contract_type = contract_type  # 记住选择

            buf = io.StringIO()
            progress_bar = st.progress(0, "准备审查...")
            status_text = st.empty()

            result = {"report": "", "done": False, "error": None}

            def _run():
                try:
                    attach_web_buffer(buf)
                    with redirect_stdout(buf):
                        agent = ContractReviewAgent(api_key=api_key, verbose=True)
                        result["report"] = agent.run(contract_text, contract_type)
                except Exception as e:
                    result["error"] = e
                finally:
                    detach_web_buffer()
                    result["done"] = True

            t = threading.Thread(target=_run, daemon=True)
            t.start()

            # 在右栏实时展示审查过程
            live_display = st.empty()
            while not result["done"]:
                log_snapshot = buf.getvalue()
                rounds = log_snapshot.count("┌─ 第")
                if "generate_final_report" in log_snapshot:
                    pct, label = 0.92, f"生成报告中... 92%"
                elif rounds > 0:
                    pct = min(0.88, rounds / 20)
                    label = f"第 {rounds} 轮 · {int(pct * 100)}%"
                else:
                    pct, label = 0.02, "启动 Agent... 2%"
                progress_bar.progress(pct, label)

                # 实时展示工具调用
                tool_lines = []
                for line in log_snapshot.split("\n"):
                    line = line.strip()
                    if "🔧" in line or "📋" in line:
                        tool_lines.append(line)
                    elif "第" in line and "轮" in line:
                        tool_lines.append(line)
                if tool_lines:
                    html = '<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;color:#5c5240;max-height:360px;overflow-y:auto;padding:8px;background:rgba(250,248,245,0.7);border-left:3px solid #c9a96e;border-radius:0 4px 4px 0;">'
                    for tl in tool_lines[-12:]:  # 最近12行
                        css_class = "timeline-round"
                        if "轮" in tl:
                            html += f'<div style="border-left-color:#f59e0b;font-weight:600;padding:4px 0 4px 10px;margin:2px 0;">{tl}</div>'
                        else:
                            html += f'<div style="padding:2px 0 2px 10px;margin:1px 0;">{tl}</div>'
                    html += '</div>'
                    live_display.markdown(html, unsafe_allow_html=True)

                time.sleep(0.5)

            progress_bar.progress(1.0, "审查完成 ✅")
            time.sleep(0.3)
            progress_bar.empty()
            status_text.empty()
            live_display.empty()

            if result["error"]:
                err_str = str(result["error"])
                st.error(f"审查出错：{err_str}")
                st.stop()

            report = result["report"]
            st.session_state.report = report
            st.session_state.log = buf.getvalue()

            # 从报告中提取统计
            high_m = re.search(r'🔴\s*高风险条款[：:]\s*(\d+)', report)
            med_m  = re.search(r'🟡\s*中风险条款[：:]\s*(\d+)', report)
            high = int(high_m.group(1)) if high_m else 0
            med  = int(med_m.group(1)) if med_m else 0
            rounds = st.session_state.log.count("┌─ 第")
            st.session_state.summary = {"high": high, "medium": med, "rounds": rounds}

            st.rerun()

with col_right:
    st.markdown("#### 📊 审查结果")

    if st.session_state.report:

        # 统计卡片
        s = st.session_state.summary
        if s:
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown(f"""
                <div class="stat-box">
                    <div class="stat-num" style="color:#dc2626;">{s.get('high', '-')}</div>
                    <div class="stat-label">高风险条款</div>
                </div>""", unsafe_allow_html=True)
            with sc2:
                st.markdown(f"""
                <div class="stat-box">
                    <div class="stat-num" style="color:#d97706;">{s.get('medium', '-')}</div>
                    <div class="stat-label">中风险条款</div>
                </div>""", unsafe_allow_html=True)
            with sc3:
                st.markdown(f"""
                <div class="stat-box">
                    <div class="stat-num" style="color:#3b82f6;">{s.get('rounds', '-')}</div>
                    <div class="stat-label">审查轮次</div>
                </div>""", unsafe_allow_html=True)

        # 审查过程（时间线式折叠）
        with st.expander("🔎 审查过程（点击展开）", expanded=False):
            log = st.session_state.log
            # 把原始日志转成时间线
            for line in log.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "🔧" in line or "📋" in line:
                    st.markdown(f'<div class="timeline-round">{line}</div>', unsafe_allow_html=True)
                elif "第" in line and "轮" in line:
                    st.markdown(f'<div class="timeline-round" style="border-left-color:#f59e0b;font-weight:600;">{line}</div>', unsafe_allow_html=True)
                else:
                    st.text(line)

        st.divider()

        # 报告卡片
        st.markdown('<div class="report-card">', unsafe_allow_html=True)
        st.markdown(st.session_state.report)
        st.markdown('</div>', unsafe_allow_html=True)

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
            # 一键复制：用 text_area + JavaScript 实现
            copy_js = """
            <script>
            function copyReport() {
                const text = document.querySelector('.report-card').innerText;
                navigator.clipboard.writeText(text).then(() => {
                    const btn = document.getElementById('copy-btn');
                    btn.innerHTML = '✅ 已复制';
                    setTimeout(() => { btn.innerHTML = '📋 复制报告'; }, 2000);
                });
            }
            </script>
            <button id="copy-btn" onclick="copyReport()" style="
                width:100%; padding:11px 16px; border-radius:4px; border:1px solid rgba(201,169,110,0.3);
                background:#1a1f36; color:#e0cc9a; font-weight:500; font-size:0.9rem;
                cursor:pointer; letter-spacing:0.5px; transition:all 0.3s;
            " onmouseover="this.style.background='#2a3050';this.style.color='white';this.style.borderColor='#c9a96e'"
               onmouseout="this.style.background='#1a1f36';this.style.color='#e0cc9a';this.style.borderColor='rgba(201,169,110,0.3)'">
            📋 复制报告</button>
            """
            st.markdown(copy_js, unsafe_allow_html=True)
    else:
        st.info("👆 粘贴合同后点击「🔍 开始审查」，或上传 .txt / .jpg 合同文件")

    # ── 功能概览卡片（右下角，始终可见）──
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📌 法眼 · 能力概览", expanded=True):
        st.markdown("""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px;">
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">⚖ 10工具 ReAct Agent</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">自主决策审查步骤</div>
            </div>
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">📚 四重知识库</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">法规·判例·政策·税务</div>
            </div>
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">📋 六种合同类型</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">每种配备法定红线标准</div>
            </div>
            <div style="background:#faf8f5;border:1px solid #e0d8c8;border-radius:4px;padding:14px 16px;">
                <div style="font-weight:600;color:#1a1f36;font-size:0.85rem;">🚀 多种使用方式</div>
                <div style="font-size:0.75rem;color:#5c5240;margin-top:4px;">CLI·Web·API·MCP·Docker</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
