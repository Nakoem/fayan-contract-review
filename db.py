"""
法眼 · MySQL 数据库模块
用户 + 合同 + 报告 + 风险点 持久化存储
"""

import os
import re

import pymysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "fayan"),
    "password": os.getenv("DB_PASSWORD", "fayan123"),
    "database": os.getenv("DB_NAME", "fayan"),
    "charset": "utf8mb4",
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def ensure_user(username: str = "Nakko") -> int:
    """确保默认用户存在，返回 user_id。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, 'demo')",
                (username,),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def save_review(
    user_id: int,
    file_name: str,
    file_type: str,
    report_text: str,
    high_count: int,
    medium_count: int,
) -> None:
    """保存一次完整审查：合同 + 报告 + 风险点，单个事务。"""
    score = max(0, min(100, 100 - high_count * 15 - medium_count * 5))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 合同
            cur.execute(
                "INSERT INTO contracts (user_id, file_name, file_type, status) VALUES (%s, %s, %s, '已完成')",
                (user_id, file_name, file_type),
            )
            contract_id = cur.lastrowid

            # 报告
            cur.execute(
                "INSERT INTO reports (contract_id, score, summary, full_report) VALUES (%s, %s, '', %s)",
                (contract_id, score, report_text),
            )
            report_id = cur.lastrowid

            # 风险点
            _extract_and_insert_risks(cur, report_id, report_text)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _extract_and_insert_risks(cur, report_id: int, report_text: str):
    """从报告文本提取风险点并写入 risks 表（在已有事务中）。"""
    sections = [
        ("高风险", "高风险条款"),
        ("中风险", "中风险条款"),
        ("低风险", "低风险条款"),
    ]

    for level, section_keyword in sections:
        header_match = re.search(
            rf"[一二三四五六七八九十]+[、.]\s*.*?{section_keyword}",
            report_text,
        )
        if not header_match:
            continue
        start = header_match.end()

        next_section = re.search(
            r"\n(?=[一二三四五六七八九十]+[、．.])",
            report_text[start:],
        )
        section_end = start + next_section.start() if next_section else len(report_text)
        section_text = report_text[start:section_end]

        items = re.split(r"\n(?=\d+\.\s*【)", section_text)[1:]

        for item in items:
            item = item.strip()
            title_match = re.match(r"\d+\.\s*【(.+?)】", item)
            title = title_match.group(1) if title_match else ""

            def _extract(label: str) -> str:
                m = re.search(rf"▸\s*{label}\s*[：:]?\s*(.+?)(?=\n\s*▸|\n\s*$|\Z)", item, re.DOTALL)
                return m.group(1).strip()[:500] if m else ""

            original = _extract("原文")
            risk_desc = _extract("风险说明") or _extract("判断依据")
            suggestion = _extract("修改建议")

            if not original and not risk_desc:
                risk_desc = item[:500]

            cur.execute(
                "INSERT INTO risks (report_id, level, original_text, section, description, suggestion) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (report_id, level, original, title, risk_desc, suggestion),
            )


def get_review_history(user_id: int, limit: int = 20):
    """获取用户的审查历史。"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.file_name, c.file_type, c.status, c.upload_time,
                       r.score, r.full_report AS summary,
                       COUNT(rs.id) AS risk_count,
                       SUM(CASE WHEN rs.level = '高风险' THEN 1 ELSE 0 END) AS high_risk
                FROM contracts c
                JOIN reports r ON c.id = r.contract_id
                LEFT JOIN risks rs ON r.id = rs.report_id
                WHERE c.user_id = %s
                GROUP BY c.id, r.id
                ORDER BY c.upload_time DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return cur.fetchall()
    finally:
        conn.close()
