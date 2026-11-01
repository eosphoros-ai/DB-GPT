"""Three original native layouts based on the user's Sive references."""

HEART_NOTE = (
    "UCI Heart Disease / Cleveland，303 条历史研究记录。Janosi、Steinbrunn、"
    "Pfisterer 与 Detrano (1989)，DOI:10.24432/C52P4X，CC BY 4.0。"
    "每行一个去标识样本；目标阳性指原 num>0，比例分母为当前分组样本数。"
    "只描述样本关联，不代表总体患病率或个体诊断；缺失值保留，不推算临床筛查规则。"
)
VOICE_NOTE = (
    "DB-GPT 固定种子合成数据，2022–2026 年历史示意；不是行业预测、"
    "真实产品评测或真实用户规模。每行为月份×场景×交互方式汇总；"
    "延迟按语音交互次数加权，表达评测通过率按通过次数/评测次数计算。"
)

RESEARCH_DATASETS = {
    "heart_cleveland": dict(
        source="sqlite_heart_cleveland",
        table="facts",
        grain="measurement",
        unit="例",
        metric="研究样本量",
        segment="性别",
        facts="SELECT * FROM facts",
        extras=dict(
            age="年龄",
            bp="静息血压",
            max_hr="最大心率",
            cholesterol="胆固醇",
            slope="ST 段斜率",
            exang="运动心绞痛标记",
            diagnosis="目标标签",
        ),
        notes=HEART_NOTE,
    ),
    "voice_lab": dict(
        source="sqlite_voice_lab",
        table="facts",
        grain="measurement",
        unit="次",
        metric="交互会话量",
        segment="业务场景",
        facts="SELECT * FROM facts",
        extras=dict(
            latency_total="语音响应毫秒总数",
            evaluations="表达评测次数",
            passed="评测通过次数",
        ),
        notes=VOICE_NOTE,
    ),
}

RESEARCH_RECIPES = [
    dict(
        id="clinical-insight",
        title="趋势洞察 · 健康研究总览",
        category="研究分析",
        base=None,
        style="clinical_insight",
        dataset="heart_cleveland",
        temporal=False,
        scope_label="样本集",
        reference="https://sive.antv.antgroup.com/eD6aPMgRkPOOX27GpwQJ",
        description=(
            "蓝白双栏研究看板，集中查看样本构成、年龄分布与临床字段关联。"
            "内置 UCI Cleveland 公开历史研究数据。"
        ),
    ),
    dict(
        id="cardio-journal",
        title="数据脉搏 · 健康分析长报告",
        category="研究分析",
        base=None,
        style="cardio_journal",
        dataset="heart_cleveland",
        temporal=False,
        scope_label="样本集",
        reference="https://sive.antv.antgroup.com/oAqbY5dRr5bO920VeE4J",
        description=(
            "蓝黑分章长报告，带侧栏章节导航；从数据全貌、人口学特征，"
            "逐步阅读临床字段与胸痛分组。内置 UCI 公开研究数据。"
        ),
    ),
    dict(
        id="voice-observatory",
        title="AI 语音趋势实验室",
        category="科技",
        base=None,
        style="voice_observatory",
        dataset="voice_lab",
        reference="https://sive.antv.antgroup.com/NADVaGQL9OGp91pYxvm6",
        description="黑底玫红科技看板，结合响应延迟、表达评测、会话增长与交互构成。内置可查询的合成演示数据，可替换业务数据源。",
    ),
]
RESEARCH_IDS = {r["id"] for r in RESEARCH_RECIPES}


