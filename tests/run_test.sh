#!/usr/bin/env bash
# Test local being python2 and python3. Inside of the tests, it test for 
#     local --> local
#     local --> remote py2
#     local --> remote py3

# pip install pytest-cov

# Assuming you have py.test installed for both python2 and 3
P0=$(pwd)
cd "$(dirname "$0")"

p2dir=$(dirname $(command which python2))
${p2dir}/py.test --cov=PyFiSync --cov-report html test_*.py

p3dir=$(dirname $(command which python3))
${p3dir}/py.test --cov=PyFiSync --cov-report html test_*.py

cd $P0