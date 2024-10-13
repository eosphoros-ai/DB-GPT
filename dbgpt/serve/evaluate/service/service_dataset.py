import io
import json
import logging
import os
import uuid
from typing import List, Optional

import chardet
import pandas as pd
from fastapi import UploadFile

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.core.interface.evaluation import (
    EVALUATE_FILE_COL_ANSWER,
    EVALUATE_FILE_COL_QUESTION,
)
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.util.oss_utils import a_delete_object, a_get_object, a_put_object
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import DatasetServeRequest, DatasetServeResponse, DatasetStorageType
from ..config import (
    SERVE_CONFIG_KEY_PREFIX,
    SERVE_DATASET_SERVICE_COMPONENT_NAME,
    ServeConfig,
)
from ..models.models_dataset import DatasetServeDao, DatasetServeEntity

logger = logging.getLogger(__name__)

CFG = Config()


class DatasetService(
    BaseService[DatasetServeEntity, DatasetServeRequest, DatasetServeResponse]
):
    """The service class for Evaluate"""

    name = SERVE_DATASET_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, dao: Optional[DatasetServeDao] = None):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: DatasetServeDao = dao
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or DatasetServeDao(self._serve_config)
        self._system_app = system_app

    @property
    def dao(
        self,
    ) -> BaseDao[DatasetServeEntity, DatasetServeRequest, DatasetServeResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    async def upload_content_dataset(
        self,
        content: str,
        dataset_name: Optional[str] = None,
        members: Optional[str] = None,
    ):
        logger.info(f"upload_content_dataset:{dataset_name},{members}")
        try:
            datasets_dicts = json.loads(content)
            datasets_df = pd.DataFrame(datasets_dicts)

            if EVALUATE_FILE_COL_QUESTION not in datasets_df.columns:
                raise ValueError(f"cannot be recognized and columns are missing "
                                 f"{EVALUATE_FILE_COL_QUESTION}")

            have_answer = False
            if EVALUATE_FILE_COL_ANSWER in datasets_df.columns:
                have_answer = True
            dataset_code = str(uuid.uuid1())
            request: DatasetServeRequest = DatasetServeRequest(
                code=dataset_code,
                name=dataset_name,
                file_type=".csv",
                storage_type="db",
                storage_position=content,
                datasets_count=len(datasets_df),
                have_answer=have_answer,
                members=members,
            )
            return self.create(request)
        except Exception as e:
            logger.exception("data upload failed")
            raise ValueError("data upload failed" + str(e))

    async def upload_file_dataset(
        self,
        file: UploadFile,
        dataset_name: Optional[str] = None,
        members: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ):
        logger.info(f"upload_file_dataset:{file.filename},{members},{user_name}")

        dataset_code = str(uuid.uuid1())
        file_content = await file.read()
        file_name = file.filename
        extension = os.path.splitext(file_name)[1]
        try:
            result = chardet.detect(file_content)
            encoding = result["encoding"]
            confidence = result["confidence"]

            df = None
            # read excel file
            if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
                df_tmp = pd.read_excel(io.BytesIO(file_content), index_col=False)
            elif file_name.endswith(".csv"):
                df_tmp = pd.read_csv(
                    io.BytesIO(file_content),
                    index_col=False,
                    encoding=encoding,
                )
            else:
                raise ValueError(f"do not support file type {file.filename}.")

            oss_key = f"{dataset_code}_{file_name}"
            await a_put_object(oss_key=oss_key, data=file_content)
            if EVALUATE_FILE_COL_QUESTION not in df_tmp.columns:
                raise ValueError(f"evaluate column {EVALUATE_FILE_COL_QUESTION}")

            have_answer = False
            if EVALUATE_FILE_COL_ANSWER in df_tmp.columns:
                have_answer = True

            request: DatasetServeRequest = DatasetServeRequest(
                code=dataset_code,
                name=dataset_name,
                file_type=extension,
                storage_type="oss",
                storage_position=oss_key,
                datasets_count=len(df_tmp),
                have_answer=have_answer,
                members=members,
                user_name=user_name,
                user_id=user_id,
            )
            return self.create(request)
        except Exception as e:
            logger.exception("evaluation upload error")
            raise ValueError("evaluation upload error" + str(e))

    async def get_dataset_stream(self, code: str):
        logger.info(f"get_dataset_stream:{code}")
        dataset_info: DatasetServeRequest = self.get(DatasetServeRequest(code=code))
        if dataset_info:
            file_name = f"{dataset_info.name}{dataset_info.file_type}"
            if dataset_info.storage_type == "oss":
                dataset_bytes = await a_get_object(
                    oss_key=dataset_info.storage_position
                )
                return file_name, io.BytesIO(dataset_bytes)
            elif dataset_info.storage_type == "db":
                datasets_dicts = json.loads(dataset_info.storage_position)
                datasets_df = pd.DataFrame(datasets_dicts)
                if dataset_info.file_type.endswith(
                    ".xlsx"
                ) or dataset_info.file_type.endswith(".xls"):
                    file_stream = io.BytesIO()
                    datasets_df.to_excel(file_stream, index=False, encoding="utf-8-sig")
                    file_stream.seek(0)
                    file_string = file_stream.getvalue()
                elif dataset_info.file_type.endswith(".csv"):
                    file_string = datasets_df.to_csv(index=False, encoding="utf-8-sig")

                return file_name, io.BytesIO(file_string)
            else:
                raise ValueError("do not support dataset type")
        else:
            raise ValueError(f"unknown data[{code}]")

    async def get_dataset_json_record(
        self, dataset_info: DatasetServeResponse
    ) -> (DatasetServeRequest, List[dict]):
        logger.info(f"get_dataset_json_record:{dataset_info.name}")
        if dataset_info:
            if dataset_info.storage_type == DatasetStorageType.OSS.value:
                file_content = await a_get_object(oss_key=dataset_info.storage_position)
                result = chardet.detect(file_content)
                encoding = result["encoding"]
                if dataset_info.file_type.endswith(
                    ".xlsx"
                ) or dataset_info.file_type.endswith(".xls"):
                    df_tmp = pd.read_excel(io.BytesIO(file_content), index_col=False)
                elif dataset_info.file_type.endswith(".csv"):
                    df_tmp = pd.read_csv(
                        io.BytesIO(file_content),
                        index_col=False,
                        encoding=encoding,
                    )
                else:
                    raise ValueError(f"Evaluate does not support the current file "
                                     f"type {dataset_info.file_type}.")

                return dataset_info, df_tmp.to_dict(orient="records")
            elif dataset_info.storage_type == DatasetStorageType.DB.value:
                return dataset_info, json.loads(dataset_info.storage_position)
            else:
                raise ValueError("Dataset storage type not yet supported")
        else:
            raise ValueError(f"unknown data info")

    def _check_permissions(
        self, dataset_info: DatasetServeRequest, user_id: str, user_name: str
    ):
        if dataset_info and dataset_info.user_id != user_id:
            if dataset_info.members and user_name:
                if user_name not in dataset_info.members:
                    return
            raise ValueError("你不是数据集成员或拥有者，无法删除!")

    async def delete_dataset(self, code: str, user_id: str, user_name: str):
        dataset_info: DatasetServeRequest = self.get(DatasetServeRequest(code=code))
        self._check_permissions(dataset_info, user_id, user_name)
        if dataset_info:
            if dataset_info.storage_type == "oss":
                await a_delete_object(oss_key=dataset_info.storage_position)

            request = DatasetServeRequest(code=code)
            self.delete(request)

    def create(self, request: DatasetServeRequest) -> DatasetServeResponse:
        """Create a new Dataset entity

        Args:
            request (DatasetServeRequest): The request

        Returns:
            DatasetServeResponse: The response
        """

        if not request.user_name:
            request.user_name = self.config.default_user
        if not request.sys_code:
            request.sys_code = self.config.default_sys_code
        return super().create(request)

    def update(self, request: DatasetServeRequest) -> DatasetServeResponse:
        """Update a Dataset entity

        Args:
            request (DatasetServeRequest): The request

        Returns:
            DatasetServeResponse: The response
        """
        # Build the query request from the request
        query_request = {
            "prompt_code": request.prompt_code,
            "sys_code": request.sys_code,
        }
        return self.dao.update(query_request, update_request=request)

    def get(self, request: DatasetServeRequest) -> Optional[DatasetServeResponse]:
        """Get a Evaluate entity

        Args:
            request (DatasetServeRequest): The request

        Returns:
            DatasetServeResponse: The response
        """
        query_request = request
        return self.dao.get_one(query_request)

    def delete(self, request: DatasetServeRequest) -> None:
        """Delete a Evaluate entity

        Args:
            request (DatasetServeRequest): The request
        """
        # Build the query request from the request
        query_request = {
            "code": request.code,
            "user_id": request.user_id,
        }
        self.dao.delete(query_request)

    def get_list(self, request: DatasetServeRequest) -> List[DatasetServeResponse]:
        """Get a list of Evaluate entities

        Args:
            request (DatasetServeRequest): The request

        Returns:
            List[DatasetServeResponse]: The response
        """

        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: DatasetServeRequest, page: int, page_size: int
    ) -> PaginationResult[DatasetServeResponse]:
        """Get a list of Dataset entities by page

        Args:
            request (DatasetServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[DatasetServeResponse]: The response
        """
        query_request = request
        return self.dao.get_list_page(
            query_request, page, page_size, DatasetServeEntity.id.name
        )

    def update_members(self, code, members):
        if code is None:
            raise Exception("code can not be None when update members.")
        return self._dao.update({"code": code}, DatasetServeRequest(members=members))
