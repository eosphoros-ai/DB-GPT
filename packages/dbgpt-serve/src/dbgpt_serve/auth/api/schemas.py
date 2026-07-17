"""Pydantic schemas for authentication endpoints."""

import json
from datetime import date, datetime
from typing import Generic, Literal, Optional, TypeVar

from pydantic import SecretStr, model_validator

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, field_validator
from dbgpt_serve.auth.models.models import UserEntity

T = TypeVar("T")
RoleName = Literal["system_admin", "operations_admin", "query_user"]
CreatableRoleName = Literal["operations_admin", "query_user"]
ResourceTypeName = Literal["DATASOURCE", "KNOWLEDGE_BASE", "AGENT"]


def _trim_required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


class LoginRequest(BaseModel):
    """Credentials accepted by the login endpoint."""

    login_name: str = Field(min_length=1, max_length=128)
    password: str

    @field_validator("login_name")
    @classmethod
    def normalize_login_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("login_name must not be blank")
        return value


class UserResponse(BaseModel):
    """Non-sensitive user fields returned by authentication APIs."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    login_name: str
    display_name: str
    role: str
    is_active: bool
    gmt_created: datetime
    disabled_at: datetime | None = None

    @classmethod
    def from_entity(cls, entity: UserEntity) -> "UserResponse":
        return cls.model_validate(entity)


class UserCreateRequest(BaseModel):
    """Administrator-supplied fields for a new independent DB-GPT user."""

    login_name: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    role: CreatableRoleName
    initial_password: Optional[SecretStr] = None
    send_activation: bool = False
    initial_account_set_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("login_name", "display_name")
    @classmethod
    def normalize_required_text(cls, value: str, info) -> str:
        return _trim_required(value, info.field_name)

    @field_validator("login_name")
    @classmethod
    def reject_login_whitespace(cls, value: str) -> str:
        if any(character.isspace() for character in value):
            raise ValueError("login_name must not contain whitespace")
        return value


class UserUpdateRequest(BaseModel):
    """Partial user update with explicit confirmation for role changes."""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[RoleName] = None
    change_reason: Optional[str] = Field(default=None, max_length=512)
    confirm_role_change: bool = False

    @field_validator("display_name", "change_reason")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        return _trim_required(value, info.field_name)

    @model_validator(mode="after")
    def require_update_field(self):
        if self.display_name is None and self.role is None:
            raise ValueError("At least one user field must be updated")
        return self


class UserListRequest(BaseModel):
    """Supported user list filters."""

    login_name_like: Optional[str] = Field(default=None, max_length=128)
    display_name_like: Optional[str] = Field(default=None, max_length=255)
    role: Optional[RoleName] = None
    is_active: Optional[bool] = None


class SetPasswordRequest(BaseModel):
    """Administrative password replacement."""

    new_password: SecretStr


class AccountSetCreateRequest(BaseModel):
    """Create an internal account-set directory entry."""

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _trim_required(value, "name")


class AccountSetUpdateRequest(BaseModel):
    """Partial account-set directory update."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        return _trim_required(value, "name") if value is not None else None

    @model_validator(mode="after")
    def require_update_field(self):
        if not self.model_fields_set.intersection({"name", "description"}):
            raise ValueError("At least one account-set field must be updated")
        return self


class AccountSetResponse(BaseModel):
    """Public account-set directory fields."""

    model_config = ConfigDict(from_attributes=True)

    account_set_id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    gmt_created: datetime


class ConfirmImpactRequest(BaseModel):
    """Confirmation payload for a high-risk state change."""

    reason: str = Field(min_length=1, max_length=512)
    confirm_impact: bool = False
    impact_token: str = Field(min_length=64, max_length=64)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return _trim_required(value, "reason")


class AccountSetImpactResponse(BaseModel):
    """Current impact snapshot for account-set deactivation."""

    account_set_id: str
    user_grant_count: int
    resource_grant_count: int
    resource_count: int
    impact_token: str


class RoleResponse(BaseModel):
    """Read-only fixed role and capability group."""

    role: RoleName
    permissions: list[str]
    user_count: int


