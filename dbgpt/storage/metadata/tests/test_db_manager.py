from __future__ import annotations
import pytest
from typing import Type
from dbgpt.storage.metadata.db_manager import (
    DatabaseManager,
    PaginationResult,
    create_model,
    BaseModel,
)
from sqlalchemy import Column, Integer, String


@pytest.fixture
def db():
    db = DatabaseManager()
    db.init_db("sqlite:///:memory:")
    return db


@pytest.fixture
def Model(db):
    return create_model(db)


def test_database_initialization(db: DatabaseManager, Model: Type[BaseModel]):
    assert db.engine is not None
    assert db.session is not None

    with db.session() as session:
        assert session is not None


def test_model_creation(db: DatabaseManager, Model: Type[BaseModel]):
    assert db.metadata.tables == {}

    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()
    assert list(db.metadata.tables.keys())[0] == "user"


def test_crud_operations(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()

    # Create
    with db.session() as session:
        user = User.create(name="John Doe")
        session.add(user)
        session.commit()

    # Read
    with db.session() as session:
        user = session.query(User).filter_by(name="John Doe").first()
        assert user is not None

    # Update
    with db.session() as session:
        user = session.query(User).filter_by(name="John Doe").first()
        user.update(name="Jane Doe")

    # Delete
    with db.session() as session:
        user = session.query(User).filter_by(name="Jane Doe").first()
        user.delete()


def test_crud_mixins(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()

    # Create
    user = User.create(name="John Doe")
    assert User.get(user.id) is not None
    users = User.all()
    assert len(users) == 1

    # Update
    user.update(name="Bob Doe")
    assert User.get(user.id).name == "Bob Doe"

    user = User.get(user.id)
    user.delete()
    assert User.get(user.id) is None


def test_pagination_query(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()

    # 添加数据
    with db.session() as session:
        for i in range(30):
            user = User(name=f"User {i}")
            session.add(user)
        session.commit()

    users_page_1 = User.query.paginate_query(page=1, per_page=10)
    assert len(users_page_1.items) == 10
    assert users_page_1.total_pages == 3


def test_invalid_pagination(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()

    with pytest.raises(ValueError):
        User.query.paginate_query(page=0, per_page=10)
    with pytest.raises(ValueError):
        User.query.paginate_query(page=1, per_page=-1)
