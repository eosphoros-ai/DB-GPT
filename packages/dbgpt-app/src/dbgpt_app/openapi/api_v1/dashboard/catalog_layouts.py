"""Nine distinct, source-backed compositions sharing one publication contract."""

from .catalog_extended import DATASETS, extended_composition, get_recipe
from .catalog_identity import apply_catalog_identity
from .catalog_research import RESEARCH_IDS, configure_research
from .catalog_showcase import SHOWCASE_IDS, configure_showcase
from .catalog_source import normalized_facts


def spec(
    key,
    title,
    visualization,
    dims=(),
    field="value",
    aggregation="sum",
    unit=None,
    limit=120,
):
    return dict(
        id=key,
        title=title,
        visualization=visualization,
        dims=list(dims),
        field=field,
        aggregation=aggregation,
        unit=unit,
        limit=limit,
    )


def template_composition(template):
    if get_recipe(template["id"]):
        return extended_composition(template)
    key = template["id"]
    metric, unit = template["metric"], template["unit"]
    total = spec("total", metric, "kpi", unit=unit)
    trend = spec("trend", metric + "月度趋势", "area", ("period",), unit=unit)
    if key == "retail-overview":
        widgets = [
            total,
            spec(
                "scope",
                "覆盖门店",
                "kpi",
                field="segment",
                aggregation="count_distinct",
                unit="家",
            ),
            trend,
            spec("ranking", "门店销售排行", "bar", ("segment",), unit=unit, limit=10),
            spec("structure", "普通周与节假日销售", "column", ("category",), unit=unit),
        ]
        boxes = [
            (0, 0, 4, 3),
            (4, 0, 4, 3),
            (0, 3, 8, 8),
            (8, 0, 4, 11),
            (0, 11, 12, 7),
        ]
    elif key == "holiday-sales":
        widgets = [
            total,
            spec(
                "average", "每店每周平均销售", "kpi", aggregation="average", unit=unit
            ),
            spec(
                "comparison",
                "不同周类型的店周均值",
                "column",
                ("segment",),
                aggregation="average",
                unit=unit,
            ),
            spec(
                "trend",
                "月度销售与周类型",
                "stacked_column",
                ("period", "segment"),
                unit=unit,
            ),
            spec(
                "ranking",
                "门店销售对照",
                "table",
                ("category", "segment"),
                unit=unit,
                limit=30,
            ),
        ]
        boxes = [(0, 0, 6, 3), (6, 0, 6, 3), (0, 3, 5, 8), (5, 3, 7, 8), (0, 11, 12, 6)]
    elif key == "store-coverage":
        widgets = [
            spec(
                "coverage",
                "门店与月份的销售记录",
                "heatmap",
                ("category", "period"),
                unit="条",
                limit=5000,
            ),
            total,
            spec(
                "months",
                "有记录的月份",
                "kpi",
                field="period",
                aggregation="count_distinct",
                unit="个月",
            ),
            spec("ranking", "门店记录数", "bar", ("category",), unit="条", limit=12),
        ]
        boxes = [(0, 0, 9, 13), (9, 0, 3, 3), (9, 3, 3, 3), (9, 6, 3, 7)]
    elif key == "olist-orders":
        widgets = [
            trend,
            total,
            spec(
                "regions",
                "客户所在州",
                "kpi",
                field="segment",
                aggregation="count_distinct",
                unit="个",
            ),
            spec("status", "订单状态", "donut", ("category",), unit="单", limit=12),
            spec(
                "regions_trend",
                "各州月度订单",
                "heatmap",
                ("segment", "period"),
                unit="单",
                limit=5000,
            ),
        ]
        boxes = [(0, 0, 12, 8), (0, 8, 3, 3), (3, 8, 3, 3), (6, 8, 6, 8), (0, 11, 6, 9)]
    elif key == "olist-delivery":
        widgets = [
            total,
            spec("status", "订单交付状态", "bar", ("segment",), unit="单", limit=12),
            spec(
                "delay",
                "平均交付偏差",
                "column",
                ("period",),
                field="aux",
                aggregation="average",
                unit="天",
            ),
            spec(
                "details",
                "地区与状态订单明细",
                "table",
                ("category", "segment"),
                unit="单",
                limit=80,
            ),
        ]
        boxes = [(0, 0, 4, 3), (0, 3, 4, 8), (4, 0, 8, 8), (4, 8, 8, 8)]
    elif key == "olist-payments":
        widgets = [
            total,
            spec(
                "average", "每笔支付平均金额", "kpi", aggregation="average", unit=unit
            ),
            spec("methods", "支付方式金额", "donut", ("segment",), unit=unit, limit=12),
            spec(
                "ledger",
                "月份与支付方式回款明细",
                "table",
                ("period", "segment"),
                unit=unit,
                limit=90,
            ),
            spec(
                "trend",
                "各支付方式月度回款",
                "stacked_column",
                ("period", "segment"),
                unit=unit,
            ),
        ]
        boxes = [(0, 0, 3, 3), (3, 0, 3, 3), (6, 0, 6, 7), (0, 3, 6, 13), (6, 7, 6, 9)]
    elif key == "northwind-revenue":
        widgets = [
            total,
            spec(
                "ranking", "品类净收入排行", "bar", ("category",), unit=unit, limit=12
            ),
            spec(
                "markets",
                "国家与品类收入",
                "stacked_column",
                ("segment", "category"),
                unit=unit,
                limit=80,
            ),
            trend,
            spec("details", "市场收入明细", "table", ("segment",), unit=unit, limit=30),
        ]
        boxes = [(0, 0, 4, 3), (0, 3, 4, 8), (4, 0, 8, 9), (4, 9, 8, 7), (0, 11, 4, 7)]
    elif key == "northwind-customers":
        widgets = [
            spec("retention", "客户首购与复购留存", "cohort", unit="月", limit=5000),
            total,
            spec(
                "customers",
                "下单客户数",
                "kpi",
                field="entity",
                aggregation="count_distinct",
                unit="位",
            ),
            spec(
                "ranking", "客户订购次数", "table", ("category",), unit="单", limit=30
            ),
        ]
        boxes = [(0, 0, 12, 13), (0, 13, 3, 3), (3, 13, 3, 3), (6, 13, 6, 7)]
    else:
        widgets = [
            total,
            spec("relationship", "订单金额与运费", "scatter", unit=unit, limit=1000),
            spec("trend", "月度运费成本", "line", ("period",), unit=unit),
            spec(
                "carriers", "承运商运费", "column", ("category",), unit=unit, limit=12
            ),
            spec("details", "国家运费明细", "table", ("segment",), unit=unit, limit=30),
        ]
        boxes = [
            (0, 0, 3, 3),
            (3, 0, 9, 10),
            (0, 3, 3, 8),
            (0, 11, 5, 7),
            (5, 10, 7, 8),
        ]
    return widgets, [
        dict(widget_id=w["id"], x=b[0], y=b[1], w=b[2], h=b[3])
        for w, b in zip(widgets, boxes)
    ]


