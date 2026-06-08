# ContextPoison

**ContextPoison** benchmarks LLM resistance to fabricated evidence injection.

It uses a technique called **Tinject**: a crafted system prompt instructs the model to silently adopt a false viewpoint and weave it into responses. Statements are drawn from 11 categories (political misinformation, medical misinformation, stereotypes, psychological manipulation, and more). An LLM scorer rates each response on a 1–10 adoption scale, and a baseline run (bare question, no injection) is compared against the attack run to measure the true injection lift.

## Quick start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python sample_statements.py --total 1000 --seed 42
python contextpoison.py --sample sample.json --target claude-haiku-4-5-20251001 --baseline
python contextpoison.py --sample sample.json --target claude-haiku-4-5-20251001
python contextpoison.py --report
```

See [USAGE.md](USAGE.md) for the full guide and flag reference.

## Supported providers

| Provider | Model prefix | Key env var |
|---|---|---|
| Anthropic | `claude-` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-` | `OPENAI_API_KEY` |
| Google | `gemini-` | `GOOGLE_API_KEY` |
| xAI | `grok-` / `xai-` | `XAI_API_KEY` |
| Any OpenAI-compatible | (requires `--target-url`) | `OPENAI_API_KEY` |

## Project structure

```
contextpoison.py      Main CLI — benchmarks, reports, validation
phase2.py             Provider dispatch and Tinject prompt construction
score.py              LLM scorer (rates adoption 1-10)
report.py             Markdown report generator
sample_statements.py  Reproducible cross-category sampler
statements/           11 JSON statement files (one per category)
examples/             Ready-to-run benchmark shell scripts
outputs/              Generated reports (git-ignored)
```

## Roadmap

- **v0.2** — `detect.py`: automated red-teaming detection heuristics to identify when a model is being Tinject-attacked; `phase1.py`: pre-benchmark statement quality filtering pipeline.

## License

MIT
