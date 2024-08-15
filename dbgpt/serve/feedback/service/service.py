from typing import List, Optional

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity


class Service(BaseService[ServeEntity, ServeRequest, ServerResponse]):
    """The service class for Feedback"""

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

    def get(self, request: ServeRequest) -> Optional[ServerResponse]:
        """Get a Feedback entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # Build the query request from the request
        query_request = request
        return self.dao.get_one(query_request)

    def delete(self, request: ServeRequest) -> None:
        """Delete a Feedback entity

        Args:
            request (ServeRequest): The request
        """

        query_request = {"id": request.id}
        self.dao.delete(query_request)

    def get_list(self, request: ServeRequest) -> List[ServerResponse]:
        """Get a list of Feedback entities

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
        """Get a list of Feedback entities by page

        Args:
            request (ServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[ServerResponse]: The response
        """
        query_request = request
        return self.dao.get_list_page(query_request, page, page_size)

    def list_conv_feedbacks(
        self,
        conv_uid: Optional[str] = None,
        feedback_type: Optional[str] = None,
    ) -> List[ServerResponse]:
        feedbacks = self.dao.get_list(
            ServeRequest(conv_uid=conv_uid, feedback_type=feedback_type)
        )
        return feedbacks

    def create_or_update(self, request: ServeRequest) -> ServerResponse:
        """
        First check whether the current user has likes, and if so, check whether it's consistent with the previous likes

        If it is inconsistent, delete the previous likes and create a new like;

        if it is consistent, an error will be reported and the likes already exist. Please do not like repeatedly
        """
        feedbacks = self.dao.get_list(
            ServeRequest(
                conv_uid=request.conv_uid,
                message_id=request.message_id,
                user_code=request.user_code,
            )
        )
        if len(feedbacks) > 1:
            raise Exception(f"current conversation message has more than one feedback.")
        if len(feedbacks) == 1:
            fb = feedbacks[0]
            if fb.feedback_type == request.feedback_type:
                raise Exception(f"Please do not repeat feedback")
            self.dao.delete(ServeRequest(id=fb.id))

        return self.dao.create(request)

    def cancel_feedback(self, request: ServeRequest) -> None:
        if not (request.conv_uid and request.message_id):
            raise Exception(f"cancel feedback参数缺失异常.")

        self.dao.delete(
            ServeRequest(
                conv_uid=request.conv_uid,
                message_id=request.message_id,
            )
        )

    def delete_feedback(self, feedback_id: int) -> None:
        self.dao.delete(ServeRequest(id=feedback_id))
