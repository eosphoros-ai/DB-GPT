from typing import Type

from sqlalchemy.orm import Session

from dbgpt.core.interface.prompt import PromptTemplateIdentifier, StoragePromptTemplate
from dbgpt.core.interface.storage import StorageItemAdapter

from .models import ServeEntity


class PromptTemplateAdapter(StorageItemAdapter[StoragePromptTemplate, ServeEntity]):
    def to_storage_format(self, item: StoragePromptTemplate) -> ServeEntity:
        return ServeEntity(
            chat_scene=item.chat_scene,
            sub_chat_scene=item.sub_chat_scene,
            prompt_type=item.prompt_type,
            prompt_name=item.prompt_name,
            content=item.content,
            input_variables=item.input_variables,
            model=item.model,
            prompt_language=item.prompt_language,
            prompt_format=item.prompt_format,
            user_name=item.user_name,
            sys_code=item.sys_code,
        )

    def from_storage_format(self, model: ServeEntity) -> StoragePromptTemplate:
        return StoragePromptTemplate(
            chat_scene=model.chat_scene,
            sub_chat_scene=model.sub_chat_scene,
            prompt_type=model.prompt_type,
            prompt_name=model.prompt_name,
            content=model.content,
            input_variables=model.input_variables,
            model=model.model,
            prompt_language=model.prompt_language,
            prompt_format=model.prompt_format,
            user_name=model.user_name,
            sys_code=model.sys_code,
        )

    def get_query_for_identifier(
        self,
        storage_format: Type[ServeEntity],
        resource_id: PromptTemplateIdentifier,
        **kwargs,
    ):
        session: Session = kwargs.get("session")
        if session is None:
            raise Exception("session is None")
        query_obj = session.query(ServeEntity)
        for key, value in resource_id.to_dict().items():
            if value is None:
                continue
            query_obj = query_obj.filter(getattr(ServeEntity, key) == value)
        return query_obj
