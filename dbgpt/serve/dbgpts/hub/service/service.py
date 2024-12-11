import logging
import re
from typing import List, Optional, Tuple

from dbgpt.agent import PluginStorageType
from dbgpt.component import BaseComponent, SystemApp
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.util.dbgpts.repo import _install_default_repos_if_no_repos, list_dbgpts
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity

logger = logging.getLogger(__name__)


class Service(BaseService[ServeEntity, ServeRequest, ServerResponse]):
    """The service class for DbgptsHub"""

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
    def dao(self) -> ServeDao:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def update(self, request: ServeRequest) -> ServerResponse:
        """Update a DbgptsHub entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = {"id": request.id}
        return self.dao.update(query_request, update_request=request)

    def get(self, request: ServeRequest) -> Optional[ServerResponse]:
        """Get a DbgptsHub entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_one(query_request)

    def delete(self, request: ServeRequest) -> None:
        """Delete a DbgptsHub entity

        Args:
            request (ServeRequest): The request
        """

        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = {
            # "id": request.id
        }
        self.dao.delete(query_request)

    def get_list(self, request: ServeRequest) -> List[ServerResponse]:
        """Get a list of DbgptsHub entities

        Args:
            request (ServeRequest): The request

        Returns:
            List[ServerResponse]: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: ServeRequest, page: int, page_size: int
    ) -> PaginationResult[ServerResponse]:
        """Get a list of DbgptsHub entities by page

        Args:
            request (ServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[ServerResponse]: The response
        """
        query_request = ServeRequest(
            name=request.name,
            type=request.type,
            version=request.version,
            description=request.description,
            author=request.author,
            storage_channel=request.storage_channel,
            storage_url=request.storage_url,
            installed=request.installed,
        )

        return self.dao.dbgpts_list(query_request, page, page_size)

    def refresh_hub_from_git(
        self,
        github_repo: str = None,
        branch_name: str = "main",
        authorization: str = None,
    ):
        logger.info("refresh_hub_by_git start!")
        _install_default_repos_if_no_repos()
        data: List[Tuple[str, str, str, str]] = list_dbgpts()

        from dbgpt.util.dbgpts.base import get_repo_path
        from dbgpt.util.dbgpts.loader import (
            BasePackage,
            InstalledPackage,
            parse_package_metadata,
        )

        try:
            for repo, package, name, gpts_path in data:
                try:
                    if not name:
                        logger.info(
                            f"dbgpts error repo:{repo}, package:{package}, name:{name}, gpts_path:{gpts_path}"
                        )
                        continue
                    old_hub_info = self.get(ServeRequest(name=name, type=package))
                    base_package: BasePackage = parse_package_metadata(
                        InstalledPackage(
                            name=name,
                            repo=repo,
                            root=str(gpts_path),
                            package=package,
                        )
                    )
                    if old_hub_info:
                        self.dao.update(
                            query_request=ServeRequest(
                                name=old_hub_info.name, type=old_hub_info.type
                            ),
                            update_request=ServeRequest(
                                version=base_package.version,
                                description=base_package.description,
                            ),
                        )
                    else:
                        request = ServeRequest()
                        request.type = package
                        request.name = name
                        request.storage_channel = repo
                        request.storage_url = str(gpts_path)
                        request.author = self._get_dbgpts_author(base_package.authors)
                        request.email = self._get_dbgpts_email(base_package.authors)

                        request.download_param = None
                        request.installed = 0
                        request.version = base_package.version
                        request.description = base_package.description
                        self.create(request)
                except Exception as e:
                    logger.warning(
                        f"Load from git failed repo:{repo}, package:{package}, name:{name}, gpts_path:{gpts_path}",
                        e,
                    )

        except Exception as e:
            raise ValueError(f"Update Agent Hub Db Info Faild!{str(e)}")

    def _get_dbgpts_author(self, authors):
        pattern = r"(.+?)<"
        names = []
        for item in authors:
            names.extend(re.findall(pattern, item))
        return ",".join(names)

    def _get_dbgpts_email(self, authors):
        pattern = r"<(.*?)>"
        emails: List[str] = []
        for item in authors:
            emails.extend(re.findall(pattern, item))
        return ",".join(emails)
