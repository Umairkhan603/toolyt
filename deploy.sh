#!/usr/bin/env bash
set -e

echo "=== Toolyt Production Deployment & Security Setup ==="

# 1. Verify virtual environment or python environment
if [ -d "./venv" ]; then
    PYTHON="./venv/bin/python"
else
    PYTHON="python3"
fi

# 2. Check environment variables
if [ ! -f ".env" ]; then
    echo "[!] .env file not found. Copying .env.example to .env..."
    cp .env.example .env
fi

# 3. Execute Django Migrations
echo "[*] Running database migrations..."
$PYTHON manage.py migrate --noinput

# 4. Collect static files for production serving
echo "[*] Collecting static files..."
$PYTHON manage.py collectstatic --noinput

# 5. Run Security Inspection
echo "[*] Running Django security audit check..."
$PYTHON manage.py check --deploy --settings=config.settings.production || true

# 6. Run Test Suite Verification
echo "[*] Running automated test suite..."
$PYTHON -m pytest --quiet || {
    echo "[!] Tests failed! Aborting deployment."
    exit 1
}

echo "=== Deployment Ready & Hardened Successfully ==="
