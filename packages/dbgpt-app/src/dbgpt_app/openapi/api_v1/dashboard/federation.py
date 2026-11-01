"""Bounded in-memory combination for independently executed data sources."""

import json
from typing import Any, Dict, List, Tuple

from .schemas import FederatedQuery, FederationJoinType, FederationMode


class DashboardFederationService:
    """Combine already-authorized source rows without executing SQL itself."""

    def __init__(
        self,
        *,
        max_input_rows: int = 5000,
        max_input_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.max_input_rows = max_input_rows
        self.max_input_bytes = max_input_bytes

    @staticmethod
    def _join_key(value: Any, *, field: str) -> Any:
        try:
            hash(value)
        except TypeError as exc:
            raise ValueError(
                f"Federation join field '{field}' must contain scalar values."
            ) from exc
        return value

    def combine(
        self,
        federation: FederatedQuery,
        source_rows: Dict[str, List[Dict[str, Any]]],
        output_columns: List[str],
        *,
        source_truncated: bool = False,
    ) -> Tuple[List[str], List[List[Any]], bool]:
        """Apply only the schema's bounded union or two-source equality join."""

        total_input_rows = sum(len(rows) for rows in source_rows.values())
        if total_input_rows > self.max_input_rows:
            raise ValueError(
                "Federation input exceeds the total row limit of "
                f"{self.max_input_rows}."
            )
        input_bytes = len(
            json.dumps(
                source_rows, ensure_ascii=False, separators=(",", ":"), default=str
            ).encode("utf-8")
        )
        if input_bytes > self.max_input_bytes:
            raise ValueError(
                "Federation input exceeds the in-memory byte limit of "
                f"{self.max_input_bytes}."
            )

        output_limit = federation.max_output_rows
        truncated = source_truncated
        combined_rows: List[Dict[str, Any]] = []
        if federation.mode == FederationMode.UNION_ALL:
            for source in federation.sources:
                for row in source_rows[source.alias]:
                    missing = set(output_columns).difference(row)
                    if missing:
                        raise ValueError(
                            f"Federation source '{source.alias}' does not map: "
                            f"{', '.join(sorted(missing))}."
                        )
                    combined_rows.append(row)
                    if len(combined_rows) > output_limit:
                        truncated = True
                        break
                if len(combined_rows) > output_limit:
                    break
        elif federation.mode == FederationMode.JOIN:
            join = federation.join
            if join is None or len(federation.sources) != 2:
                raise ValueError(
                    "Federated join requires exactly two sources and join fields."
                )
            if join.left_alias == join.right_alias:
                raise ValueError("Federation join aliases must be different.")
            if (
                join.left_alias not in source_rows
                or join.right_alias not in source_rows
            ):
                raise ValueError("Federation join refers to an unknown source alias.")
            right_index: Dict[Any, List[Dict[str, Any]]] = {}
            for right_row in source_rows[join.right_alias]:
                if join.right_field not in right_row:
                    raise ValueError(
                        f"Right join field '{join.right_field}' is not mapped."
                    )
                key = self._join_key(
                    right_row[join.right_field], field=join.right_field
                )
                right_index.setdefault(key, []).append(right_row)

            for left_row in source_rows[join.left_alias]:
                if join.left_field not in left_row:
                    raise ValueError(
                        f"Left join field '{join.left_field}' is not mapped."
                    )
                key = self._join_key(left_row[join.left_field], field=join.left_field)
                matches = right_index.get(key, [])
                if not matches and join.join_type == FederationJoinType.LEFT:
                    matches = [{}]
                for right_row in matches:
                    combined = dict(left_row)
                    for name, value in right_row.items():
                        if name in combined and combined[name] != value:
                            raise ValueError(
                                f"Federation join produced conflicting output '{name}'."
                            )
                        combined[name] = value
                    combined_rows.append(combined)
                    if len(combined_rows) > output_limit:
                        truncated = True
                        break
                if len(combined_rows) > output_limit:
                    break
        else:  # pragma: no cover - enum validation guards this
            raise ValueError(f"Unsupported federation mode: {federation.mode}.")

        rows = [
            [row.get(column) for column in output_columns]
            for row in combined_rows[:output_limit]
        ]
        return output_columns, rows, truncated
