"""Reference-inspired layouts. Queries remain native editable dashboard widgets."""

from .catalog_research import (
    RESEARCH_DATASETS,
    RESEARCH_IDS,
    RESEARCH_RECIPES,
    research_composition,
)
from .catalog_showcase import (
    SHOWCASE_DATASETS,
    SHOWCASE_IDS,
    SHOWCASE_RECIPES,
    showcase_composition,
)

NORTHWIND = "upload_001_3a6ee8a2d1ad4a2a"
GALLERY = "https://ai-for-business-intelligence.org/variants/"


def recipe(key, title, category, base, style, description, reference, **options):
    return dict(
        id=key,
        title=title,
        category=category,
        base=base,
        style=style,
        description=description,
        reference=reference,
        **options,
    )


RECIPES = [
    recipe(
        "brand-revenue",
        "品牌营收驾驶舱",
        "销售",
        "northwind-revenue",
        "brand",
        (
            "品牌侧栏与场景主视觉，结合收入指标、全球市场地图"
            "、覆盖仪表盘和品类贡献。使用 Northwind 实际订单"
            "明细；不推算缺失的转化率或同比。"
        ),
        "用户提供的 PitchSide Pro 品牌经营驾驶舱参考图",
    ),
    recipe(
        "growth-map",
        "营收增长技能树",
        "经营",
        "northwind-revenue",
        "skill_tree",
        "从总收入展开到客户、市场和品类，沿分支逐层阅读经营结构。",
        GALLERY + "35-story-skill-tree-pro",
    ),
    recipe(
        "quarterly-timeline",
        "季度经营时间线",
        "销售",
        "retail-overview",
        "timeline",
        "按季度翻阅门店销售，年度总览与四季趋势采用分章布局。",
        GALLERY + "31-story-timeline",
    ),
    recipe(
        "business-dossier",
        "经营分析档案",
        "财务",
        "northwind-revenue",
        "dossier",
        "纸质档案与编号章节，依次核对收入、客户、品类和市场明细。",
        GALLERY + "36-story-declassified",
    ),
    recipe(
        "sales-receipt",
        "销售结算小票",
        "财务",
        "northwind-revenue",
        "receipt",
        "窄幅小票、虚线分隔与等宽数字，将收入和分类账表汇成一张凭条。",
        GALLERY + "40-story-receipt",
    ),
    recipe(
        "annual-story",
        "年度经营故事",
        "经营",
        "northwind-revenue",
        "story",
        "大标题引导的纵向长页，沿规模、节奏、品类和市场阅读数据。",
        GALLERY + "19-story-vertical",
    ),
    recipe(
        "retail-terminal",
        "零售数据终端",
        "销售",
        "retail-overview",
        "terminal",
        "深色终端、紧凑指标和密集账表，集中核查门店销售与时间变化。",
        GALLERY + "02-bloomberg-terminal",
    ),
    recipe(
        "executive-pulse",
        "管理层经营总览",
        "经营",
        "northwind-revenue",
        "executive",
        "深蓝经营总览，以收入主指标、市场覆盖和趋势分区观察经营规模。",
        "https://www.geckoboard.com/dashboard-examples/executive/",
    ),
    recipe(
        "service-desk",
        "IT 服务工单总览",
        "IT 服务",
        None,
        "monitor",
        "去重工单量、关闭比例、解决耗时及优先级分布；展示历史事件快照。",
        "https://www.geckoboard.com/dashboard-examples/itsm/",
        dataset="itsm",
    ),
    recipe(
        "revenue-growth",
        "营收驱动与增长",
        "销售",
        "northwind-revenue",
        "executive",
        "珊瑚色指标纵栏搭配收入趋势、品类排行与市场热力图，定位增长贡献。",
        "用户提供的行业参考图",
    ),
    recipe(
        "customer-value",
        "客户价值与复购",
        "客户",
        None,
        "editorial",
        "按订单金额、稳定客户标识和首购月份查看客户贡献与复购留存。",
        "用户提供的行业参考图",
        dataset="customer",
    ),
    recipe(
        "inventory-watch",
        "商品库存与补货",
        "供应链",
        None,
        "executive",
        "查看当前库存、在途商品和补货缺口，按供应商与商品分类筛选。",
        "用户提供的行业参考图",
        dataset="inventory",
        temporal=False,
        scope_label="品类",
    ),
    recipe(
        "ecommerce-revenue",
        "电商收入与履约",
        "电商",
        None,
        "monitor",
        "按订单汇总支付后计算回款，结合州分布、交付偏差与状态结构。",
        "用户提供的行业参考图",
        dataset="ecommerce",
    ),
    recipe(
        "logistics-flow",
        "物流交付追踪",
        "供应链",
        "olist-delivery",
        "monitor",
        "从订单状态到地区热力矩阵，跟踪实际送达相对预计日期的偏差。",
        "用户提供的行业参考图",
    ),
    recipe(
        "support-operations",
        "服务团队与 SLA 标记",
        "IT 服务",
        None,
        "editorial",
        "比较工单团队负载、重开次数与源系统 SLA 标记，保留清晰计算口径。",
        "https://www.geckoboard.com/dashboard-examples/itsm/",
        dataset="itsm",
    ),
    recipe(
        "energy-monitor",
        "住宅能耗监测",
        "能源",
        None,
        "executive",
        "电器与照明耗电、每日走势和小时分布，来自住宅每十分钟的实测数据。",
        "用户提供的行业参考图",
        dataset="energy",
        scope_label="月份",
    ),
    recipe(
        "manufacturing-quality",
        "制造故障与设备状态",
        "制造",
        None,
        "monitor",
        "观察故障占比、刀具磨损与转速；UCI 合成工业样本，样本组不是时间轴。",
        "用户提供的行业参考图",
        dataset="maintenance",
        temporal=False,
        scope_label="数据范围",
    ),
    recipe(
        "student-performance",
        "学生成绩与学习投入",
        "教育",
        None,
        "editorial",
        "两所中学的葡语课程成绩、缺课和学习时长；成绩满分 20，不推算毕业率。",
        "用户提供的行业参考图",
        dataset="students",
        temporal=False,
        scope_label="课程",
    ),
]

