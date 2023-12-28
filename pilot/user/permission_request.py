
from pydantic import BaseModel


class UserPermissionRequest(BaseModel):
    id: int = None
    user_id: str = None
    resource_type: str = None
    resource_id: str = None
    permission_code: str = None
