"""合同照片 OCR（默认智谱 GLM-4.6V-Flash 免费；失败自动重试并回退阿里云 qwen3.6-flash）"""

import base64
import logging
import os
import random
import time
from pathlib import Path

from openai import OpenAI

_ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_TIMEOUT = 60  # 秒，避免"已连接但不响应"时同步 UI 卡死

logger = logging.getLogger(__name__)


def _image_to_base64(image_path: str) -> str:
    """读取图片并转为 base64 data URL。"""
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".bmp": "bmp", ".webp": "webp"}
    mime = mime_map.get(ext, "jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _vision_request(client: OpenAI, model: str, data_url: str) -> str:
    """单次视觉请求；失败或空结果时抛异常，由上层重试/回退处理。"""
    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {
                        "type": "text",
                        "text": "请完整提取这张合同照片中的所有文字，不要遗漏任何条款。保持原文格式和段落结构。",
                    },
                ],
            }
        ],
    )
    content = resp.choices[0].message.content
    if not content:
        # 免费额度/并发受限时部分服务返回 200 + 空内容，视为失败以触发重试/回退
        raise ValueError(f"{model} 返回空内容")
    return content


def _call_vision_retry(
    api_key: str, base_url: str, model: str, image_path: str, retries: int = 3, delay: float = 2.0
) -> str:
    """带重试的视觉调用。

    免费模型限 1 并发，多人同时失败时用「指数退避 + 随机抖动」错开重试时间，
    避免同步风暴（thundering herd）。client 与图片 base64 只构建一次，复用。
    """
    retries = max(1, retries)
    # 关闭 SDK 内置重试（max_retries=0），统一由本层控制，避免双重重试放大请求数
    client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=_TIMEOUT)
    data_url = _image_to_base64(image_path)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return _vision_request(client, model, data_url)
        except Exception as e:
            last_err = e
            logger.warning("OCR %s 第 %d/%d 次失败: %s", model, attempt, retries, e, exc_info=True)
            if attempt < retries:
                time.sleep(delay * (2 ** (attempt - 1)) + random.random())
    raise last_err


def ocr_image(image_path: str, api_key: str) -> str:
    """提取合同照片中的全部文字。

    尝试顺序（失败自动重试 + 回退，保证任一路径可用时 OCR 不挂）：
      1. 智谱 GLM-4.6V-Flash（免费）—— 默认，需配置 ZHIPU_API_KEY；限 1 并发，失败重试 3 次
      2. 阿里云 qwen3.6-flash —— 备选，需配置 DASHSCOPE_API_KEY 或传 api_key；重试 2 次
    显式设 OCR_PROVIDER=dashscope 则跳过智谱、只走 Qwen。

    Args:
        image_path: 图片路径（支持 jpg/png/bmp/webp）
        api_key: 兜底 API Key（DashScope 路径的环境变量缺失时使用）

    Returns:
        识别出的文字内容
    """
    provider = os.getenv("OCR_PROVIDER", "zhipu")
    zhipu_key = os.getenv("ZHIPU_API_KEY")
    dashscope_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")

    errors = []

    # 第一优先：智谱（免费额度/并发偶发失败，重试后仍失败则回退下一层）
    if provider != "dashscope" and zhipu_key:
        try:
            text = _call_vision_retry(zhipu_key, _ZHIPU_BASE, "glm-4.6v-flash", image_path)
            logger.info("OCR via zhipu glm-4.6v-flash")
            return text
        except Exception as e:
            errors.append(f"智谱 GLM-4.6V-Flash: {e}")

    # 第二优先：阿里云 Qwen（智谱失败或未配置时兜底）
    if dashscope_key:
        try:
            text = _call_vision_retry(
                dashscope_key, _DASHSCOPE_BASE, "qwen3.6-flash", image_path, retries=2
            )
            logger.info("OCR via dashscope qwen3.6-flash")
            return text
        except Exception as e:
            errors.append(f"阿里云 qwen3.6-flash: {e}")

    if errors:
        raise RuntimeError("OCR 全部路径失败：" + " | ".join(errors))
    raise RuntimeError("OCR 未配置任何 API Key")
