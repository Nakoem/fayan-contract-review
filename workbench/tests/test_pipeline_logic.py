"""核心纯逻辑测试（通过 Node 执行浏览器同名代码）。

覆盖：脱敏往返、等级映射、综合评分、规则匹配、报告 HTML 转义。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("未安装 Node，跳过逻辑测试")
    return node


def _require(rel: str) -> str:
    p = (SRC / rel).as_posix()
    return f"require({json.dumps(p)});"


def test_core_logic():
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("data/rules.js"),
            _require("data/knowledge.js"),
            _require("prompts.js"),
            _require("llm.js"),
            _require("pipeline.js"),
            "const WB = globalThis.WB;",
            """
            // 脱敏往返
            const original = '甲方：张三，身份证320102199001011234，电话13800001111，邮箱a@b.com，账号6222020202020202020';
            const m = WB.maskText(original, ['张三']);
            assert(!m.text.includes('张三'));
            assert(!m.text.includes('320102199001011234'));
            assert(!m.text.includes('13800001111'));
            assert(!m.text.includes('a@b.com'));
            assert(/【主体1_[a-z0-9]+】/.test(m.text));
            assert.strictEqual(WB.unmaskText(m.text, m.map), original);
            """,
            """
            // 等级映射与评分
            assert.strictEqual(WB.deriveLevel({ fairness: 4, clarity: 1, exposure: 1 }), '高');
            assert.strictEqual(WB.deriveLevel({ fairness: 3, clarity: 1, exposure: 1 }), '中');
            assert.strictEqual(WB.deriveLevel({ fairness: 2, clarity: 2, exposure: 2 }), '低');
            assert.strictEqual(WB.computeScore({ high: 3, mid: 5, low: 2 }), 77);
            assert.strictEqual(WB.computeScore({ high: 20, mid: 0, low: 0 }), 100);
            """,
            """
            // 规则匹配：类型规则 + 通用规则
            const rules = WB.matchRules('房屋租赁合同', [{ index: 1, title: 'x', text: '押金 违约金 管辖 维修 费用承担' }]);
            assert(rules.some((r) => r.id === 'r_lease_penalty'));
            assert(rules.some((r) => r.id === 'r_common_jurisdiction'));
            assert(!rules.some((r) => r.id === 'r_loan_rate'));
            """,
            """
            // 报告转义：合同文本里的 HTML 不得生效
            const html = WB.renderReport({
              contractType: '房屋租赁合同',
              findings: [{
                rule_id: 'x', rule_name: '<img>', clause_index: 1,
                clause_text: '<script>alert(1)</script>',
                fairness: 5, clarity: 5, exposure: 5,
                risk_reason: '<b>x</b>', basis: '民法典第585条',
                suggestion: '<i>y</i>', level: '高'
              }],
              lowRiskClauses: [],
              summary: '<script>alert(2)</script>',
              dateText: '2026-11-19'
            });
            assert(!html.includes('<script>'));
            assert(html.includes('&lt;script&gt;'));
            """,
            "console.log('OK');",
        ]
    )
    out = subprocess.run(
        [_node(), "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout
