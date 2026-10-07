"""Original, editable compositions inspired by the user's Sive/Jimu references.

All figures come from explicitly labelled synthetic SQLite examples or mapped
customer data. Ratios are recalculated from sums, including frozen share data.
"""

SIVE = "https://sive.antv.antgroup.com/bY0qQaJRMm5PRxG3KANM"
JIMU = "https://github.com/jeecgboot/jimureport#大屏设计效果"
DEMO_NOTE = (
    "DB-GPT 自建合成演示数据，固定随机种子；2025、20"
    "26 年同期历史样本，不代表真实机构、患者或经营结果，也不是"
    "实时数据。"
)


def dataset(key, metric, unit, segment, extras, grain_note):
    return dict(
        source="sqlite_" + key,
        table="facts",
        grain="measurement",
        unit=unit,
        metric=metric,
        segment=segment,
        extras=extras,
        facts="SELECT * FROM facts",
        notes=DEMO_NOTE + grain_note,
    )


SHOWCASE_DATASETS = {
    "marketing_showcase": dataset(
        "marketing_showcase",
        "营销收入",
        "元",
        "门店",
        dict(channel="营销渠道", reach="触达次数", visits="到店次数"),
        (
            "每行是月份 × 门店 × 活动 × 渠道的汇总。触达和到店按"
            "次数累计；核销客单价=收入/核销次数，转化率=核销/触达，不"
            "将重复触达解释为去重人数。"
        ),
    ),
    "operations_showcase": dataset(
        "operations_showcase",
        "销售收入",
        "元",
        "省区",
        dict(
            units="销售件数",
            delivered="已交付订单",
            on_time="准时交付订单",
            target="销售目标",
        ),
        (
            "每行是月份 × 省区 × 品类的汇总；准时交付率=准时交付单"
            "数/已交付单数。地图气泡面积表示收入，地理位置为省级标记点。"
        ),
    ),
    "healthcare_showcase": dataset(
        "healthcare_showcase",
        "问诊订单",
        "单",
        "科室",
        dict(fees="服务金额", response_minutes="响应分钟总数", completed="已完成问诊"),
        (
            "每行是月份 × 虚拟机构 × 科室 × 渠道的汇总，不含任何"
            "个人信息；响应均值=响应分钟总数/问诊单数，完成率=完成单数"
            "/问诊单数。"
        ),
    ),
    "rural_showcase": dataset(
        "rural_showcase",
        "发放金额",
        "元",
        "省区",
        dict(
            applications="申请笔数",
            approved="通过笔数",
            due="到期笔数",
            on_time="按期还款笔数",
        ),
        (
            "每行是月份 × 省区 × 金融产品的汇总。发放笔数不等于去重"
            "农户数；审批通过率=通过/申请，按期还款率=按期还款/到期。"
            "地图气泡表示发放金额，无数据省份明确区分。"
        ),
    ),
}

SHOWCASE_RECIPES = [
    dict(
        id="store-marketing",
        title="门店营销沙盘",
        category="营销",
        base=None,
        style="marketing",
        dataset="marketing_showcase",
        reference=SIVE,
        description="奶油底色、橙色重点与硬边阴影；从活动核销、渠道贡献到门店表现，串联营销全貌。内置合成演示数据，可替换自己的数据源。",
    ),
    dict(
        id="national-command",
        title="全国经营指挥大屏",
        category="大屏",
        base=None,
        style="command",
        dataset="operations_showcase",
        reference=JIMU,
        description="蓝青科技大屏，以全国地图为中心，联动收入、交付、品类与省区排名。内置合成演示数据，支持全屏与明细放大。",
    ),
    dict(
        id="healthcare-command",
        title="互联网医疗服务大屏",
        category="大屏",
        base=None,
        style="clinical",
        dataset="healthcare_showcase",
        reference=JIMU,
        description="蓝紫医疗运营大屏，汇集问诊、处方、渠道和科室负载。仅使用合成汇总数据，不含患者信息；支持全屏与明细查看。",
    ),
    dict(
        id="rural-finance",
        title="乡村普惠金融大屏",
        category="大屏",
        base=None,
        style="rural",
        dataset="rural_showcase",
        reference=JIMU,
        description="深绿普惠金融大屏，全国分布与发放趋势居中，审批和还款指标分列两侧。内置合成演示数据，可按年份、省区联动筛选。",
    ),
]
SHOWCASE_IDS = {r["id"] for r in SHOWCASE_RECIPES}


def showcase_composition(template):
    from .catalog_layouts import spec

    unit = template["unit"]

    def w(
        key,
        title,
        viz="kpi",
        dims=(),
        field="value",
        agg="sum",
        u=None,
        limit=120,
        **extra,
    ):
        return {**spec(key, title, viz, dims, field, agg, u or unit, limit), **extra}

    def ratio(key, title, numerator, denominator, u="%", viz="kpi"):
        return w(
            key,
            title,
            viz,
            field=numerator,
            u=u,
            denominator=denominator,
            scale=100 if u == "%" else 1,
        )

    key = template["id"]
    if key == "store-marketing":
        items = [
            w("campaigns", "营销活动", field="category", agg="count_distinct", u="项"),
            w("redemptions", "活动核销", field="aux", u="次"),
            ratio("basket", "核销客单价", "value", "aux", "元"),
            w("reach", "活动触达", field="reach", u="次"),
            w("trend", "活动核销趋势", "area", ("period",), field="aux", u="次"),
            w("channels", "渠道贡献", "donut", ("channel",)),
            w(
                "promotions",
                "热门营销活动",
                "bar",
                ("category",),
                field="aux",
                u="次",
                limit=8,
            ),
            w("revenue", "渠道收入趋势", "stacked_column", ("period", "channel")),
            w(
                "ledger",
                "活动经营明细",
                "table",
                ("category", "channel"),
                measures=[
                    ("reach", "触达次数", "reach"),
                    ("aux", "核销次数", "aux"),
                    ("value", "营销收入（元）", "value"),
                ],
            ),
            w("venues", "门店收入分布", "bar", ("segment",), limit=10),
            ratio("conversion", "触达核销率", "aux", "reach", viz="gauge"),
            w(
                "visits",
                "各渠道到店次数",
                "column",
                ("channel",),
                field="visits",
                u="次",
            ),
        ]
        boxes = [(i * 3, 0, 3, 4) for i in range(4)] + [
            (0, 4, 8, 8),
            (8, 4, 4, 8),
            (0, 12, 6, 7),
            (6, 12, 6, 7),
            (0, 19, 12, 7),
            (0, 26, 5, 7),
            (5, 26, 3, 7),
            (8, 26, 4, 7),
        ]
    elif key == "national-command":
        items = [
            w("revenue", "销售收入"),
            w("orders", "订单总量", field="aux", u="单"),
            w("units", "销售件数", field="units", u="件"),
            w("regions", "覆盖省区", field="segment", agg="count_distinct", u="个"),
            w("categories", "品类收入构成", "donut", ("category",)),
            w("ranking", "省区销售 · Top 8", "bar", ("segment",), limit=8),
            w("map", "全国销售分布", "geo_map", ("segment",), map_region="china"),
            w("trend", "收入月度走势", "area", ("period",)),
            ratio("fulfillment", "准时交付率", "on_time", "delivered", viz="gauge"),
            w("mix", "各品类订单量", "column", ("category",), field="aux", u="单"),
            w(
                "ledger",
                "省区经营明细",
                "table",
                ("segment",),
                measures=[
                    ("value", "销售收入（元）", "value"),
                    ("aux", "订单量", "aux"),
                    ("units", "销售件数", "units"),
                ],
            ),
        ]
        boxes = [(i * 3, 0, 3, 3) for i in range(4)] + [
            (0, 3, 3, 7),
            (0, 10, 3, 8),
            (3, 3, 6, 10),
            (3, 13, 6, 5),
            (9, 3, 3, 7),
            (9, 10, 3, 8),
            (0, 18, 12, 6),
        ]
    elif key == "healthcare-command":
        items = [
            w("consultations", "累计问诊订单"),
            w("prescriptions", "累计处方订单", field="aux"),
            w("fees", "累计服务金额", field="fees", u="元"),
            w(
                "hospitals",
                "覆盖服务机构",
                field="entity",
                agg="count_distinct",
                u="家",
            ),
            ratio("response", "平均响应时间", "response_minutes", "value", "分钟"),
            w("channels", "问诊渠道构成", "donut", ("category",)),
            w(
                "ledger",
                "科室服务明细",
                "table",
                ("segment",),
                measures=[
                    ("value", "问诊单数", "value"),
                    ("aux", "处方单数", "aux"),
                    ("fees", "服务金额（元）", "fees"),
                ],
            ),
            w("trend", "各渠道月度问诊", "line", ("period", "category")),
            w("ranking", "科室问诊量", "bar", ("segment",), limit=8),
            ratio("completion", "问诊完成率", "completed", "value", viz="gauge"),
            w("providers", "机构服务订单", "column", ("entity",)),
            w("prescription_trend", "月度处方订单", "area", ("period",), field="aux"),
        ]
        boxes = [
            (0, 0, 2, 3),
            (2, 0, 2, 3),
            (4, 0, 3, 3),
            (7, 0, 2, 3),
            (9, 0, 3, 3),
            (0, 3, 3, 8),
            (0, 11, 3, 13),
            (3, 3, 6, 10),
            (3, 13, 6, 11),
            (9, 3, 3, 7),
            (9, 10, 3, 7),
            (9, 17, 3, 7),
        ]
    else:
        items = [
            w("amount", "累计发放金额"),
            w("loans", "累计发放笔数", field="aux", u="笔"),
            w("regions", "服务覆盖省区", field="segment", agg="count_distinct", u="个"),
            ratio("average", "平均每笔发放", "value", "aux", "元"),
            w("products", "金融产品分布", "donut", ("category",)),
            ratio("approval", "审批通过率", "approved", "applications", viz="gauge"),
            w("map", "普惠服务地域分布", "geo_map", ("segment",), map_region="china"),
            w("trend", "各产品月度发放", "line", ("period", "category")),
            ratio("repayment", "按期还款率", "on_time", "due", viz="gauge"),
            w("ranking", "省区发放 · Top 6", "bar", ("segment",), limit=6),
            w(
                "ledger",
                "普惠业务分类明细",
                "table",
                ("segment", "category"),
                measures=[
                    ("value", "发放金额（元）", "value"),
                    ("aux", "发放笔数", "aux"),
                    ("applications", "申请笔数", "applications"),
                ],
            ),
        ]
        boxes = [(i * 3, 0, 3, 3) for i in range(4)] + [
            (0, 3, 3, 8),
            (0, 11, 3, 7),
            (3, 3, 6, 10),
            (3, 13, 6, 5),
            (9, 3, 3, 7),
            (9, 10, 3, 8),
            (0, 18, 12, 6),
        ]
    # The wall-display density is intentional; the renderer must not silently
    # expand shorter charts and overlap the carefully arranged neighbouring panels.
    return items, [
        dict(widget_id=w["id"], x=x, y=y, w=width, h=h, max_h=40)
        for w, (x, y, width, h) in zip(items, boxes)
    ]


def configure_showcase(schema, template, items):
    definitions = {item["id"]: item for item in items}
    data = SHOWCASE_DATASETS[template["dataset"]]
    schema["metric_context"].update(
        grain=data["notes"].split("。", 2)[-1],
        data_freshness="合成历史演示样本；刷新会重新查询所选数据源",
    )
    if schema["dashboard"]["data_source_id"] != data["source"]:
        schema["metric_context"].update(
            grain="按匹配后的源字段与当前筛选聚合",
            data_freshness="查询时读取所选数据源",
            source_notes=["已切换至所选数据源；数值按匹配字段计算，非模板演示样本。"],
        )
    units = {
        "value": data["unit"],
        "aux": {"store-marketing": "次", "rural-finance": "笔"}.get(
            template["id"], "单"
        ),
        "reach": "次",
        "units": "件",
        "fees": "元",
        "applications": "笔",
    }
    schema["metric_context"]["metrics"] = [
        dict(
            id=name,
            name=name,
            business_definition="源汇总字段；按当前筛选汇总，口径见数据来源说明",
            source_field=name,
            unit=unit,
        )
        for name, unit in units.items()
    ]
    presentation = schema["metadata"]["compatibility"]["catalog_presentation"]
    presentation.update(
        demo_source=data["source"], sample_period="2025 / 2026 同期样本"
    )
    for widget in schema["widgets"]:
        item = definitions[widget["id"]]
        widget["style"] = dict(
            showLegend=len(item["dims"]) > 1 or item["visualization"] == "donut",
            animate=False,
        )
        if item.get("map_region"):
            widget["style"]["map_region"] = item["map_region"]
        if item.get("denominator"):
            widget["presentation"]["precision"] = 1
            widget["description"] = "按汇总分子与分母重算"
            if item["visualization"] == "gauge":
                widget["style"].update(
                    target=100, target_label="百分比刻度", progress_label="当前比例"
                )
        if item.get("measures"):
            widget["presentation"]["unit"] = ""
        labels = {
            "segment": template["segment"],
            "category": "营销活动"
            if template["id"] == "store-marketing"
            else "渠道"
            if template["id"] == "healthcare-command"
            else "产品品类",
            "period": "月份",
            "channel": "渠道",
            "entity": "服务机构",
            "value": item["title"],
        }
        labels.update({name: label for name, label, _ in item.get("measures", [])})
        for field in widget["query"]["output_fields"]:
            field["label"] = labels.get(field["name"], field["name"])
    return schema
