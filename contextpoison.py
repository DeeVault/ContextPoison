# Main CLI: runs benchmark attacks and baselines, stores results in SQLite, and generates reports.
#!/usr/bin/env python3
import argparse
import json
import os
import random
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from phase2 import (
    PROVIDER_EXAMPLES,
    detect_provider,
    list_categories,
    load_statements,
    resolve_base_url,
    run_attack,
    run_baseline,
)
from report import generate_report
from score import score_response

DB_PATH = "results.db"
OUTPUTS_DIR = "outputs"

# Default statement set shipped with the tool. The harmful third-party corpus
# is not bundled (see README "Dataset"); out of the box the tool runs against
# the self-authored benign example seeds in statements/example_seeds.json.
DEFAULT_CATEGORY = "example_seeds"


def _resolve_output(path: str) -> str:
    """Prefix a bare filename with outputs/ and create the directory.

    If path already contains a directory component it is returned unchanged,
    allowing callers to write anywhere with an explicit path.
    """
    if not os.path.dirname(path):
        path = os.path.join(OUTPUTS_DIR, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


_TARGET_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
    "openai-compatible": "OPENAI_API_KEY",
}


def _pearson(xs: list, ys: list) -> float:
    """Compute Pearson correlation coefficient between two equal-length lists."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) ** 0.5) * (sum((y - my) ** 2 for y in ys) ** 0.5)
    return num / den if den else float("nan")


def run_validation(validate_scorer: str, validate_scorer_key: str, n: int = 150, seed: int = 42, scorer_url: str | None = None) -> None:
    """Re-score a random sample of stored responses and report agreement with original scores.

    Only statements that have both a baseline and an attack response in the DB
    are eligible for sampling, ensuring the validation covers paired data.
    Prints Pearson correlation, mean absolute difference, and any individual
    responses where the two scores diverged by 3 or more points.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cols = [row[1] for row in conn.execute("PRAGMA table_info(results)").fetchall()]
    if "baseline" not in cols:
        conn.close()
        print("Error: database has no baseline column — run --baseline first.", file=sys.stderr)
        sys.exit(1)

    rows = conn.execute("""
        SELECT * FROM results
        WHERE statement_id IN (
            SELECT statement_id FROM results
            GROUP BY statement_id
            HAVING SUM(CASE WHEN baseline=0 THEN 1 ELSE 0 END) > 0
               AND SUM(CASE WHEN baseline=1 THEN 1 ELSE 0 END) > 0
        )
        ORDER BY statement_id, baseline
    """).fetchall()
    conn.close()

    if not rows:
        print("No statements with both baseline and attack scores found.")
        return

    rng = random.Random(seed)
    sample = rng.sample(rows, min(n, len(rows)))
    print(f"Validating {len(sample)} responses (seed={seed}, scorer={validate_scorer})...\n")

    original: list[int] = []
    validated: list[int] = []
    divergent: list[tuple] = []
    errors = 0

    for row in sample:
        label = f"{row['statement_id']} baseline={row['baseline']} [{row['target_model']}]"
        try:
            v = score_response(row["basic_statement"], row["model_response"],
                               validate_scorer_key, model=validate_scorer, base_url=scorer_url)
            diff = abs(row["score"] - v)
            print(f"  {label}  orig={row['score']}  valid={v}  diff={diff}")
            original.append(row["score"])
            validated.append(v)
            if diff >= 3:
                divergent.append((row, v, diff))
        except Exception as exc:
            print(f"  {label}  ERROR: {exc}")
            errors += 1

    if len(original) < 2:
        print("\nNot enough successful validations to compute statistics.")
        return

    corr = _pearson(original, validated)
    mad = sum(abs(o - v) for o, v in zip(original, validated)) / len(original)

    print(f"\n{'='*50}")
    print(f"Validation summary")
    print(f"{'='*50}")
    print(f"  Responses validated : {len(original)}")
    print(f"  Scorer errors       : {errors}")
    print(f"  Pearson correlation : {corr:.4f}")
    print(f"  Mean abs difference : {mad:.4f}")
    print(f"  Divergent (|Δ|≥3)  : {len(divergent)}")

    if divergent:
        print(f"\nDivergent responses:")
        for row, v, diff in sorted(divergent, key=lambda x: -x[2]):
            print(f"  id={row['statement_id']}  baseline={row['baseline']}"
                  f"  model={row['target_model']}"
                  f"  orig={row['score']}  valid={v}  diff={diff}")
            print(f"    viewpoint: {row['basic_statement'][:120]}")


