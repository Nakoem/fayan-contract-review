"""合同照片 OCR（默认智谱 GLM-4.6V-Flash 免费；失败自动回退阿里云 qwen3.6-flash）"""

import base64
import logging
import os
from pathlib import Path

from openai import OpenAI

_ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

logger = logging.getLogger(__name__)


def _image_to_base64(image_path: str) -> str:
    """读取图片并转为 base64 data URL。"""
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".bmp": "bmp", ".webp": "webp"}
    mime = mime_map.get(ext, "jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _call_vision(api_key: str, base_url: str, model: str, image_path: str) -> str:
    """调用单个视觉模型提取图片文字，失败或空结果时抛出异常由上层回退。"""
    client = OpenAI(api_key=api_key, base_url=base_url)
    data_url = _image_to_base64(image_path)
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
        # 免费额度耗尽时部分服务返回 200 + 空内容，视为失败以触发上层回退
        raise ValueError(f"{model} 返回空内容")
    return content


def ocr_image(image_path: str, api_key: str) -> str:
    """提取合同照片中的全部文字。

    尝试顺序（自动回退，保证任一路径可用时 OCR 不挂）：
      1. 智谱 GLM-4.6V-Flash（免费）—— 默认，需配置 ZHIPU_API_KEY
      2. 阿里云 qwen3.6-flash —— 备选，需配置 DASHSCOPE_API_KEY 或传 api_key
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

    # 第一优先：智谱（免费额度偶发耗尽，失败后回退下一层）
    if provider != "dashscope" and zhipu_key:
        try:
            text = _call_vision(zhipu_key, _ZHIPU_BASE, "glm-4.6v-flash", image_path)
            logger.info("OCR via zhipu glm-4.6v-flash")
            return text
        except Exception as e:
            logger.warning("OCR 智谱失败，尝试回退阿里云: %s", e)
            errors.append(f"智谱 GLM-4.6V-Flash: {e}")

    # 第二优先：阿里云 Qwen（智谱失败或未配置时兜底）
    if dashscope_key:
        try:
            text = _call_vision(dashscope_key, _DASHSCOPE_BASE, "qwen3.6-flash", image_path)
            logger.info("OCR via dashscope qwen3.6-flash")
            return text
        except Exception as e:
            logger.warning("OCR 阿里云失败: %s", e)
            errors.append(f"阿里云 qwen3.6-flash: {e}")

    if errors:
        raise RuntimeError("OCR 全部路径失败：" + " | ".join(errors))
    raise RuntimeError("OCR 未配置任何 API Key")
