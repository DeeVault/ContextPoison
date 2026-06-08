#!/usr/bin/env bash
# Complete ContextPoison benchmark against Claude Haiku.
# Requires: ANTHROPIC_API_KEY set in your environment.
#
# Usage:
#   chmod +x examples/benchmark_claude.sh
#   ./examples/benchmark_claude.sh

set -euo pipefail

MODEL="claude-haiku-4-5-20251001"

echo "==> Step 1: generate a reproducible 1000-statement sample"
python sample_statements.py --total 1000 --seed 42

echo ""
echo "==> Step 2: run baseline (bare questions, no injection)"
python contextpoison.py \
  --sample sample.json \
  --target "$MODEL" \
  --baseline \
  --workers 3

echo ""
echo "==> Step 3: run attack (Tinject fabricated-evidence injection)"
python contextpoison.py \
  --sample sample.json \
  --target "$MODEL" \
  --workers 3

echo ""
echo "==> Step 4: generate markdown report"
python contextpoison.py --report --output "${MODEL}_report.md"

echo ""
echo "Done. Report written to outputs/${MODEL}_report.md"
