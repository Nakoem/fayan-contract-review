"""
法眼 · 业务逻辑层
从 app.py 抽离，纯函数，不依赖 Streamlit。

包含：合同类型配置、文件读取、Agent 执行、报告统计、历史管理、文件保存。
"""

import io
import os
import queue
import re
import tempfile
import threading
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from cache import contract_cache_key, get_cache

load_dotenv()

# ═══════════════════════════════════════════════════════════
# 合同类型配置
# ═══════════════════════════════════════════════════════════

CONTRACT_TYPES = [
    "房屋租赁合同",
    "劳动合同",
    "买卖合同",
    "服务合同",
    "合作协议",
    "借款合同",
    "自定义",
]


# ═══════════════════════════════════════════════════════════
# 文件读取
# ═══════════════════════════════════════════════════════════


def read_uploaded_contract(uploaded_file, api_key: str) -> tuple[str, str | None]:
    """读取上传的合同文件，返回 (文本, 错误消息)。
    支持 .txt / .pdf / .docx / .jpg/.png（OCR）。
    """
    ext = Path(uploaded_file.name).suffix.lower()

    # 图片 → OCR
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        if not api_key:
            return "", "OCR 需要 API Key，请在侧边栏填写或配置到 .env / Streamlit Secrets"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            from ocr_utils import ocr_image

            contract_text = ocr_image(tmp_path, api_key)
        except Exception as e:
            return "", f"OCR 失败：{e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return contract_text, None

    # PDF → pypdf 提取文本
    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            from pypdf import PdfReader

            reader = PdfReader(tmp_path)
            parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            contract_text = "\n\n".join(parts)
        except Exception as e:
            return "", f"PDF 解析失败：{e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return contract_text, None

    # DOCX → python-docx 提取文本
    if ext == ".docx":
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            from docx import Document

            doc = Document(tmp_path)
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            contract_text = "\n\n".join(parts)
        except Exception as e:
            return "", f"DOCX 解析失败：{e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return contract_text, None

    return uploaded_file.read().decode("utf-8"), None


# ═══════════════════════════════════════════════════════════
# Agent 执行器
# ═══════════════════════════════════════════════════════════


