# ContextPoison

LLMs trust text that looks authoritative. Fake citations, fabricated statistics, academic phrasing — models treat these as legitimate context and incorporate the viewpoints they contain into their responses, even when those viewpoints are false or harmful.

This is not a jailbreak. The model isn't being tricked into revealing something it knows is wrong. It genuinely believes the fabricated evidence it's been given. That's what makes this attack surface persistent and hard to patch.

ContextPoison is a modular red team toolkit for testing whether your LLM deployment is vulnerable to this class of attack, and measuring how well your defenses catch it.

---

## The attack surface

Fabricated evidence injection works in three steps:

1. **Repackage** — a misleading statement is rewritten with fake statistics, citations, and authoritative framing
2. **Inject** — the repackaged statement is embedded in the target model's context with a conditional template that triggers on relevant queries
3. **Measure** — responses are scored for viewpoint alignment to quantify attack success

The target model never sees a jailbreak prompt. It sees what looks like legitimate background context. That's why standard safety alignment doesn't catch it.

---

## Current techniques

| Technique | Paper | Status |
|-----------|-------|--------|
| Ghostwriter | Yang et al., 2026 (arXiv:2606.06244) | ✅ Implemented |
| More planned | — | 🔜 |

---

## Responsible use

This toolkit is for authorised security testing only. Test only systems you own or have explicit permission to test.

---

## Based on

Yang et al. (2026). *Steering LLM Viewpoints through Fabricated Evidence Injection.* arXiv:2606.06244

---

© 2026 Connor. All rights reserved.
