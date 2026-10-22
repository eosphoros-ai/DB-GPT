# Define your Pydantic schemas here
from datetime import datetime
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field


class SuiteRequest(BaseModel):
    """Query / mutation request for the suite registry."""

    name: Optional[str] = Field(None, description="Suite slug, e.g. db-query")
    workspace_id: Optional[str] = Field(
        None, description="Workspace (instance) scope; None = global"
    )
    user_name: Optional[str] = Field(None, description="Operator user name")


class SuiteResponse(BaseModel):
    """Registry row plus the renderable manifest projection."""

    id: Optional[int] = Field(None, description="Auto increment id")
    name: str = Field(..., description="Suite slug")
    display: Optional[str] = Field(None, description="Display name")
    icon: Optional[str] = Field(None, description="Icon emoji")
    scenario_id: Optional[str] = Field(None, description="query|analysis|ops")
    version: str = Field(..., description="Installed / active version")
    source: str = Field("official", description="official|enterprise|market")
    execution: Optional[str] = Field("react", description="react|flow")
    status: str = Field("installed", description="installed|enabled|disabled")
    workspace_id: Optional[str] = Field(None, description="Instance-level scope")
    package_path: Optional[str] = Field(None, description="Package location")
    package_digest: Optional[str] = Field(None, description="sha256 of package")
    manifest_snapshot: Optional[Dict[str, Any]] = Field(
        None, description="Derived renderable projection, rebuildable from package"
    )
    readme: Optional[str] = Field(
        None, description="Package README.md text (detail page only, read from disk)"
    )
    use_count: Optional[int] = Field(0, description="Pin / invoke count")
    enabled_at: Optional[datetime] = Field(None, description="Last enabled time")
    user_name: Optional[str] = Field(None, description="Installer / owner")
    gmt_created: Optional[datetime] = Field(None, description="Install time")
    gmt_modified: Optional[datetime] = Field(None, description="Update time")


class SuiteEventResponse(BaseModel):
    """Audit / timeline event row."""

    id: Optional[int] = None
    suite_name: str = Field(..., description="Suite slug")
    event_type: str = Field(
        ..., description="install|enable|disable|uninstall|upgrade|switch|pin"
    )
    from_version: Optional[str] = None
    to_version: Optional[str] = None
    conv_uid: Optional[str] = Field(None, description="Conversation for switch/pin")
    workspace_id: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    user_name: Optional[str] = None
    gmt_created: Optional[datetime] = None


class SuiteSyncSummary(BaseModel):
    """Result of a startup / manual sync of official suite packages."""

    installed: List[str] = Field(default_factory=list)
    upgraded: List[str] = Field(default_factory=list)
    unchanged: List[str] = Field(default_factory=list)
    disabled_missing: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
