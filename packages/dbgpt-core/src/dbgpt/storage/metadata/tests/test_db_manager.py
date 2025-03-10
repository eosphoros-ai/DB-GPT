from __future__ import annotations

import tempfile
from typing import Type

import pytest
from sqlalchemy import Column, Integer, String

from dbgpt.storage.metadata.db_manager import (
    BaseModel,
    DatabaseManager,
    create_model,
)


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
        user = User(name="John Doe")
        session.add(user)

    # # Read
    with db.session() as session:
        user = session.query(User).filter_by(name="John Doe").first()
        assert user is not None

    # Update
    with db.session() as session:
        user = session.query(User).filter_by(name="John Doe").first()
        user.name = "Mike Doe"
        session.merge(user)
    with db.session() as session:
        user = session.query(User).filter_by(name="Mike Doe").first()
        assert user is not None
        session.query(User).filter(User.name == "John Doe").first() is None
    #
    # # Delete
    with db.session() as session:
        user = session.query(User).filter_by(name="Mike Doe").first()
        session.delete(user)

    with db.session() as session:
        assert len(session.query(User).all()) == 0


def test_crud_mixins(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()
    User.db() == db


def test_pagination_query(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()

    with db.session() as session:
        for i in range(30):
            user = User(name=f"User {i}")
            session.add(user)
    with db.session() as session:
        users_page_1 = session.query(User).paginate_query(page=1, per_page=10)
        assert len(users_page_1.items) == 10
        assert users_page_1.total_pages == 3


def test_invalid_pagination(db: DatabaseManager, Model: Type[BaseModel]):
    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    db.create_all()

    with pytest.raises(ValueError):
        with db.session() as session:
            session.query(User).paginate_query(page=0, per_page=10)
    with pytest.raises(ValueError):
        with db.session() as session:
            session.query(User).paginate_query(page=1, per_page=-1)


def test_set_model_db_manager(db: DatabaseManager, Model: Type[BaseModel]):
    assert db.metadata.tables == {}

    class User(Model):
        __tablename__ = "user"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    with tempfile.NamedTemporaryFile(delete=True) as db_file:
        filename = db_file.name
        new_db = DatabaseManager.build_from(
            f"sqlite:///{filename}", base=Model, override_query_class=True
        )
        Model.set_db(new_db)
        new_db.create_all()
        db.create_all()
        assert list(new_db.metadata.tables.keys())[0] == "user"
        with new_db.session() as session:
            user = User(name="John Doe")
            session.add(user)
        with new_db.session() as session:
            assert session.query(User).filter_by(name="John Doe").first() is not None
        with db.session() as session:
            assert session.query(User).filter_by(name="John Doe").first() is None
        with new_db.session() as session:
            session.query(User).all() == 1
            session.query(User).filter(
                User.name == "John Doe"
            ).first().name == "John Doe"
