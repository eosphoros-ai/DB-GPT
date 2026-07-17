"""Read-only LSZYZD candidate adapter."""

from typing import Any, Optional

from sqlalchemy import column, select, table

from dbgpt_serve.auth.api.schemas import ImportCandidateResponse
from dbgpt_serve.auth.service.errors import ImportSourceError

LSZYZD_ALLOWED_FIELDS = {
    "employee_no": "LSZYZD_BH",
    "name": "LSZYZD_MC",
    "is_enabled": "LSZYZD_YXBZ",
    "category": "LSZYZD_LBBH",
    "position": "LSZYZD_ZW",
    "team": "LSZYZD_BANZU",
    "role_label": "LSZYZD_ROLE",
}
LSZYZD_REQUIRED_FIELDS = frozenset({"LSZYZD_BH", "LSZYZD_MC"})


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _optional_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "enabled", "启用"}:
        return True
    if normalized in {"0", "false", "no", "n", "disabled", "停用"}:
        return False
    return None


class LszyzdImporter:
    """Read only configured LSZYZD fields through a DB-GPT connector."""

    def __init__(
        self,
        connector_manager: Any,
        datasource_name: str,
        table_name: str = "LSZYZD",
    ) -> None:
        self._connector_manager = connector_manager
        self._datasource_name = datasource_name
        self._table_name = table_name

    @property
    def source_name(self) -> str:
        return self._datasource_name

    def preview(self, limit: int = 100) -> list[ImportCandidateResponse]:
        """Return bounded candidates without ever selecting password fields."""
        if limit < 1 or limit > 100:
            raise ValueError("Import preview limit must be between 1 and 100")
        try:
            connector = self._connector_manager.get_connector(self._datasource_name)
            actual_table_name = self._resolve_table_name(connector)
            columns_by_upper = {
                str(item["name"]).upper(): str(item["name"])
                for item in connector.get_columns(actual_table_name)
                if item.get("name")
            }
            missing = LSZYZD_REQUIRED_FIELDS - set(columns_by_upper)
            if missing:
                raise ImportSourceError(
                    f"LSZYZD is missing required fields: {sorted(missing)}"
                )

            selected_fields = {
                alias: columns_by_upper[column_name]
                for alias, column_name in LSZYZD_ALLOWED_FIELDS.items()
                if column_name in columns_by_upper
            }
            source_table = table(
                actual_table_name,
                *(column(name) for name in selected_fields.values()),
            )
            statement = (
                select(
                    *(
                        source_table.c[name].label(alias)
                        for alias, name in selected_fields.items()
                    )
                )
                .order_by(source_table.c[selected_fields["employee_no"]])
                .limit(limit)
            )
            with connector.session_scope(commit=False) as session:
                rows = session.execute(statement).mappings().all()
        except ImportSourceError:
            raise
        except Exception as exc:
            raise ImportSourceError("Configured LSZYZD source is unavailable") from exc

        return [self._to_candidate(dict(row)) for row in rows]

    def _resolve_table_name(self, connector: Any) -> str:
        table_names = {
            str(name).upper(): str(name) for name in connector.get_table_names()
        }
        actual_name = table_names.get(self._table_name.upper())
        if actual_name is None:
            raise ImportSourceError("Configured LSZYZD table does not exist")
        return actual_name

    @staticmethod
    def _to_candidate(row: dict[str, Any]) -> ImportCandidateResponse:
        employee_no = _optional_text(row.get("employee_no"))
        name = _optional_text(row.get("name"))
        if not employee_no or not name:
            raise ImportSourceError("LSZYZD contains a record without number or name")
        return ImportCandidateResponse(
            employee_no=employee_no,
            name=name,
            is_enabled=_optional_bool(row.get("is_enabled")),
            category=_optional_text(row.get("category")),
            position=_optional_text(row.get("position")),
            team=_optional_text(row.get("team")),
            role_label=_optional_text(row.get("role_label")),
        )