def research_composition(template):
    from .catalog_layouts import spec

    def w(key, title, viz="kpi", dims=(), field="value", agg="sum", unit="例", **extra):
        return {**spec(key, title, viz, dims, field, agg, unit, 120), **extra}

    def ratio(
        key, title, numerator="aux", denominator="value", viz="kpi", dims=(), unit="%"
    ):
        return w(
            key,
            title,
            viz,
            dims,
            numerator,
            unit=unit,
            denominator=denominator,
            scale=100 if unit == "%" else 1,
        )

    key = template["id"]
    if key == "clinical-insight":
        items = [
            w("sample", "研究样本量"),
            w("positive", "目标阳性样本", field="aux"),
            w("negative", "目标阴性样本", where="aux=0"),
            ratio("prevalence", "样本阳性比例"),
            w("gender", "人口学特征 · 性别构成", "donut", ("segment",)),
            ratio("ages", "年龄分组 · 样本阳性比例", viz="column", dims=("period",)),
            w(
                "pressure",
                "静息血压 · 按目标标签比较均值",
                "column",
                ("diagnosis",),
                "bp",
                "average",
                "mmHg",
            ),
            w(
                "heart_rate",
                "最大心率 · 按目标标签比较均值",
                "column",
                ("diagnosis",),
                "max_hr",
                "average",
                "bpm",
            ),
            ratio("chest", "胸痛类型 · 样本阳性比例", viz="bar", dims=("category",)),
            ratio("slope", "ST 段斜率 · 样本阳性比例", viz="bar", dims=("slope",)),
            w(
                "ledger",
                "分组样本明细",
                "table",
                ("segment", "period"),
                measures=[
                    ("value", "样本量", "value"),
                    ("positive", "目标阳性数", "aux"),
                ],
            ),
        ]
        boxes = [
            (0, 0, 3, 3),
            (3, 0, 3, 3),
            (6, 0, 3, 3),
            (9, 0, 3, 3),
            (0, 3, 6, 8),
            (6, 3, 6, 8),
            (0, 11, 6, 7),
            (6, 11, 6, 7),
            (0, 18, 6, 8),
            (6, 18, 6, 8),
            (0, 26, 12, 7),
        ]
    elif key == "cardio-journal":
        items = [
            w("sample", "样本容量"),
            ratio("prevalence", "样本阳性比例"),
            w("age", "平均年龄", field="age", agg="average", unit="岁"),
            w("heart_rate", "平均最大心率", field="max_hr", agg="average", unit="bpm"),
            w(
                "foundation",
                "01 / 数据全貌 · 年龄与目标标签",
                "stacked_column",
                ("period", "diagnosis"),
            ),
            w(
                "gender",
                "02 / 人口学特征 · 性别与目标标签",
                "stacked_column",
                ("segment", "diagnosis"),
            ),
            ratio("ages", "年龄分组的样本阳性比例", viz="line", dims=("period",)),
            w(
                "pressure",
                "03 / 临床字段 · 静息血压均值",
                "column",
                ("diagnosis",),
                "bp",
                "average",
                "mmHg",
            ),
            ratio("exercise", "运动心绞痛标记与目标标签", viz="bar", dims=("exang",)),
            w("chest", "04 / 胸痛分组 · 样本构成", "donut", ("category",)),
            ratio(
                "chest_rate",
                "不同胸痛分组的样本阳性比例",
                viz="bar",
                dims=("category",),
            ),
            ratio("slope", "05 / 分组核查 · ST 段斜率", viz="bar", dims=("slope",)),
            w(
                "ledger",
                "样本汇总明细",
                "table",
                ("segment", "period"),
                measures=[
                    ("value", "样本量", "value"),
                    ("positive", "目标阳性数", "aux"),
                ],
            ),
        ]
        boxes = [
            (0, 0, 3, 3),
            (3, 0, 3, 3),
            (6, 0, 3, 3),
            (9, 0, 3, 3),
            (0, 4, 12, 7),
            (0, 12, 6, 8),
            (6, 12, 6, 8),
            (0, 21, 6, 8),
            (6, 21, 6, 8),
            (0, 30, 6, 8),
            (6, 30, 6, 8),
            (0, 39, 5, 8),
            (5, 39, 7, 8),
        ]
    else:
        items = [
            ratio("latency", "平均语音响应", "latency_total", "aux", unit="ms"),
            ratio("expression", "表达评测通过率", "passed", "evaluations"),
            w("sessions", "累计交互会话", unit="次"),
            ratio("voice_share", "语音交互占比"),
            ratio(
                "latency_trend",
                "响应延迟变化",
                "latency_total",
                "aux",
                "line",
                ("period",),
                "ms",
            ),
            ratio("expression_ring", "表达评测表现", "passed", "evaluations", "gauge"),
            w("growth", "月度交互增长", "area", ("period",), unit="次"),
            w("interaction", "交互方式构成", "donut", ("category",), unit="次"),
        ]
        boxes = [
            (0, 0, 3, 4),
            (3, 0, 3, 4),
            (6, 0, 3, 4),
            (9, 0, 3, 4),
            (0, 4, 6, 8),
            (6, 4, 6, 8),
            (0, 12, 6, 8),
            (6, 12, 6, 8),
        ]
    return items, [
        dict(widget_id=item["id"], x=x, y=y, w=width, h=h, max_h=60)
        for item, (x, y, width, h) in zip(items, boxes)
    ]


