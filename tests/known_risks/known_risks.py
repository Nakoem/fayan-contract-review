"""
每个样本合同对应的已知风险点定义。
格式：list[dict]，每个dict描述一个风险点。
"""

# ── 房屋租赁合同 ──
LEASE_RISKS = [
    {
        "id": "LEASE-01",
        "clause_location": "第七条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["违约金", "5%", "日", "过高", "LPR", "损失", "30%", "585条"],
        "description": "逾期违约金按日5%计算，年化1825%，远超法定上限",
    },
    {
        "id": "LEASE-02",
        "clause_location": "第二条",
        "category": "期限条款",
        "risk_level": "🟡中风险",
        "keywords": ["续租", "优先承租", "优先购买", "未约定"],
        "description": "未约定优先承租权和优先购买权，承租方在续约时缺少法律保障",
    },
    {
        "id": "LEASE-03",
        "clause_location": "第五条",
        "category": "费用承担",
        "risk_level": "🟡中风险",
        "keywords": ["费用", "分摊", "物业费", "水电", "网络费"],
        "description": "费用分摊仅列水电网络/物业/取暖，未涉及其他可能的费用（如空调加时费等）",
    },
]

# ── 劳动合同 ──
EMPLOYMENT_RISKS = [
    {
        "id": "EMP-01",
        "clause_location": "第二条",
        "category": "权利义务",
        "risk_level": "🔴高风险",
        "keywords": ["调岗", "调薪", "单方", "35条", "协商"],
        "description": "甲方单方调岗调薪权，未要求协商一致，违反劳动合同法第35条",
    },
    {
        "id": "EMP-02",
        "clause_location": "第三条",
        "category": "劳动报酬",
        "risk_level": "🔴高风险",
        "keywords": ["加班费", "1倍", "100%", "150%", "44条"],
        "description": "加班费按基本工资1倍计算，低于法定的延时150%/休息日200%/节假日300%",
    },
    {
        "id": "EMP-03",
        "clause_location": "第三条",
        "category": "工作时间",
        "risk_level": "🔴高风险",
        "keywords": ["周六", "固定加班", "36", "每月"],
        "description": "周六固定加班日可能导致月加班超过36小时法定上限",
    },
    {
        "id": "EMP-04",
        "clause_location": "第五条",
        "category": "社会保险",
        "risk_level": "🔴高风险",
        "keywords": ["放弃", "公积金", "无效", "司法解释", "绝对无效"],
        "description": "自愿放弃住房公积金条款违反强制性规定，绝对无效",
    },
    {
        "id": "EMP-05",
        "clause_location": "第六条",
        "category": "竞业限制",
        "risk_level": "🔴高风险",
        "keywords": ["竞业限制", "5年", "2年", "24条", "补偿"],
        "description": "竞业限制期限5年超法定2年上限，且未约定经济补偿，违反24条",
    },
    {
        "id": "EMP-06",
        "clause_location": "第六条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["违约金", "50万", "25条", "竞业", "保密"],
        "description": "保密违约金50万可能过高，且劳动合同法第25条严格限制违约金适用",
    },
    {
        "id": "EMP-07",
        "clause_location": "第七条",
        "category": "合同解除",
        "risk_level": "🔴高风险",
        "keywords": ["辞职", "90日", "30日", "37条"],
        "description": "辞职通知期90日远超法定的30日，违反劳动合同法第37条",
    },
    {
        "id": "EMP-08",
        "clause_location": "第七条",
        "category": "合同解除",
        "risk_level": "🔴高风险",
        "keywords": ["不得", "解除", "赔偿", "10万", "培训费", "25条"],
        "description": "合同期内禁止解除+赔偿10万元，严重限制劳动者解除权",
    },
    {
        "id": "EMP-09",
        "clause_location": "第一条",
        "category": "试用期",
        "risk_level": "🟡中风险",
        "keywords": ["试用期", "录用条件", "考核", "标准", "未约定"],
        "description": "试用期6个月虽在法定上限内，但未约定录用条件和考核标准",
    },
    {
        "id": "EMP-10",
        "clause_location": "第八条",
        "category": "争议解决",
        "risk_level": "🟡中风险",
        "keywords": ["管辖", "甲方所在地", "劳动者", "选择权", "劳动争议"],
        "description": "争议管辖限定在甲方所在地，排除劳动者在劳动合同履行地的选择权",
    },
]

