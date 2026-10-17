"""Executable templates with parameterized filters and publication contracts.

Template generation is deterministic and runs against the selected real source.
AI is available afterwards for scoped proposals, not needed to wire basic filters.
"""

import uuid
from datetime import datetime

from .catalog_extended import extend_catalog, get_recipe
from .publication import DashboardPublicationError
from .schemas import DashboardCreateRequest, DashboardSchemaV1, DashboardSnapshot

WALMART = "Walmart_Sales"
OLIST = "olist_ecommerce_demo"
NORTHWIND = "upload_001_3a6ee8a2d1ad4a2a"
# Date is DD-MM-YYYY in this example source; preserve year/month rather than
# merging multiple years into a generic January–December series.
WALMART_PERIOD = "substr(Date,7,4)||'-'||substr(Date,4,2)"

TEMPLATES = [
    dict(
        id="retail-overview",
        title="零售经营总览",
        category="销售",
        source=WALMART,
        description="门店、月份与节假日销售结构，定位经营变化。",
        metric="销售额",
        unit="美元",
        segment="门店",
        sql=(
            f"SELECT {WALMART_PERIOD} AS period, CAST(Store AS"
            f" TEXT) AS segment, CASE Holiday_Flag WHEN 1 THEN"
            f" '节假日' ELSE '普通周' END AS category, SUM(Wee"
            f"kly_Sales) AS value FROM walmart_sales GROUP BY "
            f"1,2,3"
        ),
        theme="clarity",
    ),
    dict(
        id="holiday-sales",
        title="节假日销售表现",
        category="销售",
        source=WALMART,
        description="切换节假日和普通周，比较销售趋势与门店贡献。",
        metric="销售额",
        unit="美元",
        segment="周类型",
        sql=(
            f"SELECT {WALMART_PERIOD} AS period, CASE Holiday_"
            f"Flag WHEN 1 THEN '节假日' ELSE '普通周' END AS s"
            f"egment, CAST(Store AS TEXT) AS category, SUM(Wee"
            f"kly_Sales) AS value FROM walmart_sales GROUP BY "
            f"1,2,3"
        ),
        theme="warm",
    ),
    dict(
        id="store-coverage",
        title="门店经营覆盖",
        category="运营",
        source=WALMART,
        description="按门店观察有销售记录的周数与月份覆盖。",
        metric="门店周记录",
        unit="条",
        segment="周类型",
        sql=(
            f"SELECT {WALMART_PERIOD} AS period, CASE Holiday_"
            f"Flag WHEN 1 THEN '节假日' ELSE '普通周' END AS s"
            f"egment, CAST(Store AS TEXT) AS category, COUNT(*"
            f") AS value FROM walmart_sales GROUP BY 1,2,3"
        ),
        theme="ocean",
    ),
    dict(
        id="olist-orders",
        title="电商订单趋势",
        category="电商",
        source=OLIST,
        description="按州与订单状态分析订单趋势，每笔订单只计一次。",
        metric="订单数",
        unit="单",
        segment="客户所在州",
        sql=(
            "SELECT substr(o.order_purchase_timestamp,1,7) AS"
            " period, c.customer_state AS segment, o.order_st"
            "atus AS category, COUNT(*) AS value FROM olist_o"
            "rders o JOIN olist_customers c ON o.customer_id="
            "c.customer_id GROUP BY 1,2,3"
        ),
        theme="clarity",
    ),
    dict(
        id="olist-delivery",
        title="订单交付与状态",
        category="运营",
        source=OLIST,
        description="选择交付状态，查看订单所在区域和时间分布。",
        metric="订单数",
        unit="单",
        segment="订单状态",
        sql=(
            "SELECT substr(o.order_purchase_timestamp,1,7) AS"
            " period, o.order_status AS segment, c.customer_s"
            "tate AS category, COUNT(*) AS value FROM olist_o"
            "rders o JOIN olist_customers c ON o.customer_id="
            "c.customer_id GROUP BY 1,2,3"
        ),
        theme="graphite",
    ),
    dict(
        id="olist-payments",
        title="支付方式与回款",
        category="财务",
        source=OLIST,
        description="比较支付方式与订单状态下的回款金额，不关联订单明细。",
        metric="付款金额",
        unit="巴西雷亚尔",
        segment="支付方式",
        sql=(
            "SELECT substr(o.order_purchase_timestamp,1,7) AS"
            " period, p.payment_type AS segment, o.order_stat"
            "us AS category, SUM(p.payment_value) AS value FR"
            "OM olist_order_payments p JOIN olist_orders o ON"
            " p.order_id=o.order_id GROUP BY 1,2,3"
        ),
        theme="ocean",
    ),
    dict(
        id="northwind-revenue",
        title="品类收入与市场",
        category="销售",
        source=NORTHWIND,
        description="按国家和品类查看扣除折扣后的商品净收入。",
        metric="商品净收入",
        unit="美元",
        segment="收货国家",
        sql=(
            "SELECT substr(o.orderDate,1,7) AS period, o.ship"
            "Country AS segment, c.categoryName AS category, "
            "SUM(d.unitPrice*d.quantity*(1-d.discount)) AS va"
            "lue FROM orders o JOIN order_details d ON o.orde"
            "rID=d.orderID JOIN products p ON d.productID=p.p"
            "roductID JOIN categories c ON p.categoryID=c.cat"
            "egoryID GROUP BY 1,2,3"
        ),
        theme="warm",
    ),
    dict(
        id="northwind-customers",
        title="客户订购分析",
        category="客户",
        source=NORTHWIND,
        description="按收货国家比较客户订购频次，识别重点客户。",
        metric="订单数",
        unit="单",
        segment="收货国家",
        sql=(
            "SELECT substr(o.orderDate,1,7) AS period, o.ship"
            "Country AS segment, c.companyName AS category, C"
            "OUNT(*) AS value FROM orders o JOIN customers c "
            "ON o.customerID=c.customerID GROUP BY 1,2,3"
        ),
        theme="clarity",
    ),
    dict(
        id="northwind-freight",
        title="物流运费成本",
        category="运营",
        source=NORTHWIND,
        description="按国家与承运商编号分析订单运费和月度成本。",
        metric="运费",
        unit="美元",
        segment="收货国家",
        sql=(
            "SELECT substr(orderDate,1,7) AS period, shipCoun"
            "try AS segment, '承运商 '||CAST(shipVia AS TEXT)"
            " AS category, SUM(freight) AS value FROM orders "
            "GROUP BY 1,2,3"
        ),
        theme="graphite",
    ),
]

