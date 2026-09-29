"""Source-preserving visual identities for the template gallery.

Applied only when composing a new template, never by migrating saved dashboards.
"""

# Each business family has a distinct accent, composition and visual weight.
IDENTITIES = {
    "retail-overview": (
        "clarity",
        "light",
        "#365C9B",
        ["#365C9B", "#B6834C", "#748DA2", "#72917C"],
        "quiet",
    ),
    "holiday-sales": (
        "warm",
        "light",
        "#AE483C",
        ["#AE483C", "#A48349", "#5F9389", "#BD7667"],
        "solid",
    ),
    "store-coverage": (
        "ocean",
        "light",
        "#237D78",
        ["#237D78", "#62978F", "#9C8B5A", "#768DA7"],
        "quiet",
    ),
    "olist-delivery": (
        "warm",
        "light",
        "#B26532",
        ["#B26532", "#708F7F", "#A4835D", "#7588A9"],
        "quiet",
    ),
    "olist-payments": (
        "clarity",
        "light",
        "#3D6C7C",
        ["#3D6C7C", "#B3814F", "#728F89", "#9982A9"],
        "solid",
    ),
    "northwind-revenue": (
        "warm",
        "light",
        "#A34564",
        ["#A34564", "#AE7D67", "#649296", "#98865B"],
        "quiet",
    ),
    "northwind-customers": (
        "clarity",
        "light",
        "#756093",
        ["#756093", "#AA7D9B", "#6C909F", "#9D8A61"],
        "quiet",
    ),
    "northwind-freight": (
        "ocean",
        "light",
        "#21756D",
        ["#21756D", "#66948E", "#B3834C", "#7D88AF"],
        "quiet",
    ),
    "growth-map": (
        "clarity",
        "light",
        "#925369",
        ["#925369", "#AE7D91", "#6C9492", "#A8885C"],
        "quiet",
    ),
    "business-dossier": (
        "warm",
        "light",
        "#6E6248",
        ["#6E6248", "#A2865A", "#789183", "#9D7974"],
        "quiet",
    ),
    "sales-receipt": (
        "clarity",
        "light",
        "#4B535E",
        ["#4B535E", "#888C90", "#74887F", "#9F8867"],
        "quiet",
    ),
    "annual-story": (
        "ocean",
        "light",
        "#2C807E",
        ["#2C807E", "#73908C", "#B18553", "#997992"],
        "quiet",
    ),
    "executive-pulse": (
        "graphite",
        "dark",
        "#7CB0D4",
        ["#7CB0D4", "#E0BE78", "#90B9AA", "#B49ACB"],
        "quiet",
    ),
    "revenue-growth": (
        "warm",
        "light",
        "#B3553F",
        ["#B3553F", "#AD815D", "#658A83", "#9D838B"],
        "solid",
    ),
    "service-desk": (
        "graphite",
        "dark",
        "#72C6D0",
        ["#72C6D0", "#DCBA70", "#908ECC", "#D393A3"],
        "quiet",
    ),
    "customer-value": (
        "warm",
        "light",
        "#7D5976",
        ["#7D5976", "#A57F93", "#7D8E78", "#A0875A"],
        "quiet",
    ),
    "inventory-watch": (
        "clarity",
        "light",
        "#AC7830",
        ["#AC7830", "#9E8758", "#667F9C", "#6E9588"],
        "solid",
    ),
    "ecommerce-revenue": (
        "warm",
        "light",
        "#A04C72",
        ["#A04C72", "#B07889", "#497F93", "#A18851"],
        "quiet",
    ),
    "logistics-flow": (
        "ocean",
        "light",
        "#277DA0",
        ["#277DA0", "#6A929E", "#B58351", "#79907C"],
        "quiet",
    ),
    "support-operations": (
        "clarity",
        "light",
        "#6D7289",
        ["#6D7289", "#868998", "#689582", "#AA855E"],
        "quiet",
    ),
    "energy-monitor": (
        "clarity",
        "light",
        "#77852E",
        ["#77852E", "#8A8F57", "#477E83", "#AD8352"],
        "quiet",
    ),
    "manufacturing-quality": (
        "graphite",
        "dark",
        "#E9AA66",
        ["#E9AA66", "#91B8C9", "#9CB68A", "#C092A5"],
        "solid",
    ),
    "student-performance": (
        "warm",
        "light",
        "#8E5562",
        ["#8E5562", "#A48382", "#6F9183", "#9B8856"],
        "quiet",
    ),
}

LAYOUTS = {
    "revenue-growth": [
        (0, 0, 4, 5),
        (0, 5, 4, 3),
        (0, 8, 4, 3),
        (4, 0, 8, 11),
        (0, 11, 5, 9),
        (5, 11, 7, 9),
    ],
    "inventory-watch": [
        (0, 0, 3, 3),
        (0, 3, 3, 3),
        (0, 6, 3, 3),
        (0, 9, 3, 3),
        (3, 0, 9, 7),
        (3, 7, 9, 7),
        (0, 14, 12, 8),
    ],
    "ecommerce-revenue": [
        (0, 0, 4, 5),
        (4, 0, 4, 5),
        (8, 0, 4, 5),
        (0, 5, 7, 9),
        (7, 5, 5, 9),
        (0, 14, 12, 10),
    ],
    "student-performance": [
        (0, 0, 3, 3),
        (0, 3, 3, 3),
        (0, 6, 3, 3),
        (0, 9, 3, 3),
        (3, 0, 9, 7),
        (3, 7, 9, 7),
        (0, 14, 6, 3),
        (6, 14, 6, 3),
    ],
    "olist-payments": [
        (0, 0, 6, 3),
        (6, 0, 6, 3),
        (0, 3, 5, 9),
        (5, 3, 7, 9),
        (0, 12, 12, 8),
    ],
    "northwind-revenue": [
        (0, 0, 5, 5),
        (0, 5, 5, 10),
        (5, 0, 7, 8),
        (5, 8, 7, 7),
        (0, 15, 12, 7),
    ],
    "northwind-freight": [
        (0, 0, 4, 4),
        (4, 0, 8, 11),
        (0, 4, 4, 7),
        (0, 11, 5, 8),
        (5, 11, 7, 8),
    ],
}


def apply_catalog_identity(schema, template_id):
    identity = IDENTITIES.get(template_id)
    if not identity:
        return schema
    preset, mode, accent, palette, kpi = identity
    theme = schema["dashboard"]["theme"]
    theme.update(preset=preset, mode=mode)
    theme["overrides"] = {
        **theme.get("overrides", {}),
        "primary_color": accent,
        "chart_palette": palette,
        "kpi_style": kpi,
    }
    boxes = LAYOUTS.get(template_id)
    # Fail loudly if a composition is changed without updating its identity.
    if boxes:
        if len(boxes) != len(schema["layouts"]["desktop"]):
            raise ValueError(f"Template identity layout out of date: {template_id}")
        for layout, (x, y, w, h) in zip(schema["layouts"]["desktop"], boxes):
            layout.update(x=x, y=y, w=w, h=h)
    compatibility = schema.setdefault("metadata", {}).setdefault("compatibility", {})
    compatibility.update(catalog_template_id=template_id, catalog_visual_revision=2)
    return schema
