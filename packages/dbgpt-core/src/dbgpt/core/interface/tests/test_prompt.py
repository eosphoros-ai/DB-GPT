import json

import pytest

from dbgpt.core.interface.prompt import (
    PromptManager,
    PromptTemplate,
    StoragePromptTemplate,
)
from dbgpt.core.interface.storage import QuerySpec


@pytest.fixture
def sample_storage_prompt_template():
    return StoragePromptTemplate(
        prompt_name="test_prompt",
        content="Sample content, {var1}, {var2}",
        prompt_language="en",
        prompt_format="f-string",
        input_variables="var1,var2",
        model="model1",
        chat_scene="scene1",
        sub_chat_scene="subscene1",
        prompt_type="type1",
        user_name="user1",
        sys_code="code1",
    )


@pytest.fixture
def complex_storage_prompt_template():
    content = """Database name: {db_name} Table structure definition: {table_info} 
    User Question:{user_input}"""
    return StoragePromptTemplate(
        prompt_name="chat_data_auto_execute_prompt",
        content=content,
        prompt_language="en",
        prompt_format="f-string",
        input_variables="db_name,table_info,user_input",
        model="vicuna-13b-v1.5",
        chat_scene="chat_data",
        sub_chat_scene="subscene1",
        prompt_type="common",
        user_name="zhangsan",
        sys_code="dbgpt",
    )


@pytest.fixture
def prompt_manager(in_memory_storage):
    return PromptManager(storage=in_memory_storage)


class TestPromptTemplate:
    @pytest.mark.parametrize(
        "template_str, input_vars, expected_output",
        [
            ("Hello {name}", {"name": "World"}, "Hello World"),
            ("{greeting}, {name}", {"greeting": "Hi", "name": "Alice"}, "Hi, Alice"),
        ],
    )
    def test_format_f_string(self, template_str, input_vars, expected_output):
        prompt = PromptTemplate(
            template=template_str,
            input_variables=list(input_vars.keys()),
            template_format="f-string",
        )
        formatted_output = prompt.format(**input_vars)
        assert formatted_output == expected_output

    @pytest.mark.parametrize(
        "template_str, input_vars, expected_output",
        [
            ("Hello {{ name }}", {"name": "World"}, "Hello World"),
            (
                "{{ greeting }}, {{ name }}",
                {"greeting": "Hi", "name": "Alice"},
                "Hi, Alice",
            ),
        ],
    )
    def test_format_jinja2(self, template_str, input_vars, expected_output):
        prompt = PromptTemplate(
            template=template_str,
            input_variables=list(input_vars.keys()),
            template_format="jinja2",
        )
        formatted_output = prompt.format(**input_vars)
        assert formatted_output == expected_output

    def test_format_with_response_format(self):
        template_str = "Response: {response}"
        prompt = PromptTemplate(
            template=template_str,
            input_variables=["response"],
            template_format="f-string",
            response_format=json.dumps({"message": "hello"}),
        )
        formatted_output = prompt.format(response="hello")
        assert "Response: " in formatted_output

    def test_format_missing_variable(self):
        template_str = "Hello {name}"
        prompt = PromptTemplate(
            template=template_str, input_variables=["name"], template_format="f-string"
        )
        with pytest.raises(KeyError):
            prompt.format()

    def test_format_extra_variable(self):
        template_str = "Hello {name}"
        prompt = PromptTemplate(
            template=template_str,
            input_variables=["name"],
            template_format="f-string",
            template_is_strict=False,
        )
        formatted_output = prompt.format(name="World", extra="unused")
        assert formatted_output == "Hello World"

    def test_format_complex(self, complex_storage_prompt_template):
        prompt = complex_storage_prompt_template.to_prompt_template()
        formatted_output = prompt.format(
            db_name="db1",
            table_info="create table users(id int, name varchar(20))",
            user_input="find all users whose name is 'Alice'",
        )
        assert "create table users(id int, name varchar(20))" in formatted_output


