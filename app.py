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

load_dotenv()

st.set_page_config(page_title="法眼 · 合同审查", page_icon="⚖️", layout="wide")

# ═══════════════════════════════════════════════════════
# 自定义 CSS
# ═══════════════════════════════════════════════════════
st.markdown("""
<style>
/* ═══════════════════════════════════════════════
   Legal Editorial — 法务精致风
   深蓝 + 香槟金 + 纸纹质感
   ═══════════════════════════════════════════════ */

/* ── 导入字体 ── */
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --navy: #1a1f36;
    --navy-light: #2a3050;
    --gold: #c9a96e;
    --gold-light: #e0cc9a;
    --cream: #faf8f5;
    --paper: #f5f0e8;
    --ink: #2c2416;
    --ink-light: #5c5240;
    --border: #e0d8c8;
    --red: #b91c1c;
    --red-bg: #fef5f5;
    --amber: #b45309;
    --amber-bg: #fffbeb;
    --green: #15803d;
    --green-bg: #f0fdf4;
}

html, body, [class*="css"] { font-family: 'DM Sans', 'Noto Sans SC', sans-serif; }
h1, h2, h3, h4, h5, h6 { font-family: 'Cormorant Garamond', 'Noto Serif SC', serif; }

/* ── 背景：仿法律文书纸纹 ── */
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

/* ── 顶部栏 ── */
[data-testid="stHeader"] {
    background: rgba(250,248,245,0.85);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
}

/* ── 标题 ── */
.main-title {
    font-family: 'Cormorant Garamond', 'Noto Serif SC', serif !important;
    font-size: 2.4rem !important; font-weight: 700 !important;
    color: var(--navy) !important; letter-spacing: -0.3px;
}
.main-subtitle { color: var(--ink-light); font-size: 0.9rem; letter-spacing: 0.3px; }

/* ── 侧边栏：深蓝底 + 金色点缀 ── */
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

/* ── 合同输入区 ── */
.contract-wrapper {
    background: white;
    border: 1px solid var(--border);
    border-radius: 4px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03), 0 0 0 1px rgba(180,160,120,0.08);
    transition: box-shadow 0.3s;
}
.contract-wrapper:focus-within { box-shadow: 0 2px 12px rgba(201,169,110,0.12), 0 0 0 1px rgba(201,169,110,0.25); }
.contract-wrapper textarea {
    background: transparent !important;
    font-family: 'JetBrains Mono', 'SF Mono', monospace !important;
    font-size: 0.85rem !important; line-height: 1.75 !important;
    color: var(--ink) !important; border: none !important; box-shadow: none !important;
}
.contract-wrapper textarea::placeholder { color: #b8a890 !important; }

/* ── 按钮 ── */
div[data-testid="stButton"] > button {
    background: var(--navy) !important; color: var(--gold-light) !important;
    border: 1px solid rgba(201,169,110,0.3) !important;
    border-radius: 4px !important; font-weight: 500 !important;
    font-size: 0.95rem !important; padding: 11px 28px !important;
    letter-spacing: 0.8px !important; text-transform: uppercase !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1.2) !important;
    box-shadow: 0 2px 8px rgba(26,31,54,0.15) !important;
}
div[data-testid="stButton"] > button:hover {
    background: var(--navy-light) !important; color: white !important;
    border-color: var(--gold) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(26,31,54,0.25), 0 0 0 1px rgba(201,169,110,0.2) !important;
}

/* ── 时间线 ── */
.timeline-round {
    background: rgba(250,248,245,0.7);
    border-left: 3px solid var(--gold);
    border-radius: 0 4px 4px 0; padding: 8px 14px; margin: 4px 0;
    font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
    color: var(--ink-light); white-space: pre-wrap;
}

/* ── 报告卡片 ── */
.report-card {
    background: white; border-radius: 4px; padding: 32px 36px; margin: 20px 0;
    border: 1px solid var(--border);
    box-shadow: 0 2px 16px rgba(0,0,0,0.04), 0 0 0 1px rgba(180,160,120,0.06);
}

/* ── 风险标签 ── */
.risk-high   { display:inline-block; background:var(--red-bg); color:var(--red); padding:3px 14px; border-radius:3px; font-weight:600; font-size:0.8rem; border:1px solid rgba(185,28,28,0.15); letter-spacing:0.5px; }
.risk-medium { display:inline-block; background:var(--amber-bg); color:var(--amber); padding:3px 14px; border-radius:3px; font-weight:600; font-size:0.8rem; border:1px solid rgba(180,83,9,0.15); letter-spacing:0.5px; }
.risk-low    { display:inline-block; background:var(--green-bg); color:var(--green); padding:3px 14px; border-radius:3px; font-weight:600; font-size:0.8rem; border:1px solid rgba(21,128,61,0.15); letter-spacing:0.5px; }

/* ── 统计卡片 ── */
.stat-box {
    background: white; border-radius: 4px; padding: 18px 20px; text-align: center;
    border: 1px solid var(--border); transition: box-shadow 0.3s;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}
.stat-box:hover { box-shadow: 0 4px 16px rgba(26,31,54,0.08); }
.stat-num { font-family: 'Cormorant Garamond', serif; font-size: 2.2rem; font-weight: 700; }
.stat-label { font-size: 0.75rem; color: var(--ink-light); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* ── 展开器 ── */
[data-testid="stExpander"] details {
    border-radius: 4px !important; border: 1px solid var(--border) !important;
    background: white !important; transition: box-shadow 0.3s;
}
[data-testid="stExpander"] details[open] { box-shadow: 0 2px 12px rgba(0,0,0,0.04); }
[data-testid="stExpander"] summary {
    font-weight: 500 !important; color: var(--navy) !important;
    padding: 10px 14px !important; letter-spacing: 0.3px;
}

/* ── 信息提示 ── */
[data-testid="stInfo"] {
    background: rgba(201,169,110,0.06) !important;
    border: 1px solid rgba(201,169,110,0.2) !important; border-radius: 4px !important;
}

/* ── 进度条 ── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, var(--gold-light), var(--gold)) !important;
}

/* ── 滚动条 ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--cream); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--gold-light); }

/* ── 移动端 ── */
@media (max-width: 768px) {
    .main-title { font-size: 1.6rem !important; }
    div[data-testid="column"] { min-width: 100% !important; }
    .report-card { padding: 20px; }
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
    contract_type = st.selectbox(
        "合同类型", [
            "房屋租赁合同", "劳动合同", "买卖合同", "服务合同", "合作协议",
            "技术开发合同", "股权转让合同", "借款合同", "建设工程合同",
            "委托合同", "居间中介合同", "特许经营合同", "广告合同",
            "自定义",
        ],
        label_visibility="collapsed",
    )
    if contract_type == "自定义":
        contract_type = st.text_input("输入合同类型", placeholder="如：技术开发合同", label_visibility="collapsed")

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
        for i, h in enumerate(st.session_state.report_history):
            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                safe_type = h["type"].replace("/", "_")
                st.download_button(
                    f"⬇ {h['time']}",
                    h["report"],
                    file_name=f"审查报告_{safe_type}_{h['time'].replace(':', '').replace(' ', '_')}.txt",
                    mime="text/plain",
                    key=f"hist_dl_{i}",
                    help=f"{h['type']} · {h['summary'].get('high', '-')}高/{h['summary'].get('medium', '-')}中",
                )
            with col_info:
                st.markdown(
                    f"<small>{h['type']} · 🔴{h['summary'].get('high', '-')} 🟡{h['summary'].get('medium', '-')}</small>",
                    unsafe_allow_html=True,
                )

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
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("#### 📄 合同原文")

    # 纸张质感容器
    st.markdown('<div class="contract-wrapper">', unsafe_allow_html=True)
    contract_text = st.text_area(
        "合同原文",
        value=contract_text,
        placeholder="在此粘贴合同全文，或从左侧上传 .txt 文件...",
        height=520,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

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

            buf = io.StringIO()
            progress_bar = st.progress(0, "准备审查...")
            status_text = st.empty()

            result = {"report": "", "done": False, "error": None}

            def _run():
                try:
                    with redirect_stdout(buf):
                        agent = ContractReviewAgent(api_key=api_key, verbose=True)
                        result["report"] = agent.run(contract_text, contract_type)
                except Exception as e:
                    result["error"] = e
                finally:
                    result["done"] = True

            t = threading.Thread(target=_run, daemon=True)
            t.start()

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
                time.sleep(0.3)

            progress_bar.progress(1.0, "审查完成 ✅")
            time.sleep(0.3)
            progress_bar.empty()
            status_text.empty()

            if result["error"]:
                err_str = str(result["error"])
                if "JSON" in err_str or "arguments" in err_str:
                    st.warning(
                        "模型返回了格式异常的输出（qwen-plus 偶发），已自动重试5次仍失败。"
                        "请点击下方按钮重新审查，通常再次运行即可正常。"
                    )
                else:
                    st.error(f"审查出错: {err_str}")
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

        st.download_button(
            "📥 下载报告 (.txt)",
            st.session_state.report,
            file_name=f"审查报告_{contract_type}_{date.today().isoformat()}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        st.info("点击左侧「🔍 开始审查」按钮启动 Agent")
