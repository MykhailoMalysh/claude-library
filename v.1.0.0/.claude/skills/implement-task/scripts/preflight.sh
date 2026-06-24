#!/usr/bin/env bash
#
# preflight.sh — verify the build environment is ready before running the test suite.
#
# This is a generic template. Adapt it to your project's actual tooling requirements.
# The contract is simple: exit 0 = ready to run tests; exit 1 = not ready, with a
# one-line fix hint on stderr explaining what to do.
#
# Idempotent — safe to run multiple times.

set -uo pipefail

fail() { echo "preflight: $1" >&2; exit 1; }

# ── Docker check (if your tests require a running Docker daemon) ──────────────
#
# Remove this section if your project does not use Docker-based test infrastructure.

if command -v docker >/dev/null 2>&1; then
  docker info >/dev/null 2>&1 \
    || fail "Docker daemon not reachable — start Docker and retry."
fi

# ── Add project-specific checks below ────────────────────────────────────────
#
# Examples:
#   - Check a required service is running (database, message broker, etc.)
#   - Verify a required CLI tool is installed
#   - Export environment variables your test runner needs
#
# export MY_ENV_VAR="${MY_ENV_VAR:-default-value}"

echo "preflight: ready."
