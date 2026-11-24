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
