import inspect
from io import StringIO
from typing import Any, Dict, Optional, TextIO


def check_serializable(
    obj: Any, obj_name: str = "Object", error_msg: str = "Object is not serializable"
):
    import cloudpickle

    try:
        cloudpickle.dumps(obj)
    except Exception as e:
        inspect_info = inspect_serializability(obj, obj_name)
        msg = f"{error_msg}\n{inspect_info['report']}"
        raise TypeError(msg) from e


class SerializabilityInspector:
    def __init__(self, stream: Optional[TextIO] = None):
        self.stream = stream or StringIO()
        self.failures = {}
        self.indent_level = 0

    def log(self, message: str):
        indent = "  " * self.indent_level
        self.stream.write(f"{indent}{message}\n")

    def inspect(self, obj: Any, name: str, depth: int = 3) -> bool:
        import cloudpickle

        self.log(f"Inspecting '{name}'")
        self.indent_level += 1

        try:
            cloudpickle.dumps(obj)
            self.indent_level -= 1
            return True
        except Exception as e:
            self.failures[name] = str(e)
            self.log(f"Failure: {str(e)}")

            if depth > 0:
                if inspect.isfunction(obj) or inspect.ismethod(obj):
                    self._inspect_function(obj, depth - 1)
                elif hasattr(obj, "__dict__"):
                    self._inspect_object(obj, depth - 1)

            self.indent_level -= 1
            return False

    def _inspect_function(self, func, depth):
        closure = inspect.getclosurevars(func)
        for name, value in closure.nonlocals.items():
            self.inspect(value, f"{func.__name__}.{name}", depth)
        for name, value in closure.globals.items():
            self.inspect(value, f"global:{name}", depth)

    def _inspect_object(self, obj, depth):
        for name, value in inspect.getmembers(obj):
            if not name.startswith("__"):
                self.inspect(value, f"{type(obj).__name__}.{name}", depth)

    def get_report(self) -> str:
        summary = "\nSummary of Serialization Failures:\n"
        if not self.failures:
            summary += "All components are serializable.\n"
        else:
            for name, error in self.failures.items():
                summary += f"  - {name}: {error}\n"

        return self.stream.getvalue() + summary


def inspect_serializability(
    obj: Any,
    name: Optional[str] = None,
    depth: int = 5,
    stream: Optional[TextIO] = None,
) -> Dict[str, Any]:
    inspector = SerializabilityInspector(stream)
    success = inspector.inspect(obj, name or type(obj).__name__, depth)
    return {
        "success": success,
        "failures": inspector.failures,
        "report": inspector.get_report(),
    }
