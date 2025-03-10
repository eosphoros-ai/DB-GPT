import pytest

from ..annotations import (
    Deprecated,
    DeveloperAPI,
    PublicAPI,
    _modify_docstring,
    immutable,
    mutable,
)


def test_public_api_without_params():
    """Test @PublicAPI without parameters"""

    @PublicAPI
    def test_func():
        pass

    assert not hasattr(test_func, "_public_stability")
    assert not hasattr(test_func, "_annotated")


def test_public_api_stable():
    """Test @PublicAPI with stable parameter"""

    @PublicAPI(stability="stable")
    def test_func():
        pass

    assert not hasattr(test_func, "_public_stability")
    assert not hasattr(test_func, "_annotated")


def test_public_api_beta():
    """Test @PublicAPI with beta parameter"""

    @PublicAPI(stability="beta")
    def test_func():
        """Original docstring."""
        pass

    assert test_func._public_stability == "beta"
    assert test_func._annotated == "test_func"
    assert "PublicAPI (beta)" in test_func.__doc__
    assert "Original docstring" in test_func.__doc__


def test_public_api_alpha():
    """Test @PublicAPI with alpha parameter"""

    @PublicAPI(stability="alpha")
    def test_func():
        pass

    assert test_func._public_stability == "alpha"
    assert test_func._annotated == "test_func"
    assert "PublicAPI (alpha)" in test_func.__doc__


def test_public_api_invalid_stability():
    """Test @PublicAPI with invalid stability parameter"""
    with pytest.raises(AssertionError):

        @PublicAPI(stability="invalid")
        def test_func():
            pass


def test_public_api_on_class():
    """Test @PublicAPI on a class"""

    @PublicAPI(stability="beta")
    class TestClass:
        pass

    assert TestClass._public_stability == "beta"
    assert TestClass._annotated == "TestClass"
    assert "PublicAPI (beta)" in TestClass.__doc__


def test_developer_api_without_params():
    """Test @DeveloperAPI without parameters"""

    @DeveloperAPI
    def test_func():
        """Original docstring."""
        pass

    assert "DeveloperAPI" in test_func.__doc__
    assert "Original docstring" in test_func.__doc__


def test_developer_api_on_class():
    """Test @DeveloperAPI on a class"""

    @DeveloperAPI
    class TestClass:
        """Original class docstring."""

        pass

    assert "DeveloperAPI" in TestClass.__doc__
    assert "Original class docstring" in TestClass.__doc__


def test_mutable_decorator():
    """Test @mutable decorator"""

    class TestClass:
        def __init__(self):
            self.value = 0

        @mutable
        def change_value(self):
            self.value += 1

    obj = TestClass()
    assert hasattr(obj.change_value, "_mutability")
    assert obj.change_value._mutability is True


def test_immutable_decorator():
    """Test @immutable decorator"""

    class TestClass:
        def __init__(self):
            self.value = 42

        @immutable
        def get_value(self):
            return self.value

    obj = TestClass()
    assert hasattr(obj.get_value, "_mutability")
    assert obj.get_value._mutability is False


def test_multiple_decorators():
    """Test multiple decorators together"""

    @PublicAPI(stability="beta")
    @DeveloperAPI
    def test_func():
        """Original docstring."""
        pass

    assert test_func._public_stability == "beta"
    assert test_func._annotated == "test_func"
    assert "PublicAPI (beta)" in test_func.__doc__
    assert "DeveloperAPI" in test_func.__doc__
    assert "Original docstring" in test_func.__doc__


def test_docstring_indentation():
    """Test docstring indentation is preserved"""

    @PublicAPI(stability="beta")
    def test_func():
        """
        Original docstring with
            indented content.
        """
        pass

    assert "PublicAPI (beta)" in test_func.__doc__
    assert "Original docstring with" in test_func.__doc__
    assert "    indented content." in test_func.__doc__


def test_mutable_immutable_together():
    """Test that mutable and immutable decorators can't be used together"""

    class TestClass:
        @immutable
        @mutable
        def conflicting_method(self):
            pass

    obj = TestClass()
    # immutable decorator should win as it's applied last
    assert obj.conflicting_method._mutability is False


