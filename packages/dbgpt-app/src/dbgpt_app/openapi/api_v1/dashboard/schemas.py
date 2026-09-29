"""Dashboard Schema v1 and API contracts.

The schema is intentionally independent from chart rendering libraries.  It is the
contract shared by the planner, persistence layer, REST API, and web editor.
"""

import json
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .release_features import layout_templates_enabled

_EMPTY_FILTER_PARAMETER_MESSAGE = (
    "A filter mapping must define at least one SQL parameter."
)
SUPPORTED_SCHEMA_VERSIONS = ("1.0", "1.1", "1.2", "1.3", "1.4")
MAX_DASHBOARD_SCHEMA_BYTES = 2 * 1024 * 1024
MAX_QUERY_PARAMETER_BYTES = 64 * 1024
_NAMED_SQL_PARAMETER = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_CANONICAL_THEME_PRESETS = {"clarity", "ocean", "warm", "graphite"}
_THEME_CARD_COLORS = {
    ("clarity", "light"): "#FFFFFF",
    ("clarity", "dark"): "#152235",
    ("ocean", "light"): "#FFFFFF",
    ("ocean", "dark"): "#102735",
    ("warm", "light"): "#FFFCF8",
    ("warm", "dark"): "#2B211C",
    ("graphite", "light"): "#FCFCFD",
    ("graphite", "dark"): "#1B1E24",
}
_THEME_CHART_PALETTES = {
    ("clarity", "light"): [
        "#1D5FD1",
        "#087A72",
        "#7B4BA8",
        "#A64B2A",
        "#7A6500",
        "#B02E62",
    ],
    ("clarity", "dark"): [
        "#78A9FF",
        "#45C8BE",
        "#D8A0F0",
        "#FF9B7A",
        "#E8CD57",
        "#83C95B",
    ],
    ("ocean", "light"): [
        "#0068A8",
        "#007A77",
        "#7251A3",
        "#A65300",
        "#7C6900",
        "#B5385D",
    ],
    ("ocean", "dark"): [
        "#67B8E8",
        "#43C6C1",
        "#BDA5E8",
        "#F2A466",
        "#D7CE64",
        "#F18BAA",
    ],
    ("warm", "light"): [
        "#9F4F2F",
        "#126E82",
        "#744FA1",
        "#8A6512",
        "#AD3D60",
        "#34745B",
    ],
    ("warm", "dark"): [
        "#F0A17C",
        "#65C0D0",
        "#C3A6E8",
        "#E9C46A",
        "#F08CAB",
        "#77C4A0",
    ],
    ("graphite", "light"): [
        "#4056B4",
        "#00777E",
        "#8B4678",
        "#9A5700",
        "#637000",
        "#6C4A96",
    ],
    ("graphite", "dark"): [
        "#91A0FF",
        "#46C7BE",
        "#E59BC8",
        "#F5A45D",
        "#C9D66B",
        "#B39DDB",
    ],
}
_COLOR_VISION_MATRICES = (
    (
        (0.56667, 0.43333, 0.0),
        (0.55833, 0.44167, 0.0),
        (0.0, 0.24167, 0.75833),
    ),
    (
        (0.625, 0.375, 0.0),
        (0.7, 0.3, 0.0),
        (0.0, 0.3, 0.7),
    ),
)


