/* 合同工作台 · 台账纯函数（日期 / 提醒 / ICS / CSV）
 * 不碰 DOM 与存储，方便在 CDP 里单独验收。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const STATUSES = ["待签", "履行中", "已归档", "已终止"];
  const REMIND_DAYS = 30;
  const STATUS_CLS = {
    待签: "pending",
    履行中: "active",
    已归档: "archived",
    已终止: "ended",
  };

  const pad = (n) => String(n).padStart(2, "0");

  function parseDate(value) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
    if (!m) return null;
    const y = Number(m[1]);
    const mo = Number(m[2]) - 1;
    const d = Number(m[3]);
    const date = new Date(y, mo, d, 12, 0, 0, 0);
    if (date.getFullYear() !== y || date.getMonth() !== mo || date.getDate() !== d) return null;
    return date;
  }

  function startOfDay(now) {
    const d = now ? new Date(now.getTime()) : new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }

  /** 返回距今天的天数：负数=已过期，0=今天。日期非法返回 null。 */
  function daysUntil(value, now) {
    const date = parseDate(value);
    if (!date) return null;
    date.setHours(0, 0, 0, 0);
    return Math.round((date.getTime() - startOfDay(now).getTime()) / 86400000);
  }

  function formatDate(value, short) {
    const d = parseDate(value);
    if (!d) return "";
    const y = d.getFullYear();
    const m = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    return short ? `${m}/${day}` : `${y}/${m}/${day}`;
  }

  function countdown(kind, days) {
    if (days == null) return "";
    const verb = kind === "付款" ? "付款" : "到期";
    if (days < 0) return `已逾期 ${-days} 天`;
    if (days === 0) return `今天${verb}`;
    if (days === 1) return `明天${verb}`;
    return `${days} 天后${verb}`;
  }

  function countdownShort(days) {
    if (days == null) return "";
    if (days < 0) return `已逾期 ${-days} 天`;
    if (days === 0) return "今天";
    if (days === 1) return "明天";
    return `${days} 天后`;
  }

  function statusClass(status) {
    return STATUS_CLS[status] || STATUS_CLS["履行中"];
  }

  /** 汇总未来 N 天内（含已逾期）的到期与付款节点。 */
  function reminders(entries, now, withinDays) {
    const limit = withinDays == null ? REMIND_DAYS : withinDays;
    const out = [];
    (entries || []).forEach((entry) => {
      if (!entry || entry.status === "已归档" || entry.status === "已终止") return;
      const due = daysUntil(entry.endDate, now);
      if (due != null && due <= limit) {
        out.push({ entry, kind: "到期", date: entry.endDate, days: due, amount: "" });
      }
      const pay = daysUntil(entry.paymentDate, now);
      if (pay != null && pay <= limit) {
        out.push({ entry, kind: "付款", date: entry.paymentDate, days: pay, amount: entry.paymentAmount || "" });
      }
    });
    return out.sort(
      (a, b) =>
        a.days - b.days ||
        String(a.date).localeCompare(String(b.date)) ||
        a.kind.localeCompare(b.kind, "zh")
    );
  }

  function createId() {
    return "ct_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 6);
  }

  function icsEscape(value) {
    return String(value == null ? "" : value)
      .replace(/\\/g, "\\\\")
      .replace(/\r?\n/g, "\\n")
      .replace(/;/g, "\\;")
      .replace(/,/g, "\\,");
  }

  function icsDate(value) {
    const d = parseDate(value);
    if (!d) return "";
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
  }

  function icsNextDay(value) {
    const d = parseDate(value);
    if (!d) return "";
    d.setDate(d.getDate() + 1);
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
  }

  function utcStamp(now) {
    const d = now || new Date();
    return (
      `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
      `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`
    );
  }

  function entryDescription(entry, kind, date) {
    const parts = [`节点：${kind} ${formatDate(date)}`, `类型：${entry.contractType || "未分类"}`];
    if (entry.counterparty) parts.push(`对方：${entry.counterparty}`);
    if (entry.amount) parts.push(`合同金额：${entry.amount}`);
    if (kind === "付款" && entry.paymentAmount) parts.push(`本次付款：${entry.paymentAmount}`);
    if (entry.note) parts.push(`备注：${entry.note}`);
    return parts.join("\n");
  }

  function eventFor(entry, kind, date, alarmDays) {
    if (!parseDate(date)) return "";
    const suffix = kind === "付款" ? "pay" : "due";
    const uidSeed = String(entry.id || "contract").replace(/[^A-Za-z0-9_-]/g, "");
    const summary =
      kind === "付款"
        ? `付款节点：${entry.title || "未命名合同"}${entry.paymentAmount ? " · " + entry.paymentAmount : ""}`
        : `合同到期：${entry.title || "未命名合同"}`;
    const lines = [
      "BEGIN:VEVENT",
      `UID:${uidSeed}-${suffix}@contract-workbench.local`,
      `DTSTAMP:${utcStamp()}`,
      `DTSTART;VALUE=DATE:${icsDate(date)}`,
      `DTEND;VALUE=DATE:${icsNextDay(date)}`,
      `SUMMARY:${icsEscape(summary)}`,
      `DESCRIPTION:${icsEscape(entryDescription(entry, kind, date))}`,
    ];
    if (alarmDays != null) {
      lines.push(
        "BEGIN:VALARM",
        `TRIGGER:-P${alarmDays}D`,
        "ACTION:DISPLAY",
        `DESCRIPTION:${icsEscape(summary)}`,
        "END:VALARM"
      );
    }
    lines.push("END:VEVENT");
    return lines.join("\r\n");
  }

  /** 接受单条或数组；没有可导出的日期时返回空字符串。 */
  function buildICS(input) {
    const entries = Array.isArray(input) ? input : [input];
    const events = [];
    entries.forEach((entry) => {
      if (!entry) return;
      if (entry.endDate) {
        const ev = eventFor(entry, "到期", entry.endDate, 7);
        if (ev) events.push(ev);
      }
      if (entry.paymentDate) {
        const ev = eventFor(entry, "付款", entry.paymentDate, 1);
        if (ev) events.push(ev);
      }
    });
    if (!events.length) return "";
    return [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Contract Workbench//CN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      ...events,
      "END:VCALENDAR",
      "",
    ].join("\r\n");
  }

  const CSV_HEADERS = [
    "合同名称",
    "合同类型",
    "对方",
    "合同金额",
    "开始日期",
    "到期日期",
    "状态",
    "下次付款日",
    "付款金额",
    "备注",
  ];

  function csvCell(value) {
    let s = String(value == null ? "" : value);
    // 防 Excel 公式注入：= + - @ 开头（允许前导空白）的单元格按文本处理。
    if (/^\s*[=+\-@]/.test(s)) s = "'" + s;
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  function buildCSV(entries) {
    const rows = [CSV_HEADERS.join(",")];
    (entries || []).forEach((entry) => {
      if (!entry) return;
      rows.push(
        [
          entry.title,
          entry.contractType,
          entry.counterparty,
          entry.amount,
          entry.startDate,
          entry.endDate,
          entry.status,
          entry.paymentDate,
          entry.paymentAmount,
          entry.note,
        ]
          .map(csvCell)
          .join(",")
      );
    });
    return rows.join("\r\n") + "\r\n";
  }

  // ── 加入台账时的合同信息自动识别 ──
  // 全部在本地做，不额外调用模型；识别不到的字段留空，保存前可改。
  const PARTY_ROLE_MAP = {
    "出租方": "landlord",
    "出租人": "landlord",
    "房东": "landlord",
    "承租方": "tenant",
    "承租人": "tenant",
    "租客": "tenant",
    "租户": "tenant",
    "用人单位": "employer",
    "用工方": "employer",
    "用工单位": "employer",
    "聘用方": "employer",
    "劳动者": "employee",
    "员工": "employee",
    "职工": "employee",
    "受聘人": "employee",
    "卖方": "seller",
    "出卖人": "seller",
    "供货方": "seller",
    "供货商": "seller",
    "供方": "seller",
    "供应方": "seller",
    "供应商": "seller",
    "买方": "buyer",
    "买受人": "buyer",
    "采购方": "buyer",
    "采购人": "buyer",
    "需方": "buyer",
    "需求方": "buyer",
    "订购方": "buyer",
    "客户": "buyer",
    "委托方": "client",
    "委托人": "client",
    "委托单位": "client",
    "发包方": "client",
    "服务方": "provider",
    "受托方": "provider",
    "服务商": "provider",
    "服务提供方": "provider",
    "承包方": "provider",
    "承接方": "provider",
    "出借方": "lender",
    "出借人": "lender",
    "贷款方": "lender",
    "贷款人": "lender",
    "借款方": "borrower",
    "借款人": "borrower",
    "合作方A": "partyA",
    "合作方B": "partyB",
    "A方": "partyA",
    "B方": "partyB",
  };

  const PARTY_DEFAULT_ROLE = {
    "房屋租赁合同": { a: "landlord", b: "tenant" },
    "劳动合同": { a: "employer", b: "employee" },
    "买卖合同": { a: "seller", b: "buyer" },
    "服务合同": { a: "client", b: "provider" },
    "合作协议": { a: "partyA", b: "partyB" },
    "借款合同": { a: "lender", b: "borrower" },
  };

  const OPPOSITE_ROLE = {
    tenant: "landlord",
    landlord: "tenant",
    employee: "employer",
    employer: "employee",
    buyer: "seller",
    seller: "buyer",
    client: "provider",
    provider: "client",
    partyA: "partyB",
    partyB: "partyA",
    borrower: "lender",
    lender: "borrower",
  };

  const DATE_SRC = "\\d{4}\\s*[年./-]\\s*\\d{1,2}\\s*[月./-]\\s*\\d{1,2}\\s*日?";

  function own(obj, key) {
    return Object.prototype.hasOwnProperty.call(obj, key) ? obj[key] : undefined;
  }

  function cleanPartyName(value) {
    let s = String(value || "").split(/\r?\n/)[0].trim();
    s = s.replace(/[（(](?:盖章|签字|签章)[）)]/g, "");
    s = s.replace(/[（(]以下简称[^）)]*[）)]/g, "");
    s = s.replace(/\s+(?:身份证号|身份证|电话|地址|法定代表人|统一社会信用代码|联系人|住所|住址)\s*[:：]?.*$/, "");
    s = s.replace(/\s+/g, " ").trim();
    if (!s) return "";
    if (/^(甲方|乙方)[:：]?$/.test(s)) return "";
    if (/(甲方|乙方)\s*[（(]?\s*(?:盖章|签字|签章)/.test(s)) return "";
    if (/^(身份证|电话|地址|法定代表人|统一社会信用代码)/.test(s)) return "";
    return s.slice(0, 80);
  }

  function extractParties(text) {
    const head = String(text || "").slice(0, 5000);
    const out = { a: "", b: "", roleA: "", roleB: "", byRole: {} };
    const labelRe = /(甲方|乙方)\s*(?:[（(]([^）)]{1,20})[）)])?\s*[:：]\s*([^\n]{0,120})/g;
    let m;
    while ((m = labelRe.exec(head))) {
      const side = m[1] === "甲方" ? "a" : "b";
      const roleLabel = String(m[2] || "").replace(/\s+/g, "");
      const role = own(PARTY_ROLE_MAP, roleLabel) || "";
      const name = cleanPartyName(m[3]);
      if (!name) continue;
      if (!out[side]) out[side] = name;
      if (role) {
        if (side === "a" && !out.roleA) out.roleA = role;
        if (side === "b" && !out.roleB) out.roleB = role;
        if (!out.byRole[role]) out.byRole[role] = name;
      }
    }

    const roleRe = new RegExp(`(${Object.keys(PARTY_ROLE_MAP).join("|")})\\s*(?:[（(]([^）)]{1,20})[）)])?\\s*[:：]\\s*([^\\n]{0,120})`, "g");
    while ((m = roleRe.exec(head))) {
      const role = own(PARTY_ROLE_MAP, m[1]);
      const name = cleanPartyName(m[3]);
      if (!role || !name) continue;
      if (!out.byRole[role]) out.byRole[role] = name;
      const paren = String(m[2] || "").replace(/\s+/g, "");
      if (paren === "甲方" && !out.a) out.a = name;
      if (paren === "乙方" && !out.b) out.b = name;
      if (paren === "甲方" && !out.roleA) out.roleA = role;
      if (paren === "乙方" && !out.roleB) out.roleB = role;
    }
    return out;
  }

  function pickCounterparty(parties, stance, contractType) {
    const base = own(PARTY_DEFAULT_ROLE, contractType) || {};
    const roleA = parties.roleA || base.a || "";
    const roleB = parties.roleB || base.b || "";
    const nameA = parties.a || (roleA ? parties.byRole[roleA] : "") || "";
    const nameB = parties.b || (roleB ? parties.byRole[roleB] : "") || "";
    const target = own(OPPOSITE_ROLE, stance);
    if (target) {
      if (parties.byRole[target]) return parties.byRole[target];
      if (roleA === target && nameA) return nameA;
      if (roleB === target && nameB) return nameB;
    }
    const both = [];
    if (nameA) both.push(`甲方 ${nameA}`);
    if (nameB) both.push(`乙方 ${nameB}`);
    return both.join(" / ").slice(0, 80);
  }

  function normalizeDateToken(token) {
    const m = /^(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?$/.exec(String(token || "").trim());
    if (!m) return "";
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const d = Number(m[3]);
    const date = new Date(y, mo - 1, d, 12, 0, 0, 0);
    if (date.getFullYear() !== y || date.getMonth() !== mo - 1 || date.getDate() !== d) return "";
    return `${y}-${pad(mo)}-${pad(d)}`;
  }

  function extractTerm(text) {
    const src = String(text || "");
    const rangeRe = new RegExp(`(${DATE_SRC})\\s*(?:起|开始)?[，,\\s]*(?:至|到|—|–|~|～|-)\\s*(${DATE_SRC})`, "g");
    let best = null;
    let m;
    while ((m = rangeRe.exec(src))) {
      const start = normalizeDateToken(m[1]);
      const end = normalizeDateToken(m[2]);
      if (!start || !end || end < start) continue;
      const context = src.slice(Math.max(0, m.index - 40), m.index);
      let score = 0;
      if (/(合同期限|租赁期|租期|服务期|合作期限|借款期限|履行期限|有效期|合同期)/.test(context)) score += 3;
      if (/(试用期|保修期|质保期|保密期|付款期|通知期)/.test(context)) score -= 3;
      if (!best || score > best.score) best = { start, end, score };
    }
    if (best) return { start: best.start, end: best.end, source: "range" };

    const endRe = new RegExp(`(?:有效期至|截止(?:日期)?|终止日期|到期日)[^。\\n]{0,8}?(${DATE_SRC})`);
    const endMatch = endRe.exec(src);
    if (endMatch) {
      const end = normalizeDateToken(endMatch[1]);
      if (end) return { start: "", end, source: "end" };
    }
    return { start: "", end: "", source: "" };
  }

  function extractSignDate(text) {
    const re = new RegExp(`(?:签订|签署|签约|签字)日期\\s*[:：]?\\s*(${DATE_SRC})`);
    const m = re.exec(String(text || ""));
    return m ? normalizeDateToken(m[1]) : "";
  }

  function daysInMonth(year, monthIndex) {
    return new Date(year, monthIndex + 1, 0).getDate();
  }

  function isoFromDate(date) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function nextMonthlyDay(day, now) {
    const today = now ? new Date(now) : new Date();
    const y = today.getFullYear();
    const m = today.getMonth();
    const todayStart = new Date(y, m, today.getDate(), 0, 0, 0, 0);
    let target = new Date(y, m, Math.min(day, daysInMonth(y, m)), 12, 0, 0, 0);
    if (target < todayStart) {
      const ny = m === 11 ? y + 1 : y;
      const nm = (m + 1) % 12;
      target = new Date(ny, nm, Math.min(day, daysInMonth(ny, nm)), 12, 0, 0, 0);
    }
    return isoFromDate(target);
  }

  function lastWorkday(year, monthIndex) {
    const d = new Date(year, monthIndex + 1, 0, 12, 0, 0, 0);
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() - 1);
    return d;
  }

  function nextLastWorkday(now) {
    const today = now ? new Date(now) : new Date();
    const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 0, 0, 0, 0);
    let d = lastWorkday(today.getFullYear(), today.getMonth());
    if (d < todayStart) d = lastWorkday(today.getFullYear(), today.getMonth() + 1);
    return isoFromDate(d);
  }

  function todayIso(now) {
    const d = now ? new Date(now) : new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function extractPayment(text, now) {
    const src = String(text || "");
    const dayMatch = /每月\s*(\d{1,2})\s*(?:日|号)/.exec(src);
    if (dayMatch) {
      const day = Number(dayMatch[1]);
      if (day >= 1 && day <= 31) return { date: nextMonthlyDay(day, now), schedule: "" };
    }
    if (/每月\s*最后(?:一个)?工作日/.test(src)) {
      return { date: nextLastWorkday(now), schedule: "每月最后一个工作日" };
    }
    const today = todayIso(now);
    const re = new RegExp(`(?:于|在)\\s*(${DATE_SRC})\\s*(?:前|之前)?\\s*(?:支付|付款|缴纳|转账|汇入)`, "g");
    let m;
    let best = "";
    while ((m = re.exec(src))) {
      const d = normalizeDateToken(m[1]);
      if (d && d >= today && (!best || d < best)) best = d;
    }
    return { date: best, schedule: "" };
  }

  function moneyValue(numberText, unit) {
    const n = Number(String(numberText || "").replace(/,/g, ""));
    if (!isFinite(n) || n <= 0) return null;
    return unit === "万元" ? Math.round(n * 10000) : n;
  }

  function moneyFrom(text, re) {
    const m = re.exec(String(text || ""));
    return m ? moneyValue(m[1], m[2]) : null;
  }

  function firstMoney(text, list) {
    for (let i = 0; i < list.length; i++) {
      const value = moneyFrom(text, list[i]);
      if (value != null) return value;
    }
    return null;
  }

  function moneyText(value) {
    return value == null ? "" : String(Math.round(value * 100) / 100);
  }

  function moneyDisplay(value) {
    return value == null ? "" : Number(value).toLocaleString("zh-CN");
  }

  const CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "壹": 1,
    "贰": 2,
    "叁": 3,
    "肆": 4,
    "伍": 5,
    "陆": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
  };
  const CN_UNITS = { "十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000 };
  const CN_NUM = "零〇一二三四五六七八九壹贰叁肆伍陆柒捌玖两十拾百佰千仟万萬亿億";

  function chineseNumber(text) {
    let total = 0;
    let section = 0;
    let num = 0;
    String(text || "").split("").forEach((ch) => {
      const digit = own(CN_DIGITS, ch);
      if (digit != null) {
        num = digit;
        return;
      }
      const unit = own(CN_UNITS, ch);
      if (unit) {
        if (!num) num = 1;
        section += num * unit;
        num = 0;
        return;
      }
      if (ch === "万" || ch === "萬") {
        section = (section + num) * 10000;
        total += section;
        section = 0;
        num = 0;
        return;
      }
      if (ch === "亿" || ch === "億") {
        total = (total + section + num) * 100000000;
        section = 0;
        num = 0;
      }
    });
    return total + section + num;
  }

  const TOTAL_LABEL = "合同总价款|合同总价|合同总金额|合同金额|项目总费用|项目总金额|项目费用|项目款|服务费总额|服务费总计|服务费合计|服务费总价|服务费|费用总额|总费用|总价款|总价|总金额|价款总额|价款|合同价款|合同额|租金总额|工资总额|年薪|货款总额|货款|采购总价|采购总额|成交价|成交金额|报酬总额|总报酬|借款金额|借款本金|借款总额|本金总额|本金|借款";
  const TOTAL_RE = new RegExp(`(?:${TOTAL_LABEL})[^。\\n%；;]{0,24}?(?:人民币|RMB|¥|￥)\\s*(\\d[\\d,]*(?:\\.\\d+)?)\\s*(万元|元)?`);
  const TOTAL_UNIT_RE = new RegExp(`(?:${TOTAL_LABEL})[^。\\n%；;]{0,24}?(\\d[\\d,]*(?:\\.\\d+)?)\\s*(万元|元)`);
  const MONTHLY_LABEL = "月租金|月工资|月薪|每月租金|每月工资|基本工资|固定工资|月服务费|每月费用|租金(?!总额|总价|合计|总计)|工资(?!总额|总价|合计|总计)";
  const MONTHLY_RE = new RegExp(`(?:${MONTHLY_LABEL})[^。\\n%；;]{0,20}?(?:人民币|¥|￥)\\s*(\\d[\\d,]*(?:\\.\\d+)?)\\s*(万元|元)?`);
  const MONTHLY_UNIT_RE = new RegExp(`(?:${MONTHLY_LABEL})[^。\\n%；;]{0,20}?(\\d[\\d,]*(?:\\.\\d+)?)\\s*(万元|元)`);
  const FIRST_TOTAL_RE = /(?:共计|合计)[^。\n%；;]{0,12}?(?:人民币|¥|￥)?\s*(\d[\d,]*(?:\.\d+)?)\s*(万元|元)/;
  const FIRST_LABEL_RE = /(?:首次|首期|第一期|定金|预付款)[^。\n%；;]{0,30}?(?:人民币|¥|￥)\s*(\d[\d,]*(?:\.\d+)?)\s*(万元|元)?/;
  const FIRST_UNIT_RE = /(?:首次|首期|第一期|定金|预付款)[^。\n%；;]{0,30}?(\d[\d,]*(?:\.\d+)?)\s*(万元|元)/;

  const TOTAL_CN_RE = new RegExp(`(?:${TOTAL_LABEL})[^。\\n%；;]{0,24}?(?:人民币|RMB|¥|￥)?\\s*([${CN_NUM}]+)\\s*(?:元|圆)`);
  const MONTHLY_CN_RE = new RegExp(`(?:${MONTHLY_LABEL})[^。\\n%；;]{0,20}?(?:人民币|¥|￥)?\\s*([${CN_NUM}]+)\\s*(?:元|圆)`);
  const FIRST_CN_RE = /(?:共计|合计)[^。\n%；;]{0,12}?(?:人民币|¥|￥)?\s*([零〇一二三四五六七八九壹贰叁肆伍陆柒捌玖两十拾百佰千仟万萬亿億]+)\s*(?:元|圆)/;

  function percentMoney(text) {
    const m = /(?:支付|付款)[^。\n%]{0,16}?(\d+(?:\.\d+)?)%[（(]\s*(\d[\d,]*(?:\.\d+)?)\s*(万元|元)[）)]/.exec(String(text || ""));
    return m ? moneyValue(m[2], m[3]) : null;
  }

  function moneyFromCn(text, re) {
    const m = re.exec(String(text || ""));
    if (!m) return null;
    const n = chineseNumber(m[1]);
    return n > 0 ? n : null;
  }

  function firstCnMoney(text, list) {
    for (let i = 0; i < list.length; i++) {
      const value = moneyFromCn(text, list[i]);
      if (value != null) return value;
    }
    return null;
  }

  function extractMoney(text) {
    let total = firstMoney(text, [TOTAL_RE, TOTAL_UNIT_RE]);
    if (total == null) total = firstCnMoney(text, [TOTAL_CN_RE]);
    let monthly = firstMoney(text, [MONTHLY_RE, MONTHLY_UNIT_RE]);
    if (monthly == null) monthly = firstCnMoney(text, [MONTHLY_CN_RE]);
    let first = firstMoney(text, [FIRST_TOTAL_RE, FIRST_LABEL_RE, FIRST_UNIT_RE]);
    if (first == null) first = firstCnMoney(text, [FIRST_CN_RE]);
    return {
      total,
      monthly,
      first,
      percent: percentMoney(text),
    };
  }

  function extractNote(text, info) {
    const src = String(text || "");
    const parts = [];
    if (info.startFromSign) parts.push("开始日期按签订日期带入");
    const deposit = firstMoney(src, [
      /押金[^。\n，,；;]{0,12}?(?:人民币|¥|￥)\s*(\d[\d,]*(?:\.\d+)?)\s*(万元|元)?/,
      /押金[^。\n，,；;]{0,12}?(\d[\d,]*(?:\.\d+)?)\s*(万元|元)/,
    ]);
    if (deposit != null) parts.push(`押金 ${moneyDisplay(deposit)} 元`);
    const rate = /(?:年利率|年化利率)(?:为|是)?\s*([\d.]+)\s*%/.exec(src);
    if (rate) parts.push(`年利率 ${rate[1]}%`);
    const probation = /试用期(?:为|是)?\s*(\d+)\s*(个月|月|年)/.exec(src);
    if (probation) parts.push(`试用期 ${probation[1]}${probation[2]}`);
    const term = /(?:租赁期|租期|合同期限|合作期限|借款期限|服务期|履行期限|有效期)(?:为|是|共|计|[:：])?\s*(\d{1,3}|[一二三四五六七八九十两]+)\s*(年|个月|月)/.exec(src);
    if (term) parts.push(`期限 ${term[1]}${term[2]}`);
    if (!term) {
      const span = /(?:为期|期限为)\s*(\d+)\s*(个月|年)/.exec(src);
      if (span) parts.push(`期限 ${span[1]}${span[2]}`);
    }
    if (info.schedule) parts.push(info.schedule);
    if (/含税/.test(src)) parts.push("含税");
    const split = /甲方[^。\n]{0,12}?享有\s*(\d+)%[^。\n]{0,20}?乙方[^。\n]{0,12}?享有\s*(\d+)%/.exec(src);
    if (split) parts.push(`分成 ${split[1]}%/${split[2]}%`);
    return parts.join("；").slice(0, 300);
  }

  function extractDraft(text, options) {
    const src = String(text || "");
    const opts = options || {};
    const contractType = opts.contractType || "";
    const stance = opts.stance || "neutral";
    const parties = extractParties(src);
    const money = extractMoney(src);
    const term = extractTerm(src);
    const payment = extractPayment(src, opts.now);
    const signDate = extractSignDate(src);
    let startDate = term.start;
    let startFromSign = false;
    if (!startDate && signDate) {
      startDate = signDate;
      startFromSign = true;
    }
    const amount = money.total != null
      ? String(money.total)
      : money.monthly != null
        ? `${moneyDisplay(money.monthly)}/月`
        : "";
    const paymentAmount = money.monthly != null
      ? String(money.monthly)
      : money.first != null
        ? String(money.first)
        : money.percent != null
          ? String(money.percent)
          : "";
    // 合同已经到期时，不再提示一个到期日之后的付款节点。
    const paymentDate = payment.date && term.end && payment.date > term.end ? "" : payment.date;
    return {
      counterparty: pickCounterparty(parties, stance, contractType),
      amount,
      startDate,
      endDate: term.end,
      paymentDate,
      paymentAmount,
      note: extractNote(src, { startFromSign, schedule: payment.schedule }),
    };
  }

  WB.Ledger = {
    STATUSES,
    REMIND_DAYS,
    parseDate,
    daysUntil,
    formatDate,
    countdown,
    countdownShort,
    statusClass,
    reminders,
    createId,
    buildICS,
    buildCSV,
    extractDraft,
  };
})(globalThis);