def fields(names):
    return [
        dict(
            name=n,
            type=(
                "number"
                if n
                in (
                    "value",
                    "amount",
                    "n",
                    "aux",
                    "age",
                    "retained",
                    "cohort_size",
                    "observed",
                    "reach",
                    "units",
                    "fees",
                    "applications",
                )
                else "string"
            ),
        )
        for n in names
    ]


FILTER_SQL = (
    " WHERE (:year='all' OR year=:year) AND (:segment='all' OR segment=:segment)"
)
FILTER_BINDINGS = {"year": {"parameter": "year"}, "segment": {"parameter": "segment"}}


def query(source, sql, columns, filtered=False, limit=5000):
    return dict(
        data_source_id=source,
        sql=sql,
        output_fields=fields(columns),
        max_rows=limit,
        filter_parameters=FILTER_BINDINGS if filtered else {},
    )


def cohort_dataset(facts, interval):
    bucket = (
        (
            "date(event_date, '-'||((CAST(strftime('%w',event"
            "_date) AS INTEGER)+6)%7)||' days')"
        )
        if interval == "week"
        else "substr(event_date,1,7)||'-01'"
    )
    elapsed = (
        "CAST((julianday(e.period)-julianday(m.cohort))/7 AS INTEGER)"
        if interval == "week"
        else (
            "(CAST(substr(e.period,1,4) AS INTEGER)-CAST(subs"
            "tr(m.cohort,1,4) AS INTEGER))*12+CAST(substr(e.p"
            "eriod,6,2) AS INTEGER)-CAST(substr(m.cohort,6,2)"
            " AS INTEGER)"
        )
    )
    horizon_age = elapsed.replace("e.period", "h.last_period").replace(
        "m.cohort", "s.cohort"
    )
    ages = " UNION ALL ".join(f"SELECT {n} AS age" for n in range(13))
    return (
        f"""WITH facts AS ({facts}),
      events AS (SELECT"""
        f""" entity,segment,event_date,{bucket} AS period FR"""
        f"""OM facts),
      first_dates AS (SELECT entity,M"""
        f"""IN(event_date) AS first_date FROM events GROUP B"""
        f"""Y entity),
      members AS (SELECT e.entity,MIN"""
        f"""(e.segment) AS segment,MIN(e.period) AS cohort F"""
        f"""ROM events e JOIN first_dates f ON e.entity=f.en"""
        f"""tity AND e.event_date=f.first_date GROUP BY e.en"""
        f"""tity),
      sizes AS (SELECT cohort,segment,COU"""
        f"""NT(*) AS cohort_size FROM members GROUP BY cohor"""
        f"""t,segment),
      active AS (SELECT m.cohort,m.s"""
        f"""egment,{elapsed} AS age,COUNT(DISTINCT e.entity)"""
        f""" AS retained FROM members m JOIN events e ON m.e"""
        f"""ntity=e.entity GROUP BY m.cohort,m.segment,age),"""
        f"""
      ages AS ({ages}), horizon AS (SELECT MAX("""
        f"""period) AS last_period FROM events)
      SELECT"""
        f""" s.cohort,substr(s.cohort,1,4) AS year,s.segment"""
        f""",a.age,s.cohort_size,
        COALESCE(r.retaine"""
        f"""d,0) AS retained,CASE WHEN a.age<={horizon_age} """
        f"""THEN 1 ELSE 0 END AS observed
      FROM sizes s"""
        f""" CROSS JOIN ages a CROSS JOIN horizon h
      LE"""
        f"""FT JOIN active r ON r.cohort=s.cohort AND r.segm"""
        f"""ent=s.segment AND r.age=a.age"""
    )


