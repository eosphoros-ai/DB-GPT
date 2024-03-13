"""FastAPI utilities."""

from typing import Any, Callable, Dict

from fastapi.routing import APIRouter


class PriorityAPIRouter(APIRouter):
    """A router with priority.

    The route with higher priority will be put in the front of the route list.
    """

    def __init__(self, *args, **kwargs):
        """Init a PriorityAPIRouter."""
        super().__init__(*args, **kwargs)
        self.route_priority: Dict[str, int] = {}

    def add_api_route(
        self, path: str, endpoint: Callable, *, priority: int = 0, **kwargs: Any
    ):
        """Add a route with priority.

        Args:
            path (str): The path of the route.
            endpoint (Callable): The endpoint of the route.
            priority (int, optional): The priority of the route. Defaults to 0.
            **kwargs (Any): Other arguments.
        """
        super().add_api_route(path, endpoint, **kwargs)
        self.route_priority[path] = priority
        # Sort the routes by priority.
        self.sort_routes_by_priority()

    def sort_routes_by_priority(self):
        """Sort the routes by priority."""

        def my_func(route):
            if route.path in ["", "/"]:
                return -100
            return self.route_priority.get(route.path, 0)

        self.routes.sort(key=my_func, reverse=True)