class StrictModel(BaseModel):
    """Reject unknown fields so model output cannot silently change the contract."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, protected_namespaces=()
    )


class WidgetType(str, Enum):
    KPI = "kpi"
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    TABLE = "table"


class FilterType(str, Enum):
    DATE_RANGE = "date_range"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    TEXT = "text"
    NUMBER_RANGE = "number_range"


class DashboardStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DashboardThemePreset(str, Enum):
    """Visual theme ids stored with the dashboard contract.

    ``clean`` and ``business_blue`` are accepted only for historical schemas.
    New Schema 1.4 documents use one of the four neutral canonical names.
    """

    CLARITY = "clarity"
    OCEAN = "ocean"
    WARM = "warm"
    GRAPHITE = "graphite"
    CLEAN = "clean"
    BUSINESS_BLUE = "business_blue"


class DashboardThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"


class DashboardThemeFontScale(str, Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    LARGE = "large"


class DashboardThemeDensity(str, Enum):
    COMPACT = "compact"
    COMFORTABLE = "comfortable"
    SPACIOUS = "spacious"


class DashboardThemeShadow(str, Enum):
    NONE = "none"
    SOFT = "soft"
    ELEVATED = "elevated"


class DashboardThemeKpiStyle(str, Enum):
    QUIET = "quiet"
    ACCENT = "accent"
    SOLID = "solid"


class DashboardThemeTableStyle(str, Enum):
    PLAIN = "plain"
    STRIPED = "striped"
    DIVIDED = "divided"


class DashboardOrigin(str, Enum):
    TASK = "task"
    MANUAL = "manual"
    TEMPLATE = "template"


class DashboardAssetState(str, Enum):
    GENERATED = "generated"
    SAVED = "saved"


class DashboardRole(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


class DashboardAction(str, Enum):
    VIEW = "view"
    EDIT = "edit"
    QUERY = "query"
    PUBLISH = "publish"
    MANAGE_ACCESS = "manage_access"
    MANAGE_SCHEDULE = "manage_schedule"


class DashboardPatchOp(str, Enum):
    ADD = "add"
    REPLACE = "replace"
    REMOVE = "remove"


class DashboardVisualization(str, Enum):
    """Presentation variants supported by the shared Dashboard renderer.

    ``WidgetType`` remains the stable query/data contract.  This enum only
    controls presentation so existing Schema 1.0-1.2 documents remain valid.
    """

    KPI = "kpi"
    LINE = "line"
    AREA = "area"
    COLUMN = "column"
    BAR = "bar"
    STACKED_COLUMN = "stacked_column"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    DUAL_AXIS = "dual_axis"
    HEATMAP = "heatmap"
    COHORT = "cohort"
    GAUGE = "gauge"
    FUNNEL = "funnel"
    TREEMAP = "treemap"
    RADAR = "radar"
    WATERFALL = "waterfall"
    GEO_MAP = "geo_map"
    TABLE = "table"


class DashboardSortDirection(str, Enum):
    DEFAULT = "default"
    ASCENDING = "ascending"
    DESCENDING = "descending"


class DashboardSelectionKind(str, Enum):
    DASHBOARD = "dashboard"
    WIDGET = "widget"
    FILTER = "filter"
    CHART_DATUM = "chart_datum"
    CHART_SERIES = "chart_series"
    TABLE_COLUMN = "table_column"
    TABLE_CELL = "table_cell"


class DashboardTargetResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    NEEDS_CLARIFICATION = "needs_clarification"


class DashboardAnnotationStatus(str, Enum):
    PENDING = "pending"
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"


class DashboardAnnotationIntent(str, Enum):
    MODIFY = "modify"
    EXPLAIN = "explain"
    ANOMALY = "anomaly"


class DashboardAnomalyBaseline(str, Enum):
    PREVIOUS_PERIOD = "previous_period"
    ROLLING_AVERAGE = "rolling_average"
    TARGET_VALUE = "target_value"


class DashboardAnomalyThresholdMode(str, Enum):
    RELATIVE_CHANGE = "relative_change"
    ABSOLUTE_CHANGE = "absolute_change"


class DashboardAnomalyDirection(str, Enum):
    TWO_SIDED = "two_sided"
    ABOVE = "above"
    BELOW = "below"


class DashboardAnomalyStatus(str, Enum):
    ANOMALY = "anomaly"
    NORMAL = "normal"
    INDETERMINATE = "indeterminate"


class DashboardPublicationFilterOperator(str, Enum):
    AUTO = "auto"
    EQUAL = "equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"


class DashboardPublicationAggregation(str, Enum):
    SUM = "sum"
    AVERAGE = "average"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    FIRST = "first"
    RATIO = "ratio"


class DataFieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


class MetricAggregation(str, Enum):
    SUM = "sum"
    AVERAGE = "average"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    RATIO = "ratio"
    NONE = "none"


class SemanticDefinitionSource(str, Enum):
    CATALOG = "catalog"
    USER_CONFIRMED = "user_confirmed"
    MODEL_INFERRED = "model_inferred"


class FederationMode(str, Enum):
    """Bounded application-side operations supported across data sources."""

    UNION_ALL = "union_all"
    JOIN = "join"


class FederationJoinType(str, Enum):
    INNER = "inner"
    LEFT = "left"


class DashboardRefreshPolicy(StrictModel):
    """Refresh behavior controlled by the dashboard owner."""

    refresh_on_open: bool = False
    interval_seconds: Optional[int] = Field(default=None, ge=60, le=86400)


class DashboardThemeOverrides(StrictModel):
    """User-authored values layered on top of a visual theme preset."""

    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_scale: Optional[DashboardThemeFontScale] = None
    density: Optional[DashboardThemeDensity] = None
    card_radius: Optional[int] = Field(default=None, ge=0, le=28)
    card_shadow: Optional[DashboardThemeShadow] = None
    chart_palette: Optional[List[str]] = Field(
        default=None, min_length=3, max_length=10
    )
    kpi_style: Optional[DashboardThemeKpiStyle] = None
    table_style: Optional[DashboardThemeTableStyle] = None


class DashboardVisualTheme(BaseModel):
    """Persisted theme selection; empty values keep legacy schemas valid."""

    model_config = ConfigDict(
        extra="allow", populate_by_name=True, protected_namespaces=()
    )

    preset: Optional[DashboardThemePreset] = None
    mode: Optional[DashboardThemeMode] = None
    overrides: DashboardThemeOverrides = Field(default_factory=DashboardThemeOverrides)


class DashboardDescriptor(StrictModel):
    id: str = ""
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    data_source_id: str = Field(min_length=1, max_length=255)
    status: DashboardStatus = DashboardStatus.DRAFT
    theme: DashboardVisualTheme = Field(default_factory=DashboardVisualTheme)
    refresh_policy: DashboardRefreshPolicy = Field(
        default_factory=DashboardRefreshPolicy
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MetricDefinition(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=255)
    business_definition: str = Field(min_length=1, max_length=2000)
    aggregation: MetricAggregation = MetricAggregation.NONE
    unit: Optional[str] = Field(default=None, max_length=64)
    grain: Optional[str] = Field(default=None, max_length=255)
    source_field: Optional[str] = Field(default=None, max_length=255)
    definition_source: SemanticDefinitionSource = (
        SemanticDefinitionSource.MODEL_INFERRED
    )


class DimensionDefinition(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=255)
    business_definition: str = Field(min_length=1, max_length=2000)
    field: Optional[str] = Field(default=None, max_length=255)
    data_type: DataFieldType = DataFieldType.UNKNOWN
    definition_source: SemanticDefinitionSource = (
        SemanticDefinitionSource.MODEL_INFERRED
    )


class MetricContext(StrictModel):
    grain: str = Field(default="", max_length=255)
    time_range: Optional[str] = Field(default=None, max_length=255)
    data_freshness: Optional[str] = Field(default=None, max_length=255)
    source_notes: List[str] = Field(default_factory=list)
    metrics: List[MetricDefinition] = Field(default_factory=list, max_length=100)
    dimensions: List[DimensionDefinition] = Field(default_factory=list, max_length=100)


class FilterOption(StrictModel):
    label: str
    value: Any


class RelativeDateRange(StrictModel):
    """A date range evaluated on every refresh instead of when it is saved."""

    anchor: str = Field(default="today", pattern=r"^today$")
    start_offset_days: int = Field(default=-6, ge=-3650, le=3650)
    end_offset_days: int = Field(default=0, ge=-3650, le=3650)


class DashboardFilter(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    type: FilterType
    label: str = Field(min_length=1, max_length=255)
    field: str = Field(min_length=1, max_length=255)
    default: Any = None
    options: List[FilterOption] = Field(default_factory=list)
    relative_date: Optional[RelativeDateRange] = None


class QueryOutputField(StrictModel):
    name: str = Field(min_length=1, max_length=255)
    type: DataFieldType = DataFieldType.UNKNOWN
    label: Optional[str] = Field(default=None, max_length=255)
    nullable: bool = True


class LastExecution(StrictModel):
    status: str = "never"
    executed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    row_count: Optional[int] = None
    error: Optional[str] = None


class FilterParameterBinding(StrictModel):
    """Map one global filter to one value or a start/end parameter pair."""

    parameter: Optional[str] = None
    start_parameter: Optional[str] = None
    end_parameter: Optional[str] = None

    def parameter_names(self) -> List[str]:
        return [
            name
            for name in (self.parameter, self.start_parameter, self.end_parameter)
            if name
        ]


class FederatedSourceQuery(StrictModel):
    """One independently authorized and validated query in a federation."""

    alias: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    data_source_id: str = Field(min_length=1, max_length=255)
    sql: str = Field(min_length=1, max_length=20000)
    filter_parameters: Dict[str, Union[str, FilterParameterBinding]] = Field(
        default_factory=dict
    )
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    # Maps a physical result column to the bounded, public output name used by
    # the union/join and chart encoding.
    column_mapping: Dict[str, str] = Field(min_length=1)
    timeout_seconds: int = Field(default=30, ge=1, le=60)
    max_rows: int = Field(default=1000, ge=1, le=2000)


class FederatedJoin(StrictModel):
    left_alias: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    right_alias: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    left_field: str = Field(min_length=1, max_length=255)
    right_field: str = Field(min_length=1, max_length=255)
    join_type: FederationJoinType = FederationJoinType.INNER


class FederatedQuery(StrictModel):
    """A deliberately small alternative to arbitrary cross-database SQL."""

    mode: FederationMode
    sources: List[FederatedSourceQuery] = Field(min_length=2, max_length=4)
    join: Optional[FederatedJoin] = None
    max_output_rows: int = Field(default=2000, ge=1, le=5000)


class QueryLineageSource(StrictModel):
    data_source_id: str = Field(min_length=1, max_length=255)
    tables: List[str] = Field(default_factory=list, max_length=100)
    columns: List[str] = Field(default_factory=list, max_length=500)


class QueryLineage(StrictModel):
    sources: List[QueryLineageSource] = Field(default_factory=list, max_length=4)


class WidgetQueryBinding(StrictModel):
    data_source_id: str = Field(min_length=1, max_length=255)
    sql: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    federation: Optional[FederatedQuery] = None
    filter_parameters: Dict[str, Union[str, FilterParameterBinding]] = Field(
        default_factory=dict
    )
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    output_fields: List[QueryOutputField] = Field(default_factory=list)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_rows: int = Field(default=1000, ge=1, le=5000)
    grain: Optional[str] = Field(default=None, max_length=255)
    refresh_time: Optional[datetime] = None
    last_execution: LastExecution = Field(default_factory=LastExecution)
    lineage: QueryLineage = Field(default_factory=QueryLineage)


class ChartEncoding(StrictModel):
    x: Optional[str] = None
    y: Optional[str] = None
    value: Optional[str] = None
    series: Optional[str] = None
    category: Optional[str] = None
    angle: Optional[str] = None
    color: Optional[str] = None
    y2: Optional[str] = None
    row: Optional[str] = None
    column: Optional[str] = None
    target: Optional[str] = None
    columns: List[str] = Field(default_factory=list)

    def referenced_fields(self) -> Set[str]:
        values = {
            self.x,
            self.y,
            self.value,
            self.series,
            self.category,
            self.angle,
            self.color,
            self.y2,
            self.row,
            self.column,
            self.target,
        }
        return {value for value in values if value}.union(self.columns)


class DashboardDefaultSort(StrictModel):
    field: Optional[str] = Field(default=None, max_length=255)
    direction: DashboardSortDirection = DashboardSortDirection.DEFAULT


class DashboardPresentation(StrictModel):
    """Validated visualization settings introduced by Schema 1.3."""

    visualization: Optional[DashboardVisualization] = None
    orientation: Optional[str] = Field(default=None, pattern=r"^(vertical|horizontal)$")
    stacked: bool = False
    smooth: bool = True
    top_n: Optional[int] = Field(default=None, ge=1, le=100)
    colors: List[str] = Field(default_factory=list, max_length=20)
    unit: Optional[str] = Field(default=None, max_length=64)
    currency: Optional[str] = Field(default=None, max_length=16)
    precision: Optional[int] = Field(default=None, ge=0, le=20)
    percentage: bool = False
    show_legend: Optional[bool] = None
    show_grid: Optional[bool] = None
    default_sort: DashboardDefaultSort = Field(default_factory=DashboardDefaultSort)


class DashboardPublicationFilterBinding(StrictModel):
    """Map a public filter to one field in a frozen publication dataset."""

    field: str = Field(min_length=1, max_length=255)
    operator: DashboardPublicationFilterOperator = (
        DashboardPublicationFilterOperator.AUTO
    )


class DashboardPublicationMeasure(StrictModel):
    source_field: str = Field(min_length=1, max_length=255)
    output_field: str = Field(min_length=1, max_length=255)
    aggregation: DashboardPublicationAggregation
    denominator_field: Optional[str] = Field(default=None, min_length=1, max_length=255)
    scale: float = Field(default=1.0, gt=0, le=1000000)


class DashboardPublicationSort(StrictModel):
    field: str = Field(min_length=1, max_length=255)
    direction: DashboardSortDirection = DashboardSortDirection.ASCENDING


class DashboardPublicationBinding(StrictModel):
    """Safe materialization recipe used only while the owner publishes.

    The query result is frozen with the published revision.  Anonymous filtering
    later operates only on those rows and never receives a database connector.
    """

    query: WidgetQueryBinding
    filter_fields: Dict[str, Union[str, DashboardPublicationFilterBinding]] = Field(
        default_factory=dict
    )
    group_by: List[str] = Field(default_factory=list, max_length=20)
    measures: List[DashboardPublicationMeasure] = Field(
        default_factory=list, max_length=20
    )
    output_columns: List[str] = Field(default_factory=list, max_length=100)
    row_mode: bool = False
    sort: List[DashboardPublicationSort] = Field(default_factory=list, max_length=10)
    max_output_rows: int = Field(default=1000, ge=1, le=5000)


class DashboardPublicationQueryDraft(StrictModel):
    """Model-facing frozen-data query without a selectable data source.

    The server injects the same data source selected for the Dashboard.  This
    keeps the Agent useful for planning a shareable dataset without allowing it
    to switch connections or grant itself broader access.
    """

    sql: str = Field(min_length=1, max_length=20000)
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    output_fields: List[QueryOutputField] = Field(min_length=1)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_rows: int = Field(default=1000, ge=1, le=5000)


class DashboardPublicationDraft(StrictModel):
    """Model-facing recipe for interactive filtering of a published snapshot."""

    query: DashboardPublicationQueryDraft
    filter_fields: Dict[str, Union[str, DashboardPublicationFilterBinding]] = Field(
        default_factory=dict
    )
    group_by: List[str] = Field(default_factory=list, max_length=20)
    measures: List[DashboardPublicationMeasure] = Field(
        default_factory=list, max_length=20
    )
    output_columns: List[str] = Field(default_factory=list, max_length=100)
    row_mode: bool = False
    sort: List[DashboardPublicationSort] = Field(default_factory=list, max_length=10)
    max_output_rows: int = Field(default=1000, ge=1, le=5000)


class WidgetError(StrictModel):
    code: str
    message: str
    retryable: bool = False


class DashboardAnomalyThreshold(StrictModel):
    """Owner-configured decision threshold; no detector percentage is implicit."""

    mode: DashboardAnomalyThresholdMode = DashboardAnomalyThresholdMode.RELATIVE_CHANGE
    value: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)


class DashboardAnomalyRule(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    label: str = Field(min_length=1, max_length=255)
    baseline: DashboardAnomalyBaseline
    value_field: str = Field(min_length=1, max_length=255)
    time_field: Optional[str] = Field(default=None, max_length=255)
    direction: DashboardAnomalyDirection = DashboardAnomalyDirection.TWO_SIDED
    threshold: DashboardAnomalyThreshold = Field(
        default_factory=DashboardAnomalyThreshold
    )
    rolling_window: int = Field(default=3, ge=2, le=100)
    target_value: Optional[float] = Field(default=None, allow_inf_nan=False)
    min_samples: int = Field(default=1, ge=1, le=1000)
    enabled: bool = True


class DashboardAnomalyComparisonRange(StrictModel):
    current_start: Optional[str] = None
    current_end: Optional[str] = None
    baseline_start: Optional[str] = None
    baseline_end: Optional[str] = None


class DashboardAnomalyEvidence(StrictModel):
    """Immutable deterministic evidence attached to one widget execution."""

    rule_id: str
    rule_label: str
    status: DashboardAnomalyStatus
    baseline: DashboardAnomalyBaseline
    current_value: Optional[float] = None
    baseline_value: Optional[float] = None
    absolute_change: Optional[float] = None
    change_ratio: Optional[float] = None
    threshold: DashboardAnomalyThreshold
    comparison_time_range: DashboardAnomalyComparisonRange = Field(
        default_factory=DashboardAnomalyComparisonRange
    )
    sample_size: int = Field(default=0, ge=0)
    matched_rule: str
    reason_code: Optional[str] = None
    reason: Optional[str] = None


class DashboardWidget(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    type: WidgetType
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    query: WidgetQueryBinding
    encoding: ChartEncoding
    style: Dict[str, Any] = Field(default_factory=dict)
    presentation: DashboardPresentation = Field(default_factory=DashboardPresentation)
    publication: Optional[DashboardPublicationBinding] = None
    metric_ids: List[str] = Field(default_factory=list, max_length=20)
    dimension_ids: List[str] = Field(default_factory=list, max_length=20)
    anomaly_rules: List[DashboardAnomalyRule] = Field(
        default_factory=list, max_length=20
    )
    error: Optional[WidgetError] = None


class LayoutItem(StrictModel):
    widget_id: str = Field(min_length=1, max_length=128)
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=100)
    min_w: Optional[int] = Field(default=None, ge=1, le=12)
    min_h: Optional[int] = Field(default=None, ge=1, le=100)
    max_w: Optional[int] = Field(default=None, ge=1, le=12)
    max_h: Optional[int] = Field(default=None, ge=1, le=100)


class DashboardLayouts(StrictModel):
    columns: int = Field(default=12, ge=12, le=12)
    desktop: List[LayoutItem] = Field(default_factory=list)
    mobile_strategy: str = "stack"


class AgentGenerationInfo(StrictModel):
    generated: bool = False
    model_name: Optional[str] = None
    prompt: Optional[str] = None
    generated_at: Optional[datetime] = None


class DashboardMetadata(StrictModel):
    conversation_id: Optional[str] = None
    source_turn_id: Optional[str] = None
    agent: AgentGenerationInfo = Field(default_factory=AgentGenerationInfo)
    compatibility: Dict[str, Any] = Field(default_factory=dict)


class DashboardSchemaV1(StrictModel):
    schema_version: str = "1.0"
    dashboard: DashboardDescriptor
    metric_context: MetricContext = Field(default_factory=MetricContext)
    filters: List[DashboardFilter] = Field(default_factory=list)
    widgets: List[DashboardWidget] = Field(default_factory=list, max_length=24)
    layouts: DashboardLayouts = Field(default_factory=DashboardLayouts)
    metadata: DashboardMetadata = Field(default_factory=DashboardMetadata)


class DashboardPlanWidgetWidth(str, Enum):
    QUARTER = "quarter"
    THIRD = "third"
    HALF = "half"
    FULL = "full"


class DashboardPlanWidgetHeight(str, Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    TALL = "tall"


class DashboardPlanWidgetLayout(StrictModel):
    width: DashboardPlanWidgetWidth = DashboardPlanWidgetWidth.HALF
    height: DashboardPlanWidgetHeight = DashboardPlanWidgetHeight.STANDARD


class DashboardPlanWidget(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    type: WidgetType
    title: str = Field(min_length=1, max_length=255)
    business_question: str = Field(min_length=1, max_length=1000)
    metric: str = Field(min_length=1, max_length=255)
    dimensions: List[str] = Field(default_factory=list)
    expected_data_points: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Explored distinct X-category count (not multi-series row count); "
            "null if unknown. For a table explicitly expected to have no matching "
            "data, set 0: the approved plan then permits a genuine empty result."
        ),
    )
    analysis_level: int = Field(default=3, ge=1, le=5)
    rationale: str = Field(default="", max_length=1000)
    layout: Optional[DashboardPlanWidgetLayout] = None


class DashboardLayoutTemplate(str, Enum):
    TREND_FOCUS = "trend-focus"
    METRIC_OVERVIEW = "metric-overview"
    OPERATIONS_DETAIL = "operations-detail"


class DashboardPlan(StrictModel):
    """Model-facing planning contract.  Deliberately contains no SQL."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    business_theme: str = Field(min_length=1, max_length=1000)
    audience: str = Field(default="", max_length=500)
    decision_goal: str = Field(default="", max_length=1000)
    analysis_logic: List[str] = Field(default_factory=list, max_length=12)
    layout_rationale: str = Field(default="", max_length=2000)
    layout_template: Optional[DashboardLayoutTemplate] = Field(
        default=None,
        description=(
            "Optional layout family; when set, defines placement instead of "
            "individual widget layout hints."
        ),
    )
    filter_strategy: str = Field(default="", max_length=2000)
    metrics: List[str] = Field(min_length=1, max_length=30)
    dimensions: List[str] = Field(default_factory=list, max_length=30)
    filters: List[DashboardFilter] = Field(default_factory=list)
    widgets: List[DashboardPlanWidget] = Field(min_length=1, max_length=12)

    @model_serializer(mode="wrap")
    def serialize_released_plan(self, handler):
        payload = handler(self)
        if not layout_templates_enabled():
            # Accept old plans for reading, but never carry the unreleased
            # selection into new plan events, revisions or saved workflows.
            payload.pop("layout_template", None)
        return payload


