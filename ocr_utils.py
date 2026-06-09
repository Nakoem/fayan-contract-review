"""合同照片 OCR（调用阿里云多模态模型 qwen3.6-flash）"""

import base64
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
    """用 qwen3.6-flash 提取合同照片中的全部文字。

    Args:
        image_path: 图片路径（支持 jpg/png/bmp/webp）
        api_key: DashScope API Key

    Returns:
        识别出的文字内容
    """
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    data_url = _image_to_base64(image_path)

    resp = client.chat.completions.create(
        model="qwen3.6-flash",
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
