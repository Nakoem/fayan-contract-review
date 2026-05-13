"""临时脚本：替换 app.py 中的审查执行块。用完即删。"""

import re

with open("app.py", encoding="utf-8") as f:
    content = f.read()

# 匹配整个 else 块（从 "else:" 到下一个顶级代码 "with col_right:"）
# 使用正则匹配 else: 后面的整个缩进块
pattern = r"(            else:\n)(?:(?:            .*\n)|(?:                .*\n))+"
m = re.search(pattern, content)

if not m:
    print("未找到匹配的 else 块")
    exit(1)

old_block = m.group(0)
print(f"找到旧块: {len(old_block)} 字符, 从位置 {m.start()}")

new_block = """            else:
                # 新审查前保存旧报告到历史
                if st.session_state.report:
                    st.session_state.report_history = save_to_history(
                        st.session_state.report_history,
                        st.session_state.report,
                        st.session_state.log,
                        st.session_state.get("last_contract_type", "未知"),
                        st.session_state.summary,
                    )
                    save_report_file(st.session_state.report, st.session_state.get("last_contract_type", "未知"))

                st.session_state["last_contract_type"] = contract_type
                st.session_state.last_contract_type = contract_type

                progress_bar = st.progress(0, "准备审查...")
                live_display = st.empty()

                runner = ReviewRunner(api_key=api_key)
                runner.start(contract_text, contract_type)

                while not runner.done:
                    pct, label = runner.get_progress()
                    progress_bar.progress(pct, label)

                    tool_lines = runner.get_tool_log()
                    if tool_lines:
                        html = ('<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                                'color:#5c5240;max-height:360px;overflow-y:auto;padding:8px;'
                                'background:rgba(250,248,245,0.7);border-left:3px solid #c9a96e;'
                                'border-radius:0 4px 4px 0;">')
                        for tl in tool_lines:
                            if "轮" in tl:
                                html += f'<div style="border-left-color:#f59e0b;font-weight:600;'
                                        f'padding:4px 0 4px 10px;margin:2px 0;">{tl}</div>'
                            else:
                                html += f'<div style="padding:2px 0 2px 10px;margin:1px 0;">{tl}</div>'
                        html += '</div>'
                        live_display.markdown(html, unsafe_allow_html=True)

                    time.sleep(0.5)

                progress_bar.progress(1.0, "审查完成 ✅")
                time.sleep(0.3)
                progress_bar.empty()
                live_display.empty()

                if runner.error:
                    st.error(f"审查出错：{runner.error}")
                    st.stop()

                st.session_state.report = runner.report
                st.session_state.log = runner.log
                st.session_state.summary = extract_summary(runner.report, runner.log)
                st.rerun()
"""

content = content[: m.start()] + new_block + content[m.end() :]

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("替换完成")