class DashboardWidgetQueryDraft(StrictModel):
    """Model-produced query for one already-approved plan widget.

    The data source is intentionally absent.  The server injects the caller's
    selected data source so a model cannot switch to a different connection.
    """

    widget_id: str = Field(min_length=1, max_length=128)
    sql: str = Field(min_length=1, max_length=20000)
    filter_parameters: Dict[str, Union[str, FilterParameterBinding]] = Field(
        default_factory=dict
    )
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    output_fields: List[QueryOutputField] = Field(min_length=1)
    encoding: ChartEncoding
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_rows: int = Field(default=1000, ge=1, le=5000)
    grain: Optional[str] = Field(default=None, max_length=255)
    publication: Optional[DashboardPublicationDraft] = None
    anomaly_rules: List[DashboardAnomalyRule] = Field(
        default_factory=list, max_length=20
    )


class DashboardQueryDraftRequest(StrictModel):
    dashboard_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    expected_revision: Optional[int] = Field(default=None, ge=1)
    widgets: List[DashboardWidgetQueryDraft] = Field(min_length=1, max_length=12)


class ValidationIssue(StrictModel):
    path: str
    code: str
    message: str
    severity: str = "error"


class DashboardValidationResult(StrictModel):
    valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    widget_status: Dict[str, str] = Field(default_factory=dict)