DATASETS = {
    "itsm": dict(
        source="sqlite_itsm",
        table="facts",
        grain="incident",
        unit="单",
        metric="去重工单",
        segment="优先级",
        extras={
            "sla_true": "源 SLA 为 True（0/100）",
            "reopen": "重开次数",
            "closed": "关闭标记（0/100）",
        },
        facts="SELECT * FROM facts",
        notes=(
            "UCI / Amaral、Fantinato、Peres（2018），CC BY 4.0。按工单取最后一次更"
            "新，解决时长只计非负已知值；made_sla=True 比例不等于自"
            "行定义的 SLA 达标率。https:/"
            "/doi.org/10.24432/C57S4H"
        ),
    ),
    "energy": dict(
        source="sqlite_energy",
        table="facts",
        grain="measurement",
        unit="kWh",
        metric="电器耗电",
        segment="日期类型",
        extras={"temperature": "室外温度（℃）"},
        facts="SELECT * FROM facts",
        notes=(
            "UCI / Candanedo（2017），CC BY 4.0。比利时一栋住宅2016年实测，Wh/1000"
            "=kWh；最后一天采样不完整。https://doi.org/10.24432/C5VC8G"
        ),
    ),
    "maintenance": dict(
        source="sqlite_maintenance",
        table="facts",
        grain="measurement",
        unit="条",
        metric="工业样本",
        segment="设备质量类型",
        extras={"wear": "刀具磨损（分钟）", "rpm": "转速（rpm）"},
        facts="SELECT * FROM facts",
        notes=(
            "UCI AI4I 2020 / Matzka，CC BY 4.0。合成数据；样本按编号每1000条分组，没有"
            "采集日期，不解释为时间趋势。https://doi.org/10.24432/C5HS5C"
        ),
    ),
    "students": dict(
        source="sqlite_students",
        table="facts",
        grain="student",
        unit="分",
        metric="期末成绩",
        segment="学校",
        extras={
            "first_grade": "第一阶段成绩",
            "second_grade": "第二阶段成绩",
            "pass_score": "成绩达10分（0/100）",
        },
        facts="SELECT * FROM facts",
        notes=(
            "UCI / Cortez（2008），CC BY 4.0。仅葡语649名学生，成绩"
            "范围0–20；不和数学记录"
            "相加。https://doi.org/10.24432/C5TG7T"
        ),
    ),
    "customer": dict(
        source=NORTHWIND,
        table="orders",
        grain="order",
        unit="美元",
        metric="商品净收入",
        segment="收货国家",
        extras={},
        required={"orders", "order_details", "customers"},
        facts=(
            "SELECT date(o.orderDate) AS event_date,substr(o.orderD"
            "ate,1,4) AS year,substr(o.orderDate,1,7) AS period,o.s"
            "hipCountry AS segment,c.companyName AS category,CAST(o"
            ".customerID AS TEXT) AS entity,CAST(o.orderID AS TEXT)"
            " AS record_id,1.0 AS value,(SELECT SUM(d.unitPrice*d.q"
            "uantity*(1-d.discount)) FROM order_details d WHERE d.o"
            "rderID=o.orderID) AS aux FROM orders o JOIN customers "
            "c ON o.customerID=c.customerID"
        ),
        notes="Northwind 示例订单；先按订单汇总扣折商品净收入，客户按"
        "稳定 ID 去重；复购观察截止于数据最后一笔订单。",
    ),
    "inventory": dict(
        source=NORTHWIND,
        table="products",
        grain="product",
        unit="件",
        metric="在库数量",
        segment="供应商编号",
        extras={"incoming": "在途数量", "shortage": "库存低于补货线的缺口"},
        required={"products", "categories"},
        facts=(
            "SELECT NULL AS event_date,c.categoryName AS year,'当前快照"
            "' AS period,CAST(p.supplierID AS TEXT) AS segment,p.pr"
            "oductName AS category,CAST(p.productID AS TEXT) AS ent"
            "ity,p.unitsInStock*1.0 AS value,p.unitPrice AS aux,p.u"
            "nitsOnOrder*1.0 AS incoming,MAX(p.reorderLevel-p.units"
            "InStock,0)*1.0 AS shortage FROM products p JOIN catego"
            "ries c ON p.categoryID=c.categoryID WHERE p.discontinu"
            "ed=0"
        ),
        notes=(
            "Northwind 当前商品快照，排除 discontinued=1；补货缺口=max(reorderLev"
            "el-unitsInStock,0)，不冒充销量或库存历史。"
        ),
    ),
    "ecommerce": dict(
        source="olist_ecommerce_demo",
        table="olist_orders",
        grain="order",
        unit="巴西雷亚尔",
        metric="回款金额",
        segment="客户所在州",
        extras={},
        required={"olist_orders", "olist_customers", "olist_order_payments"},
        facts=(
            "SELECT date(o.order_purchase_timestamp) AS event_date,"
            "substr(o.order_purchase_timestamp,1,4) AS year,substr("
            "o.order_purchase_timestamp,1,7) AS period,c.customer_s"
            "tate AS segment,o.order_status AS category,o.order_id "
            "AS record_id,o.order_id AS entity,COALESCE(p.amount,0)"
            " AS value,julianday(o.order_delivered_customer_date)-j"
            "ulianday(o.order_estimated_delivery_date) AS aux FROM "
            "olist_orders o JOIN olist_customers c ON o.customer_id"
            "=c.customer_id LEFT JOIN (SELECT order_id,SUM(payment_"
            "value) AS amount FROM olist_order_payments GROUP BY or"
            "der_id) p ON p.order_id=o.order_id"
        ),
        notes="Olist 历史订单，支付先按 order_id 汇总避免重复计算；负"
        "交付偏差代表提前，缺失送达日期不计平均。",
    ),
}


