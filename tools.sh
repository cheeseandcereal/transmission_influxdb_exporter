#!/bin/sh
set -e

# Check and try to use python3.8 explicitly, if possible
if command -v python3.8 > /dev/null 2>&1; then
    py_exec=python3.8
else
    py_exec=python3
fi

# Makes sure we're in this script's directory (avoid symlinks and escape special chars)
cd "$(cd "$(dirname "$0")"; pwd -P)"

USAGE="usage: tools.sh [command]

command
run         : run the project
unit        : run unit tests on the project
coverage    : view coverage for the project (must run unit first)
tests       : run all tests for the project and display coverage when finished
lint        : check that the project has no linting errors with black
format      : automatically try to fix any linting problems that exist with the black formatter
clean       : remove compiled python/docs/other build or distribution artifacts from the local project
venv        : reset venv from scratch (removes existing venv if it exists)
full-test   : run all the checks
docker-test : run all the checks in a docker container"

if [ $# -lt 1 ]; then
    printf "%s\\n" "$USAGE"
    exit 1
elif [ "$1" = "run" ]; then
    $py_exec -m transmission_influxdb.main
elif [ "$1" = "unit" ]; then
    $py_exec -m coverage run --branch --source=./transmission_influxdb -m unittest discover -p '*utest.py'
elif [ "$1" = "coverage" ]; then
    include=$(find transmission_influxdb -path "*.py" -not -path ".git*" -not -path ".mypy_cache*" -not -path ".venv*" | tr '\n' ',' | rev | cut -c 2- | rev)
    $py_exec -m coverage report -m --include="$include"
elif [ "$1" = "tests" ]; then
    sh tools.sh unit
    sh tools.sh coverage
elif [ "$1" = "lint" ]; then
    find transmission_influxdb -name "*.py" -exec $py_exec -m flake8 {} +
    $py_exec -m black --check -l 150 -t py38 transmission_influxdb
elif [ "$1" = "format" ]; then
    $py_exec -m black -l 150 -t py38 transmission_influxdb
elif [ "$1" = "clean" ]; then
    find . \( -path ./.venv -o -path ./.mypy_cache \) -prune -o \( -name __pycache__ -o -name .build -o -name .coverage \) -exec rm -rfv {} +
elif [ "$1" = "venv" ]; then
    rm -rf .venv/
    $py_exec -m venv .venv
    source .venv/bin/activate
    pip install -U pip setuptools wheel
    pip install -U -r dev_requirements.txt
    pip install -r requirements.txt
    echo "virtual env set up. Run source ./.venv/bin/activate to enable it in your shell"
elif [ "$1" = "docker-test" ]; then
    docker build . -f ./Dockerfile.test -t transmission_influxdb_testing_container --pull
    docker run -it transmission_influxdb_testing_container
elif [ "$1" = "full-test" ]; then
    set +e
    printf "\\nChecking for linting errors\\n\\n"
    if ! sh tools.sh lint; then printf "\\n!!! Linting Failure. You may need to run 'tools.sh format' !!!\\n" && exit 1; fi
    printf "\\nRunning all tests\\n\\n"
    if ! sh tools.sh tests; then printf "\\n!!! Tests Failure !!!\\n" && exit 1; fi
    printf "\\nSuccess!\\nUse 'tools.sh clean' to cleanup if desired\\n"
else
    printf "%s\\n" "$USAGE"
    exit 1
fi
