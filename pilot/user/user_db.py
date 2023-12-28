from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import Base, engine, session
from pilot.configs.config import Config
from datetime import datetime

from sqlalchemy import Column, String, DateTime
from pilot.user.user_request import UserRequest
import uuid

CFG = Config()

DB_AUTH = "auth"
TABLE_USER = "user"


class UserEntity(Base):
    __tablename__ = TABLE_USER
    user_id = Column(String(36), primary_key=True)
    nick_name = Column(String(127))
    user_no = Column(String(127))
    user_channel = Column(String(127))
    role = Column(String(100))
    email = Column(String(100))
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)
    avatar_url = Column(String(256))

    def __repr__(self):
        return f"UserEntity(user_id='{self.user_id}', nick_name='{self.nick_name}', user_no='{self.user_no}', user_channel='{self.user_channel}', role='{self.role}', email='{self.email}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class UserDao(BaseDao):
    def __init__(self):
        """
          create database `auth` firstly.
        """
        super().__init__(
            database=DB_AUTH, orm_base=Base, db_engine=engine, session=session
        )

    def get_by_user_id(self, user_id: str):
        """
          get user info by user_id
        """
        session = self.get_session()
        user_query = session.query(UserEntity).filter(UserEntity.user_id == user_id)
        result = user_query.all()
        session.close()

        if len(result) > 0:
            return result[0]
        raise f"user({user_id}) is not existed!"

    def get_by_user_no_and_channel(self, user_no: str, user_channel: str):
        """
          query user by user_no
        """
        session = self.get_session()
        user_query = session.query(UserEntity).filter(
            UserEntity.user_no == user_no
        ).filter(
            UserEntity.user_channel == user_channel
        )

        result = user_query.all()
        session.close()
        return result

    def add_user_if_not_exist(self, user_req: UserRequest):
        """
          check before do addition, add new user.
        """
        if user_req is None:
            raise f"user info is empty!"

        # new user, by user_channel and user_no:
        if user_req.user_no is not None and user_req.user_channel is not None:
            result = self.get_by_user_no_and_channel(user_req.user_no, user_req.user_channel)
            if len(result) == 0:
                session = self.get_session()
                user = UserEntity(
                    user_id=uuid.uuid4().hex,
                    nick_name=user_req.nick_name,
                    user_no=user_req.user_no,
                    user_channel=user_req.user_channel,
                    role=user_req.role,
                    email=user_req.email,
                    gmt_created=datetime.now(),
                    gmt_modified=datetime.now(),
                    avatar_url=user_req.avatar_url
                )
                session.add(user)
                session.commit()
                session.close()
                return self.get_by_user_no_and_channel(user_no=user_req.user_no, user_channel=user_req.user_channel)[0]
        return None

    def get_all_users(self):
        """
          query user by user_no
        """
        session = self.get_session()
        user_query = session.query(UserEntity).order_by(
            UserEntity.gmt_created.desc()
        )
        result = user_query.all()
        session.close()
        return result

    def update_user(self, user: UserEntity):
        session = self.get_session()
        session.merge(user)
        session.commit()
        session.close()
        return True

    def delete_user(self, user: UserEntity):
        session = self.get_session()
        if user:
            session.delete(user)
            session.commit()
        session.close()


if __name__ == "__main__":
    user_dao = UserDao()

    result = user_dao.get_all_users()
    print(result)

    user_dao.add_user_if_not_exist(UserRequest(user_no="101", nick_name="shine", user_channel="GITHUB"))
    result2 = user_dao.get_by_user_no_and_channel("101", "GITHUB")
    print(result2)

    result3 = user_dao.get_all_users()
    print(result3)

    user_dao.delete_user(result2[0])
    result4 = user_dao.get_all_users()
    print(result4)


    user: UserEntity = result3[0]
    ret5 = user_dao.get_by_user_id(user.user_id)
    print(ret5)
