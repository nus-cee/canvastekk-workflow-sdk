#!/bin/bash
# Test verification script for Phase 2 tests

set -e

PYTHON_DIR="/home/silentx/VSCODE/canvastekk-workflow-sdk/python"
cd "$PYTHON_DIR"

echo "=== Test Phase 2 Verification ==="
echo ""

echo "1. Checking test file syntax with Python..."
python3 -m py_compile tests/test_auth.py 2>&1 || echo "  test_auth.py has syntax errors"
python3 -m py_compile tests/test_app.py 2>&1 || echo "  test_app.py has syntax errors"
python3 -m py_compile tests/test_base.py 2>&1 || echo "  test_base.py has syntax errors"
echo ""

echo "2. Running ruff linter..."
.venv/bin/ruff check canvastekk_workflow_sdk/auth.py tests/test_auth.py 2>&1 || true
.venv/bin/ruff check canvastekk_workflow_sdk/app.py tests/test_app.py 2>&1 || true
.venv/bin/ruff check canvastekk_workflow_sdk/base.py tests/test_base.py 2>&1 || true
echo ""

echo "3. Counting tests..."
AUTH_TESTS=$(grep -c "^    def test_" tests/test_auth.py)
APP_TESTS=$(grep -c "^    def test_" tests/test_app.py)
BASE_TESTS=$(grep -c "^    def test_" tests/test_base.py)

echo "  test_auth.py: $AUTH_TESTS tests"
echo "  test_app.py: $APP_TESTS tests"
echo "  test_base.py: $BASE_TESTS tests"
echo "  Total new tests: $((AUTH_TESTS + APP_TESTS + BASE_TESTS - 39 - 35 - 26))"
echo ""

echo "4. Running pytest on new tests..."
.venv/bin/pytest tests/test_auth.py -v --tb=short 2>&1 | tail -30 || echo "  Some tests failed"
echo ""

echo "=== Verification Complete ==="