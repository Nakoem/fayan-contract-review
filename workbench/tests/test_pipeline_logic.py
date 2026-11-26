"""核心纯逻辑测试（通过 Node 执行浏览器同名代码）。

覆盖：脱敏往返、等级映射、综合评分、规则匹配、报告 HTML 转义。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
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
            // 审查视角：按合同角色映射；非法/缺失回落中立
            assert.strictEqual(WB.stanceLabel('房屋租赁合同', 'tenant'), '承租人');
            assert.strictEqual(WB.stanceLabel('房屋租赁合同', 'landlord'), '出租人');
            assert.strictEqual(WB.stanceLabel('劳动合同', 'employee'), '劳动者');
            assert.strictEqual(WB.stanceLabel('房屋租赁合同', 'neutral'), '中立（双方）');
            assert.strictEqual(WB.stanceLabel('房屋租赁合同', 'lender'), '中立（双方）');
            assert.strictEqual(WB.stanceLabel('房屋租赁合同', null), '中立（双方）');
            assert.strictEqual(WB.stanceLabel('__proto__', 'tenant'), '中立（双方）');
            """,
            """
            // 审查视角进入评估 / 复核提示词
            const evalMsgs = WB.buildEvalMessages({
              contractType: '房屋租赁合同', stanceLabel: '承租人',
              clauses: [{ index: 1, text: '押金不退' }],
              matchedRules: [], regSnippets: []
            });
            assert(evalMsgs[0].content.indexOf('审查视角') >= 0);
            assert(evalMsgs[0].content.indexOf('优先承租权') >= 0);
            assert(evalMsgs[0].content.indexOf('法定义务') >= 0);
            assert(evalMsgs[0].content.indexOf('同时覆盖') >= 0);
            assert(evalMsgs[0].content.indexOf('提前解约违约金') >= 0);
            assert(evalMsgs[0].content.indexOf('优先使用候选规则') >= 0);
            assert(evalMsgs[0].content.indexOf('必须在 findings 中以“条款缺失”提示') >= 0);
            assert(evalMsgs[0].content.indexOf('即使合同没有对应原文') >= 0);
            assert(evalMsgs[1].content.indexOf('审查视角：承租人') >= 0);
            const reviewMsgs = WB.buildReviewMessages({
              contractType: '房屋租赁合同', stanceLabel: '承租人',
              clauses: [], findings: [], lowRiskClauses: []
            });
            assert(reviewMsgs[1].content.indexOf('审查视角：承租人') >= 0);
            assert(reviewMsgs[0].content.indexOf('semantic|stance') >= 0);
            const stanceIssueMsgs = WB.buildEvalMessages({
              contractType: '房屋租赁合同', stanceLabel: '承租人',
              clauses: [{ index: 1, text: '押金不退' }],
              matchedRules: [], regSnippets: [],
              issues: [{ type: 'stance', description: '把对承租人有利的条款报为风险', suggestion: '移入低风险' }]
            });
            assert(stanceIssueMsgs[1].content.indexOf('stance 类必须按「审查视角」重评') >= 0);
            """,
            """
            // 审查视角进入报告元信息
            const htmlStance = WB.renderReport({
              contractType: '房屋租赁合同', stanceLabel: '承租人',
              findings: [], lowRiskClauses: [], summary: 's', dateText: '2026-11-24'
            });
            assert(htmlStance.indexOf('审查视角：承租人') >= 0);
            const htmlNeutral = WB.renderReport({
              contractType: '房屋租赁合同', findings: [], lowRiskClauses: [],
              summary: 's', dateText: '2026-11-24'
            });
            assert(htmlNeutral.indexOf('审查视角：中立（双方）') >= 0);
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
            """
            // Word 导出：表格重排、去掉按钮/折叠块、保留法条参考并转义
            const wordDoc = WB.buildDocHtml({
              contractType: '房屋租赁合同',
              stanceLabel: '承租人',
              findings: [{
                rule_id: 'x', rule_name: '测试规则', clause_index: 1,
                clause_text: '<script>alert(1)</script>',
                fairness: 5, clarity: 5, exposure: 5,
                risk_reason: '<b>风险</b>', basis: '民法典第585条',
                suggestion: '<i>建议</i>', level: '高',
                refs: [{ topic: '测试法规', text: '参考原文' }]
              }],
              lowRiskClauses: [{ clause_index: 2, clause_text: '低风险条款', reason: '无风险' }],
              summary: '总结',
              dateText: '2026-11-24'
            });
            assert(wordDoc.includes('WordSection1'));
            assert(wordDoc.includes('@page WordSection1'));
            assert(wordDoc.includes('审查视角：承租人'));
            assert(wordDoc.includes('审查日期：2026-11-24'));
            assert(wordDoc.includes('P0 必须改'));
            assert(wordDoc.includes('低风险条款'));
            assert(wordDoc.includes('法条参考'));
            assert(!wordDoc.includes('copy-btn'));
            assert(!wordDoc.includes('<details'));
            assert(!wordDoc.includes('<button'));
            assert(!wordDoc.includes('<script>'));
            assert(wordDoc.includes('&lt;script&gt;'));

            // 缺失条款不应显示成“原文：（合同未约定）”
            const missingFinding = {
              rule_id: 'missing', rule_name: '缺失条款测试', clause_index: 0,
              clause_text: '（合同未约定）', fairness: 3, clarity: 3, exposure: 3,
              risk_reason: '合同未约定该条款', basis: '民法典第180条',
              suggestion: '建议补充', level: '中'
            };
            const missingDoc = WB.buildDocHtml({
              contractType: '房屋租赁合同', stanceLabel: '承租人',
              findings: [missingFinding], lowRiskClauses: [], summary: '总结', dateText: '2026-11-24'
            });
            assert(missingDoc.includes('缺失条款'));
            assert(missingDoc.includes('本合同未约定该条款'));
            assert(!missingDoc.includes('>原文<'));
            const missingReport = WB.renderReport({
              contractType: '房屋租赁合同', findings: [missingFinding],
              lowRiskClauses: [], summary: '总结', dateText: '2026-11-24'
            });
            assert(missingReport.includes('缺失条款'));
            assert(missingReport.includes('本合同未约定该条款'));

            // 同条款其他约定：第七条同时有逾期违约金和提前解约违约金
            const leaseClauses = [{
              index: 7,
              text: '第七条 违约责任\\n乙方逾期支付租金超过15日的，每逾期一日按应付租金的5%支付违约金。\\n任何一方提前解除合同的，应提前60日书面通知对方，并向对方支付相当于2个月租金的违约金。'
            }];
            const extraFinding = {
              rule_id: 'r_lease_penalty', rule_name: '违约金过高', clause_index: 7,
              clause_text: '乙方逾期支付租金超过15日的，每逾期一日按应付租金的5%支付违约金。',
              fairness: 5, clarity: 4, exposure: 5, level: '高',
              risk_reason: '日违约金畸高', basis: '民法典第585条', suggestion: '建议调整'
            };
            const extraReport = WB.renderReport({
              contractType: '房屋租赁合同', clauses: leaseClauses,
              findings: [extraFinding], lowRiskClauses: [], summary: '总结', dateText: '2026-11-24'
            });
            assert(extraReport.includes('其他约定'));
            assert(extraReport.includes('提前解除合同'));
            const extraDoc = WB.buildDocHtml({
              contractType: '房屋租赁合同', clauses: leaseClauses,
              findings: [extraFinding], lowRiskClauses: [], summary: '总结', dateText: '2026-11-24'
            });
            assert(extraDoc.includes('其他约定'));
            assert(extraDoc.includes('提前解除合同'));
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