TEMPLATES.extend(extend_catalog(TEMPLATES))


def build_template(template_id, source, years=(), segments=(), mapping=None):
    from .catalog_layouts import compose_template

    template = next((item for item in TEMPLATES if item["id"] == template_id), None)
    if template is None:
        raise ValueError("模板不存在")
    return DashboardSchemaV1.model_validate(
        compose_template(template, source, years, segments, mapping)
    )


def _profile_mapping(service, source, template_id, mapping):
    from .catalog_source import source_facts

    # The connector query still goes through the same metadata allowlist,
    # read-only parser, timeout and row budget as any normal dashboard query.
    tests = {
        "records": "COUNT(*)",
        "invalid_date": "SUM(CASE WHEN event_date IS NULL THEN 1 ELSE 0 END)",
        "invalid_value": (
            "SUM(CASE WHEN typeof(value) NOT IN ('integer','real') THEN 1 ELSE 0 END)"
        ),
        "missing_dimension": (
            "SUM(CASE WHEN segment IS NULL OR category IS NULL THEN 1 ELSE 0 END)"
        ),
    }
    recipe = get_recipe(template_id)
    if recipe and not recipe.get("temporal", True):
        tests.pop("invalid_date")
    if template_id == "northwind-customers":
        tests["missing_customer"] = (
            "SUM(CASE WHEN entity IS NULL OR trim(entity)='' THEN 1 ELSE 0 END)"
        )
    if template_id in ("olist-delivery", "northwind-freight"):
        tests["available_aux"] = "COUNT(aux)"
        tests["invalid_aux"] = (
            "SUM(CASE WHEN aux IS NOT NULL AND typeof(aux) NO"
            "T IN ('integer','real') THEN 1 ELSE 0 END)"
        )
    if mapping is not None and mapping.grain == "order":
        tests["unique_orders"] = "COUNT(DISTINCT NULLIF(trim(record_id),''))"
    fields = [dict(name=n, type="number") for n in tests]
    sql = (
        "SELECT "
        + ",".join(f"{expression} AS {name}" for name, expression in tests.items())
        + f" FROM ({source_facts(template_id, mapping)}) source_profile"
    )
    schema = DashboardSchemaV1.model_validate(
        dict(
            schema_version="1.4",
            dashboard=dict(title="字段验证", data_source_id=source),
            widgets=[
                dict(
                    id="profile",
                    type="table",
                    title="字段验证",
                    query=dict(
                        data_source_id=source, sql=sql, output_fields=fields, max_rows=1
                    ),
                    encoding=dict(columns=list(tests)),
                )
            ],
            layouts=dict(desktop=[dict(widget_id="profile", x=0, y=0, w=12, h=4)]),
        )
    )
    result = service.query_executor.execute_widget(schema, "profile", {})
    if result.error:
        raise ValueError(
            "无法读取映射字段，请检查数据表、字段和日期格式：" + result.error.message
        )
    values = dict(zip(result.columns, result.rows[0]))
    if not values["records"]:
        raise ValueError("当前数据源没有可用记录，未创建空模板。")
    labels = {
        "invalid_date": "存在无法解析的日期，请选择匹配的日期格式",
        "invalid_value": "金额必须是数值列，不能包含空值或文本",
        "missing_dimension": "分类字段存在缺失或关联未匹配，请先补齐分类",
        "missing_customer": "留存分析必须提供每条订单的稳定客户标识",
        "invalid_aux": "辅助数值列包含非数值，请先转换",
    }
    for key, label in labels.items():
        if values.get(key):
            raise ValueError(f"{label}（{values[key]} 条）。")
    if "available_aux" in values and not values["available_aux"]:
        raise ValueError("没有可用的交付偏差或订单金额，无法生成此模板。")
    if "unique_orders" in values and values["unique_orders"] != values["records"]:
        raise ValueError(
            "订单编号缺失或重复。此模板要求每笔订单一条记录，请先去重或汇总订单明细。"
        )
    return values


