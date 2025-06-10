# SWE-Flow-Trace

This is a tool for tracing the execution of a Python package.

## Installation

```bash
git clone https://github.com/Hambaobao/SWE-Flow-Trace.git
cd SWE-Flow-Trace
pip install -e .
```

## Usage
To trace the funcation calls during the unittests execution of a Python package, you need to make sure all the dependencies for the package are installed.
Then you can run the following command to trace the funcation calls during the unittests execution.

```bash
sweflow-trace-python \
    --project-root /workspace \ # the root directory of the project
    --max-workers $MAX_WORKERS \ # the number of workers to use
    --max-tests $MAX_TESTS \ # the number of tests to run, default to None
    --random $RANDOM \ # whether to run the tests randomly, default to False
    --random-seed $RANDOM_SEED \ # the seed for the random number generator
    --output-dir $OUTPUT_DIR # the directory to save the trace results

```

## Testing

To run the unit tests for this project:

```bash
# Install the package with test dependencies
pip install -e ".[test]"

# Run the tests
pytest

# Run the tests with verbose output
pytest -v
```

The tests cover the main functionality of the project:
- `CallTracer` class in the hooks module
- Test collection and tracing functions in the trace module