RECIPES.extend(SHOWCASE_RECIPES)
DATASETS.update(SHOWCASE_DATASETS)
RECIPES.extend(RESEARCH_RECIPES)
DATASETS.update(RESEARCH_DATASETS)


def get_recipe(template_id):
    return next((r for r in RECIPES if r["id"] == template_id), None)


def extend_catalog(existing):
    indexed = {t["id"]: t for t in existing}
    for r in RECIPES:
        data = DATASETS.get(r.get("dataset"), {})
        base = indexed.get(r["base"], {})
        overrides = dict(
            card_radius=3
            if r["style"]
            in ("terminal", "dossier", "receipt", "command", "clinical", "rural")
            else 16,
            card_shadow="none",
            density="compact"
            if r["style"]
            in (
                "terminal",
                "monitor",
                "receipt",
                "command",
                "clinical",
                "rural",
                "voice_observatory",
            )
            else "comfortable",
            kpi_style="solid" if r["style"] in ("executive", "monitor") else "quiet",
        )
        yield {
            **base,
            **{
                k: data[k] for k in ("source", "unit", "metric", "segment") if k in data
            },
            **r,
            "theme": "graphite"
            if r["style"]
            in (
                "terminal",
                "monitor",
                "timeline",
                "command",
                "clinical",
                "rural",
                "voice_observatory",
            )
            else "warm"
            if r["style"] in ("dossier", "receipt", "marketing")
            else "ocean"
            if r["style"] in ("executive", "brand")
            else "clarity",
            "mode": "dark"
            if r["style"]
            in (
                "terminal",
                "monitor",
                "timeline",
                "command",
                "clinical",
                "rural",
                "voice_observatory",
            )
            else "light",
            "overrides": overrides,
        }


