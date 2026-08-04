"""合同照片 OCR（默认智谱 GLM-4.6V-Flash 免费；备选阿里云 qwen3.6-flash）"""

import base64
import os
from pathlib import Path

from openai import OpenAI


def _image_to_base64(image_path: str) -> str:
    """读取图片并转为 base64 data URL。"""
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".bmp": "bmp", ".webp": "webp"}
    mime = mime_map.get(ext, "jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def ocr_image(image_path: str, api_key: str) -> str:
    """提取合同照片中的全部文字。

    默认调用智谱 GLM-4.6V-Flash（免费）；未配置 ZHIPU_API_KEY 时自动回退
    阿里云 qwen3.6-flash（保证线上没有智谱 key 也不会挂）。
    显式设 OCR_PROVIDER=dashscope 则固定走 Qwen。

    Args:
        image_path: 图片路径（支持 jpg/png/bmp/webp）
        api_key: 兜底 API Key（对应 provider 的环境变量缺失时使用）

    Returns:
        识别出的文字内容
    """
    provider = os.getenv("OCR_PROVIDER", "zhipu")

    # 智谱 key 存在才走智谱；没配（如线上）时自动回退 DashScope，避免 OCR 挂掉
    zhipu_key = os.getenv("ZHIPU_API_KEY")
    use_zhipu = provider != "dashscope" and bool(zhipu_key)

    if use_zhipu:
        client = OpenAI(
            api_key=zhipu_key,
            base_url="https://open.bigmodel.cn/api/paas/v4",
        )
        model = "glm-4.6v-flash"
    else:
        client = OpenAI(
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY", ""),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        model = "qwen3.6-flash"

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

    return resp.choices[0].message.content
