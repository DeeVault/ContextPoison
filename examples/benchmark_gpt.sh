#!/usr/bin/env bash
# Complete ContextPoison benchmark against GPT-4o-mini.
# Requires:
#   OPENAI_API_KEY  — for the target model
#   ANTHROPIC_API_KEY — for the scorer
#
# Usage:
#   chmod +x examples/benchmark_gpt.sh
#   ./examples/benchmark_gpt.sh

set -euo pipefail

MODEL="gpt-4o-mini"

echo "==> Step 1: generate a reproducible 1000-statement sample"
# Skip this step if sample.json already exists from a previous run —
# using the same sample across models ensures fair comparison.
if [ ! -f sample.json ]; then
  python sample_statements.py --total 1000 --seed 42
else
  echo "  sample.json already exists, skipping generation."
fi

echo ""
echo "==> Step 2: run baseline (bare questions, no injection)"
python contextpoison.py \
  --sample sample.json \
  --target "$MODEL" \
  --baseline \
  --workers 5

echo ""
echo "==> Step 3: run attack (Tinject fabricated-evidence injection)"
python contextpoison.py \
  --sample sample.json \
  --target "$MODEL" \
  --workers 5

echo ""
echo "==> Step 4: generate markdown report"
python contextpoison.py --report --output "${MODEL}_report.md"

echo ""
echo "Done. Report written to outputs/${MODEL}_report.md"
