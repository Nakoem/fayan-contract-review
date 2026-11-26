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
SRC = ROOT / "src"
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


def test_legal_citations_current(rules):
    """2026-11-24 按现行法规核对后修正的关键条文号。"""
    by_id = {r["id"]: r for r in rules}
    expected = {
        "r_lease_jurisdiction": "民事诉讼法第34条",
        "r_common_jurisdiction": "民事诉讼法第35条",
        "r_labor_social_insurance": "劳动争议司法解释（二）第19条",
        "r_service_ip": "著作权法第19条",
        "r_service_no_refund": "预付式消费司法解释第9条",
        "r_service_business_closure": "预付式消费司法解释第7条、第23条",
    }
    for rid, basis in expected.items():
        assert by_id[rid]["basis"] == basis, f"{rid} 法条未更新：{by_id[rid]['basis']}"


def test_rules_meta():
    """规则核对日期与来源版本可追溯。"""
    node = _node()
    script = (
        "require(" + json.dumps(str(RULES_JS).replace("\\", "/")) + ");"
        "process.stdout.write(JSON.stringify(globalThis.WB.RULES_META));"
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    meta = json.loads(out.stdout)
    assert meta["verifiedAt"] == "2026-11-24"
    assert len(meta["sources"]) >= 20
    assert all(s.get("name") and s.get("version") for s in meta["sources"])
    names = {s["name"] for s in meta["sources"]}
    for name in (
        "中华人民共和国公司法",
        "中华人民共和国合伙企业法",
        "中华人民共和国仲裁法",
        "中华人民共和国消费者权益保护法",
        "中华人民共和国反不正当竞争法",
        "最高人民法院关于适用《中华人民共和国民事诉讼法》的解释",
    ):
        assert name in names, f"法规来源缺少 {name}"


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


def test_expanded_rule_coverage(rules):
    """P0 + P1 扩容后的规则数量与关键新增规则。"""
    counts: dict[str, int] = {}
    for r in rules:
        counts[r["contractType"]] = counts.get(r["contractType"], 0) + 1
    assert counts == {
        "房屋租赁合同": 18,
        "劳动合同": 20,
        "买卖合同": 15,
        "服务合同": 17,
        "合作协议": 16,
        "借款合同": 14,
        "通用": 11,
    }, counts
    by_id = {r["id"]: r for r in rules}
    for rid in (
        "r_lease_filing",
        "r_labor_written_contract",
        "r_sale_title_defect",
        "r_service_consumer_format",
        "r_coop_capital_contribution",
        "r_loan_unlicensed_lending",
        "r_common_arbitration_clause",
    ):
        assert rid in by_id, f"缺少扩容规则 {rid}"
    assert by_id["r_service_consumer_format"]["basis"] == "消费者权益保护法第26条"
    assert "公司法" in by_id["r_coop_capital_contribution"]["basis"]
    assert by_id["r_common_arbitration_clause"]["basis"] == "仲裁法第27条、第29条"


def test_review_stances():
    """审查视角覆盖 6 类合同 + 通用，每类两个角色。"""
    node = _node()
    script = (
        "require(" + json.dumps(str(RULES_JS).replace("\\", "/")) + ");"
        "process.stdout.write(JSON.stringify({"
        "stances: globalThis.WB.STANCES,"
        "tenant: globalThis.WB.stanceLabel('房屋租赁合同', 'tenant'),"
        "neutral: globalThis.WB.stanceLabel('房屋租赁合同', 'neutral')"
        "}));"
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    data = json.loads(out.stdout)
    stances = data["stances"]
    assert set(stances) == TYPES | {"通用"}, f"审查视角类型不全：{sorted(stances)}"
    for contract_type, roles in stances.items():
        assert len(roles) == 2, f"{contract_type} 角色数量不对"
        assert len({r.get("key") for r in roles}) == 2, f"{contract_type} 角色 key 重复"
        assert all(r.get("key") and r.get("label") for r in roles), f"{contract_type} 角色字段为空"
    assert data["tenant"] == "承租人"
    assert data["neutral"] == "中立（双方）"


def test_rule_store_merge():
    """内置覆盖只接受已存在的 id；自定义规则做字段校验；非法数据被丢弃。"""
    node = _node()

    def require(rel: str) -> str:
        return "require(" + json.dumps((SRC / rel).as_posix()) + ");"

    script = "\n".join(
        [
            "const assert = require('node:assert');",
            require("data/rules.js"),
            require("storage.js"),
            require("rule_store.js"),
            "const WB = globalThis.WB;",
            "const S = WB.RuleStore;",
            "const before = S.builtinCount;",
            """
            (async () => {
              S.applyState({
                overrides: {
                  r_lease_penalty: {
                    contractType: "房屋租赁合同", name: "改过的违约金",
                    keywords: "违约金, 逾期", condition: "新条件", level: "中",
                    basis: "民法典第585条", advice: "新建议", enabled: false
                  },
                  r_not_exist: { name: "不应出现" }
                },
                custom: [
                  {
                    id: "r_custom_test", contractType: "买卖合同", name: "测试规则",
                    keywords: "测试、验收", condition: "条件", level: "低",
                    basis: "民法典第509条", advice: "建议"
                  },
                  { id: "r_custom_bad", name: "", keywords: "", condition: "", basis: "", advice: "" }
                ]
              });
              assert.strictEqual(WB.RULES.length, before + 1);
              const changed = S.find("r_lease_penalty");
              assert.strictEqual(changed.name, "改过的违约金");
              assert.deepStrictEqual(changed.keywords, ["违约金", "逾期"]);
              assert.strictEqual(changed.enabled, false);
              assert.strictEqual(changed.builtin, true);
              const custom = S.find("r_custom_test");
              assert(custom && custom.builtin === false);
              assert.deepStrictEqual(custom.keywords, ["测试", "验收"]);
              assert(!S.find("r_custom_bad"));
              assert(!S.find("r_not_exist"));
              assert.strictEqual(
                S.validate({ name: "x", keywords: "k", condition: "c", basis: "民法典", advice: "a" }).ok,
                false
              );
              assert.strictEqual(
                S.validate({ name: "x", keywords: "k", condition: "c", basis: "民法典第585条", advice: "a" }).ok,
                true
              );

              // 存储不可用：写入失败必须回滚，不能“看起来改了”
              S.applyState({ overrides: {}, custom: [] });
              WB.loadRuleState = async () => null;
              WB.saveRuleState = async () => ({ ok: false });
              const rollback = await S.setEnabled("r_lease_penalty", false);
              assert.strictEqual(rollback.ok, false);
              assert.strictEqual(rollback.reason, "storage");
              assert.strictEqual(S.find("r_lease_penalty").enabled, true);

              // 另一标签页写入新 revision：本次编辑放弃并载入最新状态
              let stored = { overrides: {}, custom: [], updatedAt: 10 };
              WB.loadRuleState = async () => stored;
              WB.saveRuleState = async (next, expected) => {
                const rev = stored && stored.updatedAt || 0;
                if (expected != null && stored && rev !== expected) {
                  return { ok: false, conflict: true };
                }
                stored = next;
                return { ok: true };
              };
              S.applyState({ overrides: {}, custom: [], updatedAt: 10 });
              stored = { overrides: {}, custom: [], updatedAt: 20 };
              const conflict = await S.setEnabled("r_lease_penalty", false);
              assert.strictEqual(conflict.ok, false);
              assert.strictEqual(conflict.reason, "conflict");
              assert.strictEqual(S.find("r_lease_penalty").enabled, true);
              assert.strictEqual(S.revision(), 20);

              // 同标签页连续写入排队执行，不会共用旧 revision 互相冲突
              stored = { overrides: {}, custom: [], updatedAt: 20 };
              S.applyState({ overrides: {}, custom: [], updatedAt: 20 });
              const [r1, r2] = await Promise.all([
                S.setEnabled("r_lease_penalty", false),
                S.setEnabled("r_lease_penalty", true)
              ]);
              assert(r1.ok && r2.ok);
              assert.strictEqual(S.find("r_lease_penalty").enabled, true);

              // 自定义规则上限
              const many = [];
              for (let i = 0; i < S.maxCustom; i++) {
                many.push({
                  id: "r_custom_" + i, contractType: "通用", name: "规则" + i,
                  keywords: "k", condition: "c", basis: "民法典第1条", advice: "a"
                });
              }
              stored = { overrides: {}, custom: many, updatedAt: 30 };
              S.applyState(stored);
              const limit = await S.addCustom({
                contractType: "通用", name: "x", keywords: "k",
                condition: "c", basis: "民法典第1条", advice: "a"
              });
              assert.strictEqual(limit.ok, false);
              assert.strictEqual(limit.reason, "limit");
              assert.strictEqual(S.state().custom.length, S.maxCustom);
              const removed = await S.removeCustom("r_custom_0");
              assert.strictEqual(removed.ok, true);
              assert.strictEqual(S.state().custom.length, S.maxCustom - 1);

              console.log("OK");
            })().catch((e) => { console.error(e); process.exit(1); });
            """,
        ]
    )
    out = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_rule_pack():
    """规则包：格式校验、导入合并、持久化失败回滚。"""
    node = _node()

    def require(rel: str) -> str:
        return "require(" + json.dumps((SRC / rel).as_posix()) + ");"

    script = "\n".join(
        [
            "const assert = require('node:assert');",
            require("data/rules.js"),
            require("storage.js"),
            require("rule_pack.js"),
            require("rule_store.js"),
            "const WB = globalThis.WB;",
            "const S = WB.RuleStore;",
            """
            (async () => {
              const packState = {
                overrides: {
                  r_lease_penalty: {
                    contractType: "房屋租赁合同", name: "包内覆盖", keywords: ["违约金"],
                    condition: "押金超过两个月租金", level: "高",
                    basis: "民法典第585条", advice: "包内建议", enabled: false
                  }
                },
                custom: [
                  {
                    id: "r_custom_pack_a", contractType: "买卖合同", name: "包内自定义",
                    keywords: ["验收", "测试"], condition: "出现验收字样", level: "中",
                    basis: "民法典第509条", advice: "包内自定义建议"
                  }
                ]
              };
              const pack = WB.RulePack.build(packState, { name: " 测试包 ", note: "导入测试" });
              assert.strictEqual(pack.app, "contract-workbench-rules");
              assert.strictEqual(pack.version, 1);
              assert.strictEqual(pack.name, "测试包");
              assert.strictEqual(pack.note, "导入测试");
              assert(pack.exportedAt);
              const parsed = WB.RulePack.parse(JSON.stringify(pack));
              assert.deepStrictEqual(parsed.overrides, packState.overrides);
              assert.deepStrictEqual(parsed.custom, packState.custom);
              assert.throws(() => WB.RulePack.parse("not json"), /JSON/);
              assert.throws(
                () => WB.RulePack.parse(JSON.stringify(Object.assign({}, pack, { app: "other" }))),
                /合同工作台/
              );
              assert.throws(
                () => WB.RulePack.parse(JSON.stringify(Object.assign({}, pack, { version: 2 }))),
                /版本/
              );

              let stored = {
                overrides: {
                  r_lease_penalty: {
                    contractType: "房屋租赁合同", name: "本地覆盖", keywords: ["违约金"],
                    condition: "本地条件", level: "高",
                    basis: "民法典第585条", advice: "本地建议", enabled: true
                  }
                },
                custom: [
                  {
                    id: "r_custom_local", contractType: "通用", name: "本地自定义",
                    keywords: ["本地"], condition: "本地条件", level: "低",
                    basis: "民法典第509条", advice: "本地建议"
                  }
                ],
                updatedAt: 5
              };
              WB.loadRuleState = async () => stored;
              WB.saveRuleState = async (next, expected) => {
                const rev = Number(stored && stored.updatedAt) || 0;
                if (expected != null && rev !== expected) return { ok: false, conflict: true };
                stored = next;
                return { ok: true };
              };
              S.applyState(stored);
              const builtinTotal = WB.RULES.length;

              const res = await S.importPack({
                overrides: {
                  r_lease_penalty: packState.overrides.r_lease_penalty,
                  r_not_builtin: packState.overrides.r_lease_penalty
                },
                custom: [
                  packState.custom[0],
                  Object.assign({}, packState.custom[0], { name: "重复 id 应被忽略" }),
                  {
                    id: "r_custom_bad", contractType: "通用", name: "",
                    keywords: [], condition: "", basis: "", advice: ""
                  }
                ]
              });
              assert.strictEqual(res.ok, true);
              assert.strictEqual(res.overrides, 1, "非内置 id 不应写入覆盖");
              assert.strictEqual(res.custom, 1, "重复/非法自定义规则应被丢弃");
              assert.strictEqual(res.skipped, 0);
              assert.strictEqual(S.find("r_lease_penalty").name, "包内覆盖");
              assert.strictEqual(S.find("r_lease_penalty").enabled, false);
              assert(S.find("r_custom_pack_a"), "应导入自定义规则");
              assert(S.find("r_custom_local"), "本机原有自定义规则应保留");
              assert.strictEqual(WB.RULES.length, builtinTotal + 1);
              assert.strictEqual(S.state().custom.length, 2);
              assert.strictEqual(stored.custom.length, 2);
              assert(stored.updatedAt > 5);

              const exported = S.exportPack("当前规则");
              assert.strictEqual(exported.name, "当前规则");
              assert.strictEqual(Object.keys(exported.overrides).length, 1);
              assert.strictEqual(exported.custom.length, 2);

              // 存储失败：导入必须整笔回滚
              const beforeName = S.find("r_lease_penalty").name;
              const beforeCustom = S.state().custom.length;
              WB.saveRuleState = async () => ({ ok: false });
              const failed = await S.importPack({
                overrides: {
                  r_lease_penalty: Object.assign({}, packState.overrides.r_lease_penalty, { name: "不应生效" })
                },
                custom: []
              });
              assert.strictEqual(failed.ok, false);
              assert.strictEqual(failed.reason, "storage");
              assert.strictEqual(S.find("r_lease_penalty").name, beforeName);
              assert.strictEqual(S.state().custom.length, beforeCustom);
              console.log("OK");
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
