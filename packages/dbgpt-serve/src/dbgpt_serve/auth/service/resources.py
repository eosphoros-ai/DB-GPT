"""Uniform SQLAlchemy access to protected DB-GPT resource tables."""

import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import column, func, select, table, update


class ResourceLookupError(ValueError):
    """Raised when a resource identifier or dependency cannot be resolved."""


@dataclass(frozen=True)
class ResourceDefinition:
    resource_type: str
    table_name: str
    id_column: str
    name_column: str
    numeric_id: bool = True

    @property
    def table(self):
        return table(
            self.table_name,
            column(self.id_column),
            column(self.name_column),
            column("account_set_id"),
        )


@dataclass(frozen=True)
class ResourceRecord:
    resource_type: str
    resource_id: str
    name: str
    account_set_id: Optional[str]


RESOURCE_DEFINITIONS = {
    "DATASOURCE": ResourceDefinition("DATASOURCE", "connect_config", "id", "db_name"),
    "KNOWLEDGE_BASE": ResourceDefinition(
        "KNOWLEDGE_BASE", "knowledge_space", "id", "name"
    ),
    "AGENT": ResourceDefinition(
        "AGENT", "gpts_app", "app_code", "app_name", numeric_id=False
    ),
}

_DEPENDENCY_TYPES = {
    "database": "DATASOURCE",
    "db": "DATASOURCE",
    "datasource": "DATASOURCE",
    "knowledge": "KNOWLEDGE_BASE",
    "knowledge_base": "KNOWLEDGE_BASE",
}


def resource_definition(resource_type: str) -> ResourceDefinition:
    try:
        return RESOURCE_DEFINITIONS[resource_type]
    except KeyError as exc:
        raise ResourceLookupError(
            f"Unsupported resource type: {resource_type}"
        ) from exc


def _storage_id(definition: ResourceDefinition, resource_id: str) -> Any:
    normalized = str(resource_id).strip()
    if not normalized:
        raise ResourceLookupError("Resource ID must not be blank")
    if not definition.numeric_id:
        return normalized
    try:
        return int(normalized)
    except ValueError as exc:
        raise ResourceLookupError(
            f"{definition.resource_type} resource ID must be an integer"
        ) from exc


def get_resource(
    session, resource_type: str, resource_id: str, *, for_update: bool = False
) -> Optional[ResourceRecord]:
    definition = resource_definition(resource_type)
    resource_table = definition.table
    statement = select(
        resource_table.c[definition.id_column].label("resource_id"),
        resource_table.c[definition.name_column].label("name"),
        resource_table.c.account_set_id,
    ).where(
        resource_table.c[definition.id_column] == _storage_id(definition, resource_id)
    )
    if for_update:
        statement = statement.with_for_update()
    row = session.execute(statement).mappings().first()
    if row is None:
        return None
    return ResourceRecord(
        resource_type=resource_type,
        resource_id=str(row["resource_id"]),
        name=str(row["name"]),
        account_set_id=row["account_set_id"],
    )


def list_resources(
    session,
    resource_type: str,
    *,
    account_set_ids: Optional[set[str]] = None,
    account_set_id: Optional[str] = None,
    unassigned: bool = False,
    offset: int = 0,
    limit: Optional[int] = None,
) -> list[ResourceRecord]:
    definition = resource_definition(resource_type)
    resource_table = definition.table
    statement = select(
        resource_table.c[definition.id_column].label("resource_id"),
        resource_table.c[definition.name_column].label("name"),
        resource_table.c.account_set_id,
    )
    if account_set_ids is not None:
        if not account_set_ids:
            return []
        statement = statement.where(
            resource_table.c.account_set_id.in_(sorted(account_set_ids))
        )
    if account_set_id is not None:
        statement = statement.where(resource_table.c.account_set_id == account_set_id)
    if unassigned:
        statement = statement.where(resource_table.c.account_set_id.is_(None))
    statement = statement.order_by(resource_table.c[definition.name_column])
    statement = statement.offset(offset)
    if limit is not None:
        statement = statement.limit(limit)
    return [
        ResourceRecord(
            resource_type=resource_type,
            resource_id=str(row["resource_id"]),
            name=str(row["name"]),
            account_set_id=row["account_set_id"],
        )
        for row in session.execute(statement).mappings().all()
    ]