def extended_composition(template):
    if template["id"] in RESEARCH_IDS:
        return research_composition(template)
    if template["id"] in SHOWCASE_IDS:
        return showcase_composition(template)

    from .catalog_layouts import spec

    key, unit = template["id"], template["unit"]

    def w(key, title, viz, dims=(), field="value", agg="sum", unit_=None, limit=120):
        return spec(key, title, viz, dims, field, agg, unit_ or unit, limit)

    total = w("total", template["metric"], "kpi")
    trend = w("trend", "收入月度趋势", "area", ("period",), limit=240)
    ranking = w("ranking", "品类收入 · Top 8", "bar", ("category",), limit=8)
    markets = w("markets", "市场收入 · Top 10", "bar", ("segment",), limit=10)
    customers = w(
        "customers", "下单客户", "kpi", field="entity", agg="count_distinct", unit_="位"
    )
    regions = w(
        "regions", "覆盖市场", "kpi", field="segment", agg="count_distinct", unit_="个"
    )
    if key == "brand-revenue":
        items = [
            {**total, "id": "hero"},
            customers,
            regions,
            w("units", "销售件数", "kpi", field="aux", unit_="件"),
            w(
                "months",
                "有销售月份",
                "kpi",
                field="period",
                agg="count_distinct",
                unit_="个月",
            ),
            w("average", "平均明细净额", "kpi", agg="average"),
            w(
                "categories",
                "在售品类",
                "kpi",
                field="category",
                agg="count_distinct",
                unit_="类",
            ),
            w("world", "全球市场 · 商品净收入", "geo_map", ("segment",), limit=250),
            w(
                "coverage",
                "市场覆盖范围",
                "gauge",
                field="segment",
                agg="count_distinct",
                unit_="个",
            ),
            {
                **w(
                    "activity",
                    "最近日期 · 市场收入",
                    "table",
                    ("event_date", "segment"),
                    limit=12,
                ),
                "newest": True,
            },
            w("contribution", "品类收入贡献", "treemap", ("category",), limit=100),
            trend,
        ]
        boxes = [
            (0, 0, 5, 6),
            (5, 0, 3, 3),
            (8, 0, 2, 3),
            (10, 0, 2, 3),
            (5, 3, 3, 3),
            (8, 3, 2, 3),
            (10, 3, 2, 3),
            (0, 6, 6, 8),
            (6, 6, 3, 8),
            (9, 6, 3, 8),
            (0, 14, 5, 8),
            (5, 14, 7, 8),
        ]
    elif key == "growth-map":
        items = [total, customers, regions, ranking, markets, trend]
        boxes = [
            (4, 0, 4, 3),
            (1, 4, 4, 3),
            (7, 4, 4, 3),
            (0, 8, 6, 8),
            (6, 8, 6, 8),
            (0, 17, 12, 8),
        ]
    elif key == "quarterly-timeline":
        items = [total] + [
            w(f"q{q}", f"第 {q} 季度 · 月度销售", "area", ("period",), limit=240)
            for q in range(1, 5)
        ]
        for q, item in enumerate(items[1:], 1):
            item["where"] = (
                "CAST(substr(period,6,2) AS INTEGER) BETWEEN "
                f"{(q - 1) * 3 + 1} AND {q * 3}"
            )
        boxes = [(0, 0, 12, 3)] + [(0, 3 + q * 9, 12, 8) for q in range(4)]
    elif key == "business-dossier":
        items = [
            total,
            customers,
            w("ledger", "01 / 品类核查账表", "table", ("category",), limit=40),
            w("market_ledger", "02 / 市场核查账表", "table", ("segment",), limit=40),
            trend,
        ]
        boxes = [
            (0, 0, 8, 3),
            (8, 0, 4, 3),
            (0, 3, 12, 8),
            (0, 11, 12, 9),
            (0, 20, 12, 8),
        ]
    elif key == "sales-receipt":
        items = [
            total,
            w("categories", "品类小计", "table", ("category",), limit=30),
            w("markets", "市场小计", "table", ("segment",), limit=50),
            customers,
        ]
        boxes = [(0, 0, 12, 3), (0, 3, 12, 8), (0, 11, 12, 12), (0, 23, 12, 3)]
    elif key == "annual-story":
        items = [total, customers, regions, trend, ranking, markets]
        boxes = [
            (0, 0, 4, 3),
            (4, 0, 4, 3),
            (8, 0, 4, 3),
            (0, 4, 12, 9),
            (0, 14, 12, 8),
            (0, 23, 12, 8),
        ]
    elif key == "retail-terminal":
        items = [
            total,
            w(
                "stores",
                "门店",
                "kpi",
                field="segment",
                agg="count_distinct",
                unit_="家",
            ),
            w("average", "店周均值", "kpi", agg="average"),
            w(
                "months",
                "月份",
                "kpi",
                field="period",
                agg="count_distinct",
                unit_="个",
            ),
            w("ledger", "月度销售流水", "table", ("period",), limit=240),
            w("store_ledger", "门店排行 · Top 12", "table", ("segment",), limit=12),
            w("holiday", "周类型构成", "column", ("category",)),
            w("trend", "全时段销售趋势", "area", ("period",), limit=240),
        ]
        boxes = [
            (0, 0, 3, 3),
            (3, 0, 3, 3),
            (6, 0, 3, 3),
            (9, 0, 3, 3),
            (0, 3, 5, 9),
            (5, 3, 4, 9),
            (9, 3, 3, 9),
            (0, 12, 12, 7),
        ]
    elif key in ("executive-pulse", "revenue-growth"):
        items = [
            total,
            customers,
            regions,
            trend,
            ranking,
            w(
                "matrix",
                "国家与品类收入",
                "heatmap",
                ("segment", "category"),
                limit=5000,
            ),
        ]
        boxes = (
            [
                (0, 0, 6, 5),
                (6, 0, 3, 5),
                (9, 0, 3, 5),
                (0, 5, 8, 8),
                (8, 5, 4, 8),
                (0, 13, 12, 9),
            ]
            if key == "executive-pulse"
            else [
                (0, 0, 4, 4),
                (4, 0, 4, 4),
                (8, 0, 4, 4),
                (0, 4, 12, 8),
                (0, 12, 5, 9),
                (5, 12, 7, 9),
            ]
        )
    elif key in ("service-desk", "support-operations"):
        items = [
            total,
            w("hours", "平均解决耗时", "kpi", field="aux", agg="average", unit_="小时"),
            w(
                "closed",
                "最后状态为关闭",
                "kpi",
                field="closed",
                agg="average",
                unit_="%",
            ),
            w(
                "sla",
                "SLA 标记为 True",
                "kpi",
                field="sla_true",
                agg="average",
                unit_="%",
            ),
            w("trend", "按开单月份统计工单", "line", ("period",), unit_="单"),
            w("priority", "优先级工单分布", "donut", ("segment",), unit_="单"),
            w("teams", "团队负载 · Top 10", "bar", ("category",), unit_="单", limit=10),
            w(
                "reopen",
                "各优先级平均重开次数",
                "column",
                ("segment",),
                field="reopen",
                agg="average",
                unit_="次",
            ),
        ]
        boxes = [(i * 3, 0, 3, 3) for i in range(4)] + [
            (0, 3, 8, 8),
            (8, 3, 4, 8),
            (0, 11, 6, 8),
            (6, 11, 6, 8),
        ]
        if key == "support-operations":
            boxes = [
                (0, 0, 3, 3),
                (3, 0, 3, 3),
                (0, 3, 3, 3),
                (3, 3, 3, 3),
                (6, 0, 6, 8),
                (0, 6, 6, 8),
                (6, 8, 6, 8),
                (0, 14, 6, 8),
            ]
    elif key == "customer-value":
        items = [
            w("revenue", "客户商品净收入", "kpi", field="aux"),
            customers,
            w("orders", "订单总数", "kpi", unit_="单"),
            w(
                "ranking",
                "客户收入 · Top 10",
                "bar",
                ("category",),
                field="aux",
                limit=10,
            ),
            w("cohort", "首购与复购留存", "cohort", unit_="月", limit=5000),
        ]
        boxes = [(0, 0, 5, 3), (5, 0, 3, 3), (8, 0, 4, 3), (0, 3, 4, 11), (4, 3, 8, 11)]
    elif key == "inventory-watch":
        items = [
            total,
            w("incoming", "在途数量", "kpi", field="incoming"),
            w("shortage", "低于补货线缺口", "kpi", field="shortage"),
            w(
                "products",
                "在售商品",
                "kpi",
                field="entity",
                agg="count_distinct",
                unit_="种",
            ),
            w("stock", "商品在库 · Top 10", "bar", ("category",), limit=10),
            w(
                "restock",
                "补货缺口 · Top 10",
                "bar",
                ("category",),
                field="shortage",
                limit=10,
            ),
            w("suppliers", "供应商库存", "table", ("segment",), limit=100),
        ]
        boxes = [(i * 3, 0, 3, 3) for i in range(4)] + [
            (0, 3, 6, 9),
            (6, 3, 6, 9),
            (0, 12, 12, 8),
        ]
    elif key == "ecommerce-revenue":
        items = [
            total,
            w("orders", "订单数", "kpi", field="entity", agg="count", unit_="单"),
            w("average", "每单平均回款", "kpi", agg="average"),
            trend,
            w("status", "订单状态下的回款", "donut", ("category",), limit=12),
            w("regions", "各州月度回款", "heatmap", ("segment", "period"), limit=5000),
        ]
        boxes = [
            (0, 0, 6, 4),
            (6, 0, 3, 4),
            (9, 0, 3, 4),
            (0, 4, 8, 8),
            (8, 4, 4, 8),
            (0, 12, 12, 10),
        ]
    elif key == "logistics-flow":
        items = [
            total,
            w("delay", "平均交付偏差", "kpi", field="aux", agg="average", unit_="天"),
            w("flow", "订单状态", "bar", ("segment",), unit_="单", limit=12),
            w(
                "trend",
                "按下单月份的平均交付偏差",
                "line",
                ("period",),
                field="aux",
                agg="average",
                unit_="天",
            ),
            w(
                "matrix",
                "地区与订单状态",
                "heatmap",
                ("category", "segment"),
                unit_="单",
                limit=5000,
            ),
        ]
        boxes = [
            (0, 0, 3, 3),
            (3, 0, 3, 3),
            (0, 3, 6, 8),
            (6, 0, 6, 11),
            (0, 11, 12, 9),
        ]
    elif key == "energy-monitor":
        items = [
            total,
            w("lighting", "照明耗电", "kpi", field="aux"),
            w(
                "days",
                "采样日期",
                "kpi",
                field="period",
                agg="count_distinct",
                unit_="天",
            ),
            w("trend", "每日电器耗电", "area", ("period",), limit=240),
            w(
                "hours",
                "每十分钟平均耗电 · 按小时",
                "column",
                ("category",),
                agg="average",
                limit=24,
            ),
            w(
                "heatmap",
                "日期类型与小时耗电",
                "heatmap",
                ("segment", "category"),
                limit=100,
            ),
        ]
        boxes = [
            (0, 0, 4, 3),
            (4, 0, 4, 3),
            (8, 0, 4, 3),
            (0, 3, 12, 8),
            (0, 11, 7, 8),
            (7, 11, 5, 8),
        ]
    elif key == "manufacturing-quality":
        items = [
            total,
            w("failure", "故障样本占比", "kpi", field="aux", agg="average", unit_="%"),
            w("wear", "平均刀具磨损", "kpi", field="wear", agg="average", unit_="分钟"),
            w("rpm", "平均转速", "kpi", field="rpm", agg="average", unit_="rpm"),
            w(
                "batch",
                "按样本编号分组的故障占比",
                "column",
                ("period",),
                field="aux",
                agg="average",
                unit_="%",
                limit=10,
            ),
            w(
                "types",
                "各设备类型故障占比",
                "bar",
                ("segment",),
                field="aux",
                agg="average",
                unit_="%",
            ),
            w("states", "样本状态", "donut", ("category",), unit_="条"),
        ]
        boxes = [(i * 3, 0, 3, 3) for i in range(4)] + [
            (0, 3, 8, 8),
            (8, 3, 4, 8),
            (0, 11, 12, 7),
        ]
    else:
        items = [
            w(
                "students",
                "课程学生",
                "kpi",
                field="entity",
                agg="count_distinct",
                unit_="名",
            ),
            w("grade", "期末平均成绩 / 20", "kpi", agg="average"),
            w(
                "pass",
                "期末成绩达到 10 分",
                "kpi",
                field="pass_score",
                agg="average",
                unit_="%",
            ),
            w(
                "absences",
                "平均缺课次数",
                "kpi",
                field="aux",
                agg="average",
                unit_="次",
            ),
            w(
                "study",
                "学习时长与期末平均成绩",
                "column",
                ("category",),
                agg="average",
            ),
            w("schools", "学校平均成绩", "bar", ("segment",), agg="average"),
            w("first", "第一阶段平均成绩", "kpi", field="first_grade", agg="average"),
            w("second", "第二阶段平均成绩", "kpi", field="second_grade", agg="average"),
        ]
        boxes = [(i * 3, 0, 3, 3) for i in range(4)] + [
            (0, 3, 8, 9),
            (8, 3, 4, 9),
            (0, 12, 6, 3),
            (6, 12, 6, 3),
        ]
    return items, [
        dict(widget_id=item["id"], x=x, y=y, w=width, h=height)
        for item, (x, y, width, height) in zip(items, boxes)
    ]