class TestStoragePromptTemplate:
    def test_constructor_and_properties(self):
        storage_item = StoragePromptTemplate(
            prompt_name="test",
            content="Hello {name}",
            prompt_language="en",
            prompt_format="f-string",
            input_variables="name",
            model="model1",
            chat_scene="chat",
            sub_chat_scene="sub_chat",
            prompt_type="type",
            user_name="user",
            sys_code="sys",
        )
        assert storage_item.prompt_name == "test"
        assert storage_item.content == "Hello {name}"
        assert storage_item.prompt_language == "en"
        assert storage_item.prompt_format == "f-string"
        assert storage_item.input_variables == "name"
        assert storage_item.model == "model1"

    def test_constructor_exceptions(self):
        with pytest.raises(ValueError):
            StoragePromptTemplate(prompt_name=None, content="Hello")

    def test_to_prompt_template(self, sample_storage_prompt_template):
        prompt_template = sample_storage_prompt_template.to_prompt_template()
        assert isinstance(prompt_template, PromptTemplate)
        assert prompt_template.template == "Sample content, {var1}, {var2}"
        assert prompt_template.input_variables == ["var1", "var2"]

    def test_from_prompt_template(self):
        prompt_template = PromptTemplate(
            template="Sample content, {var1}, {var2}",
            input_variables=["var1", "var2"],
            template_format="f-string",
        )
        storage_prompt_template = StoragePromptTemplate.from_prompt_template(
            prompt_template=prompt_template, prompt_name="test_prompt"
        )
        assert storage_prompt_template.prompt_name == "test_prompt"
        assert storage_prompt_template.content == "Sample content, {var1}, {var2}"
        assert storage_prompt_template.input_variables == "var1,var2"

    def test_merge(self, sample_storage_prompt_template):
        other = StoragePromptTemplate(
            prompt_name="other_prompt",
            content="Other content",
        )
        sample_storage_prompt_template.merge(other)
        assert sample_storage_prompt_template.content == "Other content"

    def test_to_dict(self, sample_storage_prompt_template):
        result = sample_storage_prompt_template.to_dict()
        assert result == {
            "prompt_name": "test_prompt",
            "content": "Sample content, {var1}, {var2}",
            "prompt_language": "en",
            "prompt_format": "f-string",
            "input_variables": "var1,var2",
            "model": "model1",
            "chat_scene": "scene1",
            "sub_chat_scene": "subscene1",
            "prompt_type": "type1",
            "user_name": "user1",
            "sys_code": "code1",
        }

    def test_save_and_load_storage(
        self, sample_storage_prompt_template, in_memory_storage
    ):
        in_memory_storage.save(sample_storage_prompt_template)
        loaded_item = in_memory_storage.load(
            sample_storage_prompt_template.identifier, StoragePromptTemplate
        )
        assert loaded_item.content == "Sample content, {var1}, {var2}"

    def test_check_exceptions(self):
        with pytest.raises(ValueError):
            StoragePromptTemplate(prompt_name=None, content="Hello")

    def test_from_object(self, sample_storage_prompt_template):
        other = StoragePromptTemplate(prompt_name="other", content="Other content")
        sample_storage_prompt_template.from_object(other)
        assert sample_storage_prompt_template.content == "Other content"
        assert sample_storage_prompt_template.input_variables != "var1,var2"
        # Prompt name should not be changed
        assert sample_storage_prompt_template.prompt_name == "test_prompt"
        assert sample_storage_prompt_template.sys_code == "code1"


class TestPromptManager:
    def test_save(self, prompt_manager, in_memory_storage):
        prompt_template = PromptTemplate(
            template="hello {input}",
            input_variables=["input"],
            template_scene="chat_normal",
        )
        prompt_manager.save(
            prompt_template,
            prompt_name="hello",
        )
        result = in_memory_storage.query(
            QuerySpec(conditions={"prompt_name": "hello"}), StoragePromptTemplate
        )
        assert len(result) == 1
        assert result[0].content == "hello {input}"

    def test_prefer_query_simple(self, prompt_manager, in_memory_storage):
        in_memory_storage.save(
            StoragePromptTemplate(prompt_name="test_prompt", content="test")
        )
        result = prompt_manager.prefer_query("test_prompt")
        assert len(result) == 1
        assert result[0].content == "test"

    def test_prefer_query_language(self, prompt_manager, in_memory_storage):
        for language in ["en", "zh"]:
            in_memory_storage.save(
                StoragePromptTemplate(
                    prompt_name="test_prompt",
                    content="test",
                    prompt_language=language,
                )
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

    def test_prefer_query_model(self, prompt_manager, in_memory_storage):
        for model in ["model1", "model2"]:
            in_memory_storage.save(
                StoragePromptTemplate(
                    prompt_name="test_prompt", content="test", model=model
                )
            )
        # Prefer model1, and model1 exists, will return model1 prompt template
        result = prompt_manager.prefer_query("test_prompt", prefer_model="model1")
        assert len(result) == 1
        assert result[0].content == "test"
        assert result[0].model == "model1"
        # Prefer model not exists, will return all prompt templates of this name
        result = prompt_manager.prefer_query("test_prompt", prefer_model="not_exist")
        assert len(result) == 2

    def test_list(self, prompt_manager, in_memory_storage):
        prompt_manager.save(
            PromptTemplate(template="Hello {name}", input_variables=["name"]),
            prompt_name="name1",
        )
        prompt_manager.save(
            PromptTemplate(
                template="Write a SQL of {dialect} to query all data of {table_name}.",
                input_variables=["dialect", "table_name"],
            ),
            prompt_name="sql_template",
        )
        all_templates = prompt_manager.list()
        assert len(all_templates) == 2
        assert len(prompt_manager.list(prompt_name="name1")) == 1
        assert len(prompt_manager.list(prompt_name="not exist")) == 0

    def test_delete(self, prompt_manager, in_memory_storage):
        prompt_manager.save(
            PromptTemplate(template="Hello {name}", input_variables=["name"]),
            prompt_name="to_delete",
        )
        prompt_manager.delete("to_delete")
        result = in_memory_storage.query(
            QuerySpec(conditions={"prompt_name": "to_delete"}), StoragePromptTemplate
        )
        assert len(result) == 0
