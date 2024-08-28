import logging
from typing import List, Optional

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.util.dbgpts.base import INSTALL_DIR
from dbgpt.util.dbgpts.repo import (
    copy_and_install,
    inner_copy_and_install,
    inner_uninstall,
    install,
    uninstall,
)
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity

logger = logging.getLogger(__name__)


class Service(BaseService[ServeEntity, ServeRequest, ServerResponse]):
    """The service class for DbgptsMy"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, dao: Optional[ServeDao] = None):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: ServeDao = dao
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        super().init_app(system_app)
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or ServeDao(self._serve_config)
        self._system_app = system_app

    @property
    def dao(self) -> BaseDao[ServeEntity, ServeRequest, ServerResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def update(self, request: ServeRequest) -> ServerResponse:
        """Update a DbgptsMy entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """

        # Build the query request from the request
        query_request = {"id": request.id}
        return self.dao.update(query_request, update_request=request)

    def get(self, request: ServeRequest) -> Optional[ServerResponse]:
        """Get a DbgptsMy entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # Build the query request from the request
        query_request = request
        return self.dao.get_one(query_request)

    def delete(self, request: ServeRequest) -> None:
        """Delete a DbgptsMy entity

        Args:
            request (ServeRequest): The request
        """

        # TODO: implement your own logic here
        # Build the query request from the request

        self.dao.delete(request)

    def get_list(self, request: ServeRequest) -> List[ServerResponse]:
        """Get a list of DbgptsMy entities

        Args:
            request (ServeRequest): The request

        Returns:
            List[ServerResponse]: The response
        """
        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: ServeRequest, page: int, page_size: int
    ) -> PaginationResult[ServerResponse]:
        """Get a list of DbgptsMy entities by page

        Args:
            request (ServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[ServerResponse]: The response
        """
        query_request = request
        return self.dao.get_list_page(query_request, page, page_size)

    def install_gpts(
        self,
        name: str,
        type: str,
        repo: str,
        dbgpt_path: str,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
    ):
        logger.info(f"install_gpts {name}")

        # install(name, repo)
        try:
            from pathlib import Path

            inner_copy_and_install(repo, name, Path(dbgpt_path))
        except Exception as e:
            logger.exception(f"install_gpts failed!{str(e)}")
            raise ValueError(f"Install dbgpts [{type}:{name}] Failed! {str(e)}", e)

        from dbgpt.util.dbgpts.base import get_repo_path
        from dbgpt.util.dbgpts.loader import (
            BasePackage,
            InstalledPackage,
            parse_package_metadata,
        )

        base_package: BasePackage = parse_package_metadata(
            InstalledPackage(
                name=name,
                repo=repo,
                root=dbgpt_path,
                package=type,
            )
        )
        dbgpts_entity = self.get(ServeRequest(name=name, type=type))

        if not dbgpts_entity:
            request = ServeRequest()
            request.name = name

            request.user_name = user_name
            request.sys_code = sys_code
            request.type = type
            request.file_name = str(INSTALL_DIR / name)
            request.version = base_package.version
            return self.create(request)
        else:
            dbgpts_entity.version = base_package.version

            return self.update(ServeRequest(**dbgpts_entity.to_dict()))

    def uninstall_gpts(
        self,
        name: str,
        type: str,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
    ):
        logger.info(f"install_gpts {name}")
        try:
            inner_uninstall(name)
        except Exception as e:
            logger.warning(f"Uninstall dbgpts [{type}:{name}] Failed! {str(e)}", e)
            raise ValueError(f"Uninstall dbgpts [{type}:{name}] Failed! {str(e)}", e)
        self.delete(ServeRequest(name=name, type=type))
