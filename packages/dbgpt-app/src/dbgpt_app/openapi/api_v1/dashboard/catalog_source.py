"""Source contracts for reusable layouts. Metadata is read only after authorization.

Custom mappings start at a fact table and permit only many-to-one lookup joins.
Identifiers must exist in connector metadata; user input is never a SQL fragment.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .catalog_extended import DATASETS, get_recipe


class SourceField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str = Field(min_length=1, max_length=255)
    column: str = Field(min_length=1, max_length=255)


class SourceJoin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str = Field(min_length=1, max_length=255)
    left: SourceField
    right_column: str = Field(min_length=1, max_length=255)


class TemplateSourceMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str = Field(min_length=1, max_length=255)
    fields: Dict[str, SourceField]
    joins: List[SourceJoin] = Field(default_factory=list, max_length=3)
    date_format: Literal["iso", "dmy"] = "iso"
    unit: str = Field(min_length=1, max_length=32)
    interval: Literal["week", "month"] = "month"
    grain: Literal[
        "store_week",
        "order",
        "order_line",
        "payment",
        "incident",
        "measurement",
        "student",
        "product",
    ]


def required_grain(template_id):
    recipe = get_recipe(template_id)
    if recipe:
        return (
            required_grain(recipe["base"])
            if recipe["base"]
            else DATASETS[recipe["dataset"]]["grain"]
        )
    if template_family(template_id) == "retail":
        return "store_week"
    if template_id == "northwind-revenue":
        return "order_line"
    return "payment" if template_id == "olist-payments" else "order"


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def template_family(template_id):
    recipe = get_recipe(template_id)
    if recipe:
        return template_family(recipe["base"]) if recipe["base"] else "extended"
    if template_id.startswith("olist-"):
        return "olist"
    if template_id.startswith("northwind-"):
        return "northwind"
    return "retail"


def field_roles(template_id):
    recipe = get_recipe(template_id)
    if recipe and recipe["base"]:
        return field_roles(recipe["base"])
    if recipe:
        dataset = DATASETS[recipe["dataset"]]
        labels = dict(
            date="业务日期",
            value="主要数值",
            segment=dataset["segment"],
            category="分类维度",
            entity="稳定记录 / 客户标识",
            aux="辅助数值",
            **dataset["extras"],
        )
        if not recipe.get("temporal", True):
            labels.update(
                scope=recipe.get("scope_label", "数据范围"), period="样本组 / 观察阶段"
            )
        if dataset["grain"] == "order":
            labels["record_id"] = "唯一订单编号"
        return [
            dict(
                id=key,
                label=label,
                required=key != "date" or recipe.get("temporal", True),
                hint=label + "，使用实际存在的字段",
            )
            for key, label in labels.items()
        ]
    count = template_id in (
        "store-coverage",
        "olist-orders",
        "olist-delivery",
        "northwind-customers",
    )
    return [
        {
            "id": "date",
            "label": "业务日期",
            "required": True,
            "hint": "订单日期或销售日期",
        },
        {
            "id": "value",
            "label": "金额",
            "required": not count,
            "hint": "每条明细的金额，按所填单位累计",
        },
        {
            "id": "segment",
            "label": "筛选维度",
            "required": True,
            "hint": "门店、国家、状态或支付方式",
        },
        {
            "id": "category",
            "label": "分类维度",
            "required": True,
            "hint": "品类、门店、地区或客户名称",
        },
        {
            "id": "entity",
            "label": "稳定客户标识",
            "required": template_id == "northwind-customers",
            "hint": "同一客户的所有订单必须使用同一标识",
        },
        {
            "id": "aux",
            "label": (
                "交付偏差（天）" if template_id == "olist-delivery" else "订单净金额"
            ),
            "required": template_id in ("northwind-freight", "olist-delivery"),
            "hint": "交付分析：实际送达日期减预计日期的天数；物流分析：每笔订单净金额",
        },
        {
            "id": "record_id",
            "label": "唯一订单编号",
            "required": required_grain(template_id) == "order",
            "hint": "验证每条记录对应一笔订单，避免重复计算",
        },
    ]


def inspect_source(service, source, actor, template_id, *, allow_any_dialect=False):
    from .catalog import TEMPLATES

    if template_id not in {t["id"] for t in TEMPLATES}:
        raise ValueError("模板不存在")
    if service.authorization is not None:
        service.authorization.require_data_sources(service._owner(actor), [source])
    connector = service.query_executor._get_connector(source)
    dialect = service.query_executor._dialect(connector)
    # CSV/XLS uploads and the installed example sources use SQLite. Other
    # connectors remain available to AI analysis, never silently transliterated.
    if not allow_any_dialect and dialect not in ("sqlite", "sqlite3"):
        raise ValueError(
            (
                "模板字段适配当前支持 SQLite 数据库及上传的数据表"
                "；此连接器尚未验证，请使用数据助理分析或先导入数"
                "据表。"
            )
        )
    tables = []
    for table in connector.get_table_names():
        try:
            fields = connector.get_fields(table, source)
        except TypeError:
            fields = connector.get_fields(table)
        tables.append(
            {
                "name": str(table),
                "columns": [
                    {
                        "name": (
                            str(f.get("name", ""))
                            if isinstance(f, dict)
                            else service.query_executor._column_name(f)
                        ),
                        "type": str(
                            f.get("type", "")
                            if isinstance(f, dict)
                            else f[1]
                            if len(f) > 1
                            else ""
                        ),
                    }
                    for f in fields
                ],
            }
        )
    names = {t["name"].lower() for t in tables}
    recipe = get_recipe(template_id)
    source_template = recipe["base"] if recipe and recipe["base"] else template_id
    required = {
        "retail": {"walmart_sales"},
        "olist": {"olist_orders", "olist_customers"}
        | ({"olist_order_payments"} if source_template == "olist-payments" else set()),
        "northwind": {"orders", "customers"}
        | (
            {"order_details", "products", "categories"}
            if source_template == "northwind-revenue"
            else {"order_details"}
            if source_template == "northwind-freight"
            else set()
        ),
        "extended": set(),
    }[template_family(template_id)]
    recipe = get_recipe(template_id)
    if recipe and not recipe["base"]:
        dataset = DATASETS[recipe["dataset"]]
        required = dataset.get("required", {dataset["table"]})
    builtin = dialect in ("sqlite", "sqlite3") and required.issubset(names)
    if (
        builtin
        and recipe
        and not recipe["base"]
        and DATASETS[recipe["dataset"]]["table"] == "facts"
    ):
        expected = {
            "event_date",
            "period",
            "year",
            "segment",
            "category",
            "entity",
            "value",
            "aux",
            *DATASETS[recipe["dataset"]]["extras"],
        }
        builtin = any(
            t["name"] == "facts"
            and expected.issubset({c["name"] for c in t["columns"]})
            for t in tables
        )
    return {
        "data_source_id": source,
        "dialect": dialect,
        "tables": tables,
        "roles": field_roles(template_id),
        "grain": required_grain(template_id),
        "builtin_available": builtin,
    }


def validate_mapping(service, source, actor, template_id, mapping):
    info = inspect_source(service, source, actor, template_id)
    if mapping is None:
        if not info["builtin_available"]:
            raise ValueError(
                "此数据库需要字段匹配。请选择明细表，匹配日期、数值与分类字段后预览。"
            )
        return info
    tables = {t["name"]: {c["name"] for c in t["columns"]} for t in info["tables"]}

    def check(field):
        if field.table not in tables or field.column not in tables[field.table]:
            raise ValueError("映射字段不存在：" + field.table + "." + field.column)

    if mapping.table not in tables:
        raise ValueError("请选择存在的明细表")
    if mapping.grain != info["grain"]:
        raise ValueError("明细粒度与模板要求不一致，请先整理数据粒度")
    required = {r["id"] for r in info["roles"] if r["required"]}
    if not required.issubset(mapping.fields):
        labels = [
            r["label"]
            for r in info["roles"]
            if r["id"] in required - mapping.fields.keys()
        ]
        raise ValueError("尚未匹配：" + "、".join(labels))
    if set(mapping.fields) - {r["id"] for r in info["roles"]}:
        raise ValueError("包含不支持的字段角色")
    available = {mapping.table}
    connector = service.query_executor._get_connector(source)
    for join in mapping.joins:
        check(join.left)
        check(SourceField(table=join.table, column=join.right_column))
        if join.left.table not in available or join.table in available:
            raise ValueError("关联应从已选择的表指向另一张表，不能重复或循环关联")
        q = identifier(join.right_column)
        sql = (
            f"SELECT {q}, COUNT(*) AS matches FROM "
            f"{identifier(join.table)} WHERE {q} IS NOT NULL G"
            f"ROUP BY {q} HAVING COUNT(*) > 1 LIMIT 1"
        )
        _, rows = connector.query_ex(sql, timeout=30)
        if rows:
            raise ValueError(
                (
                    f"关联表 {join.table} 的 {join.right_column} 不唯"
                    f"一，会重复计算；请使用唯一键或先汇总关联表。"
                )
            )
        available.add(join.table)
    for field in mapping.fields.values():
        check(field)
        if field.table not in available:
            raise ValueError("字段来自尚未关联的数据表：" + field.table)
    return info


def source_facts(template_id, mapping: Optional[TemplateSourceMapping] = None):
    """Return one SQL relation with an explicit business grain."""
    recipe = get_recipe(template_id)
    if recipe and recipe["base"]:
        return source_facts(recipe["base"], mapping)
    if recipe and mapping is None:
        return DATASETS[recipe["dataset"]]["facts"]
    if mapping is not None:

        def f(role, default="NULL"):
            field = mapping.fields.get(role)
            return (
                f"{identifier(field.table)}.{identifier(field.column)}"
                if field
                else default
            )

        date = f("date")
        date = (
            f"date(substr({date},7,4)||'-'||substr({date},4,2)||'-'||substr({date},1,2))"
            if mapping.date_format == "dmy"
            else f"date({date})"
        )
        count = template_id in (
            "store-coverage",
            "olist-orders",
            "olist-delivery",
            "northwind-customers",
        )
        value = "1.0" if count else f("value")
        sql_from = identifier(mapping.table)
        for join in mapping.joins:
            sql_from += (
                f" LEFT JOIN {identifier(join.table)} ON "
                f"{identifier(join.left.table)}."
                f"{identifier(join.left.column)}="
                f"{identifier(join.table)}."
                f"{identifier(join.right_column)}"
            )
        extras = ""
        if recipe:
            extras = (
                ","
                + ",".join(
                    f"{f(key)} AS {identifier(key)}"
                    for key in DATASETS[recipe["dataset"]]["extras"]
                )
                if DATASETS[recipe["dataset"]]["extras"]
                else ""
            )
            extras += (
                f",substr({date},1,4) AS year,substr({date},1,7) AS period"
                if recipe.get("temporal", True)
                else (
                    f",CAST({f('scope')} AS TEXT) AS year,CAST("
                    f"{f('period')} AS TEXT) AS period"
                )
            )
        return (
            f"SELECT {date} AS event_date, CAST({f('segment')}"
            f" AS TEXT) AS segment, CAST({f('category')} AS TE"
            f"XT) AS category, {value} AS value, CAST("
            f"{f('entity')} AS TEXT) AS entity, {f('aux')} AS "
            f"aux,CAST({f('record_id')} AS TEXT) AS record_id"
            f"{extras} FROM {sql_from}"
        )
    if template_family(template_id) == "retail":
        date = "date(substr(Date,7,4)||'-'||substr(Date,4,2)||'-'||substr(Date,1,2))"
        holiday = "CASE Holiday_Flag WHEN 1 THEN '节假日' ELSE '普通周' END"
        segment, category = (
            ("CAST(Store AS TEXT)", holiday)
            if template_id == "retail-overview"
            else (holiday, "CAST(Store AS TEXT)")
        )
        value = "1.0" if template_id == "store-coverage" else "Weekly_Sales"
        return (
            f"SELECT {date} AS event_date,{segment} AS segment"
            f",{category} AS category,{value} AS value,CAST(St"
            f"ore AS TEXT) AS entity,Weekly_Sales AS aux FROM "
            f"walmart_sales"
        )
    if template_family(template_id) == "olist":
        base = "olist_orders o JOIN olist_customers c ON o.customer_id=c.customer_id"
        segment, category, value, aux = (
            "c.customer_state",
            "o.order_status",
            "1.0",
            "NULL",
        )
        if template_id == "olist-payments":
            base += " JOIN olist_order_payments p ON o.order_id=p.order_id"
            segment, value = "p.payment_type", "p.payment_value"
        elif template_id == "olist-delivery":
            segment, category = "o.order_status", "c.customer_state"
            aux = (
                "julianday(o.order_delivered_customer_date)-julia"
                "nday(o.order_estimated_delivery_date)"
            )
        return (
            f"SELECT date(o.order_purchase_timestamp) AS event"
            f"_date,{segment} AS segment,{category} AS categor"
            f"y,{value} AS value,c.customer_unique_id AS entit"
            f"y,{aux} AS aux FROM {base}"
        )
    base = "orders o JOIN customers c ON o.customerID=c.customerID"
    value, category, aux = "1.0", "c.companyName", "NULL"
    if template_id == "northwind-revenue":
        base += (
            " JOIN order_details d ON o.orderID=d.orderID JOI"
            "N products p ON d.productID=p.productID JOIN cat"
            "egories cat ON p.categoryID=cat.categoryID"
        )
        value, category, aux = (
            "d.unitPrice*d.quantity*(1-d.discount)",
            "cat.categoryName",
            "d.quantity",
        )
    elif template_id == "northwind-freight":
        value, category = "o.freight", "CAST(o.shipVia AS TEXT)"
        aux = (
            "(SELECT SUM(d.unitPrice*d.quantity*(1-d.discount"
            ")) FROM order_details d WHERE d.orderID=o.orderI"
            "D)"
        )
    return (
        f"SELECT date(o.orderDate) AS event_date,o.shipCou"
        f"ntry AS segment,{category} AS category,{value} A"
        f"S value,CAST(o.customerID AS TEXT) AS entity,"
        f"{aux} AS aux FROM {base}"
    )


def normalized_facts(template_id, mapping=None):
    recipe = get_recipe(template_id)
    if recipe and not recipe["base"]:
        return source_facts(template_id, mapping)
    return (
        f"SELECT event_date,substr(event_date,1,7) AS peri"
        f"od,substr(event_date,1,4) AS year,COALESCE(segme"
        f"nt,'未分类') AS segment,COALESCE(category,'未分"
        f"类') AS category,value,entity,aux FROM ("
        f"{source_facts(template_id, mapping)}) source_fac"
        f"ts"
    )