class WidgetQueryResult(StrictModel):
    widget_id: str
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    duration_ms: int = 0
    refreshed_at: datetime
    anomalies: List[DashboardAnomalyEvidence] = Field(default_factory=list)
    error: Optional[WidgetError] = None


class DashboardSnapshot(StrictModel):
    dashboard_id: str
    refreshed_at: datetime
    filters: Dict[str, Any] = Field(default_factory=dict)
    widgets: Dict[str, WidgetQueryResult] = Field(default_factory=dict)
    publication_datasets: Dict[str, WidgetQueryResult] = Field(default_factory=dict)


class DashboardCreateRequest(StrictModel):
    schema_payload: DashboardSchemaV1 = Field(alias="schema")
    conversation_id: Optional[str] = None
    source_turn_id: Optional[str] = Field(default=None, max_length=64)
    origin: DashboardOrigin = DashboardOrigin.MANUAL
    asset_state: DashboardAssetState = DashboardAssetState.SAVED


class LegacyDashboardImportRequest(StrictModel):
    """Import payload produced by the existing ``chat_dashboard`` scene."""

    report: Dict[str, Any]
    data_source_id: str = Field(min_length=1, max_length=255)
    conversation_id: Optional[str] = None


class DashboardUpdateRequest(StrictModel):
    schema_payload: DashboardSchemaV1 = Field(alias="schema")
    expected_revision: int = Field(ge=1)


class DashboardPatchOperation(StrictModel):
    op: DashboardPatchOp
    path: str = Field(min_length=2, max_length=512, pattern=r"^/.*")
    value: Any = None


class DashboardOperationRequest(StrictModel):
    operation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    client_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    expected_revision: int = Field(ge=1)
    promote_to_asset: bool = True
    operations: List[DashboardPatchOperation] = Field(min_length=1, max_length=50)


class DashboardSelectionTarget(StrictModel):
    kind: DashboardSelectionKind
    widget_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    filter_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)
    datum_key: Dict[str, Any] = Field(default_factory=dict)
    series: Optional[str] = Field(default=None, max_length=255)
    column: Optional[str] = Field(default=None, max_length=255)
    row_key: Dict[str, Any] = Field(default_factory=dict)
    value: Any = None


class DashboardTargetResolutionRequest(StrictModel):
    reference: str = Field(min_length=1, max_length=1000)
    selected_widget_id: Optional[str] = Field(
        default=None, min_length=1, max_length=128
    )


class DashboardTargetCandidate(StrictModel):
    widget_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)


class DashboardTargetResolution(StrictModel):
    status: DashboardTargetResolutionStatus
    target: Optional[DashboardSelectionTarget] = None
    candidates: List[DashboardTargetCandidate] = Field(default_factory=list)
    question: Optional[str] = Field(default=None, max_length=2000)
    matched_by: Optional[str] = Field(default=None, max_length=64)