def count_resources(
    session,
    resource_type: str,
    *,
    account_set_ids: Optional[set[str]] = None,
    account_set_id: Optional[str] = None,
    unassigned: bool = False,
) -> int:
    definition = resource_definition(resource_type)
    resource_table = definition.table
    if account_set_ids is not None and not account_set_ids:
        return 0
    statement = select(func.count()).select_from(resource_table)
    if account_set_ids is not None:
        statement = statement.where(
            resource_table.c.account_set_id.in_(sorted(account_set_ids))
        )
    if account_set_id is not None:
        statement = statement.where(resource_table.c.account_set_id == account_set_id)
    if unassigned:
        statement = statement.where(resource_table.c.account_set_id.is_(None))
    return session.execute(statement).scalar_one()


def assign_resource_account(
    session, resource_type: str, resource_id: str, account_set_id: str
) -> None:
    definition = resource_definition(resource_type)
    resource_table = definition.table
    session.execute(
        update(resource_table)
        .where(
            resource_table.c[definition.id_column]
            == _storage_id(definition, resource_id)
        )
        .values(account_set_id=account_set_id)
    )


def agent_dependencies(session, agent_id: str) -> list[ResourceRecord]:
    """Resolve datasource and knowledge dependencies stored on an agent."""
    detail_table = table("gpts_app_detail", column("app_code"), column("resources"))
    rows = session.execute(
        select(detail_table.c.resources).where(detail_table.c.app_code == agent_id)
    ).all()
    dependencies: dict[tuple[str, str], ResourceRecord] = {}
    for (serialized,) in rows:
        if not serialized:
            continue
        try:
            items = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ResourceLookupError(
                f"Agent {agent_id} contains invalid dependency metadata"
            ) from exc
        if not isinstance(items, list):
            raise ResourceLookupError(
                f"Agent {agent_id} contains invalid dependency metadata"
            )
        for item in items:
            dependency = _resolve_dependency(session, agent_id, item)
            if dependency is not None:
                dependencies[(dependency.resource_type, dependency.resource_id)] = (
                    dependency
                )
    return list(dependencies.values())


def dependent_agent_ids(session, dependency_type: str, dependency_id: str) -> set[str]:
    """Find agents whose stored configuration references a protected resource."""
    app_table = RESOURCE_DEFINITIONS["AGENT"].table
    agent_ids = {
        str(value)
        for value in session.execute(select(app_table.c.app_code)).scalars().all()
    }
    matches: set[str] = set()
    for agent_id in agent_ids:
        for dependency in agent_dependencies(session, agent_id):
            if (
                dependency.resource_type == dependency_type
                and dependency.resource_id == str(dependency_id)
            ):
                matches.add(agent_id)
                break
    return matches


def _resolve_dependency(session, agent_id: str, item: Any) -> Optional[ResourceRecord]:
    if not isinstance(item, dict):
        raise ResourceLookupError(
            f"Agent {agent_id} contains invalid dependency metadata"
        )
    resource_type = _DEPENDENCY_TYPES.get(str(item.get("type", "")).lower())
    if resource_type is None:
        return None
    raw_value = item.get("value")
    if isinstance(raw_value, str):
        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            decoded_value = raw_value
    else:
        decoded_value = raw_value
    lookup_value = _dependency_lookup_value(resource_type, decoded_value)
    if lookup_value is None:
        raise ResourceLookupError(
            f"Agent {agent_id} has an unresolved {resource_type} dependency"
        )
    dependency = _get_resource_by_id_or_name(session, resource_type, lookup_value)
    if dependency is None:
        raise ResourceLookupError(
            f"Agent {agent_id} references a missing {resource_type} dependency"
        )
    return dependency


def _dependency_lookup_value(resource_type: str, value: Any) -> Optional[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if not isinstance(value, dict):
        return None
    preferred_keys = (
        ("resource_id", "db_name", "id", "value", "name")
        if resource_type == "DATASOURCE"
        else ("resource_id", "space_name", "id", "value", "name")
    )
    for key in preferred_keys:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None


def _get_resource_by_id_or_name(
    session, resource_type: str, lookup_value: str
) -> Optional[ResourceRecord]:
    definition = resource_definition(resource_type)
    try:
        by_id = get_resource(session, resource_type, lookup_value)
    except ResourceLookupError:
        by_id = None
    if by_id is not None:
        return by_id
    resource_table = definition.table
    row = (
        session.execute(
            select(
                resource_table.c[definition.id_column].label("resource_id"),
                resource_table.c[definition.name_column].label("name"),
                resource_table.c.account_set_id,
            ).where(resource_table.c[definition.name_column] == lookup_value)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return ResourceRecord(
        resource_type=resource_type,
        resource_id=str(row["resource_id"]),
        name=str(row["name"]),
        account_set_id=row["account_set_id"],
    )
