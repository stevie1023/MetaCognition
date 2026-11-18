#!/usr/bin/env python3
"""Conform notes/bib to the corrected deck's per-leaf SELECTED WORKS lines.

The deck does not just rename chapters — it names, for every one of the 37
sub-questions, the works that belong there and the evidence tier each carries.
That list is the authority. This script makes the bibliography agree with it:

  1. COVERAGE. If the deck names a work under a sub-question, the work must be
     listed under that sub-question. v1 grouped papers by chapter topic, so a
     work the deck now cites in 4.4 could be sitting in 4.3. Such works are
     re-filed into the section the deck assigns them (and kept where they
     already were, if they legitimately serve both).

  2. TIER. The tier is overwritten with exactly what the deck states. Where the
     deck is silent the existing tier survives, so the role-derived default
     still applies to works the deck did not name.

  3. DECK ORDER. Each work records its `deck_rank` — its position in the deck's
     own citation string for that leaf. The figure sorts on it, so the figure's
     citation line reproduces the deck's column rather than inventing an order.

  4. SURVEY PROPOSALS. Five leaves carry an S entry that is not a paper at all
     but this survey's own protocol or accounting ("Survey protocol: compare Q
     estimates to outcomes"). Those become real entries so the README can say
     what the survey proposes at that leaf, which is otherwise invisible.

Run:  python3 tools/conform_v2.py       (after tools/migrate_v2.py)
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "notes" / "bib"
BAK = ROOT / "notes" / "bib.v1.bak"
SLIDES = Path("/tmp/slidep-inspect.mjgJTX/slides.md")

# --------------------------------------------------------------- deck -> title
#
# The deck prints author-year or short labels; the bibliography keeps full
# titles. Every label the deck uses is resolved explicitly — no fuzzy matching,
# because a wrong match would silently move a paper to the wrong sub-question.
DECK_LABEL = {
    "Flavell":
        "Metacognition and Cognitive Monitoring: A New Area of Cognitive-Developmental Inquiry",
    "Nelson & Narens": "Metamemory: A Theoretical Framework and New Findings",
    "Russell & Wefald": "Principles of Metareasoning",
    "Resource-Rational Analysis":
        "Resource-Rational Analysis: Understanding Human Cognition as the "
        "Optimal Use of Limited Computational Resources",
    "Maniscalco & Lau":
        "A Signal Detection Theoretic Approach for Estimating Metacognitive "
        "Sensitivity from Confidence Ratings",
    "Fleming & Daw":
        "Self-Evaluation of Decision-Making: A General Bayesian Framework for "
        "Metacognitive Computation",
    "MC²":
        "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving "
        "LLM Reasoning (MC-squared)",
    "Kadavath et al.": "Language Models (Mostly) Know What They Know",
    # the deck prints this one as the truncated "LMs (Mostly) Know (2022)",
    # which strips to the bare label "LMs" — same work as Kadavath et al.
    "LMs": "Language Models (Mostly) Know What They Know",
    "Li et al.":
        "Language Models Are Capable of Metacognitive Monitoring and Control of "
        "Their Internal Activations",
    "Self-Refine": "Self-Refine: Iterative Refinement with Self-Feedback",
    "LMs (Mostly) Know": "Language Models (Mostly) Know What They Know",
    "Semantic Uncertainty":
        "Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation "
        "in Natural Language Generation",
    "R-Tuning": "R-Tuning: Instructing Large Language Models to Say 'I Don't Know'",
    "SelfAware": "Do Large Language Models Know What They Don't Know? (SelfAware)",
    "MUR": "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models",
    "Activation Monitoring":
        "Language Models Are Capable of Metacognitive Monitoring and Control of "
        "Their Internal Activations",
    "Capability Awareness": "Do Large Language Models Know What They Are Capable Of?",
    "Overthinking of Long Reasoning Models":
        "Do NOT Think That Much for 2+3=? On the Overthinking of o1-Like LLMs",
    "Semantic Entropy Probes":
        "Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs",
    "Self-RAG":
        "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection",
    "Tree of Thoughts": "Tree of Thoughts: Deliberate Problem Solving with Large Language Models",
    "Self-Discover": "Self-Discover: Large Language Models Self-Compose Reasoning Structures",
    "ReAct": "ReAct: Synergizing Reasoning and Acting in Language Models",
    "AutoMix": "AutoMix: Automatically Mixing Language Models",
    "CRITIC": "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing",
    "SCoRe": "Training Language Models to Self-Correct via Reinforcement Learning (SCoRe)",
    "s1": "s1: Simple Test-Time Scaling",
    "Test-Time Compute vs. Parameters":
        "Scaling LLM Test-Time Compute Optimally Can Be More Effective than "
        "Scaling Model Parameters",
    "RouteLLM": "RouteLLM: Learning to Route LLMs with Preference Data",
    "LLM2Jev": "LLM-as-Jev: LLMs Are Already Jev-Style Decision Models—When and How to Fine-Tune Them",
    "Self-Correction Limits": "Large Language Models Cannot Self-Correct Reasoning Yet",
    "Self-Rewarding LMs": "Self-Rewarding Language Models",
    "Meta-Rewarding LMs": "Meta-Rewarding Language Models: Self-Improving Alignment with LLM-as-a-Meta-Judge",
    "ReasoningBank": "ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory",
    "ExpeL": "ExpeL: LLM Agents Are Experiential Learners",
    "Meta Agent Search / ADAS": "Automated Design of Agentic Systems (Meta Agent Search)",
    "Darwin Gödel Machine": "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents",
    "Huxley-Gödel Machine":
        "Huxley-Gödel Machine: Human-Level Coding Agent Development by an "
        "Approximation of the Optimal Self-Improving Machine",
    "STOP": "Self-Taught Optimizer (STOP): Recursively Self-Improving Code Generation",
}

# The five leaves where the deck's own entry is an S proposal rather than a
# paper. `title` is what the README and figure print; `why` is the one-liner.
PROPOSALS = {
    "2.1": ("This survey: an L0 / L1 / L2 synthesis",
            "The organising claim itself: that cognition, regulation and learning "
            "can be separated by what each level takes as input and returns as "
            "output. Stated here so that the later claims which depend on it are "
            "visible as depending on it."),
    "5.3": ("Survey protocol: compare Q estimates to outcomes",
            "The evaluation protocol this survey proposes but no cited paper "
            "runs end to end: record the controller's ex-ante expected utility Q "
            "at each decision point, then score it against the realized gain."),
    "5.4": ("Survey protocol: matched-state action ablations",
            "The attribution standard this survey proposes: intervene and "
            "withhold the metacognitive action from the same state, so that the "
            "difference is the action rather than the state that triggered it."),
    "5.6": ("Survey accounting: ΔU1 (L1→L0) and ΔU2 (L2→L1)",
            "The bookkeeping this survey proposes for cross-level comparison: "
            "ΔU1 is the gain from regulating L0 within a fixed policy, ΔU2 the "
            "gain from having learned that policy at all."),
    "8.2": ("Intervention-based value-of-information tests",
            "The test this survey proposes for causal signal value: perturb or "
            "withhold the monitor's signal and measure whether behaviour changes, "
            "since correlation between a probe and an outcome is not evidence "
            "that the signal is used."),
}


# Two deck lines name a *pair* of works in one token, because the pair is the
# point: 5.3 offers them as the two existing illustrations of the protocol, and
# 5.4 contrasts them. The generic label parser would keep only the first, so
# they are declared here with both members and the tier the deck gives them.
DECK_PAIRS = {
    ("5.3", "A  AutoMix (2024), MUR (2026): examples"): [
        ("A", "AutoMix: Automatically Mixing Language Models"),
        ("A", "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models"),
    ],
    ("5.4", "B  Self-Refine (2023) vs. Self-Correction Limits (2024)"): [
        ("B", "Self-Refine: Iterative Refinement with Self-Feedback"),
        ("B", "Large Language Models Cannot Self-Correct Reasoning Yet"),
    ],
}


def load_deck():
    """Return {section: [(tier, title, venue_text), ...]} in deck order."""
    if not SLIDES.exists():
        sys.exit(f"missing deck extraction at {SLIDES}")
    txt = SLIDES.read_text(encoding="utf-8")
    blocks = re.findall(r"\n(\d\.\d)\s\s(.+?)\n\n\*\*c\d+\*\*[^\n]*\n\n(.+?)\n", txt)
    out, unmapped = {}, []
    for sid, _sub, works in blocks:
        items = []
        for raw in re.split(r"\s+·\s+", works):
            raw = raw.replace("\\&", "&").strip()
            pair = DECK_PAIRS.get((sid, raw))
            if pair:
                items.extend((t, ttl, raw) for t, ttl in pair)
                continue
            m = re.match(r"^([DABS])\s+(.+)$", raw)
            if not m:
                continue
            tier, rest = m.group(1), m.group(2)
            label = re.sub(r"\s*\(.*$", "", rest).strip()
            if tier == "S":
                continue                      # handled by PROPOSALS
            title = DECK_LABEL.get(label)
            if not title:
                unmapped.append((sid, label, tier))
                continue
            items.append((tier, title, rest))
        out[sid] = items
    return out, unmapped


def chapter_of(sec):
    return "ch" + sec.split(".")[0]


def main():
    deck, unmapped = load_deck()
    if unmapped:
        print("  ! deck labels not resolved — add them to DECK_LABEL:")
        for sid, lab, t in unmapped:
            print(f"      {sid}  [{t}] {lab}")
        sys.exit("refusing to write with unresolved deck labels")

    # ---- read current bib, and a metadata pool for works we must copy in
    sections, pool, meta = {}, {}, {}
    for path in sorted(BIB.glob("*.yaml")):
        for block in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            sec = str(block["section"])
            sections[sec] = list(block.get("papers") or [])
            for p in sections[sec]:
                pool.setdefault(p["title"], dict(p))
                meta.setdefault(p["title"], dict(p))
    for path in sorted(BAK.glob("*.yaml")):
        for block in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            for p in block.get("papers") or []:
                pool.setdefault(p["title"], dict(p))
                meta.setdefault(p["title"], dict(p))

    added, retiered, moved = 0, 0, 0

    # ---- 1-3. coverage, tier and deck order
    for sec, items in deck.items():
        if sec not in sections:
            print(f"  ! {sec}: not a known section")
            continue
        have = {p["title"]: p for p in sections[sec]}
        for rank, (tier, title, _raw) in enumerate(items):
            if title not in have:
                base = pool.get(title)
                if not base:
                    print(f"  ! {sec}: deck names an unknown work: {title[:60]}")
                    continue
                rec = dict(base)
                sections[sec].append(rec)
                have[title] = rec
                added += 1
                print(f"  + {sec} <- {title[:66]}")
            rec = have[title]
            if rec.get("tier") != tier:
                print(f"  ~ {sec}  {title[:52]:52s}  {rec.get('tier')} -> {tier}")
                rec["tier"] = tier
                retiered += 1
            rec["deck_rank"] = rank

    # a work the deck names in more than one leaf keeps one rank per leaf, so
    # deck_rank is a per-entry field, not per-work — nothing to dedupe here
    for sec, papers in sections.items():
        for p in papers:
            p.setdefault("deck_rank", 999)

    # ---- 4. survey proposals
    for sec, (title, why) in PROPOSALS.items():
        if sec not in sections:
            continue
        have = {p["title"] for p in sections[sec]}
        if title in have:
            continue
        sections[sec].append(dict(
            title=title, venue="this survey (proposal)", links={},
            role="positioning", tier="S", deck_rank=-1, why=why))
        added += 1
        print(f"  + {sec} <- S proposal: {title[:58]}")

    # ---- write back, one file per chapter, ordered by section
    def sec_key(s):
        return [int(x) for x in s.split(".")]

    files = {}
    for sec in sorted(sections, key=sec_key):
        files.setdefault(chapter_of(sec), []).append(sec)

    total = 0
    for cname, secs in sorted(files.items(), key=lambda kv: int(kv[0][2:])):
        body = [
            f"# Bibliography: {cname} — see notes/taxonomy.yaml for the structure.",
            "# Two facets per entry:",
            "#   role  — what job the citation does in the argument",
            "#   tier  — D primary / A adjacent / B boundary / V others' survey / S own",
            "#   deck_rank — position in the corrected deck's citation string",
            "#               (-1 marks this survey's own proposal; 999 = unnamed)",
            "",
        ]
        for sec in secs:
            papers = sorted(sections[sec], key=lambda p: p["deck_rank"])
            body.append(f'- section: "{sec}"')
            body.append("  papers:")
            for p in papers:
                body.append(f"    - title: {scalar(p['title'])}")
                body.append(f"      venue: {scalar(p['venue'])}")
                body.append(f"      links: {mapping(p.get('links') or {})}")
                body.append(f"      role: {p['role']}")
                body.append(f"      tier: {p['tier']}")
                body.append(f"      deck_rank: {p['deck_rank']}")
                body.append(f"      why: {scalar(p['why'])}")
                total += 1
            body.append("")
        (BIB / f"{cname}.yaml").write_text("\n".join(body) + "\n", encoding="utf-8")

    print(f"\nadded {added}, retiered {retiered}, entries now {total}")
    dist = {}
    for papers in sections.values():
        for p in papers:
            dist[p["tier"]] = dist.get(p["tier"], 0) + 1
    print("tier distribution:", dict(sorted(dist.items())))


def quoted(text):
    """Single-quoted YAML scalar: `?`, `:` and `,` are all safe inside."""
    return "'" + str(text).replace("'", "''") + "'"


def scalar(value, indent=8):
    """Emit a YAML scalar without yaml.dump's `...` end-of-document marker."""
    text = str(value)
    if "\n" in text:
        pad = " " * indent
        return "|-\n" + "\n".join(pad + ln for ln in text.splitlines())
    return quoted(text)


def mapping(value):
    inner = ", ".join(f"{quoted(k)}: {quoted(v)}" for k, v in value.items())
    return "{" + inner + "}"


if __name__ == "__main__":
    main()