# ── 买卖合同 ──
SALES_RISKS = [
    {
        "id": "SALES-01",
        "clause_location": "第三条",
        "category": "金额条款",
        "risk_level": "🔴高风险",
        "keywords": ["定金", "50%", "20%", "586条", "超出"],
        "description": "定金为合同总额50%远超20%法定上限，超出部分不产生定金效力",
    },
    {
        "id": "SALES-02",
        "clause_location": "第一条",
        "category": "权利义务",
        "risk_level": "🔴高风险",
        "keywords": ["微调", "配置", "单方", "变更", "496条", "格式条款"],
        "description": "卖方单方微调配置权属于无效格式条款，违反民法典第496条",
    },
    {
        "id": "SALES-03",
        "clause_location": "第三条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["违约金", "2%", "日", "LPR", "四倍", "过高", "585条"],
        "description": "逾期付款违约金日2%折合年化730%，远超LPR四倍，违反民法典585条",
    },
    {
        "id": "SALES-04",
        "clause_location": "第四条",
        "category": "验收条款",
        "risk_level": "🔴高风险",
        "keywords": ["验收", "3日", "过短", "621条", "合理", "服务器"],
        "description": "3日验收期对AI服务器（复杂设备）明显过短，违反民法典第621条",
    },
    {
        "id": "SALES-05",
        "clause_location": "第四条",
        "category": "验收条款",
        "risk_level": "🔴高风险",
        "keywords": ["验收后", "质量", "不承担", "617条", "产品质量法", "40条"],
        "description": "验收后免除卖方全部质量责任，违反民法典617条和产品质量法40条",
    },
    {
        "id": "SALES-06",
        "clause_location": "第五条",
        "category": "权利义务",
        "risk_level": "🔴高风险",
        "keywords": ["运输", "风险", "买方", "604条", "交付"],
        "description": "运输风险全归买方，与民法典604条交付转移原则冲突",
    },
    {
        "id": "SALES-07",
        "clause_location": "第六条",
        "category": "售后保修",
        "risk_level": "🟡中风险",
        "keywords": ["保修", "6个月", "发货", "验收", "起算"],
        "description": "保修期仅6个月且从发货日起算，实际质保时间不足",
    },
    {
        "id": "SALES-08",
        "clause_location": "第六条",
        "category": "售后保修",
        "risk_level": "🟡中风险",
        "keywords": ["换配件", "现场", "维修", "不提供"],
        "description": "保修仅更换配件不提供现场维修，对服务器设备保障不足",
    },
    {
        "id": "SALES-09",
        "clause_location": "第六条",
        "category": "权利义务",
        "risk_level": "🔴高风险",
        "keywords": ["保留", "调整", "保修政策", "随时", "单方", "496条"],
        "description": "卖方单方保留调整保修政策权，属无效格式条款",
    },
    {
        "id": "SALES-10",
        "clause_location": "第七条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["违约金", "3倍", "合同", "过高", "知识产权"],
        "description": "知识产权违约金为合同总价3倍，违约金畸高",
    },
    {
        "id": "SALES-11",
        "clause_location": "第八条",
        "category": "不可抗力",
        "risk_level": "🔴高风险",
        "keywords": ["不可抗力", "供应链", "涨价", "漏洞", "扩大化", "180条"],
        "description": "将商业风险加入不可抗力条款，违反民法典180条三要件",
    },
    {
        "id": "SALES-12",
        "clause_location": "第十条",
        "category": "权利义务",
        "risk_level": "🔴高风险",
        "keywords": ["3日", "未异议", "视为", "接受", "沉默", "140条"],
        "description": "3日未异议视为接受单方文件，违反民法典140条沉默规则",
    },
]

