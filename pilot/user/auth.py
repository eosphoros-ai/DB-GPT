from fastapi import Header
from pilot.user import UserDao, UserRequest


def get_user_from_headers(user_id: str = Header(...)):
    try:
        if user_id:
            # 确保数据库存在当前用户，如果不存在则抛出异常
            user_dao = UserDao()
            user_dao.get_by_user_id(user_id=user_id)
            return UserRequest(user_id=user_id)
        else:
            raise f"User Not Login"
    except Exception as e:
        raise f"Authentication failed. {str(e)}"