def init_db(conn: sqlite3.Connection) -> None:
    """Create the results table if it does not already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            statement_id    TEXT NOT NULL,
            category        TEXT NOT NULL,
            target_model    TEXT NOT NULL,
            target_base_url TEXT NOT NULL,
            basic_statement TEXT NOT NULL,
            query_new       TEXT NOT NULL,
            model_response  TEXT NOT NULL,
            score           INTEGER NOT NULL,
            created_at      TEXT NOT NULL,
            baseline        INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (statement_id, target_model, target_base_url, baseline)
        )
    """)
    conn.commit()


def migrate_db(conn: sqlite3.Connection) -> None:
    """Add the baseline column to an existing database that pre-dates it."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(results)").fetchall()]
    if "baseline" not in cols:
        conn.execute("ALTER TABLE results RENAME TO results_old")
        conn.execute("""
            CREATE TABLE results (
                statement_id    TEXT NOT NULL,
                category        TEXT NOT NULL,
                target_model    TEXT NOT NULL,
                target_base_url TEXT NOT NULL,
                basic_statement TEXT NOT NULL,
                query_new       TEXT NOT NULL,
                model_response  TEXT NOT NULL,
                score           INTEGER NOT NULL,
                created_at      TEXT NOT NULL,
                baseline        INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (statement_id, target_model, target_base_url, baseline)
            )
        """)
        conn.execute("INSERT INTO results SELECT *, 0 FROM results_old")
        conn.execute("DROP TABLE results_old")
        conn.commit()


def is_cached(conn: sqlite3.Connection, statement_id: str, target_model: str, target_base_url: str, baseline: bool = False) -> bool:
    """Return True if a result already exists for this statement / model / mode combination."""
    row = conn.execute(
        "SELECT 1 FROM results WHERE statement_id=? AND target_model=? AND target_base_url=? AND baseline=?",
        (statement_id, target_model, target_base_url, int(baseline)),
    ).fetchone()
    return row is not None


def save_result(conn, statement, target_model, target_base_url, model_response, score, baseline: bool = False):
    """Insert a scored result row; silently skips if the row already exists."""
    conn.execute(
        """INSERT OR IGNORE INTO results
           (statement_id, category, target_model, target_base_url, basic_statement,
            query_new, model_response, score, created_at, baseline)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            statement["id"],
            statement["_category"],
            target_model,
            target_base_url,
            statement["basic_statement"],
            statement["query_new"],
            model_response,
            score,
            datetime.now(timezone.utc).isoformat(),
            int(baseline),
        ),
    )
    conn.commit()


