# 合同工作台（个人版）· MVP

> 法眼企业版的 C 端产品线：同一套审查内核，另一种包装。
> 给没有法务部的人，一个「一个人的法务部」。

---

## 快速开始

1. 双击 `dist/index.html`（Chrome / Edge，1280px 以上）
2. 右上角「设置」→ 选服务商 → 填 API Key → 保存
3. 粘贴合同，或上传 PDF / Word，或点一份示例合同 → 「开始审查」
4. 审完可点「加入台账」，在「合同台账」里记到期日与付款节点；案头会显示 30 天内待办

首次使用必须配置自己的模型 Key。合同原文只会发送给你选择的模型服务商；其余数据留在本机浏览器。

### 服务商

| 服务商 | 默认模型 | 浏览器直连 |
|---|---|---|
| DashScope（通义） | `qwen3.8-max-0902` | ✅ |
| DeepSeek | `deepseek-flash` | ✅ |

模型名可编辑；Key 分服务商保存在 IndexedDB。

### 文件解析

- 支持文字层 PDF、DOCX、TXT / MD；旧版 `.doc` 会提示另存为 `.docx`
- 文件只在本机浏览器解析，不上传；点「开始审查」时才把提取出的文字发给所选模型
- 扫描版 PDF（没有文字层）V1 不做 OCR，会提示粘贴文字或换 DOCX
- 上限：单文件 25MB、PDF 300 页、提取文字 20 万字；送审仍受 5 万字限制
- 解析器版本与许可证见 `vendor/README.md`

### 合同台账

- 审查结果页「加入台账」自动带入合同名称与类型；也可在台账页手动新增
- 字段：名称 / 类型 / 状态 / 对方 / 金额 / 起止日期 / 下次付款日 / 付款金额 / 备注
- 案头「待办 · 30 天内」汇总到期与付款节点，逾期会标红；「我的合同」按风险色条列出全部台账条目
- 台账页按状态胶囊、类型下拉、关键词筛选；关键词与案头 / 侧栏搜索共用，类型与状态筛选独立叠加；表格显示合同名 / 对方 / 金额 / 到期日 / 状态，点行直接编辑
- 右侧「关键日期」按时间轴列出到期与付款节点；导出 CSV，按条或全部导出 `.ics` 到手机日历
- 全部存在本机 IndexedDB；CSV 公式注入已做文本化处理

---

## 开发

### 构建

```bash
python workbench/build.py
```

- 读取仓库根目录 `sample_*.txt` 和 `knowledge/*.json`
- 生成 `src/data/samples.js` / `src/data/knowledge.js`（自动生成，勿手改）
- 把 CSS / JS 全部内联成 `dist/index.html`
- 构建后自动检查体积、外链和必备内容

### 测试

```bash
# 规则 schema + 构建产物
.venv/Scripts/python.exe -m pytest workbench/tests -v

# UI 冒烟（真 Chrome + mock LLM，含台账 / 提醒 / ICS / CSV）
node workbench/scripts/ui_smoke.mjs

# 文件解析验收（中文 PDF / 英文 PDF / DOCX / .doc 拒绝）
node workbench/scripts/parser_check.mjs

# 单份示例真调模型（量耗时与 JSON 稳定性）
node workbench/scripts/spike.mjs --sample=lease --provider=dashscope

# 3000 字长合同压测（长合同会自动跳过 LLM 复核保 90 秒）
node workbench/scripts/spike.mjs --file=workbench/tests/fixtures/lease_3000.txt --type=房屋租赁合同 --gate

# 断网 / 关浏览器重开
node workbench/scripts/offline_check.mjs
node workbench/scripts/restart_check.mjs

# PRD 验收（真调模型，检查 90 秒 / ≥5 条风险 / 持久化）
node workbench/scripts/acceptance.mjs --provider=dashscope

# 端到端：上传中文 PDF → 解析 → 真调模型 → 报告
node workbench/scripts/acceptance.mjs --file=workbench/tests/fixtures/lease_sample.pdf
```

真调脚本从仓库根目录 `.env` 读取 `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY`。

---

## 目录

```
workbench/
├─ src/
│  ├─ index.html      页面骨架
│  ├─ styles.css      屏幕玻璃风（含报告）+ 打印纸感
│  ├─ data/
│  │  ├─ rules.js     111 条审查规则（手写源）
│  │  ├─ samples.js   6 份示例合同（自动生成）
│  │  └─ knowledge.js 法规库（自动生成）
│  ├─ prompts.js      提示词构建
│  ├─ llm.js          服务商预设 + 调用 + JSON 修复
│  ├─ pipeline.js     5 步流水线 + 本地评分 + 报告渲染
│  ├─ file_parser.js  PDF / DOCX / TXT 本地解析
│  ├─ storage.js      IndexedDB（失败回退 localStorage）
│  ├─ ledger.js       台账日期 / 提醒 / ICS / CSV 纯函数
│  └─ app.js          UI 逻辑
├─ vendor/            pdf.js / mammoth（含 LICENSE）
├─ build.py           零依赖构建脚本
├─ scripts/           冒烟 / 真调 / 解析 / 验收脚本
├─ tests/             pytest + 解析夹具
└─ dist/index.html    交付物
```

