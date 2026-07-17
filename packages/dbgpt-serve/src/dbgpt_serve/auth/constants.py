"""Fixed roles and capability groups for the authorization center."""

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "system_admin": frozenset(
        {
            "USER_MANAGE",
            "ROLE_READ",
            "USER_ROLE_ASSIGN",
            "ACCOUNT_SET_MANAGE",
            "USER_ACCOUNT_SET_GRANT",
            "USER_RESOURCE_GRANT",
            "DATASOURCE_MANAGE",
            "KNOWLEDGE_BASE_MANAGE",
            "AGENT_MANAGE",
            "DATASOURCE_USE",
            "KNOWLEDGE_BASE_USE",
            "AGENT_USE",
            "CHAT_USE",
            "USAGE_READ",
            "AUDIT_READ",
        }
    ),
    "operations_admin": frozenset(
        {
            "DATASOURCE_MANAGE",
            "KNOWLEDGE_BASE_MANAGE",
            "AGENT_MANAGE",
            "DATASOURCE_USE",
            "KNOWLEDGE_BASE_USE",
            "AGENT_USE",
            "CHAT_USE",
            "USAGE_READ",
        }
    ),
    "query_user": frozenset(
        {
            "DATASOURCE_USE",
            "KNOWLEDGE_BASE_USE",
            "AGENT_USE",
            "CHAT_USE",
            "USAGE_READ",
        }
    ),
}

FIXED_ROLES = frozenset(ROLE_PERMISSIONS)
