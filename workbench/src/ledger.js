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
  };
})(globalThis);