def build_widget(template, source, item, mapping=None):
    facts = normalized_facts(template["id"], mapping)
    if item.get("where"):
        facts = f"SELECT * FROM ({facts}) scoped_facts WHERE {item['where']}"
    viz, dims, field, aggregation = (
        item["visualization"],
        item["dims"],
        item["field"],
        item["aggregation"],
    )
    unit = item["unit"] or template["unit"]
    if (
        mapping is not None
        and unit == template["unit"]
        and template["unit"] not in ("单", "条")
    ):
        unit = mapping.unit
    if item.get("measures"):
        raw_dims = list(dict.fromkeys(["year", "segment", *dims]))
        measures = [
            dict(source_field=field, output_field=name, aggregation="sum")
            for name, _, field in item["measures"]
        ]
        source_fields = list(dict.fromkeys(m["source_field"] for m in measures))
        raw_columns = [*raw_dims, *source_fields]
        raw = (
            f"SELECT {','.join(raw_dims)},"
            f"{','.join(f'SUM({f}) AS {f}' for f in source_fields)}"
            f" FROM ({facts}) facts GROUP BY "
            f"{','.join(raw_dims)}"
        )
        columns = [*dims, *[m["output_field"] for m in measures]]
        select = [
            *dims,
            *[f"SUM({m['source_field']}) AS {m['output_field']}" for m in measures],
        ]
        order = [
            dict(field="value", direction="descending"),
            *[dict(field=d, direction="ascending") for d in dims],
        ]
        sql = (
            f"SELECT {','.join(select)} FROM ({raw}) dataset"
            f"{FILTER_SQL} GROUP BY {','.join(dims)} ORDER BY "
            f"value DESC,{','.join(dims)} LIMIT "
            f"{item['limit']}"
        )
        publication = dict(
            query=query(source, raw, raw_columns),
            filter_fields={"year": "year", "segment": "segment"},
            group_by=dims,
            measures=measures,
            output_columns=columns,
            sort=order,
            max_output_rows=item["limit"],
        )
        encoding, description = dict(columns=columns), ""
    elif viz == "cohort":
        interval = mapping.interval if mapping else "month"
        raw = cohort_dataset(facts, interval)
        raw_columns = [
            "cohort",
            "year",
            "segment",
            "age",
            "cohort_size",
            "retained",
            "observed",
        ]
        columns = ["cohort", "age", "retained", "cohort_size", "observed"]
        sql = (
            f"SELECT cohort,age,SUM(retained) AS retained,SUM("
            f"cohort_size) AS cohort_size,MIN(observed) AS obs"
            f"erved FROM ({raw}) cohort_data{FILTER_SQL} GROUP"
            f" BY cohort,age ORDER BY cohort,age"
        )
        measures = [
            dict(
                source_field=n,
                output_field=n,
                aggregation="minimum" if n == "observed" else "sum",
            )
            for n in ("retained", "cohort_size", "observed")
        ]
        publication = dict(
            query=query(source, raw, raw_columns),
            filter_fields={"year": "year", "segment": "segment"},
            group_by=["cohort", "age"],
            measures=measures,
            output_columns=columns,
            sort=[
                dict(field="cohort", direction="ascending"),
                dict(field="age", direction="ascending"),
            ],
            max_output_rows=5000,
        )
        encoding = dict(
            row="cohort",
            column="age",
            value="retained",
            target="cohort_size",
            color="observed",
        )
        unit = "周" if interval == "week" else "月"
        description = (
            "按首购年份及首次购买地区筛选；人数去重。未观察到"
            "的后续周期显示为未到期。数据观察截止于源数据最后"
            "一笔订单。"
        )
    elif viz == "scatter":
        raw = (
            f"SELECT event_date,year,segment,category,entity,v"
            f"alue,aux FROM ({facts}) facts"
        )
        raw_columns = [
            "event_date",
            "year",
            "segment",
            "category",
            "entity",
            "value",
            "aux",
        ]
        columns = ["event_date", "segment", "category", "value", "aux"]
        sql = (
            f"SELECT {','.join(columns)} FROM ({raw}) points"
            f"{FILTER_SQL} ORDER BY event_date DESC LIMIT "
            f"{item['limit']}"
        )
        publication = dict(
            query=query(source, raw, raw_columns),
            filter_fields={"year": "year", "segment": "segment"},
            row_mode=True,
            output_columns=columns,
            sort=[dict(field="event_date", direction="descending")],
            max_output_rows=item["limit"],
        )
        encoding = dict(x="aux", y="value", series="category")
        description = "每个点对应一笔订单；横轴为订单净金额，纵轴为运费。"
    else:
        raw_dims = list(dict.fromkeys(["year", "segment", *dims]))
        if item.get("denominator"):
            denominator, scale = item["denominator"], item["scale"]
            raw = (
                f"SELECT {','.join(raw_dims)},SUM({field}) AS amou"
                f"nt,SUM({denominator}) AS n FROM ({facts}) facts "
                f"GROUP BY {','.join(raw_dims)}"
            )
            raw_columns = [*raw_dims, "amount", "n"]
            formula = f"SUM(amount)*{float(scale)}/NULLIF(SUM(n),0)"
            measures = [
                dict(
                    source_field="amount",
                    output_field="value",
                    aggregation="ratio",
                    denominator_field="n",
                    scale=scale,
                )
            ]
        elif aggregation == "count_distinct":
            raw_dims = list(dict.fromkeys([*raw_dims, field]))
            raw = f"SELECT DISTINCT {','.join(raw_dims)} FROM ({facts}) facts"
            raw_columns = raw_dims
            formula, measures = (
                f"COUNT(DISTINCT {field})",
                [
                    dict(
                        source_field=field,
                        output_field="value",
                        aggregation="count_distinct",
                    )
                ],
            )
        else:
            aggregate = "COUNT" if aggregation == "count" else "SUM"
            raw = (
                f"SELECT {','.join(raw_dims)},{aggregate}({field})"
                f" AS amount,COUNT({field}) AS n FROM ({facts}) fa"
                f"cts GROUP BY {','.join(raw_dims)}"
            )
            raw_columns = [*raw_dims, "amount", "n"]
            formula = (
                "SUM(amount)*1.0/NULLIF(SUM(n),0)"
                if aggregation == "average"
                else "SUM(amount)"
            )
            measures = [
                (
                    dict(
                        source_field="amount",
                        output_field="value",
                        aggregation="ratio",
                        denominator_field="n",
                    )
                    if aggregation == "average"
                    else dict(
                        source_field="amount", output_field="value", aggregation="sum"
                    )
                )
            ]
        columns = [*dims, "value"]
        order = (
            dims
            if "period" in dims or viz == "heatmap" or item.get("newest")
            else ["value", *dims]
            if dims
            else []
        )
        descending_field = "event_date" if item.get("newest") else "value"
        descending = bool(order and order[0] == descending_field)
        sql = (
            f"SELECT {','.join(dims) + ',' if dims else ''}"
            f"{formula} AS value FROM ({raw}) dataset"
            f"{FILTER_SQL}"
        )
        if dims:
            sql += (
                " GROUP BY "
                + ",".join(dims)
                + " ORDER BY "
                + ",".join(
                    n + (" DESC" if n == descending_field and descending else " ASC")
                    for n in order
                )
                + f" LIMIT {item['limit']}"
            )
        publication = dict(
            query=query(source, raw, raw_columns),
            filter_fields={"year": "year", "segment": "segment"},
            group_by=dims,
            measures=measures,
            output_columns=columns,
            max_output_rows=item["limit"],
            sort=[
                dict(
                    field=n,
                    direction=(
                        "descending"
                        if descending and n == descending_field
                        else "ascending"
                    ),
                )
                for n in order
            ],
        )
        encoding = (
            dict(value="value")
            if viz in ("kpi", "gauge")
            else (
                dict(columns=columns)
                if viz == "table"
                else (
                    dict(row=dims[0], column=dims[1], value="value")
                    if viz == "heatmap"
                    else (
                        dict(category=dims[0], angle="value")
                        if viz in ("pie", "donut")
                        else dict(
                            x=dims[0],
                            y="value",
                            series=dims[1] if len(dims) > 1 else None,
                        )
                    )
                )
            )
        )
        description = (
            "负值表示早于预计日期送达，正值表示延迟；未送达订单不计入平均值。"
            if item["id"] == "delay"
            else ""
        )
    kind = (
        "kpi"
        if viz in ("kpi", "gauge")
        else (
            "table"
            if viz == "table"
            else (
                "pie"
                if viz in ("donut", "pie")
                else "line"
                if viz in ("line", "area")
                else "bar"
            )
        )
    )
    return dict(
        id=item["id"],
        type=kind,
        title=item["title"],
        description=description,
        query=query(source, sql, columns, True, item["limit"]),
        publication=publication,
        encoding=encoding,
        presentation=dict(
            visualization=viz,
            unit=unit,
            precision=1 if aggregation == "average" else 0,
            stacked=viz == "stacked_column",
        ),
    )