def test_ledger_extract():
    """加入台账时从合同原文本地识别对方 / 金额 / 日期 / 付款节点。"""
    node = _node()
    samples = {
        key: (ROOT.parent / f"sample_{key}.txt").read_text(encoding="utf-8")
        for key in ("lease", "employment", "sales", "service", "loan", "cooperation")
    }
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("ledger.js"),
            "const WB = globalThis.WB;",
            f"const samples = {json.dumps(samples, ensure_ascii=False)};",
            "const now = new Date(2026, 10, 25);",
            """
            const leaseTenant = WB.Ledger.extractDraft(samples.lease, {
              contractType: '房屋租赁合同', stance: 'tenant', now
            });
            assert.strictEqual(leaseTenant.counterparty, '张三');
            assert.strictEqual(leaseTenant.sender, '李四');
            assert.strictEqual(leaseTenant.startDate, '2026-06-01');
            assert.strictEqual(leaseTenant.endDate, '2029-05-31');
            assert.strictEqual(leaseTenant.amount, '15,000/月');
            assert.strictEqual(leaseTenant.paymentAmount, '15000');
            assert.strictEqual(leaseTenant.paymentDate, '2026-12-05');
            assert(leaseTenant.note.indexOf('押金') >= 0);

            const leaseLandlord = WB.Ledger.extractDraft(samples.lease, {
              contractType: '房屋租赁合同', stance: 'landlord', now
            });
            assert.strictEqual(leaseLandlord.counterparty, '李四');
            assert.strictEqual(leaseLandlord.sender, '张三');

            const leaseNeutral = WB.Ledger.extractDraft(samples.lease, {
              contractType: '房屋租赁合同', stance: 'neutral', now
            });
            assert(leaseNeutral.counterparty.indexOf('张三') >= 0);
            assert(leaseNeutral.counterparty.indexOf('李四') >= 0);

            const employment = WB.Ledger.extractDraft(samples.employment, {
              contractType: '劳动合同', stance: 'employee', now
            });
            assert.strictEqual(employment.counterparty, '上海智创科技有限公司');
            assert.strictEqual(employment.startDate, '2026-06-01');
            assert.strictEqual(employment.endDate, '2029-05-31');
            assert.strictEqual(employment.amount, '18,000/月');
            assert.strictEqual(employment.paymentAmount, '18000');
            assert.strictEqual(employment.paymentDate, '2026-11-30');
            assert(employment.note.indexOf('试用期') >= 0);

            const sales = WB.Ledger.extractDraft(samples.sales, {
              contractType: '买卖合同', stance: 'buyer', now
            });
            assert.strictEqual(sales.counterparty, '北京华创电子科技有限公司');
            assert.strictEqual(sales.amount, '6050000');
            assert.strictEqual(sales.paymentAmount, '3025000');

            const service = WB.Ledger.extractDraft(samples.service, {
              contractType: '服务合同', stance: 'client', now
            });
            assert.strictEqual(service.counterparty, '北京云策数据技术有限公司');
            assert.strictEqual(service.amount, '1200000');
            assert.strictEqual(service.paymentAmount, '480000');

            const loan = WB.Ledger.extractDraft(samples.loan, {
              contractType: '借款合同', stance: 'borrower', now
            });
            assert.strictEqual(loan.counterparty, '陈建国');
            assert.strictEqual(loan.amount, '200000');
            assert(loan.note.indexOf('年利率') >= 0);

            const cooperation = WB.Ledger.extractDraft(samples.cooperation, {
              contractType: '合作协议', stance: 'partyA', now
            });
            assert.strictEqual(cooperation.counterparty, '杭州潮汐科技有限公司');
            assert(cooperation.note.indexOf('期限') >= 0);

            // 非模板写法：角色在前、无甲乙双方、金额用大写、服务费/供方需方
            const roleFirst = WB.Ledger.extractDraft(
              '出租人（甲方）：王强\\n承租人（乙方）：李娜\\n租赁期限：2025年1月1日至2027年12月31日\\n月租金：人民币8,000元\\n租金每月10日前支付。',
              { contractType: '房屋租赁合同', stance: 'tenant', now }
            );
            assert.strictEqual(roleFirst.counterparty, '王强');
            assert.strictEqual(roleFirst.amount, '8,000/月');
            assert.strictEqual(roleFirst.paymentAmount, '8000');

            const serviceFee = WB.Ledger.extractDraft(
              '甲方（委托方）：甲公司\\n乙方（服务方）：乙公司\\n服务费总额：人民币50,000元\\n服务期限：2025/3/1 - 2025/12/31\\n合同签订后5个工作日内支付50%（25,000元）。',
              { contractType: '服务合同', stance: 'client', now }
            );
            assert.strictEqual(serviceFee.counterparty, '乙公司');
            assert.strictEqual(serviceFee.amount, '50000');
            assert.strictEqual(serviceFee.paymentAmount, '25000');

            const salesVariant = WB.Ledger.extractDraft(
              '供方：A公司\\n需方：B公司\\n合同总价：￥1,200,000\\n交货期：2025年5月1日至2025年8月31日\\n签订日期：2025年4月1日\\n需方于2025年4月10日前支付30%预付款360,000元。',
              { contractType: '买卖合同', stance: 'buyer', now }
            );
            assert.strictEqual(salesVariant.counterparty, 'A公司');
            assert.strictEqual(salesVariant.amount, '1200000');
            assert.strictEqual(salesVariant.paymentAmount, '360000');

            const uppercaseOnly = WB.Ledger.extractDraft(
              '甲方（出借方）：张三\\n乙方（借款方）：李四\\n借款金额：人民币贰拾万元整\\n借款期限：24个月\\n年利率8%\\n签订日期：2025年1月1日',
              { contractType: '借款合同', stance: 'borrower', now }
            );
            assert.strictEqual(uppercaseOnly.amount, '200000');
            assert(uppercaseOnly.note.indexOf('期限 24个月') >= 0);

            const chineseService = WB.Ledger.extractDraft(
              '发包方：甲公司\\n承包方：乙公司\\n服务费总额为人民币壹拾贰万元整。\\n服务期限：2025年3月1日至2025年12月31日。',
              { contractType: '服务合同', stance: 'client', now }
            );
            assert.strictEqual(chineseService.counterparty, '乙公司');
            assert.strictEqual(chineseService.amount, '120000');

            const empty = WB.Ledger.extractDraft('', {});
            assert.strictEqual(empty.counterparty, '');
            assert.strictEqual(empty.amount, '');
            assert.strictEqual(empty.startDate, '');
            assert.strictEqual(empty.endDate, '');
            assert.strictEqual(empty.paymentDate, '');
            assert.strictEqual(empty.paymentAmount, '');
            assert.strictEqual(empty.note, '');
            """,
            "console.log('OK');",
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_ledger_nodes():
    """台账多付款节点 / 续签：提醒、下次付款、ICS 与 CSV 都按节点展开。"""
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("ledger.js"),
            "const WB = globalThis.WB;",
            "const now = new Date(2026, 10, 25);",
            """
            const entry = {
              id: 'ct_1', title: '租赁合同', status: '履行中', contractType: '房屋租赁合同',
              counterparty: '张三', endDate: '2026-12-31', renewalDate: '2026-12-01',
              payments: [
                { id: 'p1', date: '2026-12-05', amount: '8000', note: '第二期' },
                { id: 'p2', date: '2026-11-30', amount: '7000', note: '第一期' },
              ],
            };
            const nodes = WB.Ledger.payments(entry);
            assert.strictEqual(nodes.length, 2);
            assert.strictEqual(nodes[0].id, 'p1');
            assert.strictEqual(WB.Ledger.nextPayment(entry, now).id, 'p2');
            assert.strictEqual(WB.Ledger.nextPayment({}, now), null);

            const legacy = { id: 'ct_2', paymentDate: '2026-12-10', paymentAmount: '500' };
            assert.strictEqual(WB.Ledger.payments(legacy).length, 1);
            assert.strictEqual(WB.Ledger.payments(legacy)[0].id, 'legacy');
            assert.strictEqual(WB.Ledger.payments({ payments: [{ date: 'bad' }] }).length, 0);

            const reminders = WB.Ledger.reminders([entry], now);
            assert(!reminders.some((r) => r.kind === '到期'));
            assert(reminders.some((r) => r.kind === '续签' && r.days === 6));
            assert.strictEqual(reminders.filter((r) => r.kind === '付款').length, 2);
            assert(reminders.filter((r) => r.kind === '付款').some((r) => r.note === '第一期'));
            assert(WB.Ledger.reminders([entry], now, 60).some((r) => r.kind === '到期' && r.days === 36));

            const ics = WB.Ledger.buildICS([entry]);
            assert(ics.includes('续签提醒'));
            assert(ics.includes('付款节点'));
            assert.strictEqual((ics.match(/BEGIN:VEVENT/g) || []).length, 4);
            assert(ics.includes('UID:ct_1-pay-p1@'));
            assert(ics.includes('UID:ct_1-pay-p2@'));
            assert(ics.includes('UID:ct_1-renew@'));

            const csv = WB.Ledger.buildCSV([entry]);
            assert(csv.includes('续签日期'));
            assert(csv.includes('付款节点'));
            assert(csv.includes('第二期'));
            const row = csv.split('\\r\\n')[1];
            assert(row.includes('2026-11-30'));
            assert(row.includes('2026-12-01'));
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


def test_attachments():
    """附件管理：文件类型 / 大小限制与可读体积。"""
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("attachments.js"),
            "const WB = globalThis.WB;",
            """
            assert.strictEqual(WB.Attachments.extension('合同 原件.PDF'), 'pdf');
            assert.strictEqual(WB.Attachments.formatSize(512), '512 B');
            assert.strictEqual(WB.Attachments.formatSize(2048), '2.0 KB');
            assert.strictEqual(WB.Attachments.formatSize(25 * 1024 * 1024), '25.0 MB');
            assert.strictEqual(WB.Attachments.checkFile({ name: '合同.pdf', size: 1024 }, 0), '');
            assert(WB.Attachments.checkFile({ name: '程序.exe', size: 10 }, 0).indexOf('不支持') >= 0);
            assert(WB.Attachments.checkFile({ name: '无扩展名', size: 10 }, 0).indexOf('扩展名') >= 0);
            assert(WB.Attachments.checkFile({ name: '空.pdf', size: 0 }, 0).indexOf('空') >= 0);
            assert(WB.Attachments.checkFile({ name: '大.pdf', size: WB.Attachments.MAX_FILE + 1 }, 0).indexOf('25.0 MB') >= 0);
            assert(WB.Attachments.checkFile({ name: 'b.pdf', size: 1024 }, WB.Attachments.MAX_TOTAL).indexOf('合计') >= 0);
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


