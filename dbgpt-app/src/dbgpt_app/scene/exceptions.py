"""Exceptions for Application."""
import logging

logger = logging.getLogger(__name__)


class BaseAppException(Exception):
    """Base Exception for App"""

    def __init__(self, message: str, view: str):
        """Base Exception for App"""
        super().__init__(message)
        self.message = message
        self.view = view


class AppActionException(BaseAppException):
    """Exception for App Action."""

    def __init__(self, message: str, view: str):
        """Exception for App Action"""
        super().__init__(message, view)