def preview_template(service, template_id, source, actor, mapping=None):
    from .catalog_source import validate_mapping

    validate_mapping(service, source, actor, template_id, mapping)
    profile = _profile_mapping(service, source, template_id, mapping)
    schema = build_template(template_id, source, mapping=mapping)
    service.authorize_schema_sources(actor, schema)
    raw = service.publication_service.materialize(schema, service.query_executor)
    years, segments = set(), set()
    for dataset in raw.values():
        positions = {column: index for index, column in enumerate(dataset.columns)}
        for row in dataset.rows:
            if row[positions["year"]] is not None:
                years.add(str(row[positions["year"]]))
            if row[positions["segment"]] is not None:
                segments.add(str(row[positions["segment"]]))
    years, segments = sorted(years), sorted(segments)
    if not years or not segments:
        raise DashboardPublicationError("当前数据源没有可用记录，未创建空模板。")
    schema = build_template(template_id, source, years, segments, mapping)
    validation = service.validate_schema(
        schema, execute_queries=True, require_publication_bindings=True
    )
    if not validation.valid:
        raise DashboardPublicationError(
            "; ".join(issue.message for issue in validation.issues[:3])
        )
    base_snapshot = DashboardSnapshot(
        dashboard_id="template-preview",
        refreshed_at=datetime.now(),
        widgets={},
        publication_datasets=raw,
    )
    snapshots = []
    for values in ({}, {"year": years[-1]}, {"segment": segments[0]}):
        results = service.query_executor.execute_dashboard(schema, values)
        if any(result.error or result.truncated for result in results.values()):
            raise DashboardPublicationError(
                "模板筛选查询失败或结果超出上限，未创建看板。"
            )
        filtered = service.publication_service.filter_snapshot(
            schema, base_snapshot, values
        )
        if filtered.unsupported_widget_ids:
            raise DashboardPublicationError("模板分享筛选绑定不完整。")
        # Compare values, not just successful HTTP responses. Float aggregates
        # may differ slightly between SQLite and Python's summation order.
        for key, expected in results.items():
            actual = filtered.snapshot.widgets[key]
            if expected.columns != actual.columns or len(expected.rows) != len(
                actual.rows
            ):
                raise DashboardPublicationError("查询与分享筛选结果不一致：" + key)

            def canonical(rows):
                import json

                return sorted(
                    json.dumps(
                        [
                            f"{float(v):.4f}" if isinstance(v, (int, float)) else v
                            for v in row
                        ],
                        ensure_ascii=False,
                    )
                    for row in rows
                )

            if canonical(expected.rows) != canonical(actual.rows):
                raise DashboardPublicationError("查询与分享筛选数值不一致：" + key)
        snapshots.append(
            DashboardSnapshot(
                dashboard_id="template-preview",
                refreshed_at=datetime.now(),
                filters=values,
                widgets=results,
            )
        )
    schema.metadata.compatibility["catalog_template_id"] = template_id
    if mapping is not None:
        schema.metadata.compatibility["catalog_source_mapping"] = mapping.model_dump()
    return {
        "schema": schema.model_dump(mode="json", by_alias=True),
        "snapshot": snapshots[0].model_dump(mode="json"),
        "validation": {
            "records": profile["records"],
            "widgets": len(schema.widgets),
            "filter_checks": 3,
            "publication_equivalent": True,
            "grain": mapping.grain if mapping else "示例业务明细",
        },
    }


def instantiate_template(service, template_id, source, actor, mapping=None):
    preview = preview_template(service, template_id, source, actor, mapping)
    schema = DashboardSchemaV1.model_validate(preview["schema"])
    schema.metadata.conversation_id = str(uuid.uuid4())
    return service.create_dashboard(
        DashboardCreateRequest(schema=schema, origin="manual"), actor
    )
