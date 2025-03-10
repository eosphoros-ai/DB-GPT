"""The parameter utility."""

import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional

from dbgpt._private.pydantic import BaseModel, Field, model_validator
from dbgpt.component import SystemApp
from dbgpt.core.interface.serialization import Serializable

_DEFAULT_DYNAMIC_REGISTRY = {}


class RefreshOptionDependency(BaseModel):
    """The refresh dependency."""

    name: str = Field(..., description="The name of the refresh dependency")
    value: Optional[Any] = Field(
        None, description="The value of the refresh dependency"
    )
    has_value: bool = Field(
        False, description="Whether the refresh dependency has value"
    )


class RefreshOptionRequest(BaseModel):
    """The refresh option request."""

    name: str = Field(..., description="The name of parameter to refresh")
    depends: Optional[List[RefreshOptionDependency]] = Field(
        None, description="The depends of the refresh config"
    )
    variables_key: Optional[str] = Field(
        None, description="The variables key to refresh"
    )
    variables_scope: Optional[str] = Field(
        None, description="The variables scope to refresh"
    )
    variables_scope_key: Optional[str] = Field(
        None, description="The variables scope key to refresh"
    )
    variables_sys_code: Optional[str] = Field(
        None, description="The system code to refresh"
    )
    variables_user_name: Optional[str] = Field(
        None, description="The user name to refresh"
    )


class OptionValue(Serializable, BaseModel):
    """The option value of the parameter."""

    label: str = Field(..., description="The label of the option")
    name: str = Field(..., description="The name of the option")
    value: Any = Field(..., description="The value of the option")
    children: Optional[List["OptionValue"]] = Field(
        None, description="The children of the option"
    )

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        dict_value = self.dict()
        # Force invoke the __str__ method of the value(i18n)
        dict_value["label"] = str(dict_value["label"])
        return dict_value


class BaseDynamicOptions(Serializable, BaseModel, ABC):
    """The base dynamic options."""

    def support_async(
        self,
        system_app: Optional[SystemApp] = None,
        request: Optional[RefreshOptionRequest] = None,
    ) -> bool:
        """Whether the dynamic options support async.

        Args:
            system_app (Optional[SystemApp]): The system app
            request (Optional[RefreshOptionRequest]): The refresh request

        Returns:
            bool: Whether the dynamic options support async
        """
        return False

    def option_values(self) -> List[OptionValue]:
        """Return the option values of the parameter."""
        return self.refresh(None)

    @abstractmethod
    def refresh(
        self,
        request: Optional[RefreshOptionRequest] = None,
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> List[OptionValue]:
        """Refresh the dynamic options.

        Args:
            request (Optional[RefreshOptionRequest]): The refresh request
            trigger (Literal["default", "http"]): The trigger type, how to trigger
            the refresh
            system_app (Optional[SystemApp]): The system app
        """

    async def async_refresh(
        self,
        request: Optional[RefreshOptionRequest] = None,
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> List[OptionValue]:
        """Refresh the dynamic options async.

        Args:
            request (Optional[RefreshOptionRequest]): The refresh request
            trigger (Literal["default", "http"]): The trigger type, how to trigger
            the refresh
            system_app (Optional[SystemApp]): The system app
        """
        raise NotImplementedError("The dynamic options does not support async.")


class FunctionDynamicOptions(BaseDynamicOptions):
    """The function dynamic options."""

    func: Callable[..., List[OptionValue]] = Field(
        ..., description="The function to generate the dynamic options"
    )
    func_id: str = Field(
        ..., description="The unique id of the function to generate the dynamic options"
    )

    def refresh(
        self,
        request: Optional[RefreshOptionRequest] = None,
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> List[OptionValue]:
        """Refresh the dynamic options."""
        if not request or not request.depends:
            return self.func()
        kwargs = {dep.name: dep.value for dep in request.depends if dep.has_value}
        return self.func(**kwargs)

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the function id."""
        if not isinstance(values, dict):
            return values
        func = values.get("func")
        if func is None:
            raise ValueError(
                "The function to generate the dynamic options is required."
            )
        func_id = _generate_unique_id(func)
        values["func_id"] = func_id
        _DEFAULT_DYNAMIC_REGISTRY[func_id] = func
        return values

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        return {"func_id": self.func_id}


class VariablesDynamicOptions(BaseDynamicOptions):
    """The variables dynamic options."""

    def support_async(
        self,
        system_app: Optional[SystemApp] = None,
        request: Optional[RefreshOptionRequest] = None,
    ) -> bool:
        """Whether the dynamic options support async."""
        if not system_app or not request or not request.variables_key:
            return False

        from ...interface.variables import BuiltinVariablesProvider

        provider: BuiltinVariablesProvider = system_app.get_component(
            request.variables_key,
            component_type=BuiltinVariablesProvider,
            default_component=None,
        )
        if not provider:
            return False
        return provider.support_async()

    def refresh(
        self,
        request: Optional[RefreshOptionRequest] = None,
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> List[OptionValue]:
        """Refresh the dynamic options."""
        if (
            trigger == "default"
            or not request
            or not request.variables_key
            or not request.variables_scope
        ):
            # Only refresh when trigger is http and request is not None
            return []
        if not system_app:
            raise ValueError("The system app is required when refresh the variables.")
        from ...interface.variables import VariablesProvider

        vp: VariablesProvider = VariablesProvider.get_instance(system_app)
        variables = vp.get_variables(
            key=request.variables_key,
            scope=request.variables_scope,
            scope_key=request.variables_scope_key,
            sys_code=request.variables_sys_code,
            user_name=request.variables_user_name,
        )
        options = []
        for var in variables:
            options.append(
                OptionValue(
                    label=var.label,
                    name=var.name,
                    value=var.value,
                )
            )
        return options

    async def async_refresh(
        self,
        request: Optional[RefreshOptionRequest] = None,
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> List[OptionValue]:
        """Refresh the dynamic options async."""
        if (
            trigger == "default"
            or not request
            or not request.variables_key
            or not request.variables_scope
        ):
            return []
        if not system_app:
            raise ValueError("The system app is required when refresh the variables.")
        from ...interface.variables import VariablesProvider

        vp: VariablesProvider = VariablesProvider.get_instance(system_app)
        variables = await vp.async_get_variables(
            key=request.variables_key,
            scope=request.variables_scope,
            scope_key=request.variables_scope_key,
            sys_code=request.variables_sys_code,
            user_name=request.variables_user_name,
        )
        options = []
        for var in variables:
            options.append(
                OptionValue(
                    label=var.label,
                    name=var.name,
                    value=var.value,
                )
            )
        return options

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        return {"key": self.key}


def _generate_unique_id(func: Callable) -> str:
    if func.__name__ == "<lambda>":
        func_id = f"lambda_{inspect.getfile(func)}_{inspect.getsourcelines(func)}"
    else:
        func_id = f"{func.__module__}.{func.__name__}"
    return func_id
