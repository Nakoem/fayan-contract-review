"""
提示词版本管理器。
用法：
    from prompt_manager import prompt_manager

    text = prompt_manager.get("EXTRACT_CLAUSES_SYSTEM")
    prompt_manager.use_version("v2.0.0")
    for v in prompt_manager.list_versions():
        print(v)
"""

import yaml
from pathlib import Path
from typing import Optional


class PromptManager:
    """提示词管理器：加载YAML、版本切换、回退。"""

    def __init__(self, prompts_dir: str = "prompts"):
        self._prompts_dir = Path(prompts_dir)
        self._cache: dict = {}
        self._current_version: str = ""
        self._versions: dict = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        versions_path = self._prompts_dir / "versions.yaml"
        if not versions_path.exists():
            self._loaded = True
            return
        with open(versions_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        self._current_version = meta.get("current", "")
        self._versions = {v["id"]: v for v in meta.get("versions", [])}
        if self._current_version:
            self._load_prompts(self._current_version)
        self._loaded = True

    def _load_prompts(self, version_id: str) -> None:
        vinfo = self._versions.get(version_id, {})
        file_rel = vinfo.get("file", f"{version_id}/prompts.yaml")
        yaml_path = self._prompts_dir / file_rel
        if not yaml_path.exists():
            return
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._cache.clear()
        for key, val in data.items():
            if isinstance(val, dict) and "text" in val:
                self._cache[key] = val["text"]
            elif isinstance(val, str):
                self._cache[key] = val

    def get(self, name: str) -> str:
        self._ensure_loaded()
        if name in self._cache:
            return self._cache[name]
        raise KeyError(
            f"提示词 '{name}' 不存在。可用：{list(self._cache.keys())}"
        )

    def use_version(self, version_id: str) -> None:
        if version_id not in self._versions:
            raise KeyError(f"版本 '{version_id}' 不存在。可用：{list(self._versions.keys())}")
        self._current_version = version_id
        self._load_prompts(version_id)

    def list_versions(self) -> list[dict]:
        self._ensure_loaded()
        return list(self._versions.values())

    @property
    def current_version(self) -> str:
        self._ensure_loaded()
        return self._current_version

    def reload(self) -> None:
        self._loaded = False
        self._cache.clear()
        self._versions.clear()
        self._ensure_loaded()


prompt_manager = PromptManager()