def run_statements(statements, target_model, target_base_url, target_api_key, scorer_api_key, conn, limit=None, baseline: bool = False, workers: int = 1):
    """Run statements against the target model, score each response, and store results.

    Cache-check happens in the main thread before any workers start.
    SQLite writes are serialised with a threading.Lock so concurrent workers
    (--workers > 1) cannot race on the connection.
    """
    call = run_baseline if baseline else run_attack
    db_lock = threading.Lock()

    skipped = 0
    work = []
    for stmt in statements:
        if is_cached(conn, stmt["id"], target_model, target_base_url, baseline):
            skipped += 1
        else:
            work.append(stmt)
    if limit is not None:
        work = work[:limit]

    def process(stmt):
        label = f"{stmt['id']} ({stmt['_category']})"
        try:
            response = call(stmt, target_model, target_base_url, target_api_key)
            score = score_response(stmt["basic_statement"], response, scorer_api_key)
            with db_lock:
                save_result(conn, stmt, target_model, target_base_url, response, score, baseline)
            print(f"  [{label}] score={score}", flush=True)
            return True
        except Exception as exc:
            print(f"  [{label}] ERROR: {exc}", flush=True)
            return False

    tested = errors = 0
    if workers == 1:
        for stmt in work:
            if process(stmt):
                tested += 1
            else:
                errors += 1
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for ok in pool.map(process, work):
                if ok:
                    tested += 1
                else:
                    errors += 1

    if skipped:
        print(f"  Skipped {skipped} already-cached result(s).")
    return tested, skipped, errors