class ReviewRunner:
    """在后台线程中运行 Agent 审查，提供进度轮询接口。

    用法：
        runner = ReviewRunner(api_key)
        runner.start(contract_text, contract_type)
        while not runner.done:
            pct, label = runner.get_progress()
            tool_lines = runner.get_tool_log()
            time.sleep(0.5)
        report = runner.report
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._buf = io.StringIO()
        self._report = ""
        self._error: str | None = None
        self._done = False
        self._thread: threading.Thread | None = None

    @property
    def report(self) -> str:
        return self._report

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def done(self) -> bool:
        return self._done

    @property
    def log(self) -> str:
        return self._buf.getvalue()

    def start(self, contract_text: str, contract_type: str):
        """启动后台审查线程。"""
        self._done = False
        self._report = ""
        self._error = None
        self._buf = io.StringIO()

        def _run():
            _needs_detach = False
            try:
                from logger import attach_web_buffer, detach_web_buffer
                from main import ContractReviewAgent
                from utils import clean_report

                cache = get_cache()
                ck = contract_cache_key(contract_text, contract_type)
                cached = cache.get(ck)
                if cached:
                    self._buf.write("[缓存命中] 直接返回，跳过 LLM 审查\n")
                    self._report = clean_report(cached, contract_text, contract_type)
                else:
                    attach_web_buffer(self._buf)
                    _needs_detach = True
                    with redirect_stdout(self._buf):
                        agent = ContractReviewAgent(api_key=self.api_key, verbose=True)
                        self._report = agent.run(contract_text, contract_type)
                    if self._report:
                        self._report = clean_report(self._report, contract_text, contract_type)
                        cache.set(ck, self._report)
            except Exception as e:
                self._error = str(e)
            finally:
                if _needs_detach:
                    detach_web_buffer()
                self._done = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def get_progress(self) -> tuple[float, str]:
        """返回 (进度0-1, 标签文本)。"""
        log = self._buf.getvalue()
        rounds = log.count("┌─ 第")
        if "generate_final_report" in log:
            return 0.92, "生成报告中... 92%"
        elif rounds > 0:
            pct = min(0.88, rounds / 20)
            return pct, f"第 {rounds} 轮 · {int(pct * 100)}%"
        return 0.02, "启动 Agent... 2%"

    def get_tool_log(self) -> list[str]:
        """返回最近的工具调用日志行。"""
        lines = []
        for line in self._buf.getvalue().split("\n"):
            line = line.strip()
            if "🔧" in line or "📋" in line:
                lines.append(line)
            elif "第" in line and "轮" in line:
                lines.append(line)
        return lines[-12:]


class StreamingReviewRunner:
    """流式版审查执行器：后台线程 + Queue 传递事件。

    用法：
        runner = StreamingReviewRunner(api_key)
        runner.start(contract_text, contract_type)
        for event in runner.events():
            if event["type"] == "thinking_delta":
                ...  # 实时显示思考内容
            elif event["type"] == "done":
                report = event["report"]
    """

    def __init__(self, api_key: str, enable_reflection: bool = True):
        self.api_key = api_key
        self.enable_reflection = enable_reflection
        self._queue: queue.Queue = queue.Queue()
        self._report = ""
        self._log = ""
        self._error: str | None = None
        self._done = False
        self._thread: threading.Thread | None = None

    @property
    def report(self) -> str:
        return self._report

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def done(self) -> bool:
        return self._done

    @property
    def log(self) -> str:
        return self._log

    def start(self, contract_text: str, contract_type: str):
        """启动后台审查线程。"""
        self._done = False
        self._report = ""
        self._error = None
        self._log = ""

        def run():
            try:
                from main import ContractReviewAgent
                from utils import clean_report

                cache = get_cache()
                ck = contract_cache_key(contract_text, contract_type)
                cached = cache.get(ck)
                if cached:
                    self._log = "[缓存命中] 直接返回，跳过 LLM 审查\n"
                    self._report = clean_report(cached, contract_text, contract_type)
                    self._queue.put({"type": "thinking_delta", "content": "[缓存命中 ⚡]"})
                    self._queue.put({"type": "done", "report": self._report})
                    return

                agent = ContractReviewAgent(
                    api_key=self.api_key,
                    verbose=False,
                    enable_reflection=self.enable_reflection,
                )
                gen = agent.run_stream(contract_text, contract_type)
                for event in gen:
                    try:
                        if event.get("type") == "done":
                            report_raw = event.get("report", "")
                            self._report = clean_report(report_raw, contract_text, contract_type)
                            if self._report:
                                cache.set(ck, self._report)
                        elif event.get("type") == "thinking_delta":
                            self._log += event.get("content", "")
                        elif event.get("type") == "tool_start":
                            self._log += f"\n🔧 {event['name']}()"
                        elif event.get("type") == "tool_result":
                            self._log += f"\n📋 {event['name']} → {event['result_len']} 字符"
                        elif event.get("type") == "round_start":
                            self._log += f"\n\n第 {event['round']} 轮"
                        self._queue.put(event)
                    except Exception:
                        # 单个事件处理失败不影响整体
                        pass
            except Exception as e:
                import traceback

                self._error = traceback.format_exc()
                self._queue.put({"type": "error", "message": str(e)})
            finally:
                self._done = True

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def events(self):
        """Generator: non-blocking drain queue。审查完成后自动停止。"""
        while not self._done or not self._queue.empty():
            try:
                yield self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._done:
                    break


# ═══════════════════════════════════════════════════════════
# 报告统计
# ═══════════════════════════════════════════════════════════


def extract_summary(report: str, log: str) -> dict[str, int]:
    """从审查报告和日志中提取摘要统计。"""
    high_m = re.search(r"🔴\s*高风险条款[：:]\s*(\d+)", report)
    med_m = re.search(r"🟡\s*中风险条款[：:]\s*(\d+)", report)
    rounds = log.count("┌─ 第") or log.count("第 ") if "第 " in log else 0
    if not rounds:
        # 流式模式：匹配 "第 N 轮"
        m = re.findall(r"第\s*(\d+)\s*轮", log)
        rounds = int(m[-1]) if m else 0
    return {
        "high": int(high_m.group(1)) if high_m else 0,
        "medium": int(med_m.group(1)) if med_m else 0,
        "rounds": rounds,
    }


# ═══════════════════════════════════════════════════════════
# 历史报告管理
# ═══════════════════════════════════════════════════════════


def save_to_history(
    report_history: list[dict],
    report: str,
    log: str,
    contract_type: str,
    summary: dict,
    max_items: int = 20,
) -> list[dict]:
    """将报告插入历史列表头部，返回更新后的列表。最多保留 max_items 条。"""
    if not report:
        return report_history
    entry = {
        "time": datetime.now().strftime("%m-%d %H:%M"),
        "type": contract_type,
        "report": report,
        "log": log,
        "summary": summary,
    }
    return [entry] + report_history[: max_items - 1]


def save_report_file(report: str, contract_type: str, base_dir: str | Path = "审查报告"):
    """将报告保存到审查报告文件夹。"""
    if not report:
        return
    report_dir = Path(base_dir)
    report_dir.mkdir(exist_ok=True)
    safe_type = contract_type.replace("/", "_")
    filename = f"审查报告_{safe_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    (report_dir / filename).write_text(report, encoding="utf-8")
