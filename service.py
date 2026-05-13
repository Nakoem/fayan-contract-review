"""
法眼 · 业务逻辑层
从 app.py 抽离，纯函数，不依赖 Streamlit。

包含：合同类型配置、文件读取、Agent 执行、报告统计、历史管理、文件保存。
"""

import io
import os
import re
import tempfile
import threading
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

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
    支持 .txt 纯文本和 .jpg/.png 图片（OCR）。
    """
    ext = Path(uploaded_file.name).suffix.lower()
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
    else:
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
            try:
                from logger import attach_web_buffer, detach_web_buffer
                from main import ContractReviewAgent

                attach_web_buffer(self._buf)
                with redirect_stdout(self._buf):
                    agent = ContractReviewAgent(api_key=self.api_key, verbose=True)
                    self._report = agent.run(contract_text, contract_type)
            except Exception as e:
                self._error = str(e)
            finally:
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


# ═══════════════════════════════════════════════════════════
# 报告统计
# ═══════════════════════════════════════════════════════════


def extract_summary(report: str, log: str) -> dict[str, int]:
    """从审查报告和日志中提取摘要统计。"""
    high_m = re.search(r"🔴\s*高风险条款[：:]\s*(\d+)", report)
    med_m = re.search(r"🟡\s*中风险条款[：:]\s*(\d+)", report)
    return {
        "high": int(high_m.group(1)) if high_m else 0,
        "medium": int(med_m.group(1)) if med_m else 0,
        "rounds": log.count("┌─ 第"),
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
