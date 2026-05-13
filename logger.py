"""
法眼项目统一日志模块。
用法：
    from logger import logger, init_logger

    init_logger(mode="cli")  # 程序入口调用一次
    logger.info("审查开始，合同类型：{}", contract_type)
    logger.debug("工具参数: {}", args)
    logger.warning("API 重试 ({}/{}): {}", retry, max_retries, err)
    logger.error("审查失败: {}", e)
"""

import io
import sys
from pathlib import Path

from loguru import logger

_web_handler_id: int | None = None
_initialized = False


def init_logger(
    mode: str = "cli",
    log_dir: str = "logs",
    level: str = "DEBUG",
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """初始化日志系统。应在程序入口调用一次。

    Args:
        mode: "cli" (终端模式) 或 "web" (Streamlit 模式)
        log_dir: 日志文件目录
        level: 文件日志最低级别
        rotation: 文件轮转策略
        retention: 日志保留时间
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    logger.remove()  # 清除默认 handler

    # ── 控制台输出（CLI模式：纯净 message，保持原TUI风格）──
    if mode == "cli":
        logger.add(
            sys.stderr,
            format="{message}",
            level="INFO",
            colorize=True,
        )

    # ── 文件输出（带时间戳和位置信息）──
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path / "contract_review_{time:YYYY-MM-DD}.log",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level=level,
    )


def attach_web_buffer(buffer: io.StringIO) -> None:
    """Web 模式下，将日志输出附加到 StringIO 缓冲区，供 app.py 读取。"""
    global _web_handler_id
    if _web_handler_id is not None:
        return
    _web_handler_id = logger.add(
        buffer,
        format="{message}",
        level="INFO",
        colorize=False,
    )


def detach_web_buffer() -> None:
    """移除 Web 缓冲区的日志 sink。"""
    global _web_handler_id
    if _web_handler_id is not None:
        logger.remove(_web_handler_id)
        _web_handler_id = None