# ── 服务合同 ──
SERVICE_RISKS = [
    {
        "id": "SVC-01",
        "clause_location": "第二条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["违约金", "千分之五", "逾期", "过高", "LPR"],
        "description": "逾期付款违约金日千分之五(年化182.5%)远超LPR四倍",
    },
    {
        "id": "SVC-02",
        "clause_location": "第三条",
        "category": "保密条款",
        "risk_level": "🟡中风险",
        "keywords": ["永久", "保密", "期限", "过度", "限制"],
        "description": "永久保密义务可能被认定为过度限制，需评估合理性",
    },
    {
        "id": "SVC-03",
        "clause_location": "第四条",
        "category": "验收条款",
        "risk_level": "🟡中风险",
        "keywords": ["验收", "逾期", "视为", "通过", "试运行"],
        "description": "逾期未出具验收报告视为通过，对委托方不利",
    },
    {
        "id": "SVC-04",
        "clause_location": "第五条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["全部", "经济损失", "无限", "赔偿", "责任"],
        "description": "赔偿全部经济损失为无限责任条款，未设赔偿上限",
    },
    {
        "id": "SVC-05",
        "clause_location": "第三条",
        "category": "知识产权",
        "risk_level": "🟡中风险",
        "keywords": ["知识产权", "共同所有", "行使", "收益", "分配"],
        "description": "知识产权共同所有但未约定行使规则和收益分配方式",
    },
]

# ── 合作协议 ──
COOPERATION_RISKS = [
    {
        "id": "COOP-01",
        "clause_location": "第二条",
        "category": "权利义务",
        "risk_level": "🔴高风险",
        "keywords": ["单方面", "分配", "比例", "调整", "核定", "972条"],
        "description": "一方可单方核定分配比例，违反民法典972条合伙事务协商一致原则",
    },
    {
        "id": "COOP-02",
        "clause_location": "第三条",
        "category": "知识产权",
        "risk_level": "🔴高风险",
        "keywords": ["知识产权", "全部", "归甲方", "无对价", "显失公平"],
        "description": "合作成果知识产权全归甲方独占且无合理对价",
    },
    {
        "id": "COOP-03",
        "clause_location": "第四条",
        "category": "退出机制",
        "risk_level": "🔴高风险",
        "keywords": ["退出", "资产", "不予退还", "充公", "显失公平"],
        "description": "退出方投入资产不予退还、不折价补偿，属资产无偿充公条款",
    },
    {
        "id": "COOP-04",
        "clause_location": "第五条",
        "category": "竞业限制",
        "risk_level": "🔴高风险",
        "keywords": ["竞业", "3年", "范围", "过宽", "经营自由"],
        "description": "竞业限制3年+范围过宽（全部智慧社区），可能被认定过度限制经营自由",
    },
    {
        "id": "COOP-05",
        "clause_location": "第一条",
        "category": "期限条款",
        "risk_level": "🟡中风险",
        "keywords": ["自动", "续约", "3年", "退出", "未约定"],
        "description": "自动续约3年未设退出机制，合作方可能被长期锁定",
    },
    {
        "id": "COOP-06",
        "clause_location": "第二条",
        "category": "权利义务",
        "risk_level": "🟡中风险",
        "keywords": ["出资", "估值", "量化", "人力", "设备"],
        "description": "出资方式未量化估值（人员15名、设备200万），未来分成争议风险高",
    },
]

# ── 借款合同 ──
LOAN_RISKS = [
    {
        "id": "LOAN-01",
        "clause_location": "第二条",
        "category": "利率条款",
        "risk_level": "🟡中风险",
        "keywords": ["年利率", "12%", "LPR", "四倍", "踩线"],
        "description": "年利率12%刚好等于当前LPR四倍上限，建议留有余地",
    },
    {
        "id": "LOAN-02",
        "clause_location": "第三条",
        "category": "违约责任",
        "risk_level": "🔴高风险",
        "keywords": ["逾期", "日万分之五", "18.25%", "LPR", "四倍", "29条"],
        "description": "逾期利率日万分之五(年化18.25%)超过LPR四倍上限12%",
    },
    {
        "id": "LOAN-03",
        "clause_location": "缺失",
        "category": "担保条款",
        "risk_level": "🟡中风险",
        "keywords": ["担保", "保证", "抵押", "缺失", "686条"],
        "description": "借款合同未设任何担保，出借方债权保障不足",
    },
]

# 文件到合同类型和风险列表的映射
RISK_MAP = {
    "sample_lease.txt": ("房屋租赁合同", LEASE_RISKS),
    "sample_employment.txt": ("劳动合同", EMPLOYMENT_RISKS),
    "sample_sales.txt": ("买卖合同", SALES_RISKS),
    "sample_service.txt": ("服务合同", SERVICE_RISKS),
    "sample_cooperation.txt": ("合作协议", COOPERATION_RISKS),
    "sample_loan.txt": ("借款合同", LOAN_RISKS),
}