class DashboardStablePatchOperation(StrictModel):
    """Model-facing patch operation addressed by stable object identifiers."""

    op: DashboardPatchOp
    path: str = Field(min_length=2, max_length=512, pattern=r"^/.*")
    value: Any = Field(
        default=None,
        description=(
            "Required for add and replace (explicit null is allowed if the target "
            "field is nullable); omitted for remove."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def require_patch_value(cls, values):
        if (
            isinstance(values, dict)
            and values.get("op") in {DashboardPatchOp.ADD, DashboardPatchOp.REPLACE}
            and "value" not in values
        ):
            raise ValueError("value is required for add and replace operations.")
        return values


class DashboardAnnotationCreateRequest(StrictModel):
    base_revision: int = Field(ge=1)
    target: DashboardSelectionTarget
    prompt: str = Field(min_length=1, max_length=4000)
    intent: DashboardAnnotationIntent = DashboardAnnotationIntent.MODIFY
    conversation_id: Optional[str] = Field(default=None, max_length=255)
    source_turn_id: Optional[str] = Field(default=None, max_length=64)


class DashboardChangeProposalRequest(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    operations: List[DashboardStablePatchOperation] = Field(min_length=1, max_length=50)
    before: List[str] = Field(default_factory=list, max_length=50)
    after: List[str] = Field(default_factory=list, max_length=50)


class DashboardChangeProposal(StrictModel):
    summary: str
    operations: List[DashboardPatchOperation]
    stable_operations: List[DashboardStablePatchOperation]
    before: List[str] = Field(default_factory=list)
    after: List[str] = Field(default_factory=list)
    validation: DashboardValidationResult
    preview_schema: DashboardSchemaV1


class DashboardAnnotationRecord(StrictModel):
    id: str
    dashboard_id: str
    actor_id: str
    conversation_id: Optional[str] = None
    source_turn_id: Optional[str] = None
    base_revision: int
    target: DashboardSelectionTarget
    prompt: str
    intent: DashboardAnnotationIntent = DashboardAnnotationIntent.MODIFY
    status: DashboardAnnotationStatus
    proposal: Optional[DashboardChangeProposal] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class DashboardAnnotationApplyRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    operation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    client_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")


class DashboardAnnotationApplyResponse(StrictModel):
    annotation: DashboardAnnotationRecord
    operation: "DashboardOperationResponse"


class DashboardValidateRequest(StrictModel):
    schema_payload: Optional[DashboardSchemaV1] = Field(default=None, alias="schema")
    execute_queries: bool = True
    require_publication_bindings: bool = False
    filters: Dict[str, Any] = Field(default_factory=dict)


class DashboardRefreshRequest(StrictModel):
    filters: Dict[str, Any] = Field(default_factory=dict)


class DashboardWidgetPreviewRequest(StrictModel):
    filters: Dict[str, Any] = Field(default_factory=dict)
    schema_payload: Optional[DashboardSchemaV1] = Field(default=None, alias="schema")


class DashboardPublishRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    filters: Dict[str, Any] = Field(default_factory=dict)
    allow_static_widgets: bool = False
    share_expires_in_seconds: Optional[int] = Field(default=None, ge=60, le=31536000)


class DashboardRecord(StrictModel):
    id: str
    owner_id: str
    conversation_id: Optional[str] = None
    source_turn_id: Optional[str] = None
    origin: DashboardOrigin = DashboardOrigin.MANUAL
    asset_state: DashboardAssetState = DashboardAssetState.SAVED
    saved_at: Optional[datetime] = None
    current_revision: int
    status: DashboardStatus
    schema_payload: DashboardSchemaV1 = Field(alias="schema")
    created_at: datetime
    updated_at: datetime


class DashboardOperationLogRecord(StrictModel):
    dashboard_id: str
    operation_id: str
    client_id: str
    actor_id: str
    base_revision: int
    applied_revision: int
    operations: List[DashboardPatchOperation]
    created_at: datetime


class DashboardOperationResponse(StrictModel):
    dashboard: DashboardRecord
    operation: DashboardOperationLogRecord
    replayed: bool = False


class DashboardCollaborationTicket(StrictModel):
    ticket: str
    websocket_path: str
    expires_at: datetime


class DashboardCollaborationTicketRequest(StrictModel):
    client_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")


class DashboardListItem(StrictModel):
    id: str
    title: str
    description: str = ""
    data_source_id: str
    conversation_id: Optional[str] = None
    source_turn_id: Optional[str] = None
    origin: DashboardOrigin = DashboardOrigin.MANUAL
    asset_state: DashboardAssetState = DashboardAssetState.SAVED
    saved_at: Optional[datetime] = None
    current_revision: int
    status: DashboardStatus
    updated_at: datetime


class DashboardArtifactFile(StrictModel):
    path: str = Field(min_length=1, max_length=512)
    language: str = Field(default="text", max_length=64)
    content: str


class DashboardArtifactBundle(StrictModel):
    dashboard_id: str
    root: str
    generated_at: datetime
    files: List[DashboardArtifactFile] = Field(default_factory=list)


class DashboardListPage(StrictModel):
    items: List[DashboardListItem] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class DashboardStateRequest(StrictModel):
    expected_revision: int = Field(ge=1)


class DashboardCopyRequest(StrictModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)


class DashboardRevisionRecord(StrictModel):
    dashboard_id: str
    published_revision: int
    published_at: datetime


class DashboardEditVersionRecord(StrictModel):
    dashboard_id: str
    revision: int = Field(ge=1)
    source: str = Field(min_length=1, max_length=64)
    actor_id: str = Field(min_length=1, max_length=255)
    operation_id: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime


class DashboardEditVersionDetail(DashboardEditVersionRecord):
    schema_payload: DashboardSchemaV1 = Field(alias="schema")


class DashboardMemberUpsertRequest(StrictModel):
    principal_id: str = Field(min_length=1, max_length=255)
    role: DashboardRole


class DashboardMemberRecord(StrictModel):
    dashboard_id: str
    principal_id: str
    role: DashboardRole
    created_by: str
    created_at: datetime
    updated_at: datetime


class DashboardPermissionRecord(StrictModel):
    dashboard_id: str
    actor_id: str
    role: DashboardRole
    actions: List[DashboardAction]


class DashboardAuditRecord(StrictModel):
    id: int
    dashboard_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None
    created_at: datetime


class DashboardScheduleCreateRequest(StrictModel):
    task_name: str = Field(min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    cron_expression: str = Field(min_length=1, max_length=128)
    filters: Dict[str, Any] = Field(default_factory=dict)
    publish_after_refresh: bool = False
    timeout_seconds: int = Field(default=180, ge=5, le=600)
    max_attempts: int = Field(default=2, ge=1, le=5)


class DashboardScheduleUpdateRequest(StrictModel):
    task_name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    cron_expression: Optional[str] = Field(default=None, min_length=1, max_length=128)
    filters: Optional[Dict[str, Any]] = None
    publish_after_refresh: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=600)
    max_attempts: Optional[int] = Field(default=None, ge=1, le=5)


class DashboardScheduleToggleRequest(StrictModel):
    enabled: bool


class DashboardPublishResponse(StrictModel):
    dashboard_id: str
    published_revision: int
    share_token: str
    share_path: str
    latest_share_path: Optional[str] = None
    published_at: datetime
    expires_at: Optional[datetime] = None


class DashboardShareRotateRequest(StrictModel):
    share_expires_in_seconds: Optional[int] = Field(default=None, ge=60, le=31536000)


class DashboardShareRecord(StrictModel):
    id: int
    dashboard_id: str
    published_revision: int
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    active: bool


class PublicDashboardSnapshot(StrictModel):
    dashboard_id: str
    published_revision: int
    schema_payload: DashboardSchemaV1 = Field(alias="schema")
    snapshot: DashboardSnapshot
    published_at: datetime
    is_latest_link: bool = False
    data_mode: str = "snapshot"
    refresh_interval: int = 0
    stale: bool = False
    refresh_error: Optional[str] = None


class PublicDashboardFilterRequest(StrictModel):
    filters: Dict[str, Any] = Field(default_factory=dict)


class PublicDashboardFilterResponse(StrictModel):
    snapshot: DashboardSnapshot
    unsupported_widget_ids: List[str] = Field(default_factory=list)
    stale: bool = False
    refresh_error: Optional[str] = None


def model_dump_compat(model: BaseModel, *, by_alias: bool = True) -> Dict[str, Any]:
    """Serialize across the Pydantic v1/v2 compatibility layer."""

    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", by_alias=by_alias)
    return model.dict(by_alias=by_alias)


def model_validate_compat(model_type, value):
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(value)
    return model_type.parse_obj(value)


def _hex_rgb(value: str) -> tuple[float, float, float]:
    return tuple(int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))


def _relative_luminance(value: str) -> float:
    def linearize(channel: float) -> float:
        return (
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )

    red, green, blue = (linearize(channel) for channel in _hex_rgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(left: str, right: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(left), _relative_luminance(right)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def _simulated_rgb_distance(left: str, right: str, matrix) -> float:
    def simulate(value: str) -> tuple[float, float, float]:
        channels = _hex_rgb(value)
        return tuple(
            sum(matrix[row][column] * channels[column] for column in range(3))
            for row in range(3)
        )

    left_channels = simulate(left)
    right_channels = simulate(right)
    return (
        sum((left_channels[index] - right_channels[index]) ** 2 for index in range(3))
        ** 0.5
        * 255
    )


def _theme_override_values(theme: DashboardVisualTheme) -> Dict[str, Any]:
    return model_dump_compat(theme.overrides)


def _collect_theme_issues(schema: DashboardSchemaV1) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    theme = schema.dashboard.theme
    preset = theme.preset.value if theme.preset is not None else None
    mode = theme.mode.value if theme.mode is not None else None
    override_values = _theme_override_values(theme)
    has_overrides = any(value is not None for value in override_values.values())

    if schema.schema_version == "1.4":
        if getattr(theme, "model_extra", None):
            issues.append(
                ValidationIssue(
                    path="dashboard.theme",
                    code="unknown_theme_field",
                    message="Schema 1.4 visual themes do not allow unknown fields.",
                )
            )
        if preset not in _CANONICAL_THEME_PRESETS:
            issues.append(
                ValidationIssue(
                    path="dashboard.theme.preset",
                    code="canonical_theme_required",
                    message=(
                        "Schema 1.4 requires one of the canonical visual themes: "
                        "clarity, ocean, warm, or graphite."
                    ),
                )
            )
        if mode is None:
            issues.append(
                ValidationIssue(
                    path="dashboard.theme.mode",
                    code="theme_mode_required",
                    message="Schema 1.4 requires an explicit light or dark theme mode.",
                )
            )
    elif mode is not None or has_overrides:
        issues.append(
            ValidationIssue(
                path="dashboard.theme",
                code="visual_theme_requires_schema_1_4",
                message=(
                    "Theme mode and custom overrides require schema_version '1.4'."
                ),
            )
        )

    if not has_overrides and schema.schema_version != "1.4":
        return issues

    canonical_preset = (
        "clarity" if preset in {None, "clean", "business_blue"} else preset
    )
    effective_mode = mode or ("dark" if preset == "graphite" else "light")
    card = _THEME_CARD_COLORS.get(
        (canonical_preset, effective_mode), _THEME_CARD_COLORS[("clarity", "light")]
    )
    primary = theme.overrides.primary_color
    if primary and _contrast_ratio(primary, card) < 3:
        issues.append(
            ValidationIssue(
                path="dashboard.theme.overrides.primary_color",
                code="theme_primary_contrast_too_low",
                message=(
                    "The custom primary color must have at least 3:1 contrast "
                    "against the theme card surface."
                ),
            )
        )

    palette = theme.overrides.chart_palette or list(
        _THEME_CHART_PALETTES.get(
            (canonical_preset, effective_mode),
            _THEME_CHART_PALETTES[("clarity", "light")],
        )
    )
    if primary and theme.overrides.chart_palette is None:
        palette[0] = primary
    invalid_indices = [
        str(index)
        for index, color in enumerate(palette)
        if not _HEX_COLOR.fullmatch(color)
    ]
    if invalid_indices:
        issues.append(
            ValidationIssue(
                path="dashboard.theme.overrides.chart_palette",
                code="invalid_theme_palette_color",
                message=(
                    "Chart palette entries must be six-digit hexadecimal colors; "
                    "invalid indices: " + ", ".join(invalid_indices) + "."
                ),
            )
        )
        return issues

    normalized = [color.upper() for color in palette]
    if len(normalized) != len(set(normalized)):
        issues.append(
            ValidationIssue(
                path="dashboard.theme.overrides.chart_palette",
                code="duplicate_theme_palette_color",
                message="Chart palette colors must be unique.",
            )
        )
    low_contrast = [
        str(index)
        for index, color in enumerate(normalized)
        if _contrast_ratio(color, card) < 3
    ]
    if low_contrast:
        issues.append(
            ValidationIssue(
                path="dashboard.theme.overrides.chart_palette",
                code="theme_palette_contrast_too_low",
                message=(
                    "Every chart color must have at least 3:1 contrast against "
                    "the theme card surface; failing indices: "
                    + ", ".join(low_contrast)
                    + "."
                ),
            )
        )
    colorblind_collisions = []
    for left_index, left in enumerate(normalized):
        for right_index, right in enumerate(
            normalized[left_index + 1 :], left_index + 1
        ):
            if any(
                _simulated_rgb_distance(left, right, matrix) < 8
                for matrix in _COLOR_VISION_MATRICES
            ):
                colorblind_collisions.append(f"{left_index}/{right_index}")
    if colorblind_collisions:
        issues.append(
            ValidationIssue(
                path="dashboard.theme.overrides.chart_palette",
                code="theme_palette_colorblind_collision",
                message=(
                    "Chart palette colors become indistinguishable under a "
                    "red-green color-vision simulation; conflicting pairs: "
                    + ", ".join(colorblind_collisions)
                    + "."
                ),
            )
        )
    return issues


def collect_schema_issues(schema: DashboardSchemaV1) -> List[ValidationIssue]:
    """Apply cross-field rules that JSON Schema alone cannot express."""

    issues: List[ValidationIssue] = []
    schema_size = len(
        json.dumps(
            model_dump_compat(schema),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    )
    if schema_size > MAX_DASHBOARD_SCHEMA_BYTES:
        issues.append(
            ValidationIssue(
                path="$",
                code="schema_too_large",
                message=(
                    "Dashboard schema exceeds the 2 MiB storage and transport limit."
                ),
            )
        )
    if schema.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        issues.append(
            ValidationIssue(
                path="schema_version",
                code="unsupported_schema_version",
                message=(
                    "Dashboard Schema supports schema_version "
                    + " or ".join(
                        repr(version) for version in SUPPORTED_SCHEMA_VERSIONS
                    )
                    + "."
                ),
            )
        )
    issues.extend(_collect_theme_issues(schema))

    filter_ids = [item.id for item in schema.filters]
    widget_ids = [item.id for item in schema.widgets]
    metric_ids = [item.id for item in schema.metric_context.metrics]
    dimension_ids = [item.id for item in schema.metric_context.dimensions]
    if len(filter_ids) != len(set(filter_ids)):
        issues.append(
            ValidationIssue(
                path="filters",
                code="duplicate_filter_id",
                message="Filter ids must be unique.",
            )
        )
    if len(widget_ids) != len(set(widget_ids)):
        issues.append(
            ValidationIssue(
                path="widgets",
                code="duplicate_widget_id",
                message="Widget ids must be unique.",
            )
        )
    if len(metric_ids) != len(set(metric_ids)):
        issues.append(
            ValidationIssue(
                path="metric_context.metrics",
                code="duplicate_metric_id",
                message="Metric ids must be unique.",
            )
        )
    if len(dimension_ids) != len(set(dimension_ids)):
        issues.append(
            ValidationIssue(
                path="metric_context.dimensions",
                code="duplicate_dimension_id",
                message="Dimension ids must be unique.",
            )
        )

    known_filters = set(filter_ids)
    for index, dashboard_filter in enumerate(schema.filters):
        relative = dashboard_filter.relative_date
        if relative is None:
            continue
        if dashboard_filter.type != FilterType.DATE_RANGE:
            issues.append(
                ValidationIssue(
                    path=f"filters.{index}.relative_date",
                    code="relative_date_requires_date_range",
                    message="Relative dates are supported only by date-range filters.",
                )
            )
        if relative.start_offset_days > relative.end_offset_days:
            issues.append(
                ValidationIssue(
                    path=f"filters.{index}.relative_date",
                    code="relative_date_range_reversed",
                    message=(
                        "Relative date start offset must not follow its end offset."
                    ),
                )
            )

    def validate_filter_parameters(
        path: str,
        sql: str,
        mappings: Dict[str, Union[str, FilterParameterBinding]],
        defaults: Dict[str, Any],
    ) -> None:
        sql_parameters = set(_NAMED_SQL_PARAMETER.findall(sql))
        supplied_parameters = set(defaults)
        for filter_id, parameter_binding in mappings.items():
            if filter_id not in known_filters:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.{filter_id}",
                        code="unknown_filter",
                        message=f"Filter '{filter_id}' is not defined.",
                    )
                )
            definition = next(
                (item for item in schema.filters if item.id == filter_id), None
            )
            if definition and definition.type in {
                FilterType.DATE_RANGE,
                FilterType.NUMBER_RANGE,
            }:
                if (
                    isinstance(parameter_binding, str)
                    or parameter_binding.parameter
                    or not parameter_binding.start_parameter
                    or not parameter_binding.end_parameter
                    or parameter_binding.start_parameter
                    == parameter_binding.end_parameter
                ):
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.{filter_id}",
                            code="range_filter_parameter_binding",
                            message=(
                                "Date/number range filters require distinct "
                                "start_parameter and "
                                "end_parameter bindings, e.g. "
                                "{start_parameter: year_start, "
                                "end_parameter: year_end} and SQL BETWEEN "
                                ":year_start AND :year_end; "
                                "a two-value range cannot be bound to scalar equality."
                            ),
                        )
                    )
            parameter_names = (
                [parameter_binding]
                if isinstance(parameter_binding, str)
                else parameter_binding.parameter_names()
            )
            if not parameter_names:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.{filter_id}",
                        code="empty_filter_parameter_binding",
                        message=_EMPTY_FILTER_PARAMETER_MESSAGE,
                    )
                )
            for parameter_name in parameter_names:
                supplied_parameters.add(parameter_name)
                if parameter_name not in sql_parameters:
                    issues.append(
                        ValidationIssue(
                            path=path.rsplit(".", 1)[0] + ".sql",
                            code="missing_sql_parameter",
                            message=(
                                f"SQL does not contain named parameter "
                                f":{parameter_name}."
                            ),
                        )
                    )
        unbound = sql_parameters.difference(supplied_parameters)
        for parameter_name in sorted(unbound):
            issues.append(
                ValidationIssue(
                    path=path.rsplit(".", 1)[0] + ".sql",
                    code="unbound_sql_parameter",
                    message=(
                        f"SQL parameter :{parameter_name} has no filter mapping or "
                        "component default value."
                    ),
                )
            )

    for index, widget in enumerate(schema.widgets):
        path = f"widgets.{index}"
        parameter_size = len(
            json.dumps(
                widget.query.default_parameters,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        )
        if parameter_size > MAX_QUERY_PARAMETER_BYTES:
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.default_parameters",
                    code="query_parameters_too_large",
                    message="Widget default parameters exceed the 64 KiB limit.",
                )
            )
        unknown_metrics = set(widget.metric_ids).difference(metric_ids)
        if unknown_metrics:
            issues.append(
                ValidationIssue(
                    path=f"{path}.metric_ids",
                    code="unknown_metric_id",
                    message=(
                        "Widget references undefined metrics: "
                        f"{', '.join(sorted(unknown_metrics))}."
                    ),
                )
            )
        unknown_dimensions = set(widget.dimension_ids).difference(dimension_ids)
        if unknown_dimensions:
            issues.append(
                ValidationIssue(
                    path=f"{path}.dimension_ids",
                    code="unknown_dimension_id",
                    message=(
                        "Widget references undefined dimensions: "
                        f"{', '.join(sorted(unknown_dimensions))}."
                    ),
                )
            )
        output_names = {field.name for field in widget.query.output_fields}
        for field_name in widget.encoding.referenced_fields():
            if field_name not in output_names:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.encoding",
                        code="unknown_encoding_field",
                        message=(
                            f"Encoding field '{field_name}' is not declared in "
                            "query.output_fields."
                        ),
                    )
                )

        anomaly_rule_ids = [rule.id for rule in widget.anomaly_rules]
        if len(anomaly_rule_ids) != len(set(anomaly_rule_ids)):
            issues.append(
                ValidationIssue(
                    path=f"{path}.anomaly_rules",
                    code="duplicate_anomaly_rule_id",
                    message="Anomaly rule ids must be unique within a widget.",
                )
            )
        for rule_index, rule in enumerate(widget.anomaly_rules):
            if not rule.enabled:
                continue
            rule_path = f"{path}.anomaly_rules.{rule_index}"
            if rule.value_field not in output_names:
                issues.append(
                    ValidationIssue(
                        path=f"{rule_path}.value_field",
                        code="unknown_anomaly_value_field",
                        message=(
                            f"Anomaly value field '{rule.value_field}' is not "
                            "declared in query.output_fields."
                        ),
                    )
                )
            if rule.time_field and rule.time_field not in output_names:
                issues.append(
                    ValidationIssue(
                        path=f"{rule_path}.time_field",
                        code="unknown_anomaly_time_field",
                        message=(
                            f"Anomaly time field '{rule.time_field}' is not "
                            "declared in query.output_fields."
                        ),
                    )
                )
            if rule.threshold.value is None:
                issues.append(
                    ValidationIssue(
                        path=f"{rule_path}.threshold.value",
                        code="anomaly_threshold_required",
                        message="Enabled anomaly rules require an explicit threshold.",
                    )
                )
            if (
                rule.baseline == DashboardAnomalyBaseline.TARGET_VALUE
                and rule.target_value is None
            ):
                issues.append(
                    ValidationIssue(
                        path=f"{rule_path}.target_value",
                        code="anomaly_target_required",
                        message=(
                            "A target-value anomaly rule requires an explicit "
                            "business target."
                        ),
                    )
                )

        legacy_visualization: Dict[WidgetType, DashboardVisualization] = {
            WidgetType.KPI: DashboardVisualization.KPI,
            WidgetType.LINE: DashboardVisualization.LINE,
            WidgetType.BAR: DashboardVisualization.COLUMN,
            WidgetType.PIE: DashboardVisualization.PIE,
            WidgetType.TABLE: DashboardVisualization.TABLE,
        }
        visualization = (
            widget.presentation.visualization or legacy_visualization[widget.type]
        )
        required_by_visualization: Dict[DashboardVisualization, Set[str]] = {
            DashboardVisualization.KPI: {"value"},
            DashboardVisualization.LINE: {"x", "y"},
            DashboardVisualization.AREA: {"x", "y"},
            DashboardVisualization.COLUMN: {"x", "y"},
            DashboardVisualization.BAR: {"x", "y"},
            DashboardVisualization.STACKED_COLUMN: {"x", "y"},
            DashboardVisualization.PIE: {"angle"},
            DashboardVisualization.DONUT: {"angle"},
            DashboardVisualization.SCATTER: {"x", "y"},
            DashboardVisualization.DUAL_AXIS: {"x", "y", "y2"},
            DashboardVisualization.HEATMAP: {"row", "column", "value"},
            DashboardVisualization.COHORT: {
                "row",
                "column",
                "value",
                "target",
                "color",
            },
            DashboardVisualization.GAUGE: {"value"},
            DashboardVisualization.FUNNEL: {"x", "y"},
            DashboardVisualization.TREEMAP: {"x", "y"},
            DashboardVisualization.RADAR: {"x", "y"},
            DashboardVisualization.WATERFALL: {"x", "y"},
            DashboardVisualization.GEO_MAP: {"x", "y"},
            DashboardVisualization.TABLE: set(),
        }
        missing = [
            name
            for name in required_by_visualization[visualization]
            if not getattr(widget.encoding, name)
        ]
        if missing:
            required_names = ", ".join(missing)
            issues.append(
                ValidationIssue(
                    path=f"{path}.encoding",
                    code="missing_encoding",
                    message=(
                        f"{visualization.value} visualization requires: "
                        f"{required_names}."
                    ),
                )
            )

        has_v1_3_presentation = any(
            (
                widget.presentation.visualization is not None,
                widget.presentation.orientation is not None,
                widget.presentation.stacked,
                widget.presentation.smooth is not True,
                widget.presentation.top_n is not None,
                bool(widget.presentation.colors),
                widget.presentation.unit is not None,
                widget.presentation.currency is not None,
                widget.presentation.precision is not None,
                widget.presentation.percentage,
                widget.presentation.show_legend is not None,
                widget.presentation.show_grid is not None,
                widget.presentation.default_sort.field is not None,
                widget.presentation.default_sort.direction
                != DashboardSortDirection.DEFAULT,
            )
        )
        if has_v1_3_presentation and schema.schema_version not in {"1.3", "1.4"}:
            issues.append(
                ValidationIssue(
                    path=f"{path}.presentation",
                    code="presentation_requires_schema_1_3",
                    message=(
                        "Dashboard presentation settings require "
                        "schema_version '1.3' or later."
                    ),
                )
            )
        sort_field = widget.presentation.default_sort.field
        if sort_field is not None and sort_field not in output_names:
            issues.append(
                ValidationIssue(
                    path=f"{path}.presentation.default_sort.field",
                    code="unknown_sort_field",
                    message=(
                        f"Default sort field '{sort_field}' is not declared in "
                        "query.output_fields."
                    ),
                )
            )

        publication = widget.publication
        if publication is not None:
            if schema.schema_version not in {"1.3", "1.4"}:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication",
                        code="publication_binding_requires_schema_1_3",
                        message=(
                            "Interactive publication bindings require "
                            "schema_version '1.3' or later."
                        ),
                    )
                )
            if publication.query.filter_parameters:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication.query.filter_parameters",
                        code="publication_query_must_be_unfiltered",
                        message=(
                            "A publication query must materialize its bounded "
                            "dataset without dashboard filter parameters."
                        ),
                    )
                )
            publication_outputs = {
                field.name for field in publication.query.output_fields
            }
            filter_fields = {
                binding if isinstance(binding, str) else binding.field
                for binding in publication.filter_fields.values()
            }
            referenced_publication_fields = filter_fields.union(
                publication.group_by
            ).union(measure.source_field for measure in publication.measures)
            referenced_publication_fields.update(
                measure.denominator_field
                for measure in publication.measures
                if measure.denominator_field
            )
            unknown_publication_fields = referenced_publication_fields.difference(
                publication_outputs
            )
            if unknown_publication_fields:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication",
                        code="unknown_publication_field",
                        message=(
                            "Publication binding references undeclared dataset "
                            "fields: "
                            + ", ".join(sorted(unknown_publication_fields))
                            + f". Widget {widget.id} frozen query fields: "
                            f"{sorted(publication_outputs)}. "
                            "Use the actual frozen output alias in filter_fields, "
                            "group_by and measure source_field, or add the needed "
                            "field to the frozen SQL and output_fields together."
                        ),
                    )
                )
            unknown_publication_filters = set(publication.filter_fields).difference(
                known_filters
            )
            if unknown_publication_filters:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication.filter_fields",
                        code="unknown_publication_filter",
                        message=(
                            "Publication binding references undefined filters: "
                            + ", ".join(sorted(unknown_publication_filters))
                            + "."
                        ),
                    )
                )
            expected_outputs = output_names
            configured_outputs = set(publication.output_columns)
            unknown_publication_sort = {
                item.field for item in publication.sort
            }.difference(configured_outputs)
            if unknown_publication_sort:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication.sort",
                        code="unknown_publication_sort_field",
                        message=(
                            "Publication sort fields must be final widget outputs: "
                            + ", ".join(sorted(unknown_publication_sort))
                            + "."
                        ),
                    )
                )
            if configured_outputs != expected_outputs:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication.output_columns",
                        code="publication_output_mismatch",
                        message=(
                            "Publication output columns must exactly match the "
                            "widget query outputs. "
                            f"Widget {widget.id}: expected {sorted(expected_outputs)}, "
                            f"received {sorted(configured_outputs)}. Preserve the "
                            "widget's output aliases or update both contracts together."
                        ),
                    )
                )
            produced_outputs = set(publication.group_by).union(
                measure.output_field for measure in publication.measures
            )
            if publication.row_mode:
                missing_row_outputs = configured_outputs.difference(publication_outputs)
                if missing_row_outputs:
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.publication.output_columns",
                            code="publication_row_output_missing",
                            message=(
                                "Row-mode publication outputs are absent from "
                                "the materialized query: "
                                + ", ".join(sorted(missing_row_outputs))
                                + "."
                            ),
                        )
                    )
            elif not publication.measures:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication.measures",
                        code="publication_measure_required",
                        message=(
                            "Aggregated publication bindings require at least "
                            "one measure."
                        ),
                    )
                )
            ratio_without_denominator = [
                measure.output_field
                for measure in publication.measures
                if measure.aggregation == DashboardPublicationAggregation.RATIO
                and not measure.denominator_field
            ]
            if ratio_without_denominator:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication.measures",
                        code="publication_ratio_denominator_required",
                        message=(
                            "Ratio publication measures require denominator_field: "
                            + ", ".join(sorted(ratio_without_denominator))
                            + "."
                        ),
                    )
                )
            if (
                not publication.row_mode
                and publication.measures
                and produced_outputs != configured_outputs
            ):
                issues.append(
                    ValidationIssue(
                        path=f"{path}.publication",
                        code="publication_aggregation_output_mismatch",
                        message=(
                            "Publication group and measure outputs must exactly "
                            "produce output_columns. "
                            f"Widget {widget.id}: group_by={publication.group_by}, "
                            "measure outputs="
                            f"{[m.output_field for m in publication.measures]}, "
                            f"required outputs={sorted(configured_outputs)}. "
                            "Filter-only fields belong in "
                            "publication.query.output_fields and filter_fields, "
                            "not the final grouping."
                        ),
                    )
                )

        federation = widget.query.federation
        if federation is None:
            if not widget.query.sql:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.query.sql",
                        code="missing_widget_sql",
                        message="A non-federated widget requires SQL.",
                    )
                )
            else:
                validate_filter_parameters(
                    f"{path}.query.filter_parameters",
                    widget.query.sql,
                    widget.query.filter_parameters,
                    widget.query.default_parameters,
                )
            continue

        if schema.schema_version not in {"1.1", "1.2", "1.3", "1.4"}:
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.federation",
                    code="federation_requires_schema_1_1",
                    message=(
                        "Federated widgets require schema_version '1.1', "
                        "'1.2', '1.3', or '1.4'."
                    ),
                )
            )
        if widget.query.sql:
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.sql",
                    code="ambiguous_federated_sql",
                    message="Federated widgets keep SQL inside each source only.",
                )
            )
        if widget.query.filter_parameters or widget.query.default_parameters:
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.federation",
                    code="federation_uses_source_parameters",
                    message=(
                        "Federated widgets define filters and defaults on each "
                        "source query."
                    ),
                )
            )

        aliases = [source.alias for source in federation.sources]
        source_ids = [source.data_source_id for source in federation.sources]
        if len(aliases) != len(set(aliases)):
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.federation.sources",
                    code="duplicate_federation_alias",
                    message="Federation source aliases must be unique.",
                )
            )
        if len(set(source_ids)) < 2:
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.federation.sources",
                    code="federation_requires_multiple_sources",
                    message="A federation must use at least two data sources.",
                )
            )
        if widget.query.data_source_id not in set(source_ids):
            issues.append(
                ValidationIssue(
                    path=f"{path}.query.data_source_id",
                    code="federation_primary_source_missing",
                    message=(
                        "The widget primary data source must be one of its "
                        "federation sources."
                    ),
                )
            )

        mapped_by_alias: Dict[str, Set[str]] = {}
        for source_index, source in enumerate(federation.sources):
            source_path = f"{path}.query.federation.sources.{source_index}"
            source_parameter_size = len(
                json.dumps(
                    source.default_parameters,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            )
            if source_parameter_size > MAX_QUERY_PARAMETER_BYTES:
                issues.append(
                    ValidationIssue(
                        path=f"{source_path}.default_parameters",
                        code="query_parameters_too_large",
                        message=(
                            "Federated source default parameters exceed the 64 KiB "
                            "limit."
                        ),
                    )
                )
            validate_filter_parameters(
                f"{source_path}.filter_parameters",
                source.sql,
                source.filter_parameters,
                source.default_parameters,
            )
            mapped = set(source.column_mapping.values())
            mapped_by_alias[source.alias] = mapped
            if len(mapped) != len(source.column_mapping):
                issues.append(
                    ValidationIssue(
                        path=f"{source_path}.column_mapping",
                        code="duplicate_federation_output",
                        message="One source cannot map two columns to one output.",
                    )
                )
            unknown_outputs = mapped.difference(output_names)
            if unknown_outputs:
                issues.append(
                    ValidationIssue(
                        path=f"{source_path}.column_mapping",
                        code="unknown_federation_output",
                        message=(
                            "Mapped outputs are not declared: "
                            f"{', '.join(sorted(unknown_outputs))}."
                        ),
                    )
                )

        if federation.mode == FederationMode.UNION_ALL:
            if federation.join is not None:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.query.federation.join",
                        code="union_cannot_define_join",
                        message="union_all does not accept a join definition.",
                    )
                )
            for alias, mapped in mapped_by_alias.items():
                if mapped != output_names:
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.query.federation.sources",
                            code="union_output_mismatch",
                            message=(
                                f"Source '{alias}' must map exactly the declared "
                                "widget outputs."
                            ),
                        )
                    )
        elif federation.mode == FederationMode.JOIN:
            join = federation.join
            if len(federation.sources) != 2 or join is None:
                issues.append(
                    ValidationIssue(
                        path=f"{path}.query.federation",
                        code="join_requires_two_sources",
                        message=(
                            "join requires exactly two sources and a join definition."
                        ),
                    )
                )
            elif (
                join.left_alias not in mapped_by_alias
                or join.right_alias not in mapped_by_alias
                or join.left_alias == join.right_alias
            ):
                issues.append(
                    ValidationIssue(
                        path=f"{path}.query.federation.join",
                        code="unknown_join_alias",
                        message=(
                            "Join aliases must name two different federation sources."
                        ),
                    )
                )
            else:
                if join.left_field not in mapped_by_alias[join.left_alias]:
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.query.federation.join.left_field",
                            code="unknown_join_field",
                            message=(
                                "The left join field is not mapped by the left source."
                            ),
                        )
                    )
                if join.right_field not in mapped_by_alias[join.right_alias]:
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.query.federation.join.right_field",
                            code="unknown_join_field",
                            message=(
                                "The right join field is not mapped by the right "
                                "source."
                            ),
                        )
                    )
                combined = set().union(*mapped_by_alias.values())
                if combined != output_names:
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.query.federation.sources",
                            code="join_output_mismatch",
                            message=(
                                "Joined source mappings must match declared outputs."
                            ),
                        )
                    )
                overlap = set.intersection(*mapped_by_alias.values())
                allowed_overlap = {join.left_field, join.right_field}
                ambiguous_outputs = overlap.difference(allowed_overlap)
                if ambiguous_outputs:
                    issues.append(
                        ValidationIssue(
                            path=f"{path}.query.federation.sources",
                            code="ambiguous_join_output",
                            message=(
                                "Joined sources map the same non-key output: "
                                f"{', '.join(sorted(ambiguous_outputs))}."
                            ),
                        )
                    )

    layout_ids = [item.widget_id for item in schema.layouts.desktop]
    for index, item in enumerate(schema.layouts.desktop):
        if item.widget_id not in set(widget_ids):
            issues.append(
                ValidationIssue(
                    path=f"layouts.desktop.{index}.widget_id",
                    code="unknown_layout_widget",
                    message=f"Layout refers to unknown widget '{item.widget_id}'.",
                )
            )
        if item.x + item.w > 12:
            issues.append(
                ValidationIssue(
                    path=f"layouts.desktop.{index}",
                    code="layout_out_of_bounds",
                    message="Desktop layout item exceeds the 12-column grid.",
                )
            )
    missing_layout = set(widget_ids).difference(layout_ids)
    if missing_layout:
        issues.append(
            ValidationIssue(
                path="layouts.desktop",
                code="widget_without_layout",
                message=(
                    "Widgets missing desktop layout: "
                    f"{', '.join(sorted(missing_layout))}."
                ),
            )
        )
    if len(layout_ids) != len(set(layout_ids)):
        issues.append(
            ValidationIssue(
                path="layouts.desktop",
                code="duplicate_layout_widget",
                message="A widget can appear only once in the desktop layout.",
            )
        )
    return issues