---

## 关键设计

- **规则数据化**：规则存在 `RULES` 数组里，提示词由代码拼装；规则编辑器只读写这份数组，不改审查链路。
- **5 步流水线**：抽取（LLM）→ 法条（本地 BM25）→ 评估（LLM）→ 复核（本地 + 轻量 LLM）→ 报告（本地模板）。
- **报告不交给 LLM 排版**：LLM 只吐结构化 JSON，六段式报告由本地模板渲染，格式稳定。
- **评级确定性**：任一维度 ≥4 → 高；任一 =3 → 中；均 ≤2 → 低。
- **综合评分**：`min(100, 高×15 + 中×6 + 低×1)`。
- **脱敏**：身份证 / 手机号 / 银行卡 / 邮箱正则 + 用户自填名称列表；默认开启。
- **单文件交付**：零外链、零 CDN、零外部字体；`file://` 下 IndexedDB / 剪贴板 / PDF / DOCX 解析实测可用。
- **解析器内联**：PDF.js 与 Mammoth 以 base64 / 源码形式打进单文件，运行时零网络请求；当前交付物体积约 3.1MB。
- **单槽恢复 + 最近审查**：当前结果存 IndexedDB，刷新不丢；每次审查另存一条历史，案头支持搜索、打开、删除、清空。
- **历史预览脱敏**：首页摘要中的证件 / 手机 / 银行卡 / 邮箱固定显示占位符，完整原文只留本机。
- **台账与提醒**：审查结果可一键入台账；到期 / 付款节点在本机计算，案头汇总 30 天内待办，支持 `.ics` 日历与 CSV 导出。
- **高风险定位**：点风险清单里的高风险条目，原文对应条款出现旋转光束描边（参考问数精灵登录按钮的 BorderBeam，沿用 ocean 蓝紫配色；长条款上转速放缓到 3.1s）；中/低风险仍用闪烁定位。
- **设计稿外壳**：按 ardot P1 复刻 236px 侧栏、Brand Mark 图标、案头三卡与「最近审查 / 我的合同」双入口；整体沿用原天空玻璃配色。侧栏搜索是全局搜索，同时查审查记录与台账条目，台账结果可直接打开编辑；侧栏、最近审查、我的合同、台账页四个搜索框共用关键词并实时同步。合同台账按 P3 改成表格 + 关键日期时间轴；审查台 / 条款库的版式、配色与按钮保持原样。
- **审查规则可编辑（V1.5）**：侧栏新增「审查规则」页。111 条内置规则可修改、可停用，但不能删除；自定义规则可新增 / 编辑 / 删除。关键词、判定条件、风险等级、法条依据、建议话术都能改，改完立即参与下一次审查；规则状态存本机 IndexedDB，刷新不丢。写入带版本校验，多标签页不会互相静默覆盖；审查中途改规则也只影响下一次审查。条款库同步显示「已停用 / 自定义」标记。
- **法条依据核对（2026-11-24）**：111 条内置规则的法条依据按中国政府网、最高人民法院、人力资源和社会保障部等官方渠道现行文本逐条复核，修正 6 处条文号：房屋租赁专属管辖改为民事诉讼法第 34 条、协议管辖改为第 35 条、放弃社保改为劳动争议司法解释（二）第 19 条、委托作品著作权改为著作权法第 19 条、预付式「概不退款」改为预付式消费司法解释第 9 条、停业逃退款改为第 7 条与第 23 条。规则页展示核对日期与 20 部法规 / 司法解释版本；规则是离线预筛，法规修订后需重新核对。
- **P0 + P1 扩容（2026-11-24）**：新增 45 条规则，覆盖消保法及实施条例、公司法、合伙企业法、专利法、商标法、反不正当竞争法、仲裁法（2025 修订）等此前空白；6 类合同规则数变为租赁 18、劳动 20、买卖 15、服务 17、合作 16、借款 14，通用 11。

---

## 已知限制（MVP）

- 不做 OCR：扫描版 PDF 请先转文字或换 DOCX
- 不做文书、多案件、完整企业台账；台账只做单合同单到期日 + 单个下次付款节点，不做循环提醒 / 自动续签 / 多人同步
- 台账金额与日期需手动填写（从审查结果加入时只带入名称 / 类型），不做合同信息自动抽取
- 历史只做单机「最近审查」，不是完整合同台账
- 浏览器直连仅支持 DashScope / DeepSeek；Ollama 预设不在 MVP
- 单次输入上限 5 万字（3 万字起提示）
- 单文件构建产物上限 4MB；当前约 3.1MB
- AI 输出仅供参考，不构成法律意见；正式签署前请由执业律师复核

---

关联文档：

- `PRD-合同工作台个人版.md`
- `docs/superpowers/specs/2026-11-19-contract-workbench-mvp-design.md`
