# SWE-Flow-Trace Tests

This directory contains unit tests for the SWE-Flow-Trace project.

## Running the Tests

To run the tests, use the following command from the project root directory:

```bash
pytest
```

Or to run with more verbose output:

```bash
pytest -v
```

## Test Coverage

The tests cover the main functionality of the project:

- `test_hooks.py`: Tests for the `CallTracer` class and related functions in `sweflow_trace.python.hooks`
- `test_trace.py`: Tests for the functions in `sweflow_trace.python.trace`

## Adding New Tests

When adding new tests, follow these guidelines:

1. Create test files with the `test_` prefix
2. Group related tests in classes with the `Test` prefix
3. Name test methods with the `test_` prefix
4. Include docstrings explaining what each test is checking