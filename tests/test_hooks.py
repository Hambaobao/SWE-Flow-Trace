import os
import json
import tempfile
from unittest import mock
from pathlib import Path

import pytest
from sweflow_trace.python.hooks import CallTracer


class TestCallTracer:
    def setup_method(self):
        self.base_dir = os.getcwd()
        self.tracer = CallTracer(base_dir=self.base_dir)

    def test_init(self):
        """Test the initialization of CallTracer."""
        assert self.tracer.base_dir == self.base_dir
        assert self.tracer.call_stack == []
        assert self.tracer.call_records == []
        assert self.tracer.call_records_set == set()

        # Test with default base_dir
        tracer = CallTracer()
        assert tracer.base_dir == os.getcwd()

    def test_in_base_dir(self):
        """Test the _in_base_dir method."""
        # Create a temporary file in the base directory
        with tempfile.NamedTemporaryFile(suffix='.py', dir=self.base_dir) as temp_file:
            assert self.tracer._in_base_dir(temp_file.name) is True

        # Test with a file outside the base directory
        assert self.tracer._in_base_dir('/tmp/outside.py') is False

        # Test with a non-Python file
        with tempfile.NamedTemporaryFile(suffix='.txt', dir=self.base_dir) as temp_file:
            assert self.tracer._in_base_dir(temp_file.name) is False

    def test_is_function(self):
        """Test the _is_function method."""
        # Valid function names
        assert self.tracer._is_function('valid_function') is True
        assert self.tracer._is_function('_private_function') is True
        assert self.tracer._is_function('func123') is True

        # Invalid function names
        assert self.tracer._is_function('123invalid') is False
        assert self.tracer._is_function('invalid-name') is False
        assert self.tracer._is_function('class') is False  # Python keyword

    def test_save_to_file(self):
        """Test the save_to_file method."""
        # Add some test records
        self.tracer.call_records = [
            {
                "caller": {"filepath": "test_file.py", "lineno": 10, "func_name": "caller_func"},
                "callee": {"filepath": "test_file.py", "lineno": 20, "func_name": "callee_func"}
            }
        ]

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.json') as temp_file:
            self.tracer.save_to_file(temp_file.name)
            
            # Read the file and check the content
            with open(temp_file.name, 'r') as f:
                saved_data = json.load(f)
                assert saved_data == self.tracer.call_records

    @mock.patch('sys.setprofile')
    def test_start_stop(self, mock_setprofile):
        """Test the start and stop methods."""
        self.tracer.start()
        mock_setprofile.assert_called_once_with(self.tracer.trace_calls)
        
        mock_setprofile.reset_mock()
        self.tracer.stop()
        mock_setprofile.assert_called_once_with(None)

    def test_trace_calls_basic(self):
        """Test the basic functionality of trace_calls."""
        # Create a mock frame
        mock_frame = mock.MagicMock()
        mock_frame.f_code.co_filename = os.path.join(self.base_dir, "test.py")
        mock_frame.f_code.co_name = "test_function"
        mock_frame.f_lineno = 10
        
        # Test with call event but empty call stack
        result = self.tracer.trace_calls(mock_frame, "call", None)
        assert result == self.tracer.trace_calls
        assert len(self.tracer.call_stack) == 1
        assert self.tracer.call_stack[0][1] == "test_function"
        
        # The record should not be added because caller is None
        assert len(self.tracer.call_records) == 0
        
        # Test with return event
        result = self.tracer.trace_calls(mock_frame, "return", None)
        assert result == self.tracer.trace_calls
        assert len(self.tracer.call_stack) == 0