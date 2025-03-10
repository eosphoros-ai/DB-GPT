from typing import Any, Dict, Optional, Type, Union

import pytest
from sqlalchemy import Column, Integer, String

from dbgpt._private.pydantic import BaseModel as PydanticBaseModel
from dbgpt._private.pydantic import Field, model_to_dict
from dbgpt.storage.metadata.db_manager import (
    BaseModel,
    DatabaseManager,
    PaginationResult,
    create_model,
)

from .._base_dao import BaseDao


class UserRequest(PydanticBaseModel):
    name: str = Field(..., description="User name")
    age: Optional[int] = Field(default=-1, description="User age")
    password: Optional[str] = Field(default="", description="User password")


class UserResponse(PydanticBaseModel):
    id: int = Field(..., description="User id")
    name: str = Field(..., description="User name")
    age: Optional[int] = Field(default=-1, description="User age")


@pytest.fixture
def db():
    db = DatabaseManager()
    db.init_db("sqlite:///:memory:")
    return db


@pytest.fixture
def Model(db):
    return create_model(db)


@pytest.fixture
def User(Model):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50), unique=True)
        age = Column(Integer)
        password = Column(String(50))

    return User


@pytest.fixture
def user_req():
    return UserRequest(name="Edward Snowden", age=30, password="123456")


@pytest.fixture
def user_dao(db, User):
    class UserDao(BaseDao[User, UserRequest, UserResponse]):
        def from_request(self, request: Union[UserRequest, Dict[str, Any]]) -> User:
            if isinstance(request, UserRequest):
                return User(**model_to_dict(request))
            else:
                return User(**request)

        def to_request(self, entity: User) -> UserRequest:
            return UserRequest(
                name=entity.name, age=entity.age, password=entity.password
            )

        def from_response(self, response: UserResponse) -> User:
            return User(**model_to_dict(response))

        def to_response(self, entity: User):
            return UserResponse(id=entity.id, name=entity.name, age=entity.age)

    db.create_all()
    return UserDao(db)


def test_create_user(db: DatabaseManager, User: Type[BaseModel], user_dao, user_req):
    user_dao.create(user_req)
    with db.session() as session:
        user = session.query(User).first()
        assert user.name == user_req.name
        assert user.age == user_req.age
        assert user.password == user_req.password


def test_update_user(db: DatabaseManager, User: Type[BaseModel], user_dao, user_req):
    # Create a user
    created_user_response = user_dao.create(user_req)

    # Update the user
    updated_req = UserRequest(name=user_req.name, age=35, password="newpassword")
    updated_user = user_dao.update(
        query_request={"name": user_req.name}, update_request=updated_req
    )
    assert updated_user.id == created_user_response.id
    assert updated_user.age == 35

    # Verify that the user is updated in the database
    with db.session() as session:
        user = session.get(User, created_user_response.id)
        assert user.age == 35


def test_update_user_partial(
    db: DatabaseManager, User: Type[BaseModel], user_dao, user_req
):
    # Create a user
    created_user_response = user_dao.create(user_req)

    # Update the user
    updated_req = UserRequest(name=user_req.name, password="newpassword")
    updated_req.age = None
    updated_user = user_dao.update(
        query_request={"name": user_req.name}, update_request=updated_req
    )
    assert updated_user.id == created_user_response.id
    assert updated_user.age == user_req.age

    # Verify that the user is updated in the database
    with db.session() as session:
        user = session.get(User, created_user_response.id)
        assert user.age == user_req.age
        assert user.password == "newpassword"


def test_get_user(db: DatabaseManager, User: Type[BaseModel], user_dao, user_req):
    # Create a user
    created_user_response = user_dao.create(user_req)

    # Query the user
    fetched_user = user_dao.get_one({"name": user_req.name})
    assert fetched_user.id == created_user_response.id
    assert fetched_user.name == user_req.name
    assert fetched_user.age == user_req.age


def test_get_list_user(db: DatabaseManager, User: Type[BaseModel], user_dao):
    for i in range(20):
        user_dao.create(
            UserRequest(
                name=f"User {i}", age=i, password="123456" if i % 2 == 0 else "abcdefg"
            )
        )
    # Query the user
    fetched_user = user_dao.get_list({"password": "123456"})
    assert len(fetched_user) == 10


def test_get_list_page_user(db: DatabaseManager, User: Type[BaseModel], user_dao):
    for i in range(20):
        user_dao.create(
            UserRequest(
                name=f"User {i}", age=i, password="123456" if i % 2 == 0 else "abcdefg"
            )
        )
    page_result: PaginationResult = user_dao.get_list_page(
        {"password": "123456"}, page=1, page_size=3
    )
    assert page_result.total_count == 10
    assert page_result.total_pages == 4
    assert len(page_result.items) == 3
    assert page_result.items[0].name == "User 0"

    # Test query next page
    page_result: PaginationResult = user_dao.get_list_page(
        {"password": "123456"}, page=2, page_size=3
    )
    assert page_result.total_count == 10
    assert page_result.total_pages == 4
    assert len(page_result.items) == 3
    assert page_result.items[0].name == "User 6"