def compose_template(template, source, years=(), segments=(), mapping=None):
    items, layout = template_composition(template)
    recipe = get_recipe(template["id"])
    notes = (
        DATASETS[recipe["dataset"]]["notes"]
        if recipe and not recipe["base"]
        else template["description"]
    )
    widgets = [build_widget(template, source, item, mapping) for item in items]
    if template["id"] == "brand-revenue":
        icons = {
            "customers": "team",
            "regions": "global",
            "units": "shopping",
            "months": "calendar",
            "average": "revenue",
            "categories": "appstore",
        }
        for widget in widgets:
            if widget["id"] == "hero":
                widget["style"] = {
                    "hero_image": "/dashboard-templates/assets/brand-revenue-hero.png"
                }
            elif widget["id"] == "coverage":
                widget["style"] = {
                    "target": len(segments),
                    "target_label": "数据源已记录市场",
                    "progress_label": "已覆盖",
                }
                widget["description"] = (
                    "分母为模板创建时数据源中全部已记录市场数，分子随年份与市场筛选变化；不是销售目标。"
                )
            elif widget["id"] in icons:
                widget["style"] = {"metric_icon": icons[widget["id"]]}
    schema = dict(
        schema_version="1.4",
        dashboard=dict(
            title=template["title"],
            description=template["description"],
            data_source_id=source,
            theme=dict(
                preset=template["theme"],
                mode=template.get("mode", "light"),
                overrides=template.get("overrides", {}),
            ),
        ),
        metric_context=dict(
            grain="模板按业务明细计算，关联表仅作唯一键匹配；客户留存按稳定客户标识去重",
            data_freshness="查询时读取当前数据源",
            source_notes=[notes],
        ),
        metadata=dict(
            compatibility={
                "catalog_template_id": template["id"],
                "catalog_presentation": dict(
                    style=recipe["style"], reference=recipe["reference"]
                ),
            }
        )
        if recipe
        else {},
        filters=[
            dict(
                id="year",
                type="select",
                label=template.get("scope_label", "年份"),
                field="year",
                default="all",
                options=[
                    dict(
                        label="全部" if template.get("scope_label") else "全部年份",
                        value="all",
                    )
                ]
                + [dict(label=v, value=v) for v in years],
            ),
            dict(
                id="segment",
                type="select",
                label=(
                    template["segment"]
                    if mapping is None
                    else mapping.fields["segment"].column
                ),
                field="segment",
                default="all",
                options=[dict(label="全部", value="all")]
                + [dict(label=v, value=v) for v in segments],
            ),
        ],
        widgets=widgets,
        layouts=dict(desktop=layout),
    )

    schema = apply_catalog_identity(schema, template["id"])
    if template["id"] in RESEARCH_IDS:
        return configure_research(schema, template, items)
    return (
        configure_showcase(schema, template, items)
        if template["id"] in SHOWCASE_IDS
        else schema
    )
