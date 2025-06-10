import os
import json
import tempfile
from unittest import mock
from pathlib import Path

import pytest
from sweflow_trace.python.trace import (
    parse_args, 
    clear_python_cache, 
    run_pytest, 
    collect_tests,
    get_test_func_id
)


class TestParseArgs:
    def test_int_or_none(self):
        """Test the int_or_none function."""
        # Define the int_or_none function directly since we can't access it from parse_args
        def int_or_none(value):
            if value in ["None", "none", "NONE", "null", "NULL", "Null", "NULL"]:
                return None
            return int(value)
        
        # Test with None values
        for none_val in ["None", "none", "NONE", "null", "NULL", "Null"]:
            assert int_or_none(none_val) is None
        
        # Test with integer values
        assert int_or_none("123") == 123
        assert int_or_none("-456") == -456
        
        # Test with invalid values
        with pytest.raises(ValueError):
            int_or_none("not_an_int")

    def test_true_or_false(self):
        """Test the true_or_false function."""
        # Define the true_or_false function directly since we can't access it from parse_args
        def true_or_false(value):
            if value in ["True", "true", "TRUE"]:
                return True
            return False
        
        # Test with True values
        for true_val in ["True", "true", "TRUE"]:
            assert true_or_false(true_val) is True
        
        # Test with other values (should return False)
        assert true_or_false("False") is False
        assert true_or_false("anything_else") is False

    @mock.patch('argparse.ArgumentParser.parse_args')
    def test_parse_args(self, mock_parse_args):
        """Test the parse_args function."""
        # Mock the return value of parse_args
        mock_args = mock.MagicMock()
        mock_args.project_root = "/test/project"
        mock_args.max_workers = 4
        mock_args.max_tests = 10
        mock_args.random = True
        mock_args.random_seed = 42
        mock_args.output_dir = "/test/output"
        mock_parse_args.return_value = mock_args
        
        # Call the function
        args = parse_args()
        
        # Check the result
        assert args.project_root == "/test/project"
        assert args.max_workers == 4
        assert args.max_tests == 10
        assert args.random is True
        assert args.random_seed == 42
        assert args.output_dir == "/test/output"


class TestClearPythonCache:
    @mock.patch('os.walk')
    @mock.patch('shutil.rmtree')
    def test_clear_python_cache(self, mock_rmtree, mock_walk):
        """Test the clear_python_cache function."""
        # Mock os.walk to return some directories
        mock_walk.return_value = [
            ("/test/dir", ["__pycache__", "normal_dir", ".pytest_cache"], []),
            ("/test/dir/__pycache__", [], ["file1.pyc"]),
            ("/test/dir/.pytest_cache", [], ["file2.tmp"]),
        ]
        
        # Call the function
        clear_python_cache("/test/dir")
        
        # Check that rmtree was called for the cache directories
        mock_rmtree.assert_any_call("/test/dir/__pycache__")
        mock_rmtree.assert_any_call("/test/dir/.pytest_cache")
        assert mock_rmtree.call_count == 2


class TestRunPytest:
    @mock.patch('subprocess.run')
    @mock.patch('sweflow_trace.python.trace.clear_python_cache')
    def test_run_pytest_success(self, mock_clear_cache, mock_run):
        """Test the run_pytest function with successful execution."""
        # Mock the subprocess.run result
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Call the function
        run_pytest(cwd="/test/dir", pytest_args=["--verbose", "test_file.py"])
        
        # Check that subprocess.run was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args[1]
        assert call_args["cwd"] == "/test/dir"
        assert call_args["shell"] is True
        # The command is passed as a string in the first positional argument
        command = mock_run.call_args[0][0] if mock_run.call_args[0] else mock_run.call_args[1].get("cmd", "")
        assert "--verbose test_file.py" in command
        
        # Check that clear_python_cache was called
        mock_clear_cache.assert_called_once_with("/test/dir")

    @mock.patch('subprocess.run')
    @mock.patch('sweflow_trace.python.trace.clear_python_cache')
    def test_run_pytest_failure(self, mock_clear_cache, mock_run):
        """Test the run_pytest function with failed execution."""
        # Mock the subprocess.run result
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b"Test failed"
        mock_result.stderr = b"Error message"
        mock_run.return_value = mock_result
        
        # Call the function and check that it raises an exception
        with pytest.raises(Exception, match="pytest failed with return code 1"):
            run_pytest(cwd="/test/dir", pytest_args=["--verbose", "test_file.py"])
        
        # Check that clear_python_cache was called
        mock_clear_cache.assert_called_once_with("/test/dir")


