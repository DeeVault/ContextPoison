#!/usr/bin/env python3
"""
Generate a reproducible, evenly-distributed sample of statement IDs
across all categories for use with contextpoison.py --sample.

Samples whatever statement files are present in statements/. The harmful
third-party corpus is not bundled (see README "Dataset"), so out of the box
this samples the self-authored benign example seeds (statements/example_seeds.json).
Point it at the full dataset once you have obtained it from the authors.

Usage:
    python sample_statements.py --total 1000 --seed 42
    python sample_statements.py --total 100  --seed 42
"""
import argparse
import json
import random
from datetime import date
from pathlib import Path

STATEMENTS_DIR = Path(__file__).parent / "statements"


def load_by_category() -> dict[str, list[str]]:
    """Return {category: [id, ...]} for statements that have query_new."""
    result: dict[str, list[str]] = {}
    for path in sorted(STATEMENTS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            stmts = json.load(f)
        ids = [s["id"] for s in stmts if s.get("query_new")]
        if ids:
            result[path.stem] = ids
    return result


def even_sample(by_category: dict[str, list[str]], total: int, seed: int) -> tuple[dict[str, int], list[str]]:
    """
    Draw floor(total / n_cats) per category, then fill remaining slots
    from categories with the most leftover capacity (round-robin by size).
    Returns (counts_per_category, ordered_list_of_ids).
    """
    rng = random.Random(seed)
    cats = sorted(by_category)
    n_cats = len(cats)
    per_cat = total // n_cats
    remainder = total - per_cat * n_cats

    sampled: dict[str, list[str]] = {}
    for cat in cats:
        pool = by_category[cat][:]
        rng.shuffle(pool)
        sampled[cat] = pool[:per_cat]

    # Distribute remainder slots to categories with the most leftover capacity
    capacity = [(len(by_category[c]) - per_cat, c) for c in cats]
    capacity.sort(reverse=True)
    for i in range(remainder):
        cat = capacity[i % len(capacity)][1]
        pool = by_category[cat][:]
        rng.shuffle(pool)
        # grab the next unused id from this category
        already = set(sampled[cat])
        extras = [sid for sid in pool if sid not in already]
        if extras:
            sampled[cat].append(extras[0])

    counts = {cat: len(ids) for cat, ids in sampled.items()}
    all_ids = [sid for cat in cats for sid in sampled[cat]]
    rng.shuffle(all_ids)
    return counts, all_ids


def main():
    parser = argparse.ArgumentParser(
        description="Sample statement IDs evenly across categories for ContextPoison benchmarks"
    )
    parser.add_argument("--total", type=int, default=1000, metavar="N",
                        help="Total number of statements to sample (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, metavar="SEED",
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--output", default="sample.json", metavar="FILE",
                        help="Output path (default: sample.json)")
    args = parser.parse_args()

    by_category = load_by_category()
    if not by_category:
        print("Error: no statement files found in statements/")
        raise SystemExit(1)

    n_cats = len(by_category)
    available = sum(len(ids) for ids in by_category.values())
    if args.total > available:
        print(f"Warning: requested {args.total} but only {available} statements available; capping.")
        args.total = available

    counts, all_ids = even_sample(by_category, args.total, args.seed)

    out = {
        "total": len(all_ids),
        "seed": args.seed,
        "generated": date.today().isoformat(),
        "categories": counts,
        "statement_ids": all_ids,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Sampled {len(all_ids)} statements across {n_cats} categories → {args.output}")
    for cat in sorted(counts):
        print(f"  {cat}: {counts[cat]}")


if __name__ == "__main__":
    main()