def test_modify_docstring_empty():
    """Test _modify_docstring with empty original docstring"""

    def test_func():
        pass

    _modify_docstring(test_func, "New message")
    assert test_func.__doc__.rstrip() == "New message"


def test_modify_docstring_none_message():
    """Test _modify_docstring with None message"""

    def test_func():
        """Original doc"""
        pass

    _modify_docstring(test_func, None)
    assert test_func.__doc__ == "Original doc"


def test_decorator_order():
    """Test the order of multiple decorators"""

    class TestClass:
        @immutable
        @mutable
        def method1(self):
            pass

        @mutable
        @immutable
        def method2(self):
            pass

    obj = TestClass()
    # The outermost decorator should take precedence
    assert obj.method1._mutability is False
    assert obj.method2._mutability is True


def test_deprecated_without_params():
    """Test @Deprecated without any parameters"""

    @Deprecated
    def old_func():
        return 42

    with pytest.warns(DeprecationWarning) as record:
        result = old_func()

    assert result == 42
    assert len(record) == 1
    assert "Call to deprecated function old_func" in str(record[0].message)


def test_deprecated_with_reason():
    """Test @Deprecated with reason parameter"""

    @Deprecated(reason="This is old")
    def old_func():
        return 42

    with pytest.warns(DeprecationWarning) as record:
        result = old_func()

    assert result == 42
    assert len(record) == 1
    assert "This is old" in str(record[0].message)


def test_deprecated_with_all_params():
    """Test @Deprecated with all parameters"""

    @Deprecated(
        reason="API redesigned",
        version="0.4.0",
        remove_version="0.5.0",
        alternative="new_func()",
    )
    def old_func():
        return 42

    with pytest.warns(DeprecationWarning) as record:
        result = old_func()

    warning_message = str(record[0].message)
    assert result == 42
    assert len(record) == 1
    assert "API redesigned" in warning_message
    assert "0.4.0" in warning_message
    assert "0.5.0" in warning_message
    assert "new_func()" in warning_message


def test_deprecated_class():
    """Test @Deprecated on a class"""

    @Deprecated(reason="Use NewClass instead")
    class OldClass:
        def __init__(self):
            self.value = 42

    with pytest.warns(DeprecationWarning) as record:
        instance = OldClass()

    assert instance.value == 42
    assert len(record) == 1
    assert "class OldClass" in str(record[0].message)
    assert "Use NewClass instead" in str(record[0].message)


def test_deprecated_method():
    """Test @Deprecated on a class method"""

    class MyClass:
        @Deprecated(reason="Use new_method() instead")
        def old_method(self):
            return 42

    obj = MyClass()
    with pytest.warns(DeprecationWarning) as record:
        result = obj.old_method()

    assert result == 42
    assert len(record) == 1
    assert "function old_method" in str(record[0].message)
    assert "Use new_method() instead" in str(record[0].message)


def test_multiple_deprecated_calls():
    """Test multiple calls to deprecated function"""

    @Deprecated(reason="Do not use")
    def old_func():
        return 42

    with pytest.warns(DeprecationWarning) as record:
        old_func()
        old_func()

    assert len(record) == 2  # Should warn on each call


def test_deprecated_with_args():
    """Test @Deprecated on function with arguments"""

    @Deprecated(reason="Use new_add() instead")
    def old_add(a: int, b: int) -> int:
        return a + b

    with pytest.warns(DeprecationWarning) as record:
        result = old_add(1, 2)

    assert result == 3
    assert len(record) == 1
    assert "function old_add" in str(record[0].message)


def test_deprecated_with_kwargs():
    """Test @Deprecated on function with keyword arguments"""

    @Deprecated
    def greet(name: str = "World") -> str:
        return f"Hello, {name}!"

    with pytest.warns(DeprecationWarning) as record:
        result = greet(name="Test")

    assert result == "Hello, Test!"
    assert len(record) == 1


def test_deprecated_return_type_preservation():
    """Test that @Deprecated preserves return type hints"""

    @Deprecated
    def func() -> int:
        return 42

    assert func.__annotations__["return"] is int


def test_deprecated_docstring_preservation():
    """Test that @Deprecated preserves docstrings"""

    @Deprecated
    def func():
        """This is a test function."""
        pass

    assert "This is a test function." in func.__doc__
