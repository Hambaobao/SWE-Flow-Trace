#!/bin/bash

# Install the package in development mode
pip install -e ".[test]"

# Run the tests
pytest -v