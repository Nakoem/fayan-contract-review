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
            _require("data/samples.js"),
            "const WB = globalThis.WB;",
            """
            // 确定性拆分：示例租赁合同应切出 ≥8 条
            const lease = WB.SAMPLES.find((s) => s.key === 'lease');
            const split = WB.splitClauses(lease.text);
            assert(split.length >= 8, 'splitClauses 只切出 ' + split.length + ' 条');
            assert(split[0].text.indexOf('第一条') === 0 || split[0].text.indexOf('房屋租赁合同') === 0);
            assert.deepStrictEqual(WB.splitClauses('没有条款编号的一段文字'), []);
            """,
            """
            // JSON 修复：多对象拼接 / 代码围栏 / 尾逗号
            assert.deepStrictEqual(WB.parseJSON('{"a":1}{"a":2}'), { a: 1 });
            assert.deepStrictEqual(WB.parseJSON('```json\\n{"a":1,}\\n```'), { a: 1 });
            assert.deepStrictEqual(WB.parseJSON('说明文字 {"a":[1,2]} 结束'), { a: [1, 2] });
            """,
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
            // 审查快照：显式传入 rules 时只读快照，不受全局 WB.RULES 影响
            const snapshot = [{
              id: 'snap_rule', contractType: '房屋租赁合同', keywords: ['押金'],
              enabled: true, name: '快照规则', condition: 'c', level: '高',
              basis: '民法典第1条', advice: 'a'
            }];
            const snapMatched = WB.matchRules('房屋租赁合同', [{ index: 1, text: '押金' }], snapshot);
            assert.strictEqual(snapMatched.length, 1);
            assert.strictEqual(snapMatched[0].id, 'snap_rule');
            assert.strictEqual(WB.matchRules('房屋租赁合同', [{ index: 1, text: '押金' }], []).length, 0);
            """,
            """
            // 低风险去重：已有 finding 的条款不再进 lowRisk；重复低风险只保留一条
            const check = WB.localChecks({
              clauses: [{ index: 1, text: 'a' }, { index: 2, text: 'b' }],
              findings: [{
                rule_id: 'x', clause_index: 1, clause_text: 'a',
                fairness: 4, clarity: 1, exposure: 1,
                risk_reason: 'r', basis: '民法典第1条', suggestion: 's'
              }],
              lowRiskClauses: [
                { clause_index: 1, clause_text: 'a', reason: 'dup' },
                { clause_index: 2, clause_text: 'b', reason: 'ok' },
                { clause_index: 2, clause_text: 'b2', reason: 'dup' }
              ],
              rules: []
            });
            assert.strictEqual(check.findings.length, 1);
            assert.strictEqual(check.lowRiskClauses.length, 1);
            assert.strictEqual(check.lowRiskClauses[0].clause_index, 2);
            assert.strictEqual(check.missing.length, 0);
            """,
            """
            // 索引纠正：模型写错一位时，按原文匹配回正确的条款
            const check2 = WB.localChecks({
              clauses: [
                { index: 1, text: '第一条 租金及支付方式 乙方应于每月五日前支付当月租金人民币一万五千元' },
                { index: 2, text: '第二条 押金 乙方应支付押金人民币四万五千元' }
              ],
              findings: [{
                rule_id: 'x', clause_index: 2,
                clause_text: '乙方应于每月五日前支付当月租金人民币一万五千元',
                fairness: 4, clarity: 1, exposure: 1,
                risk_reason: 'r', basis: '民法典第1条', suggestion: 's'
              }],
              lowRiskClauses: [{
                clause_index: 1,
                clause_text: '第二条 押金 乙方应支付押金人民币四万五千元',
                reason: 'ok'
              }],
              rules: []
            });
            assert.strictEqual(check2.findings[0].clause_index, 1);
            assert.strictEqual(check2.lowRiskClauses[0].clause_index, 2);
            assert.strictEqual(check2.missing.length, 0);
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
