import pytest

from dbgpt.core.interface.prompt import PromptManager, PromptTemplate
from dbgpt.storage.metadata import db
from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
from dbgpt.util.serialization.json_serialization import JsonSerializer

from ..models.prompt_template_adapter import PromptTemplateAdapter, ServeEntity


@pytest.fixture
def serializer():
    return JsonSerializer()


@pytest.fixture
def db_url():
    """Use in-memory SQLite database for testing"""
    return "sqlite:///:memory:"


@pytest.fixture
def db_manager(db_url):
    db.init_db(db_url)
    db.create_all()
    return db


@pytest.fixture
def storage_adapter():
    return PromptTemplateAdapter()


@pytest.fixture
def storage(db_manager, serializer, storage_adapter):
    storage = SQLAlchemyStorage(
        db_manager,
        ServeEntity,
        storage_adapter,
        serializer,
    )
    return storage


@pytest.fixture
def prompt_manager(storage):
    return PromptManager(storage)


def test_save(prompt_manager: PromptManager):
    prompt_template = PromptTemplate(
        template="hello {input}",
        input_variables=["input"],
        template_scene="chat_normal",
    )
    prompt_manager.save(
        prompt_template,
        prompt_name="hello",
    )

    with db.session() as session:
        # Query from database
        result = (
            session.query(ServeEntity).filter(ServeEntity.prompt_name == "hello").all()
        )
        assert len(result) == 1
        assert result[0].prompt_name == "hello"
        assert result[0].content == "hello {input}"
        assert result[0].input_variables == "input"
    with db.session() as session:
        assert session.query(ServeEntity).count() == 1
        assert (
            session.query(ServeEntity)
            .filter(ServeEntity.prompt_name == "not exist prompt name")
            .count()
            == 0
        )


def test_prefer_query_language(prompt_manager: PromptManager):
    for language in ["en", "zh"]:
        prompt_template = PromptTemplate(
            template="test",
            input_variables=[],
            template_scene="chat_normal",
        )
        prompt_manager.save(
            prompt_template,
            prompt_name="test_prompt",
            prompt_language=language,
        )
    # Prefer zh, and zh exists, will return zh prompt template
    result = prompt_manager.prefer_query("test_prompt", prefer_prompt_language="zh")
    assert len(result) == 1
    assert result[0].content == "test"
    assert result[0].prompt_language == "zh"
    # Prefer language not exists, will return all prompt templates of this name
    result = prompt_manager.prefer_query(
        "test_prompt", prefer_prompt_language="not_exist"
    )
    assert len(result) == 2


def test_prefer_query_model(prompt_manager: PromptManager):
    for model in ["model1", "model2"]:
        prompt_template = PromptTemplate(
            template="test",
            input_variables=[],
            template_scene="chat_normal",
        )
        prompt_manager.save(
            prompt_template,
            prompt_name="test_prompt",
            model=model,
        )
    # Prefer model1, and model1 exists, will return model1 prompt template
    result = prompt_manager.prefer_query("test_prompt", prefer_model="model1")
    assert len(result) == 1
    assert result[0].content == "test"
    assert result[0].model == "model1"
    # Prefer model not exists, will return all prompt templates of this name
    result = prompt_manager.prefer_query("test_prompt", prefer_model="not_exist")
    assert len(result) == 2


def test_list(prompt_manager: PromptManager):
    for i in range(10):
        prompt_template = PromptTemplate(
            template="test",
            input_variables=[],
            template_scene="chat_normal",
        )
        prompt_manager.save(
            prompt_template,
            prompt_name=f"test_prompt_{i}",
            sys_code="dbgpt" if i % 2 == 0 else "not_dbgpt",
        )
    # Test list all
    result = prompt_manager.list()
    assert len(result) == 10

    for i in range(10):
        assert len(prompt_manager.list(prompt_name=f"test_prompt_{i}")) == 1
    assert len(prompt_manager.list(sys_code="dbgpt")) == 5
