from types import FrameType
from typing import Any
from pathlib import Path

import os
import sys
import argparse
import runpy
import json
import keyword


class CallTracer:

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir
        if base_dir is None:
            self.base_dir = os.getcwd()
        self.call_stack = []
        self.call_records = []
        self.call_records_set = set()

    def _in_base_dir(self, file_name: str) -> bool:
        """
        Check if the file is in the base directory and is a python file.
        """
        # convert to absolute path
        abs_path = os.path.abspath(file_name)
        return abs_path.startswith(self.base_dir + os.sep) and abs_path.endswith(".py")

    def _is_function(self, func_name: str) -> bool:
        """
        Check if `func_name` is a valid Python function name
        (i.e., a valid Python identifier and not a keyword).
        """
        # check if it's a valid identifier
        if not func_name.isidentifier():
            return False

        # check if it's a keyword
        if keyword.iskeyword(func_name):
            return False

        return True

    def trace_calls(self, frame: FrameType, event: str, arg: Any):
        """
        Trace the calls of the program.
        """
        code = frame.f_code
        file_name = code.co_filename
        func_name = code.co_name
        lineno = frame.f_lineno

        if event == "call":
            if not self._in_base_dir(file_name) or not self._is_function(func_name):
                return self.trace_calls

            if self.call_stack:
                caller_file, caller_func, caller_line = self.call_stack[-1]
            else:
                caller_file, caller_func, caller_line = (None, None, None)

            # push the current call to the call stack
            self.call_stack.append((str(Path(file_name).relative_to(self.base_dir)), func_name, lineno))

            new_record = {
                "caller": {
                    "filepath": caller_file,
                    "lineno": caller_line,
                    "func_name": caller_func
                },
                "callee": {
                    "filepath": str(Path(file_name).relative_to(self.base_dir)),
                    "lineno": lineno,
                    "func_name": func_name
                },
            }
            record_key = json.dumps(new_record, sort_keys=True)
            # skip if the record is already in the set
            if record_key in self.call_records_set:
                return self.trace_calls

            # skip if any of the fields are None
            if any(v is None for v in [caller_file, caller_func, caller_line, file_name, func_name, lineno]):
                return self.trace_calls

            self.call_records_set.add(record_key)
            self.call_records.append(new_record)

        elif event == "return":
            if self.call_stack:
                top_file, top_func, top_line = self.call_stack[-1]
                if self._in_base_dir(top_file) and self._is_function(top_func) and top_func == func_name:
                    # pop the current call from the call stack
                    self.call_stack.pop()

        return self.trace_calls

    def start(self):
        sys.setprofile(self.trace_calls)

    def stop(self):
        sys.setprofile(None)

    def save_to_file(self, output_file: str):
        """
        Save the call records to a file.
        """
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.call_records, f, indent=4)


def main():

    parser = argparse.ArgumentParser(description="Custom profiler for Python programs.")
    parser.add_argument("--program", type=str, required=True, help="Module to run")
    parser.add_argument("--trace-output", type=str, required=True, help="Output file for trace data.")
    parser.add_argument("--base-dir", type=str, default=None, help="Only record calls from this base directory. Default is current working directory.")

    known_args, unknown_args = parser.parse_known_args()

    tracer = CallTracer(base_dir=known_args.base_dir)
    tracer.start()

    try:
        # reconstruct sys.argv with target module name and unknown args
        sys.argv = [known_args.program] + unknown_args
        runpy.run_module(known_args.program, run_name="__main__", alter_sys=True)
    finally:
        tracer.stop()
        tracer.save_to_file(known_args.trace_output)


if __name__ == "__main__":

    main()