def configure_research(schema, template, items):
    data = RESEARCH_DATASETS[template["dataset"]]
    voice = template["id"] == "voice-observatory"
    original_source = schema["dashboard"]["data_source_id"] == data["source"]
    context = schema["metric_context"]
    context.update(
        grain="月份×场景×交互方式" if voice else "每行一个研究样本",
        data_freshness="合成历史演示样本" if voice else "UCI Cleveland 历史研究数据",
    )
    if not original_source:
        context.update(
            grain="按所选数据源字段和当前筛选聚合",
            data_freshness="查询时读取所选数据源",
            source_notes=["已切换至所选数据源，数值按匹配后的字段计算。"],
        )
    presentation = schema["metadata"]["compatibility"]["catalog_presentation"]
    presentation.update(
        reference_source=data["source"],
        source_kind="synthetic" if voice else "public",
        source_label="合成演示 · 非行业预测"
        if voice
        else "UCI · Cleveland 历史研究样本",
    )
    if template["id"] == "cardio-journal":
        presentation["chapters"] = [
            dict(id=i, label=label)
            for i, label in [
                ("sample", "报告总览"),
                ("foundation", "数据全貌"),
                ("gender", "人口学特征"),
                ("pressure", "临床字段"),
                ("chest", "胸痛分组"),
                ("slope", "分组核查"),
            ]
        ]
    definitions = {item["id"]: item for item in items}
    dimensions = {
        "event_date",
        "year",
        "segment",
        "period",
        "entity",
        "category",
        "slope",
        "exang",
        "diagnosis",
    }
    for widget in schema["widgets"]:
        item = definitions[widget["id"]]
        widget["style"] = dict(
            showLegend=len(item["dims"]) > 1 or item["visualization"] == "donut",
            animate=False,
        )
        widget["description"] = (
            "历史合成样本 · 随年份和场景筛选"
            if voice
            else "目标阳性指源字段 num>0 · 当前分组样本统计"
        )
        if item.get("denominator"):
            widget["presentation"]["precision"] = 1
            if item["visualization"] == "gauge":
                widget["style"].update(
                    target=100, target_label="百分比刻度", progress_label="评测通过比例"
                )
        if item.get("measures"):
            widget["presentation"]["unit"] = "例"
        labels = dict(
            segment=template["segment"],
            category="交互方式" if voice else "胸痛分组",
            period="月份" if voice else "年龄组",
            diagnosis="目标标签",
            slope="ST 段斜率",
            exang="运动心绞痛标记",
            value=item["title"],
            positive="目标阳性数",
        )
        if item.get("measures"):
            labels.update({name: label for name, label, _ in item["measures"]})
        for query in (widget["query"], widget["publication"]["query"]):
            for field in query["output_fields"]:
                field["type"] = "string" if field["name"] in dimensions else "number"
                field["label"] = labels.get(field["name"], field["name"])
    return schema
