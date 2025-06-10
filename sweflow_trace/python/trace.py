from typing import List, Dict
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

import os
import sys
import argparse
import shutil
import subprocess
import json
import random as rnd
import re

printf = partial(print, flush=True)


def parse_args():

    def int_or_none(value):
        if value in ["None", "none", "NONE", "null", "NULL", "Null", "NULL"]:
            return None
        return int(value)

    def true_or_false(value):
        if value in ["True", "true", "TRUE"]:
            return True
        return False

    parser = argparse.ArgumentParser(description='Generate pytest trace for a Python project')
    parser.add_argument('--project-root', type=str, help='Path to the Python project.')
    parser.add_argument('--max-workers', type=int_or_none, default=None, help='Number of workers to use for the trace.')
    parser.add_argument('--max-tests', type=int_or_none, default=None, help='Maximum number of tests to trace.')
    parser.add_argument('--random', type=true_or_false, default=False, help='Whether to randomize the order of tests.')
    parser.add_argument('--random-seed', type=int, default=42, help='The random seed to use for the trace.')
    parser.add_argument('--output-dir', type=str, help='Output directory to save the trace data.')

    return parser.parse_args()


def clear_python_cache(dir: str) -> None:
    """
    Clear the Python cache in the project.
    """
    print("clearing python cache...")
    for root, dirs, files in os.walk(dir):
        for dir in dirs:
            if dir == "__pycache__" or dir == ".pytest_cache":
                shutil.rmtree(os.path.join(root, dir))


def run_pytest(cwd: str, pytest_args: List[str]) -> None:
    """
    Run pytest with the given arguments.
    """
    pytest_args_str = " ".join(pytest_args)
    # create pytest command
    cmd = f"{sys.executable} -m pytest {pytest_args_str}"

    # set environment variable
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{cwd}/src:{env.get('PYTHONPATH', '')}"
    env["SETUPTOOLS_USE_DISTUTILS"] = "local"

    # run pytest
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True)

    # clear python cache
    clear_python_cache(cwd)

    if result.returncode != 0:
        printf(f"pytest failed with return code {result.returncode}")
        printf(f"pytest output:\n{result.stdout.decode()}")
        printf(f"pytest error:\n{result.stderr.decode()}")
        raise Exception(f"pytest failed with return code {result.returncode}")


def collect_tests(
    project_root: str,
    output_dir: str,
    random: bool = False,
    random_seed: int = 42,
    max_tests: int | None = None,
    report_file: str = "tests-info.json",
) -> List[str]:
    """
    Collect the tests in the project.
    """

    # set current working directory
    cwd = Path(project_root).resolve()
    printf(f"collecting tests in {cwd}")
    printf(f"current working directory:\n{cwd}")

    _output_dir = Path(output_dir).resolve()
    # create output directory if it doesn't exist
    os.makedirs(_output_dir, exist_ok=True)

    # create pytest args
    pytest_args = [
        "--collect-only",
        "--cache-clear",
        f"--rootdir={cwd}",
        "-o",
        f"cache_dir={cwd}/.pytest_cache",
        "--json-report",
        "--json-report-indent=4",
        f"--json-report-file={_output_dir}/{report_file}",
    ]

    # run pytest
    run_pytest(cwd=cwd, pytest_args=pytest_args)

    report = json.load(open(Path(_output_dir) / report_file))
    collectors = report['collectors']
    tests = []
    for collector in collectors:
        for res in collector['result']:
            if res['type'] not in ['Function', 'TestCaseFunction']:
                continue
            tests.append(res['nodeid'])
    printf(f"collected {len(tests)} test items")

    printf(f"merging tests with same function name...")
    tests = list(set([re.sub(r"\[.*?\]", "", test) for test in tests]))
    printf(f"total {len(tests)} merged tests")

    if random:
        printf(f"random enabled, shuffling tests with random seed {random_seed}")
        rnd.seed(random_seed)
        rnd.shuffle(tests)

    if max_tests:
        printf(f"selecting {max_tests} tests as --max-tests is set to {max_tests}")
        tests = tests[:max_tests]

    return tests


def run_trace_test(cwd: str, pytest_args: List[str], trace_file: str, timeout: int = 120) -> None:
    """
    Run hooked pytest with the given arguments.
    """
    trace_args = [
        "--trace-output",
        f"{trace_file}",
        "--program",
        "pytest",
    ] + pytest_args
    trace_args_str = " ".join(trace_args)
    cmd = f"sweflow-hooks-python {trace_args_str}"

    # set environment variable
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{cwd}/src:{env.get('PYTHONPATH', '')}"
    env["SETUPTOOLS_USE_DISTUTILS"] = "local"

    # run pytest
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        printf(f"pytest failed with return code {result.returncode}")
        printf(f"pytest output:\n{result.stdout.decode()}")
        printf(f"pytest error:\n{result.stderr.decode()}")
        raise Exception(f"pytest failed with return code {result.returncode}")


def get_test_func_id(test_result: Dict) -> str:
    """
    Get the test function id from the test result.
    """
    func_node = re.sub(r"\[.*?\]", "", test_result['nodeid'])
    filepath = func_node.split("::")[0]
    func_name = func_node.split("::")[-1]
    lineno = test_result['lineno'] + 1  # convert 0-based to 1-based
    return f"{filepath}:{lineno}:{func_name}"


def trace_test(test: str, cwd: str, temp_dir: str) -> None:
    try:
        with TemporaryDirectory(dir=temp_dir) as _temp_dir:
            printf(f"running test {test} in {_temp_dir}")

            pytest_args = [
                "--cache-clear",
                f"--rootdir={cwd}",
                "-o",
                f"cache_dir={_temp_dir}/.pytest_cache",
                "--no-cov",
                "--json-report",
                "--json-report-indent=4",
                f"--json-report-file={_temp_dir}/report.json",
                test,
            ]
            trace_file = f"{_temp_dir}/trace.json"

            run_trace_test(cwd=cwd, pytest_args=pytest_args, trace_file=trace_file)

            test_report = json.load(open(f"{_temp_dir}/report.json"))
            test_result = test_report['tests'][0]
            if test_result['outcome'] != 'passed':
                return None

            call_relationships = json.load(open(trace_file))

        test_func_id = get_test_func_id(test_result)
        return {
            "test-id": test,
            "test-func-id": test_func_id,
            "call-relations": call_relationships,
        }
    except Exception as e:
        printf(f"Error processing test {test}: {e}")
        return None


def generate_test_traces(
    project_root: str,
    output_dir: str,
    tests: List[str],
    max_workers: int | None = None,
    temp_dir: str | None = None,
) -> None:
    """
    Generate test traces.
    """
    cwd = Path(project_root).resolve()
    traces = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(trace_test, test, cwd, temp_dir): test for test in tests}
        count = 0
        for future in as_completed(futures):
            result = future.result()
            if result:
                traces.append(result)
            count += 1
            printf(f"generated {count}/{len(tests)} traces")

    # clear python cache
    clear_python_cache(cwd)

    printf(f"Generated {len(traces)} traces")

    # save the traces to the tracwrite_file
    with open(Path(output_dir) / "traces.json", "w") as f:
        json.dump(traces, f, indent=4)


def main():

    args = parse_args()

    tests = collect_tests(
        project_root=args.project_root,
        output_dir=args.output_dir,
        random=args.random,
        random_seed=args.random_seed,
        max_tests=args.max_tests,
    )

    generate_test_traces(
        project_root=args.project_root,
        max_workers=args.max_workers,
        output_dir=args.output_dir,
        tests=tests,
    )


if __name__ == '__main__':

    main()
