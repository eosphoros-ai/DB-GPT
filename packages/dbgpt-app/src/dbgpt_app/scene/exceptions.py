"""Exceptions for Application."""

import logging

from dbgpt.core import ModelOutput

logger = logging.getLogger(__name__)


class BaseAppException(Exception):
    """Base Exception for App"""

    def __init__(self, message: str, view: str):
        """Base Exception for App"""
        super().__init__(message)
        self.message = message
        self.view = view

    def get_ui_error(self) -> str:
        """Get UI Error"""
        return self.view


class AppActionException(BaseAppException):
    """Exception for App Action."""

    def __init__(self, message: str, view: str):
        """Exception for App Action"""
        super().__init__(message, view)


class ContextAppException(BaseAppException):
    """Exception for App Context."""

    def __init__(self, message: str, view: str, model_output: ModelOutput):
        """Exception for App Context"""
        super().__init__(message, view)
        self.model_output: ModelOutput = model_output

    def get_ui_error(self) -> str:
        """Get UI Error"""
        if self.model_output.has_thinking:
            return self.model_output.gen_text_with_thinking(new_text=self.view)
        return self.view
