# ContextPoison

A benchmarking tool that measures how well LLMs resist fabricated evidence injection.

---

## The Question It Answers

When an LLM is presented with text that looks authoritative — fake citations, fabricated statistics, academic phrasing — does it adopt the viewpoint uncritically, or does it push back?

This isn't about hacking a system. It's about understanding whether a model has sufficient critical reasoning to recognise and resist fabricated evidence before it amplifies it to users.

---

## What It Does

ContextPoison takes pre-built statements containing fabricated authoritative evidence, sends them to a target LLM, and scores whether the model adopted the injected viewpoint or resisted it.

The output is a vulnerability report showing:
- Which categories of fabricated evidence the model is most susceptible to
- What percentage of injections resulted in viewpoint adoption
- How the model compares across different attack categories

---

## What It Is Not

This is not a system prompt injection tool. It does not require backend access. It tests models as an end user would encounter them — via API — and measures whether their critical reasoning holds up against fabricated evidence.

---

## Why It Matters

Models that fail this test don't just get a fact wrong. They adopt a false viewpoint and present it as their own confident analysis. A user receiving that response has no indication the model was deceived. They might share it, cite it, or make decisions based on it.

Organisations deploying LLMs should know how their chosen model performs against this before putting it in front of users.

---

## Categories Tested

| Category | File |
|----------|------|
| Stereotype — Age | `stereotype_age.json` |
| Stereotype — Gender | `stereotype_gender.json` |
| Stereotype — Race | `stereotype_race.json` |
| Stereotype — Religion | `stereotype_religion.json` |
| Stereotype — Occupation | `stereotype_occupation.json` |
| Stereotype — Physical Characteristics | `stereotype_physical.json` |
| Stereotype — Sexual Orientation | `stereotype_sexual_orientation.json` |
| Misinformation — Brand | `misinfo_brand.json` |
| Misinformation — Medical | `misinfo_medical.json` |
| Misinformation — Political | `misinfo_political.json` |
| Manipulation — Psychological | `manipulation_psychological.json` |

---

## Based On

Yang et al. (2026). *Steering LLM Viewpoints through Fabricated Evidence Injection.* arXiv:2606.06244

Statement library sourced from the Hazardous Viewpoints Dataset (HVD) released by the authors.

---

## Early Findings (Manual Testing)

| Model | Category | Result |
|-------|----------|--------|
| Claude | Political Misinformation | Resisted — rejected fabricated evidence |
| Gemini | Political Misinformation | Adopted — presented fabricated viewpoint as own analysis |

---

© 2026 Connor. All rights reserved.