def test_law_lookup():
    """法条速查：本地知识库、分类过滤与离线检索。"""
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("data/knowledge.js"),
            _require("law.js"),
            "const WB = globalThis.WB;",
            """
            const docs = WB.lawDocs();
            assert(docs.length >= 40, String(docs.length));
            const counts = WB.lawCategoryCounts();
            assert(counts['法规'] > 0 && counts['判例'] > 0 && counts['地方'] > 0 && counts['税务'] > 0 && counts['新规'] > 0);
            assert.strictEqual(counts['全部'], docs.length);

            const deposit = WB.searchLaw('押金', '全部');
            assert(deposit.length > 0);
            assert(deposit[0].doc.text.indexOf('押金') >= 0 || deposit[0].doc.title.indexOf('押金') >= 0);

            const cases = WB.searchLaw('违约金', '判例');
            assert(cases.length > 0);
            assert(cases.every((r) => r.doc.category === '判例'));

            const local = WB.searchLaw('备案', '地方');
            assert(local.length > 0);
            assert(local.every((r) => r.doc.category === '地方'));

            const tax = WB.searchLaw('', '税务');
            assert(tax.length > 0);
            assert(tax.every((r) => r.doc.category === '税务'));

            assert.strictEqual(WB.searchLaw('火星基地不存在', '全部').length, 0);
            assert(WB.lawTokenize('押金退还').indexOf('押金') >= 0);
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


def test_documents():
    """V2 文书：提示词、纯文本清理、Word HTML 转义。"""
    node = _node()
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("prompts.js"),
            _require("llm.js"),
            _require("pipeline.js"),
            _require("docx.js"),
            _require("documents.js"),
            "const WB = globalThis.WB;",
            """
            const input = {
              docType: 'demand',
              contractTitle: '房屋租赁合同',
              contractType: '房屋租赁合同',
              stanceLabel: '承租人',
              sender: '李四',
              counterparty: '张三',
              amount: '15,000/月',
              dueDate: '2026-12-05',
              demandDate: '2026-12-20',
              facts: '承租人未按约支付租金。',
              findings: [{
                clause_index: 3, rule_name: '租金支付', level: '高',
                clause_text: '乙方应于每月5日前支付租金',
                risk_reason: '承租人逾期未付', basis: '民法典第721条'
              }]
            };
            const messages = WB.buildDocMessages(input);
            assert(messages[0].content.indexOf('文书起草助手') >= 0);
            assert(messages[0].content.indexOf('不得编造') >= 0);
            assert(messages[0].content.indexOf('律师复核') >= 0);
            assert(messages[1].content.indexOf('【发函方】李四') >= 0);
            assert(messages[1].content.indexOf('【对方主体】张三') >= 0);
            assert(messages[1].content.indexOf('第 3 条') >= 0);
            assert(messages[1].content.indexOf('乙方应于每月5日前支付租金') >= 0);

            const terminate = WB.buildDocMessages(Object.assign({}, input, { docType: 'terminate' }));
            assert(terminate[0].content.indexOf('解除合同通知书') >= 0);
            const rectify = WB.buildDocMessages(Object.assign({}, input, { docType: 'rectify' }));
            assert(rectify[0].content.indexOf('整改函') >= 0);
            assert.strictEqual(WB.DOC_TYPES.length, 6);
            const lawyer = WB.buildDocMessages(Object.assign({}, input, { docType: 'lawyer' }));
            assert(lawyer[0].content.indexOf('律师函（草稿）') >= 0);
            assert(lawyer[0].content.indexOf('不得编造律所') >= 0);
            assert(lawyer[0].content.indexOf('本稿需执业律师复核后方可发出') >= 0);
            assert(lawyer[1].content.indexOf('【文书类型】律师函（草稿）') >= 0);
            const renewal = WB.buildDocMessages(Object.assign({}, input, { docType: 'renewal' }));
            assert(renewal[0].content.indexOf('续签提醒函') >= 0);
            const notice = WB.buildDocMessages(Object.assign({}, input, { docType: 'notice' }));
            assert(notice[0].content.indexOf('合同变更通知') >= 0);
            assert.strictEqual(WB.docTypeMeta('missing').key, 'demand');

            const cleaned = WB.cleanDocText('```text\\n催款函\\n\\n正文\\n```');
            assert(cleaned.indexOf('```') < 0);
            assert(cleaned.indexOf('律师复核') >= 0);

            const html = WB.buildDocumentHtml({
              text: '催款函\\n\\n致：<script>alert(1)</script>\\n\\n正文',
              meta: '合同：<b>x</b>'
            });
            assert(html.indexOf('WordSection1') >= 0);
            assert(html.indexOf('&lt;script&gt;') >= 0);
            assert(html.indexOf('<script>') < 0);
            assert(html.indexOf('&lt;b&gt;x&lt;/b&gt;') >= 0);

            const blob = WB.buildDocDocx({ text: '催款函\\n\\n正文', meta: '测试' });
            assert(blob.type.indexOf('openxmlformats') >= 0);
            assert(blob.size > 1000);
            """,
            "console.log('OK');",
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_templates():
    """V2 范本：本地字段替换、占位符、HTML 转义与 .docx。"""
    node = _node()
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("prompts.js"),
            _require("llm.js"),
            _require("pipeline.js"),
            _require("docx.js"),
            _require("documents.js"),
            _require("templates.js"),
            "const WB = globalThis.WB;",
            """
            assert.strictEqual(WB.TEMPLATES.length, 6);
            const available = WB.TEMPLATES.filter((t) => t.available).map((t) => t.key);
            assert.deepStrictEqual(available, ['lease', 'employment', 'sales', 'service', 'cooperation', 'loan']);
            assert.strictEqual(WB.templateMeta('employment').contractType, '劳动合同');
            assert.strictEqual(WB.templateMeta('missing').key, 'lease');
            assert.strictEqual(WB.buildTemplateText('missing', {}), '');
            assert.strictEqual(WB.buildTemplateText('sales', {}).length > 0, true);
            WB.TEMPLATES.forEach((t) => {
              const text = WB.buildTemplateText(t.key, {});
              assert(text.length > 0, t.key);
              assert(text.indexOf('{{') < 0, t.key);
              const fieldKeys = new Set(t.fields.map((f) => f.key));
              const tokens = Array.from((t.body || '').matchAll(/\\{\\{([a-zA-Z0-9_]+)\\}\\}/g)).map((m) => m[1]);
              assert(tokens.every((key) => fieldKeys.has(key)), t.key);
            });

            const lease = WB.buildTemplateText('lease', {
              lessor: '李四', lessee: '张三', property: '上海市某区某路 1 号',
              monthlyRent: '5000 元'
            });
            assert(lease.indexOf('房屋租赁合同') >= 0);
            assert(lease.indexOf('李四') >= 0);
            assert(lease.indexOf('上海市某区某路 1 号') >= 0);
            assert(lease.indexOf('5000 元') >= 0);
            assert(lease.indexOf('【待填写：押金】') >= 0);
            assert(lease.indexOf('{{') < 0);
            assert(lease.indexOf('律师复核') >= 0);

            const labor = WB.buildTemplateText('employment', {
              employer: '上海某公司', employee: '李四', position: '产品运营',
              salary: '8000 元', probation: '无', probationSalary: '无',
              workHours: '标准工时制'
            });
            assert(labor.indexOf('劳动合同') >= 0);
            assert(labor.indexOf('上海某公司') >= 0);
            assert(labor.indexOf('产品运营') >= 0);
            assert(labor.indexOf('社会保险') >= 0);
            assert(labor.indexOf('劳动争议仲裁') >= 0);
            assert(labor.indexOf('试用期：无') >= 0);
            assert(labor.indexOf('乙方实行标准工时制。') >= 0);

            const sales = WB.buildTemplateText('sales', {
              seller: '甲公司', buyer: '乙公司', subject: '办公电脑',
              totalPrice: '100000 元', paymentTerms: '验收后 10 日内付清'
            });
            assert(sales.indexOf('买卖合同') >= 0);
            assert(sales.indexOf('甲公司') >= 0);
            assert(sales.indexOf('办公电脑') >= 0);
            assert(sales.indexOf('验收后 10 日内付清') >= 0);
            assert(sales.indexOf('风险，在交付之前') >= 0);

            const service = WB.buildTemplateText('service', {
              client: '甲公司', provider: '乙公司', serviceName: '品牌设计',
              fee: '50000 元', ipOwnership: '归甲方'
            });
            assert(service.indexOf('服务合同') >= 0);
            assert(service.indexOf('品牌设计') >= 0);
            assert(service.indexOf('知识产权归属：归甲方') >= 0);
            assert(service.indexOf('保密义务') >= 0);

            const cooperation = WB.buildTemplateText('cooperation', {
              partyA: '甲公司', partyB: '乙公司', projectName: '联名项目',
              profitShare: '甲方 60%、乙方 40%', term: '长期'
            });
            assert(cooperation.indexOf('合作协议') >= 0);
            assert(cooperation.indexOf('联名项目') >= 0);
            assert(cooperation.indexOf('甲方 60%、乙方 40%') >= 0);
            assert(cooperation.indexOf('退出机制') >= 0);

            const loan = WB.buildTemplateText('loan', {
              lender: '甲公司', borrower: '乙公司', amount: '100000 元',
              interestRate: '年利率 6%', guarantee: '无'
            });
            assert(loan.indexOf('借款合同') >= 0);
            assert(loan.indexOf('100000 元') >= 0);
            assert(loan.indexOf('年利率 6%') >= 0);
            assert(loan.indexOf('LPR 的四倍') >= 0);
            assert(loan.indexOf('担保方式：无') >= 0);

            const special = WB.buildTemplateText('lease', { lessor: 'A$&B' });
            assert(special.indexOf('A$&B') >= 0);

            const html = WB.buildTemplateHtml({
              text: '劳动合同\\n\\n甲方：<script>alert(1)</script>',
              meta: '合同：<b>x</b>'
            });
            assert(html.indexOf('WordSection1') >= 0);
            assert(html.indexOf('&lt;script&gt;') >= 0);
            assert(html.indexOf('<script>') < 0);
            assert(html.indexOf('&lt;b&gt;x&lt;/b&gt;') >= 0);

            const blob = WB.buildTemplateDocx({ text: '劳动合同\\n\\n正文', meta: '测试' });
            assert(blob.type.indexOf('openxmlformats') >= 0);
            assert(blob.size > 1000);
            """,
            "console.log('OK');",
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_compare():
    """V3 版本对比：条款对齐、风险变化、转义与 .docx。"""
    node = _node()
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("prompts.js"),
            _require("llm.js"),
            _require("pipeline.js"),
            _require("docx.js"),
            _require("compare.js"),
            "const WB = globalThis.WB;",
            """
            assert.strictEqual(WB.compareContracts('', 'x'), null);
            assert.strictEqual(WB.compareContracts('x', ''), null);

            const oldText = [
              '房屋租赁合同', '',
              '第一条 租金', '乙方应于每月5日前支付租金5000元。', '',
              '第二条 押金', '押金为10000元。', '',
              '第三条 转租', '未经甲方书面同意不得转租。'
            ].join('\\n');
            const newText = [
              '房屋租赁合同', '',
              '第一条 租金', '乙方应于每月10日前支付租金6000元。', '',
              '第二条 押金', '押金为10000元。', '',
              '第四条 维修', '房屋维修由甲方负责。'
            ].join('\\n');
            const result = WB.compareContracts(oldText, newText);
            assert.deepStrictEqual(result.summary, { same: 2, modified: 1, added: 1, removed: 1 });
            assert.strictEqual(result.rows.filter((r) => r.type === 'modified').length, 1);
            const modified = result.rows.find((r) => r.type === 'modified');
            assert(modified.oldHtml.indexOf('<del>') >= 0);
            assert(modified.newHtml.indexOf('<ins>') >= 0);
            assert.strictEqual(result.risk, null);
            assert(WB.renderCompareBody(result, { onlyChanged: true }).indexOf('只看变化') >= 0);

            const renumbered = WB.compareContracts(
              '第一条 租金\\n每月5日支付。\\n\\n第二条 押金\\n押金一万元。',
              '第三条 租金\\n每月5日支付。\\n\\n第四条 押金\\n押金一万元。'
            );
            assert.strictEqual(renumbered.summary.same, 2);
            assert.strictEqual(renumbered.summary.added, 0);
            assert.strictEqual(renumbered.summary.removed, 0);

            // 没有条款编号的纯段落文本：中间插一段，不能把后面整段都算成“修改”。
            const block = WB.compareContracts(
              '租金每月五千元，每月五日支付。\\n押金一万元，退租时无息返还。',
              '租金每月五千元，每月五日支付。\\n维修由甲方负责，七日内到场。\\n押金一万元，退租时无息返还。'
            );
            assert.deepStrictEqual(block.summary, { same: 2, modified: 0, added: 1, removed: 0 });

            // 超大文本（2000+ 条）走线性回退，避免 O(n×m) 动态规划卡死页面。
            const manyOld = Array.from({ length: 2001 }, (_x, i) =>
              '第' + (i + 1) + '条 条款' + (i + 1) + '\\n内容' + (i + 1) + '。'
            ).join('\\n');
            const manyNew = manyOld.replace('内容2001。', '内容2001变更。');
            const many = WB.compareContracts(manyOld, manyNew);
            assert.strictEqual(many.summary.same, 2000);
            assert.strictEqual(many.summary.modified, 1);

            const risk = WB.compareRisk({
              findings: [
                { rule_id: 'a', rule_name: '租金', level: '高', clause_index: 1, clause_text: '租金5000', risk_reason: '旧' },
                { rule_id: 'b', rule_name: '押金', level: '中', clause_index: 2, clause_text: '押金', risk_reason: '押金' }
              ],
              score: 50, contractType: '房屋租赁合同', stanceLabel: '中立（双方）'
            }, {
              findings: [
                { rule_id: 'a', rule_name: '租金', level: '中', clause_index: 1, clause_text: '租金6000', risk_reason: '新' },
                { rule_id: 'c', rule_name: '维修', level: '高', clause_index: 3, clause_text: '维修', risk_reason: '维修' }
              ],
              score: 55, contractType: '房屋租赁合同', stanceLabel: '中立（双方）'
            });
            assert.deepStrictEqual(risk.added.map((r) => r.rule_name), ['维修']);
            assert.deepStrictEqual(risk.resolved.map((r) => r.rule_name), ['押金']);
            assert.strictEqual(risk.levelChanged.length, 1);
            assert.strictEqual(risk.levelChanged[0].old.level, '高');
            assert.strictEqual(risk.levelChanged[0].new.level, '中');
            assert.strictEqual(risk.delta.score, 5);

            // 报告统计里的低风险包含 lowRiskClauses，比较时优先使用结果自带的 counts。
            const counted = WB.compareRisk({
              findings: [], counts: { high: 0, mid: 1, low: 7 }, score: 13
            }, {
              findings: [], counts: { high: 1, mid: 0, low: 9 }, score: 24
            });
            assert.deepStrictEqual(counted.old.counts, { high: 0, mid: 1, low: 7 });
            assert.deepStrictEqual(counted.new.counts, { high: 1, mid: 0, low: 9 });
            assert.strictEqual(counted.delta.low, 2);
            assert.strictEqual(counted.delta.score, 11);

            const emptyRisk = WB.compareRisk(null, undefined);
            assert.deepStrictEqual(emptyRisk.old.counts, { high: 0, mid: 0, low: 0 });
            assert.strictEqual(emptyRisk.delta.score, null);

            const unsafe = WB.compareContracts(
              '合同\\n\\n第一条 租金\\n<script>alert(1)</script>5000元。',
              '合同\\n\\n第一条 租金\\n<script>alert(2)</script>6000元。'
            );
            const unsafeHtml = WB.renderCompareBody(unsafe, { onlyChanged: true });
            assert(unsafeHtml.indexOf('<script>') < 0);
            assert(unsafeHtml.indexOf('&lt;script&gt;') >= 0);

            const html = WB.buildCompareHtml(result, '旧版：A · 新版：B');
            assert(html.indexOf('WordSection1') >= 0);
            assert(html.indexOf('合同版本对比') >= 0);
            assert(html.indexOf('<script>') < 0);
            // Word 会吞掉 <del>，导出 HTML 必须换成普通 span。
            assert(html.indexOf('<del>') < 0);
            assert(html.indexOf('<ins>') < 0);
            assert(html.indexOf('diff-del') >= 0);
            assert(html.indexOf('diff-ins') >= 0);

            const blob = WB.buildCompareDocx(result, '旧版：A · 新版：B');
            assert(blob.type.indexOf('openxmlformats') >= 0);
            assert(blob.size > 1000);
            """,
            "console.log('OK');",
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_ocr():
    """OCR：图片消息格式、复用当前模型配置、无 Key / 非图片文件报错。"""
    node = _node()
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("prompts.js"),
            _require("llm.js"),
            _require("file_parser.js"),
            _require("ocr.js"),
            "const WB = globalThis.WB;",
            """
            (async () => {
              const original = WB.callLLM;
              let captured = null;
              WB.callLLM = async (opts) => {
                captured = opts;
                return { content: '第一条 租金\\n乙方应于每月5日前支付租金5000元。', usage: null };
              };
              const settings = {
                provider: 'dashscope',
                baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                model: 'deepseek-v4.1-flash',
                apiKeys: { dashscope: 'test-key' }
              };
              try {
                const text = await WB.ocrImage('data:image/jpeg;base64,AAAA', settings);
                assert(text.indexOf('第一条 租金') >= 0);
                assert.strictEqual(captured.jsonMode, false);
                assert.strictEqual(captured.messages[0].content[1].type, 'image_url');
                assert.strictEqual(captured.messages[0].content[1].image_url.detail, 'high');
                assert.strictEqual(captured.extraBody.enable_thinking, false);

                await assert.rejects(
                  WB.ocrImage('data:image/jpeg;base64,AAAA', {
                    provider: 'dashscope', baseUrl: 'x', model: 'm', apiKeys: {}
                  }),
                  /API Key/
                );
                await assert.rejects(
                  WB.ocrFile(new File(['x'], 'x.txt', { type: 'text/plain' }), settings),
                  /只支持/
                );
              } finally {
                WB.callLLM = original;
              }
              console.log('OK');
            })().catch((e) => { console.error(e); process.exit(1); });
            """,
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_backup():
    """备份：不导出 API Key、结构校验、记录上限。"""
    node = _node()
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            _require("backup.js"),
            "const WB = globalThis.WB;",
            """
            const backup = WB.buildBackup({
              settings: {
                provider: 'dashscope', model: 'deepseek-v4.1-flash',
                apiKeys: { dashscope: 'sk-secret', deepseek: 'sk-other' },
                masking: true, hiddenNames: ['张三']
              },
              reviews: [{ id: 'rv_1', contractText: '合同正文', result: { score: 1 } }],
              ledger: [{ id: 'ct_1', title: '租赁合同' }],
              rules: { overrides: {}, custom: [], updatedAt: 123 },
              current: { result: { score: 1 }, contractText: '合同正文' }
            });
            assert(JSON.stringify(backup).indexOf('sk-secret') < 0);
            assert.strictEqual(backup.data.settings.model, 'deepseek-v4.1-flash');
            assert.strictEqual(backup.data.reviews.length, 1);
            assert.strictEqual(backup.data.current.result.score, 1);

            const parsed = WB.parseBackup(JSON.stringify(backup));
            assert.strictEqual(parsed.reviews[0].id, 'rv_1');
            assert.strictEqual(parsed.ledger[0].id, 'ct_1');
            assert.strictEqual(parsed.rules.updatedAt, 123);
            assert.throws(() => WB.parseBackup('not json'), /JSON/);
            assert.throws(() => WB.parseBackup('{}'), /合同工作台/);
            const tooMany = Array.from({ length: 501 }, (_x, i) => ({ id: 'rv_' + i }));
            assert.throws(() => WB.validateBackup({ app: 'contract-workbench', version: 1, data: { reviews: tooMany } }), /500/);
            const capped = WB.buildBackup({ reviews: tooMany, ledger: tooMany });
            assert.strictEqual(capped.data.reviews.length, 500);
            assert.strictEqual(capped.data.ledger.length, 500);
            console.log('OK');
            """,
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_document_docx_package(tmp_path):
    """文书导出也是真 .docx，正文转义且含律师复核提示。"""
    node = _node()
    out = tmp_path / "letter.docx"
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            "const fs = require('node:fs');",
            _require("prompts.js"),
            _require("llm.js"),
            _require("pipeline.js"),
            _require("docx.js"),
            _require("documents.js"),
            "const WB = globalThis.WB;",
            "(async () => {",
            "  const blob = WB.buildDocDocx({",
            "    text: '催款函\\n\\n致：<script>x</script>\\n\\n正文\\n\\n本函为 AI 辅助草稿，正式发出前请由律师复核。',",
            "    meta: '关联合同：房屋租赁合同 · 文书类型：催款函'",
            "  });",
            "  assert(blob.type.indexOf('openxmlformats') >= 0);",
            "  const buf = Buffer.from(await blob.arrayBuffer());",
            "  fs.writeFileSync(process.env.DOCX_OUT, buf);",
            "  assert(buf[0] === 0x50 && buf[1] === 0x4b);",
            "  console.log('OK');",
            "})().catch((e) => { console.error(e); process.exit(1); });",
        ]
    )
    env = os.environ.copy()
    env["DOCX_OUT"] = str(out)
    proc = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert "word/afchunk.html" in names
        html = z.read("word/afchunk.html").decode("utf-8")
        assert "催款函" in html
        assert "律师复核" in html
        assert "&lt;script&gt;" in html
        assert "<script" not in html.lower()


def test_docx_export_package(tmp_path):
    """Word 导出是真 .docx（ZIP + altChunk），不是 HTML 改扩展名。"""
    node = _node()
    out = tmp_path / "report.docx"
    script = "\n".join(
        [
            "const assert = require('node:assert');",
            "const fs = require('node:fs');",
            _require("data/rules.js"),
            _require("data/knowledge.js"),
            _require("prompts.js"),
            _require("llm.js"),
            _require("pipeline.js"),
            _require("docx.js"),
            "const WB = globalThis.WB;",
            "(async () => {",
            "  const blob = WB.buildDocx({",
            "    contractType: '房屋租赁合同', stanceLabel: '承租人',",
            "    findings: [{ rule_id:'x', rule_name:'测试规则', clause_index:1, clause_text:'<script>x</script>', fairness:5, clarity:5, exposure:5, risk_reason:'风险', basis:'民法典第585条', suggestion:'建议', level:'高' }],",
            "    lowRiskClauses: [{ clause_index:2, clause_text:'低风险条款', reason:'无风险' }],",
            "    summary: '总结', dateText: '2026-11-24'",
            "  });",
            "  assert(blob.type.indexOf('openxmlformats') >= 0);",
            "  const buf = Buffer.from(await blob.arrayBuffer());",
            "  fs.writeFileSync(process.env.DOCX_OUT, buf);",
            "  assert(buf[0] === 0x50 && buf[1] === 0x4b);",
            "  console.log('OK');",
            "})().catch((e) => { console.error(e); process.exit(1); });",
        ]
    )
    env = os.environ.copy()
    env["DOCX_OUT"] = str(out)
    proc = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "word/document.xml" in names
        assert "word/afchunk.html" in names
        document = z.read("word/document.xml").decode("utf-8")
        assert "altChunk" in document
        html = z.read("word/afchunk.html").decode("utf-8")
        assert "合同审查报告" in html
        assert "WordSection1" in html
        assert "审查视角：承租人" in html
        assert "审查日期：2026-11-24" in html
        assert "<script" not in html.lower()
        assert "<button" not in html.lower()
        assert "&lt;script&gt;" in html