class UserAccountGrantRequest(BaseModel):
    """Grant one active account set to a non-system administrator."""

    account_set_id: str = Field(min_length=1, max_length=128)


class UserAccountGrantResponse(BaseModel):
    """Persisted user account-set grant."""

    model_config = ConfigDict(from_attributes=True)

    grant_id: str
    user_id: str
    account_set_id: str
    is_active: bool
    granted_by: str
    revoked_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revoke_reason: Optional[str] = None
    gmt_created: datetime


class UserResourceGrantRequest(BaseModel):
    """Grant one concrete protected resource to a query user."""

    resource_type: ResourceTypeName
    resource_id: str = Field(min_length=1, max_length=128)


class UserResourceGrantResponse(BaseModel):
    """Persisted query-user resource grant."""

    model_config = ConfigDict(from_attributes=True)

    grant_id: str
    user_id: str
    resource_type: ResourceTypeName
    resource_id: str
    account_set_id: str
    is_active: bool
    granted_by: str
    revoked_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revoke_reason: Optional[str] = None
    gmt_created: datetime


class RevokeRequest(BaseModel):
    """Reason required for an auditable grant revocation."""

    reason: str = Field(min_length=1, max_length=512)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return _trim_required(value, "reason")


class ConfirmRevokeRequest(RevokeRequest):
    """Current-impact confirmation for account-set grant revocation."""

    confirm_impact: bool = False
    impact_token: str = Field(min_length=64, max_length=64)


class RevokeImpactResponse(BaseModel):
    """Resource grants affected by revoking a user's account-set scope."""

    grant_id: str
    affected_resource_grants: int
    affected_grants_detail: list[dict]
    impact_token: str


class ResourceResponse(BaseModel):
    """Common administration view over all protected resource types."""

    resource_type: ResourceTypeName
    resource_id: str
    name: str
    account_set_id: Optional[str] = None


class ResourceImpactResponse(BaseModel):
    """Current grant impact of changing a resource's account-set owner."""

    resource_type: ResourceTypeName
    resource_id: str
    current_account_set_id: Optional[str] = None
    new_account_set_id: str
    affected_resource_grants: int
    affected_agent_grants: int
    affected_grants_detail: list[dict]
    impact_token: str


class AssignResourceAccountRequest(BaseModel):
    """Confirmed high-risk account-set assignment for a resource."""

    account_set_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=512)
    confirm_impact: bool = False
    impact_token: str = Field(min_length=64, max_length=64)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return _trim_required(value, "reason")


class TokenUsageCreate(BaseModel):
    """One physical model call to meter exactly once."""

    call_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    role_snapshot: RoleName
    account_set_id: Optional[str] = Field(default=None, max_length=128)
    account_set_snapshot: Optional[str] = Field(default=None, max_length=255)
    entry_resource_type: Optional[ResourceTypeName] = None
    entry_resource_id: Optional[str] = Field(default=None, max_length=128)
    agent_id: Optional[str] = Field(default=None, max_length=128)
    model: str = Field(min_length=1, max_length=255)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    metering_source: Literal["provider", "estimated", "unknown"]
    duration_ms: Optional[int] = Field(default=None, ge=0)
    status: Literal["success", "failed"]
    error_type: Optional[str] = Field(default=None, max_length=64)
    gmt_created: datetime

    @model_validator(mode="after")
    def validate_token_total(self):
        if self.metering_source != "unknown" and self.total_tokens != (
            self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


class TokenUsageQueryRequest(BaseModel):
    """Supported filters for usage details and daily aggregates."""

    user_id: Optional[str] = Field(default=None, max_length=128)
    account_set_id: Optional[str] = Field(default=None, max_length=128)
    model: Optional[str] = Field(default=None, max_length=255)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    role: Optional[RoleName] = None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


class TokenUsageResponse(BaseModel):
    """Stored model-call usage detail."""

    model_config = ConfigDict(from_attributes=True)

    call_id: str
    request_id: str
    session_id: Optional[str] = None
    user_id: str
    role_snapshot: RoleName
    account_set_id: Optional[str] = None
    account_set_snapshot: Optional[str] = None
    entry_resource_type: Optional[ResourceTypeName] = None
    entry_resource_id: Optional[str] = None
    agent_id: Optional[str] = None
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    metering_source: str
    duration_ms: Optional[int] = None
    status: str
    error_type: Optional[str] = None
    gmt_created: datetime


class TokenDailyResponse(BaseModel):
    """Asia/Shanghai natural-day aggregate."""

    model_config = ConfigDict(from_attributes=True)

    stat_date: str
    user_id: str
    role_snapshot: RoleName
    account_set_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    call_count: int


class TokenUsageSummaryResponse(BaseModel):
    """Usage totals for one reporting day and the caller's data scope."""

    stat_date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    call_count: int


class AuditEventCreate(BaseModel):
    """Sanitized append-only audit event payload."""

    event_id: Optional[str] = Field(default=None, max_length=128)
    event_time: datetime
    operator_user_id: Optional[str] = Field(default=None, max_length=128)
    operator_role_snapshot: Optional[RoleName] = None
    target_account_set_id: Optional[str] = Field(default=None, max_length=128)
    target_type: str = Field(min_length=1, max_length=64)
    target_id: Optional[str] = Field(default=None, max_length=128)
    action: str = Field(min_length=1, max_length=64)
    result: Literal["success", "failed", "denied"]
    source_ip: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=512)
    request_id: Optional[str] = Field(default=None, max_length=128)
    before_snapshot: Optional[str] = None
    after_snapshot: Optional[str] = None
    deny_reason: Optional[str] = Field(default=None, max_length=512)