def main():
    """Entry point for the ContextPoison CLI."""
    parser = argparse.ArgumentParser(
        description="ContextPoison — benchmark LLM resistance to fabricated evidence injection"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list-categories", action="store_true",
                      help="Print available statement categories and exit")
    mode.add_argument("--list-models", action="store_true",
                      help="Print example model strings for each supported provider and exit")
    mode.add_argument("--category", metavar="NAME",
                      help="Run all statements in a single category")
    mode.add_argument("--all", action="store_true",
                      help="Run all categories sequentially")
    mode.add_argument("--sample", metavar="FILE",
                      help="Run only the statement IDs listed in a sample.json file (generated by sample_statements.py)")
    mode.add_argument("--report", action="store_true",
                      help="Generate a markdown vulnerability report from results.db")
    mode.add_argument("--validate", action="store_true",
                      help="Re-score a random sample of stored results to measure scorer reliability")

    parser.add_argument("--target", metavar="MODEL",
                        help="Target model name (e.g. gpt-4o-mini, claude-haiku-4-5-20251001, gemini-flash-latest)")
    parser.add_argument("--target-url", default=None, metavar="URL",
                        help="Base URL for OpenAI-compatible target endpoints (e.g. http://localhost:11434/v1)")
    parser.add_argument("--target-key", metavar="KEY",
                        help="API key for the target model (falls back to the provider-specific env var)")
    parser.add_argument("--scorer-key", metavar="KEY",
                        help="Anthropic API key for the LLM scorer (falls back to $ANTHROPIC_API_KEY)")
    parser.add_argument("--validate-scorer", default="claude-sonnet-4-6", metavar="MODEL",
                        help="Model to use when re-scoring for --validate (default: claude-sonnet-4-6)")
    parser.add_argument("--validate-scorer-key", metavar="KEY",
                        help="API key for the validation scorer (falls back to $ANTHROPIC_API_KEY)")
    parser.add_argument("--validate-scorer-url", default=None, metavar="URL",
                        help="Base URL for an OpenAI-compatible validation scorer (e.g. https://api.together.xyz/v1)")
    parser.add_argument("--validate-n", type=int, default=150, metavar="N",
                        help="Number of stored responses to re-score during --validate (default: 150)")
    parser.add_argument("--limit", type=int, metavar="N",
                        help="Hard stop after N statements have been tested (skipped rows do not count)")
    parser.add_argument("--workers", type=int, default=1, metavar="N",
                        help="Number of concurrent API calls; 1 = sequential (default: 1)")
    parser.add_argument("--baseline", action="store_true",
                        help="Send query_new with no Tinject injection; results are stored with baseline=1")
    parser.add_argument("--output", default="report.md", metavar="FILE",
                        help="Output path for --report; bare filenames are placed in outputs/ (default: report.md)")

    args = parser.parse_args()

    if args.list_categories:
        cats = sorted(list_categories())
        print("Available categories:")
        for cat in cats:
            print(f"  {cat}")
        return

    if args.list_models:
        print("Example model strings by provider:")
        for provider, examples in PROVIDER_EXAMPLES.items():
            print(f"\n  {provider}:")
            for ex in examples:
                print(f"    {ex}")
        return

    if args.report:
        try:
            output_path = _resolve_output(args.output)
            generate_report(output_path, DB_PATH)
            print(f"Report written to {output_path}")
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if args.validate:
        key = args.validate_scorer_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            parser.error("--validate-scorer-key not provided and $ANTHROPIC_API_KEY is not set")
        run_validation(args.validate_scorer, key, n=args.validate_n, scorer_url=args.validate_scorer_url)
        return

    # Benchmark mode
    if not args.target:
        parser.error("--target is required")
    if not args.category and not args.all and not args.sample:
        args.category = DEFAULT_CATEGORY
        print(f"No --category/--all/--sample given; defaulting to '{DEFAULT_CATEGORY}'.")

    try:
        canonical_url = resolve_base_url(args.target, args.target_url)
    except ValueError as exc:
        parser.error(str(exc))

    provider = detect_provider(args.target, args.target_url)

    scorer_key = args.scorer_key or os.environ.get("ANTHROPIC_API_KEY")
    if not scorer_key:
        parser.error("--scorer-key not provided and $ANTHROPIC_API_KEY is not set")

    target_env = _TARGET_KEY_ENV.get(provider, "OPENAI_API_KEY")
    target_key = args.target_key or os.environ.get(target_env)
    if not target_key:
        parser.error(f"--target-key not provided and ${target_env} is not set")

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    init_db(conn)
    migrate_db(conn)

    mode_label = "baseline" if args.baseline else "attack"

    try:
        if args.sample:
            try:
                with open(args.sample, encoding="utf-8") as f:
                    sample_data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Error loading sample file: {exc}", file=sys.stderr)
                sys.exit(1)
            sample_ids = set(sample_data["statement_ids"])
            all_stmts = load_statements()
            statements = [s for s in all_stmts if s["id"] in sample_ids]
            order = {sid: i for i, sid in enumerate(sample_data["statement_ids"])}
            statements.sort(key=lambda s: order.get(s["id"], 0))
            print(
                f"Sample: {len(statements)} of {len(sample_ids)} requested statements found"
                f"  |  target: {args.target}  |  mode: {mode_label}"
            )
            tested, skipped, errors = run_statements(
                statements, args.target, canonical_url, target_key, scorer_key, conn,
                args.limit, baseline=args.baseline, workers=args.workers,
            )
            print(f"Done — tested={tested}  skipped={skipped}  errors={errors}")

        elif args.category:
            print(f"Running category: {args.category}  |  target: {args.target}  |  mode: {mode_label}")
            try:
                statements = load_statements(args.category)
            except FileNotFoundError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            tested, skipped, errors = run_statements(
                statements, args.target, canonical_url, target_key, scorer_key, conn,
                args.limit, baseline=args.baseline, workers=args.workers,
            )
            print(f"Done — tested={tested}  skipped={skipped}  errors={errors}")

        elif args.all:
            cats = sorted(list_categories())
            total_tested = total_skipped = total_errors = 0
            print(f"Running all {len(cats)} categories  |  target: {args.target}  |  mode: {mode_label}")
            remaining = args.limit
            for cat in cats:
                if remaining is not None and remaining <= 0:
                    break
                print(f"\nCategory: {cat}")
                statements = load_statements(cat)
                tested, skipped, errors = run_statements(
                    statements, args.target, canonical_url, target_key, scorer_key, conn,
                    limit=remaining, baseline=args.baseline, workers=args.workers,
                )
                total_tested += tested
                total_skipped += skipped
                total_errors += errors
                if remaining is not None:
                    remaining -= tested
            print(f"\nAll done — tested={total_tested}  skipped={total_skipped}  errors={total_errors}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
