"""规则库 schema 校验。

用 Node 执行 src/data/rules.js，拿到 JSON 后逐条校验。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES_JS = ROOT / "src" / "data" / "rules.js"

TYPES = {
    "房屋租赁合同",
    "劳动合同",
    "买卖合同",
    "服务合同",
    "合作协议",
    "借款合同",
}
LEVELS = {"高", "中", "低"}
BASIS_RE = re.compile(r"第[一二三四五六七八九十百千零〇\d]+条")


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("未安装 Node，跳过规则校验")
    return node


@pytest.fixture(scope="module")
def rules() -> list[dict]:
    script = (
        "require(" + json.dumps(str(RULES_JS).replace("\\", "/")) + ");"
        "process.stdout.write(JSON.stringify(globalThis.WB.RULES));"
    )
    out = subprocess.run(
        [_node(), "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(out.stdout)


def test_rule_count(rules):
    assert len(rules) >= 60, f"规则太少：{len(rules)}"


def test_ids_unique(rules):
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids)), "存在重复 id"


def test_required_fields(rules):
    for r in rules:
        for key in (
            "id",
            "contractType",
            "name",
            "keywords",
            "condition",
            "level",
            "basis",
            "advice",
        ):
            assert r.get(key) not in (None, "", []), f"{r.get('id')} 缺少 {key}"


def test_contract_types(rules):
    for r in rules:
        assert r["contractType"] in TYPES | {"通用"}, f"{r['id']} 类型非法：{r['contractType']}"


def test_levels(rules):
    for r in rules:
        assert r["level"] in LEVELS, f"{r['id']} 等级非法：{r['level']}"


def test_basis_has_article(rules):
    for r in rules:
        assert BASIS_RE.search(r["basis"]), f"{r['id']} 法条格式不对：{r['basis']}"


def test_keywords_nonempty(rules):
    for r in rules:
        assert isinstance(r["keywords"], list) and r["keywords"], f"{r['id']} keywords 为空"
        assert all(isinstance(k, str) and k.strip() for k in r["keywords"]), (
            f"{r['id']} keywords 非法"
        )


def test_builtin_and_stance(rules):
    for r in rules:
        assert r["enabled"] is True, f"{r['id']} 应默认启用"
        assert r["builtin"] is True, f"{r['id']} 应为内置规则"
        assert r["stance"] is None, f"{r['id']} MVP 阶段 stance 应为 null"


def test_type_coverage(rules):
    counts: dict[str, int] = {}
    for r in rules:
        counts[r["contractType"]] = counts.get(r["contractType"], 0) + 1
    for t in TYPES:
        assert counts.get(t, 0) >= 10, f"{t} 规则不足 10 条：{counts.get(t, 0)}"
    assert counts.get("通用", 0) >= 6, "通用规则不足 6 条"