class AuditQueryRequest(BaseModel):
    """Indexed audit filters plus an event-time range."""

    target_type: Optional[str] = Field(default=None, max_length=64)
    action: Optional[str] = Field(default=None, max_length=64)
    operator_user_id: Optional[str] = Field(default=None, max_length=128)
    result: Optional[Literal["success", "failed", "denied"]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


class AuditEventResponse(AuditEventCreate):
    """Persisted audit event returned to a system administrator."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str


class ImportCandidateResponse(BaseModel):
    """Allowed LSZYZD candidate fields only."""

    employee_no: str
    name: str
    is_enabled: Optional[bool] = None
    category: Optional[str] = None
    position: Optional[str] = None
    team: Optional[str] = None
    role_label: Optional[str] = None


class ImportUserRequest(BaseModel):
    """Administrator choices for one imported independent account."""

    employee_no: str = Field(min_length=1, max_length=128)
    login_name: str = Field(min_length=1, max_length=128)
    role: CreatableRoleName
    initial_password: SecretStr
    initial_account_set_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("employee_no", "login_name")
    @classmethod
    def normalize_required_text(cls, value: str, info) -> str:
        return _trim_required(value, info.field_name)


class ImportBatchRequest(BaseModel):
    """Commit a bounded one-time LSZYZD selection."""

    users: list[ImportUserRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_unique_selection(self):
        employee_numbers = [item.employee_no for item in self.users]
        login_names = [item.login_name for item in self.users]
        if len(employee_numbers) != len(set(employee_numbers)):
            raise ValueError("employee_no values must be unique within a batch")
        if len(login_names) != len(set(login_names)):
            raise ValueError("login_name values must be unique within a batch")
        return self


class ImportBatchResponse(BaseModel):
    """Password-free result and duplicate-reminder summary."""

    batch_id: str
    source_name: str
    selected_count: int
    created_count: int
    skipped_count: int
    selected_summary: list[dict]
    result_summary: list[dict]
    gmt_created: datetime

    @classmethod
    def from_entity(cls, entity) -> "ImportBatchResponse":
        return cls(
            batch_id=entity.batch_id,
            source_name=entity.source_name,
            selected_count=entity.selected_count,
            created_count=entity.created_count,
            skipped_count=entity.skipped_count,
            selected_summary=json.loads(entity.selected_summary or "[]"),
            result_summary=json.loads(entity.result_summary or "[]"),
            gmt_created=entity.gmt_created,
        )


class Page(BaseModel, Generic[T]):
    """Stable administration pagination envelope."""

    items: list[T]
    total: int
    page: int
    page_size: int


class LoginResponse(BaseModel):
    """Successful authentication response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
