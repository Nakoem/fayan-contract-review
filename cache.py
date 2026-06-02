"""
Redis 缓存层 + 历史报告预热
用法：
    from cache import get_cache
    cache = get_cache()
    cached = cache.get("review:abc123")
"""

import hashlib
import os
import random
import re
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class RedisCache:
    """Redis 缓存，连接失败时自动降级为无缓存模式。"""

    def __init__(self):
        self._redis = None
        self._available = None
        self._last_attempt = 0.0
        self._retry_interval = 30

    @property
    def available(self) -> bool:
        now = time.time()
        if self._available is False and (now - self._last_attempt) < self._retry_interval:
            return False
        if self._available is None or (
            self._available is False and (now - self._last_attempt) >= self._retry_interval
        ):
            self._last_attempt = now
            try:
                import redis

                self._redis = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    db=int(os.getenv("REDIS_DB", "0")),
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                self._redis.ping()
                self._available = True
            except Exception:
                self._available = False
        return self._available

    def get(self, key: str) -> str | None:
        if not self.available:
            return None
        try:
            return self._redis.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, expire: int = 86400):
        if not self.available:
            return
        try:
            self._redis.setex(key, expire, value)
        except Exception:
            pass

    def delete(self, key: str):
        if not self.available:
            return
        try:
            self._redis.delete(key)
        except Exception:
            pass

    def warmup(self, entries: dict[str, str]):
        """批量预热。"""
        for key, value in entries.items():
            self.set(key, value)

    @property
    def info(self) -> str:
        if self.available:
            try:
                keys = self._redis.dbsize()
                return f"Redis ✅ {keys} keys"
            except Exception:
                return "Redis ⚠️"
        return "Redis ❌ (不可用，降级为无缓存)"


# ──────────────────────────────────────────────
# 缓存 key 策略
# ──────────────────────────────────────────────


def contract_cache_key(contract_text: str, contract_type: str) -> str:
    """同一合同内容 + 类型 → 相同 key，避免重复审查。"""
    h = hashlib.sha256(f"{contract_type}:{contract_text}".encode()).hexdigest()[:16]
    return f"review:{h}"


def rule_cache_key(rule_name: str) -> str:
    """法规/风险条款名 → key。"""
    return f"law:{rule_name.strip()}"


# ──────────────────────────────────────────────
# 历史报告预热
# ──────────────────────────────────────────────


def _extract_rule_names(report_text: str) -> list[str]:
    """从审查报告中提取风险条款名称。兼容新旧两种格式。"""
    rules: list[str] = []
    # 旧格式：✅ 高风险条款 1（金额条款）：
    for m in re.finditer(r"✅\s*(?:高|中|低)风险条款\s*\d+\s*[（(]([^）)]+)[）)]", report_text):
        name = m.group(1).strip()
        if name and len(name) <= 30:
            rules.append(name)
    # 新格式：从风险条款段落提取核心概念
    risk_concepts = [
        "定金",
        "违约金",
        "押金",
        "解除权",
        "验收期",
        "交付",
        "保密",
        "竞业",
        "试用期",
        "加班费",
        "社保",
        "转租",
        "质保",
        "免责",
        "不可抗力",
        "管辖",
        "送达",
        "验收",
    ]
    for concept in risk_concepts:
        if concept in report_text and concept not in rules:
            rules.append(concept + "条款")
    return rules


def _extract_legal_refs(report_text: str) -> list[str]:
    """从报告中提取引用的法规名。"""
    refs: list[str] = []
    for m in re.finditer(r"《([^》]+)》", report_text):
        ref = m.group(1).strip()
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _extract_hot_keys(report_text: str) -> list[str]:
    """从报告里提取高频关键词作为缓存热点。"""
    hot_patterns: list[str] = []
    patterns = {
        "违约金": ["违约金上限", "违约金计算标准", "违约金过高认定"],
        "押金": ["押金退还条件", "押金监管规定", "押金扣除规则"],
        "解除": ["合同解除条件", "单方解除权", "解除通知期限"],
        "逾期": ["逾期违约责任", "逾期利息计算"],
        "转租": ["转租限制条件", "转租同意要求"],
        "保密": ["保密义务期限", "保密违约责任"],
        "竞业": ["竞业限制范围", "竞业限制补偿"],
        "试用期": ["试用期最长时限", "试用期解除条件"],
        "工资": ["工资支付周期", "加班费计算"],
        "社保": ["社保缴纳义务", "社保基数计算"],
    }
    for keyword, hot_keys in patterns.items():
        if keyword in report_text:
            for hk in hot_keys:
                if hk not in hot_patterns:
                    hot_patterns.append(hk)
    return hot_patterns


def warmup_from_reports(reports_dir: str = "审查报告") -> dict[str, int]:
    """扫描历史审查报告，提取热点规则并预热缓存。

    返回: {"预热条数": N, "来源报告数": M}
    """
    cache = get_cache()
    if not cache.available:
        return {"预热条数": 0, "来源报告数": 0, "状态": "Redis 不可用，跳过预热"}

    report_files = list(Path(reports_dir).glob("审查报告_*.txt"))
    if not report_files:
        return {"预热条数": 0, "来源报告数": 0, "状态": "无历史报告"}

    all_rule_names: list[str] = []
    all_legal_refs: list[str] = []
    all_hot_keys: list[str] = []

    for fpath in report_files:
        try:
            text = fpath.read_text(encoding="utf-8")
            all_rule_names.extend(_extract_rule_names(text))
            all_legal_refs.extend(_extract_legal_refs(text))
            all_hot_keys.extend(_extract_hot_keys(text))
        except Exception:
            pass

    # 去重
    unique_rules = list(set(all_rule_names))
    unique_refs = list(set(all_legal_refs))
    unique_hot = list(set(all_hot_keys))

    count = 0
    for name in unique_rules:
        cache.set(rule_cache_key(name), "1", expire=86400 * 7 + random.randint(-3600, 3600))
        count += 1
    for ref in unique_refs:
        cache.set(rule_cache_key(ref), "1", expire=86400 * 7 + random.randint(-3600, 3600))
        count += 1
    for hk in unique_hot:
        cache.set(rule_cache_key(hk), "1", expire=86400 * 7 + random.randint(-3600, 3600))
        count += 1

    return {
        "预热条数": count,
        "来源报告数": len(report_files),
        "条款名": len(unique_rules),
        "法规引用": len(unique_refs),
        "热点词": len(unique_hot),
        "状态": "✅ 预热完成",
    }


# ──────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────

_lock = threading.Lock()
_cache: RedisCache | None = None


def get_cache() -> RedisCache:
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = RedisCache()
    return _cache