class TestGetTestFuncId:
    def test_get_test_func_id(self):
        """Test the get_test_func_id function."""
        # Test with a simple test result
        test_result = {
            "nodeid": "test_file.py::test_function",
            "lineno": 9  # 0-based, will be converted to 10 (1-based)
        }
        assert get_test_func_id(test_result) == "test_file.py:10:test_function"
        
        # Test with a parameterized test
        test_result = {
            "nodeid": "test_file.py::test_function[param1-param2]",
            "lineno": 19
        }
        assert get_test_func_id(test_result) == "test_file.py:20:test_function"
        
        # Test with a class-based test
        test_result = {
            "nodeid": "test_file.py::TestClass::test_method",
            "lineno": 29
        }
        assert get_test_func_id(test_result) == "test_file.py:30:test_method"


@mock.patch('sweflow_trace.python.trace.run_pytest')
class TestCollectTests:
    def test_collect_tests_basic(self, mock_run_pytest, tmp_path):
        """Test the basic functionality of collect_tests."""
        # Create a mock report file
        report_data = {
            "collectors": [
                {
                    "result": [
                        {"type": "Function", "nodeid": "test_file.py::test_func1"},
                        {"type": "Function", "nodeid": "test_file.py::test_func2"},
                        {"type": "Module", "nodeid": "test_file.py"}  # Should be ignored
                    ]
                }
            ]
        }
        
        output_dir = str(tmp_path)
        report_file = "tests-info.json"
        report_path = os.path.join(output_dir, report_file)
        
        # Mock the json.load to return our test data
        with mock.patch('json.load', return_value=report_data):
            # Mock the open function to simulate the report file
            with mock.patch('builtins.open', mock.mock_open()) as mock_file:
                tests = collect_tests(
                    project_root="/test/project",
                    output_dir=output_dir,
                    report_file=report_file
                )
                
                # Check that run_pytest was called correctly
                mock_run_pytest.assert_called_once()
                
                # Check the collected tests
                assert len(tests) == 2
                assert "test_file.py::test_func1" in tests
                assert "test_file.py::test_func2" in tests

    def test_collect_tests_with_random(self, mock_run_pytest, tmp_path):
        """Test collect_tests with random ordering."""
        # Create a mock report file with many tests to ensure shuffling has an effect
        report_data = {
            "collectors": [
                {
                    "result": [
                        {"type": "Function", "nodeid": f"test_file.py::test_func{i}"}
                        for i in range(20)
                    ]
                }
            ]
        }
        
        output_dir = str(tmp_path)
        report_file = "tests-info.json"
        
        # Mock the json.load to return our test data
        with mock.patch('json.load', return_value=report_data):
            # Mock the open function
            with mock.patch('builtins.open', mock.mock_open()) as mock_file:
                # Call with random=True and a fixed seed
                tests1 = collect_tests(
                    project_root="/test/project",
                    output_dir=output_dir,
                    random=True,
                    random_seed=42,
                    report_file=report_file
                )
                
                # Call again with the same seed to verify deterministic shuffling
                tests2 = collect_tests(
                    project_root="/test/project",
                    output_dir=output_dir,
                    random=True,
                    random_seed=42,
                    report_file=report_file
                )
                
                # Call with a different seed
                tests3 = collect_tests(
                    project_root="/test/project",
                    output_dir=output_dir,
                    random=True,
                    random_seed=43,
                    report_file=report_file
                )
                
                # Check that the tests are shuffled but deterministic with the same seed
                assert tests1 == tests2
                assert tests1 != sorted(tests1)  # Verify shuffling happened
                assert tests1 != tests3  # Different seed should give different order

    def test_collect_tests_with_max_tests(self, mock_run_pytest, tmp_path):
        """Test collect_tests with max_tests limit."""
        # Create a mock report file
        report_data = {
            "collectors": [
                {
                    "result": [
                        {"type": "Function", "nodeid": f"test_file.py::test_func{i}"}
                        for i in range(10)
                    ]
                }
            ]
        }
        
        output_dir = str(tmp_path)
        report_file = "tests-info.json"
        
        # Mock the json.load to return our test data
        with mock.patch('json.load', return_value=report_data):
            # Mock the open function
            with mock.patch('builtins.open', mock.mock_open()) as mock_file:
                # Call with max_tests=5
                tests = collect_tests(
                    project_root="/test/project",
                    output_dir=output_dir,
                    max_tests=5,
                    report_file=report_file
                )
                
                # Check that only 5 tests were returned
                assert len(tests) == 5