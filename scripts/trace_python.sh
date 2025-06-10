#!/bin/bash

set -e

#  make sure you are in the SWE-Flow docker container corresponding to the REPOSITORY
REPOSITORY=imageio/imageio
MAX_WORKERS=16
MAX_TESTS=None
RANDOM=True
RANDOM_SEED=42

# install the package and install the package
git clone https://github.com/Hambaobao/SWE-Flow-Trace.git
cd SWE-Flow-Trace
pip install -e .

# copy the repository to the workspace
cp -r /sweflow/sweflow-build/workspace.backup/. /workspace

# run the trace
OUTPUT_DIR=$PROJECT_ROOT/data/sweflow-trace/$REPOSITORY
sweflow-trace-python \
    --project-root /workspace \
    --max-workers $MAX_WORKERS \
    --max-tests $MAX_TESTS \
    --random $RANDOM \
    --random-seed $RANDOM_SEED \
    --output-dir $OUTPUT_DIR
