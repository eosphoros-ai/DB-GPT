import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from typing import Type

import pytest

from dbgpt.util.module_utils import ModelScanner, ScannerConfig


# Create test base classes and implementations
class TestBaseClass:
    """Base class for testing"""

    pass


class TestImplementation1(TestBaseClass):
    """First test implementation"""

    pass


class TestImplementation2(TestBaseClass):
    """Second test implementation"""

    pass


@dataclass
class TestParams:
    """Test parameters class for parameter scanning tests"""

    value: str


class TestParamsImpl1(TestParams):
    """First test parameters implementation"""

    pass


class TestParamsImpl2(TestParams):
    """Second test parameters implementation"""

    pass


# Test module content template
TEST_MODULE_CONTENT = '''
from typing import Optional
from {base_module} import TestBaseClass, TestParams

class {class_name}(TestBaseClass):
    """Test implementation in module"""
    pass

class {params_class_name}(TestParams):
    """Test parameters implementation in module"""
    value: Optional[str] = None
'''


class TestModelScanner:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup test environment and clean up after tests"""
        # Create temporary directory for test modules
        self.temp_dir = tempfile.mkdtemp()
        self.module_name = "test_modules"
        self.module_path = os.path.join(self.temp_dir, self.module_name)
        os.makedirs(self.module_path)

        # Create __init__.py
        with open(os.path.join(self.module_path, "__init__.py"), "w") as f:
            f.write("")

        # Add temporary directory to Python path
        sys.path.insert(0, self.temp_dir)

        yield

        # Cleanup
        sys.path.remove(self.temp_dir)
        shutil.rmtree(self.temp_dir)

        # Remove imported test modules from sys.modules
        for key in list(sys.modules.keys()):
            if key.startswith(self.module_name):
                del sys.modules[key]

    def create_test_module(
        self, module_name: str, class_name: str, params_class_name: str
    ):
        """Create a test module with test classes"""
        module_path = os.path.join(self.module_path, f"{module_name}.py")

        # Get the current module's name
        current_module = TestBaseClass.__module__

        with open(module_path, "w") as f:
            f.write(
                TEST_MODULE_CONTENT.format(
                    base_module=current_module,
                    class_name=class_name,
                    params_class_name=params_class_name,
                )
            )

    def test_basic_scanning(self):
        """Test basic class scanning functionality"""
        # Create test modules
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")
        self.create_test_module("module2", "TestImpl2", "TestParamsImpl2")

        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name, base_class=TestBaseClass, recursive=True
        )

        results = scanner.scan_and_register(config)

        # Check if classes were found
        assert len(results) == 2
        assert all(issubclass(cls, TestBaseClass) for cls in results.values())
        assert "test_modules.module1.testimpl1" in results
        assert "test_modules.module2.testimpl2" in results

    def test_recursive_scanning(self):
        """Test recursive directory scanning"""
        # Create nested directory structure
        nested_dir = os.path.join(self.module_path, "nested")
        os.makedirs(nested_dir)
        with open(os.path.join(nested_dir, "__init__.py"), "w") as f:
            f.write("")

        # Create test modules in different directories
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")
        self.create_test_module("nested/module2", "TestImpl2", "TestParamsImpl2")

        # Test with recursive=True
        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name, base_class=TestBaseClass, recursive=True
        )

        results = scanner.scan_and_register(config)
        assert len(results) == 2

        # Test with recursive=False
        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name, base_class=TestBaseClass, recursive=False
        )

        results = scanner.scan_and_register(config)
        assert len(results) == 1

    def test_custom_filter(self):
        """Test custom class filter functionality"""
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")
        self.create_test_module("module2", "TestImpl2", "TestParamsImpl2")

        def custom_filter(cls: Type) -> bool:
            return cls.__name__.endswith("1")

        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name,
            base_class=TestBaseClass,
            class_filter=custom_filter,
            recursive=True,
        )

        results = scanner.scan_and_register(config)
        assert len(results) == 1
        assert "test_modules.module1.testimpl1" in results

    def test_multiple_base_classes(self):
        """Test scanning for multiple different base classes"""
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")

        # Scan for TestBaseClass
        scanner1 = ModelScanner[TestBaseClass]()
        config1 = ScannerConfig(
            module_path=self.module_name, base_class=TestBaseClass, recursive=True
        )
        results1 = scanner1.scan_and_register(config1)

        # Scan for TestParams
        scanner2 = ModelScanner[TestParams]()
        config2 = ScannerConfig(
            module_path=self.module_name, base_class=TestParams, recursive=True
        )
        results2 = scanner2.scan_and_register(config2)

        assert len(results1) == 1
        assert len(results2) == 1
        assert "test_modules.module1.testimpl1" in results1
        assert "test_modules.module1.testparamsimpl1" in results2

    def test_error_handling(self):
        """Test error handling for invalid modules and paths"""
        scanner = ModelScanner[TestBaseClass]()

        # Test with non-existent module
        config = ScannerConfig(
            module_path="non_existent_module", base_class=TestBaseClass
        )
        results = scanner.scan_and_register(config)
        assert len(results) == 0

        # Test with invalid module content
        with open(os.path.join(self.module_path, "invalid_module.py"), "w") as f:
            f.write("This is invalid Python code!!!!")

        config = ScannerConfig(module_path=self.module_name, base_class=TestBaseClass)
        results = scanner.scan_and_register(config)
        assert len(results) == 0

    def test_specific_files(self):
        """Test scanning specific files"""
        # Create multiple test modules
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")
        self.create_test_module("module2", "TestImpl2", "TestParamsImpl2")
        self.create_test_module("module3", "TestImpl3", "TestParamsImpl3")

        # Test scanning specific single file
        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name,
            base_class=TestBaseClass,
            specific_files=["module1"],
        )
        results = scanner.scan_and_register(config)

        # Check results
        assert len(results) == 1
        assert "test_modules.module1.testimpl1" in results
        assert "testimpl2" not in results
        assert "testimpl3" not in results

        # Test scanning multiple specific files
        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name,
            base_class=TestBaseClass,
            specific_files=["module1", "module2"],
        )
        results = scanner.scan_and_register(config)

        # Check results
        assert len(results) == 2
        assert "test_modules.module1.testimpl1" in results
        assert "test_modules.module2.testimpl2" in results
        assert "testimpl3" not in results

    def test_specific_files_not_found(self):
        """Test scanning specific files that don't exist"""
        # Create one test module
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")

        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name,
            base_class=TestBaseClass,
            specific_files=["non_existent_module", "module1"],
        )
        results = scanner.scan_and_register(config)

        # Should still find the existing module
        assert len(results) == 1
        assert "test_modules.module1.testimpl1" in results

    def test_specific_files_in_nested_directory(self):
        """Test scanning specific files in nested directories"""
        # Create nested directory structure
        nested_dir = os.path.join(self.module_path, "nested")
        os.makedirs(nested_dir)
        with open(os.path.join(nested_dir, "__init__.py"), "w") as f:
            f.write("")

        # Create test modules in different directories
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")
        self.create_test_module("nested/module2", "TestImpl2", "TestParamsImpl2")

        # Test scanning specific file in nested directory
        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=f"{self.module_name}.nested",
            base_class=TestBaseClass,
            specific_files=["module2"],
        )
        results = scanner.scan_and_register(config)

        # Check results
        assert len(results) == 1
        assert "test_modules.nested.module2.testimpl2" in results

    def test_specific_files_with_filter(self):
        """Test scanning specific files with additional filter"""
        # Create test modules
        self.create_test_module("module1", "TestImpl1", "TestParamsImpl1")
        self.create_test_module("module2", "TestImpl2", "TestParamsImpl2")

        def custom_filter(cls: Type) -> bool:
            return cls.__name__.endswith("1")

        # Test scanning specific files with filter
        scanner = ModelScanner[TestBaseClass]()
        config = ScannerConfig(
            module_path=self.module_name,
            base_class=TestBaseClass,
            specific_files=["module1", "module2"],
            class_filter=custom_filter,
        )
        results = scanner.scan_and_register(config)

        # Should only find classes that match both criteria
        assert len(results) == 1
        assert "test_modules.module1.testimpl1" in results
        assert "testimpl2" not in results
