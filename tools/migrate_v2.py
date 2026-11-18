#!/usr/bin/env python3
"""Migrate notes/bib from the v1 numbering to the v2 (corrected) taxonomy.

One-shot, reproducible: reads the v1 backup (notes/bib.v1.bak) and writes the
new notes/bib/*.yaml. Keeps every verified `venue`/`links`/`why` untouched and
adds the new `tier` facet.

Two things change:

  1. Section ids. Chapters 3-8 keep their numbering, so they carry over as-is.
     The old theory block (2.1-2.5) is re-cut into the corrected layout:
     ch1 gains its own 1.1-1.3, and ch2 keeps 2.1-2.2.

  2. A new `tier` field (D/A/B/V/S) alongside `role`. Where the corrected deck
     states the tier explicitly we use it verbatim; otherwise we derive it from
     `role`, which is a good proxy: a foundational or representative work
     directly studies the concept (D), a contrast or boundary work tests its
     limits (B), a benchmark supplies enabling machinery (A), and a survey or
     position piece is synthesis (S).

Run:  python3 tools/migrate_v2.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BAK = ROOT / "notes" / "bib.v1.bak"
OUT = ROOT / "notes" / "bib"

# --------------------------------------------------------------- 1. re-cut ch1-2
#
# The corrected deck's theory block. Each new leaf lists the v1 titles that
# belong to it; metadata is carried over from the v1 pool by exact title.
THEORY = {
    "1.1": [   # Object-level vs. meta-level cognition
        "Metacognition and Cognitive Monitoring: A New Area of Cognitive-Developmental Inquiry",
        "Metamemory: A Theoretical Framework and New Findings",
        "Feeling of Knowing in Memory and Problem Solving",
        "Meta-Reasoning: Monitoring and Control of Thinking and Reasoning",
        "Metacognition and Confidence: A Review and Synthesis",
        "Logic, Self-Awareness and Self-Improvement: The Metacognitive Loop and the Problem of Brittleness",
        "Metacognition in Computation: A Selected Research Review",
    ],
    "1.2": [   # Metareasoning and Value of Computation
        "Principles of Metareasoning",
        "Toward a Rational and Mechanistic Account of Mental Effort",
        "Resource-Rational Analysis: Understanding Human Cognition as the Optimal Use of Limited Computational Resources",
        "Position: LLMs Need a Bayesian Meta-Reasoning Framework",
        "Position: Truly Self-Improving Agents Require Intrinsic Metacognitive Learning",
    ],
    "1.3": [   # Self-evaluation and metacognitive measurement
        "A Signal Detection Theoretic Approach for Estimating Metacognitive Sensitivity from Confidence Ratings",
        "Self-Evaluation of Decision-Making: A General Bayesian Framework for Metacognitive Computation",
        "How to Measure Metacognition",
    ],
    "2.1": [   # Cognition (L0), regulation (L1), learning (L2)
        "Common Computations for Metacognition and Meta-Metacognition",
        "Monitor-Generate-Verify: Formalising Metacognitive Theory for Language Model Reasoning",
        "Metareasoning: Thinking about Thinking",
        "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)",
    ],
    "2.2": [   # Boundary: monitoring vs. routine reflection
        "Language Models (Mostly) Know What They Know",
        "Language Models Are Capable of Metacognitive Monitoring and Control of Their Internal Activations",
        "Self-Refine: Iterative Refinement with Self-Feedback",
        "Evidence for Limited Metacognition in Large Language Models",
        "Large Language Models Cannot Self-Correct Reasoning Yet",
        "Metacognitive Myopia in Large Language Models",
        "Does It Make Sense to Speak of Introspection in Large Language Models?",
        "Language Models Fail to Introspect About Their Knowledge of Language",
        "Decoupling Metacognition from Cognition: A Framework for Evaluating Metacognition in LLMs",
        "Imagining and Building Wise Machines: The Centrality of AI Metacognition",
        "Metacognitive AI: Framework and the Case for a Neurosymbolic Approach",
        "Metacognition in LLMs: Foundations, Progress, and Opportunities",
    ],
}

# Chapters whose numbering is unchanged; only the chapter heading moved.
CARRY_OVER = ["3.1", "3.2", "3.3", "3.4", "3.5",
              "4.1", "4.2", "4.3", "4.4", "4.5", "4.6",
              "5.1", "5.2", "5.3", "5.4", "5.5", "5.6",
              "6.1", "6.2", "6.3", "6.4", "6.5",
              "7.1", "7.2", "7.3", "7.4", "7.5",
              "8.1", "8.2", "8.3", "8.4", "8.5"]

# --------------------------------------------------------------- 2. deck tiers
#
# Tiers stated explicitly in metacognition_taxonomy_corrected.pptx, keyed by
# (section, title). Anything absent falls back to the role->tier default.
DECK_TIER = {
    ("1.1", "Metacognition and Cognitive Monitoring: A New Area of Cognitive-Developmental Inquiry"): "D",
    ("1.1", "Metamemory: A Theoretical Framework and New Findings"): "D",
    ("1.2", "Principles of Metareasoning"): "D",
    ("1.2", "Resource-Rational Analysis: Understanding Human Cognition as the Optimal Use of Limited Computational Resources"): "D",
    ("1.3", "A Signal Detection Theoretic Approach for Estimating Metacognitive Sensitivity from Confidence Ratings"): "D",
    ("1.3", "Self-Evaluation of Decision-Making: A General Bayesian Framework for Metacognitive Computation"): "D",
    ("2.1", "Metamemory: A Theoretical Framework and New Findings"): "D",
    ("2.1", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "D",
    ("2.2", "Language Models (Mostly) Know What They Know"): "D",
    ("2.2", "Language Models Are Capable of Metacognitive Monitoring and Control of Their Internal Activations"): "D",
    ("2.2", "Self-Refine: Iterative Refinement with Self-Feedback"): "B",
    # ch3
    ("3.1", "Language Models (Mostly) Know What They Know"): "D",
    ("3.1", "Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in Natural Language Generation"): "D",
    ("3.2", "R-Tuning: Instructing Large Language Models to Say 'I Don't Know'"): "D",
    ("3.2", "Do Large Language Models Know What They Don't Know? (SelfAware)"): "D",
    ("3.3", "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models"): "D",
    ("3.3", "Language Models Are Capable of Metacognitive Monitoring and Control of Their Internal Activations"): "D",
    ("3.4", "Do Large Language Models Know What They Are Capable Of?"): "D",
    ("3.4", "Do NOT Think That Much for 2+3=? On the Overthinking of o1-Like LLMs"): "A",
    ("3.5", "Language Models (Mostly) Know What They Know"): "D",
    ("3.5", "Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs"): "A",
    ("3.5", "Language Models Are Capable of Metacognitive Monitoring and Control of Their Internal Activations"): "D",
    # ch4
    ("4.1", "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection"): "D",
    ("4.1", "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models"): "D",
    ("4.2", "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"): "A",
    ("4.2", "Self-Discover: Large Language Models Self-Compose Reasoning Structures"): "A",
    ("4.3", "ReAct: Synergizing Reasoning and Acting in Language Models"): "A",
    ("4.3", "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection"): "D",
    ("4.3", "AutoMix: Automatically Mixing Language Models"): "D",
    ("4.4", "Self-Refine: Iterative Refinement with Self-Feedback"): "A",
    ("4.4", "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing"): "D",
    ("4.4", "Training Language Models to Self-Correct via Reinforcement Learning (SCoRe)"): "A",
    ("4.5", "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models"): "D",
    ("4.5", "s1: Simple Test-Time Scaling"): "B",
    ("4.5", "Scaling LLM Test-Time Compute Optimally Can Be More Effective than Scaling Model Parameters"): "A",
    ("4.6", "AutoMix: Automatically Mixing Language Models"): "D",
    ("4.6", "RouteLLM: Learning to Route LLMs with Preference Data"): "A",
    # ch5
    ("5.1", "A Signal Detection Theoretic Approach for Estimating Metacognitive Sensitivity from Confidence Ratings"): "D",
    ("5.1", "Language Models (Mostly) Know What They Know"): "D",
    ("5.2", "AutoMix: Automatically Mixing Language Models"): "D",
    ("5.2", "RouteLLM: Learning to Route LLMs with Preference Data"): "A",
    ("5.3", "AutoMix: Automatically Mixing Language Models"): "A",
    ("5.3", "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models"): "A",
    ("5.4", "Self-Refine: Iterative Refinement with Self-Feedback"): "B",
    ("5.4", "Large Language Models Cannot Self-Correct Reasoning Yet"): "B",
    ("5.5", "Scaling LLM Test-Time Compute Optimally Can Be More Effective than Scaling Model Parameters"): "A",
    ("5.5", "MUR: Momentum Uncertainty Guided Reasoning for Large Language Models"): "D",
    ("5.6", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "A",
    # ch6
    ("6.1", "Self-Rewarding Language Models"): "A",
    ("6.1", "Meta-Rewarding Language Models: Self-Improving Alignment with LLM-as-a-Meta-Judge"): "D",
    ("6.2", "Training Language Models to Self-Correct via Reinforcement Learning (SCoRe)"): "A",
    ("6.2", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "D",
    ("6.3", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "D",
    ("6.3", "Training Language Models to Self-Correct via Reinforcement Learning (SCoRe)"): "A",
    ("6.4", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "D",
    ("6.4", "ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory"): "A",
    ("6.5", "ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory"): "A",
    ("6.5", "ExpeL: LLM Agents Are Experiential Learners"): "A",
    # ch7
    ("7.1", "Automated Design of Agentic Systems (Meta Agent Search)"): "A",
    ("7.1", "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents"): "D",
    ("7.2", "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents"): "D",
    ("7.2", "Huxley-Gödel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine"): "D",
    ("7.3", "Self-Taught Optimizer (STOP): Recursively Self-Improving Code Generation"): "B",
    ("7.3", "Huxley-Gödel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine"): "D",
    ("7.4", "Huxley-Gödel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine"): "D",
    ("7.4", "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents"): "A",
    ("7.5", "Self-Taught Optimizer (STOP): Recursively Self-Improving Code Generation"): "B",
    ("7.5", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "A",
    # ch8
    ("8.1", "Language Models Are Capable of Metacognitive Monitoring and Control of Their Internal Activations"): "D",
    ("8.1", "Self-Refine: Iterative Refinement with Self-Feedback"): "B",
    ("8.2", "AutoMix: Automatically Mixing Language Models"): "D",
    ("8.3", "Language Models (Mostly) Know What They Know"): "D",
    ("8.3", "RouteLLM: Learning to Route LLMs with Preference Data"): "A",
    ("8.4", "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)"): "D",
    ("8.4", "Training Language Models to Self-Correct via Reinforcement Learning (SCoRe)"): "A",
    ("8.5", "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents"): "A",
    ("8.5", "Self-Taught Optimizer (STOP): Recursively Self-Improving Code Generation"): "B",
}

ROLE_TIER = {
    "foundational": "D",
    "representative": "D",
    "contrast": "B",
    "boundary": "B",
    "benchmark": "A",
    # Another author's survey/position paper. This is tier V, NOT S: S is
    # reserved for this survey's own proposals (deck_rank -1), which are added
    # by tools/conform_v2.py. Rolling the two together made tier S mean two
    # different things at once.
    "positioning": "V",
}

# --------------------------------------------------------------- 3. corrections
#
# Venues re-verified against the venue of record while migrating; the v1 file
# had these as preprint/arXiv because that is where they were first found.
VENUE_FIX = {
    "RouteLLM: Learning to Route LLMs with Preference Data": (
        "ICLR 2025", {"paper": "https://openreview.net/forum?id=8sSqNntaMr"}),
    "Do Large Language Models Know What They Are Capable Of?": (
        "ICLR 2026", {"paper": "https://openreview.net/forum?id=EO6WtJ0q6G"}),
}

# Works cited the corrected deck that v1 did not carry.
NEW_PAPERS = {
    "4.6": [dict(
        title="LLM-as-Jev: LLMs Are Already Jev-Style Decision Models—When and How to Fine-Tune Them",
        venue="arXiv 2026",
        links={"paper": "https://arxiv.org/abs/2610.02076",
               "code": "https://github.com/nokia-applied-research/AnyJev"},
        role="representative",
        tier="A",
        why="Extracts a calibrated decision directly from next-token probabilities over "
            "candidate options instead of generating free text — the cheapest end of the "
            "cost-aware controller spectrum, and evidence that the decision can be read "
            "off the base model without a separate head.",
    )],
}

ORDER = ["paper", "pdf", "acl", "proceedings", "code", "data", "repo", "book"]


def sort_links(links):
    out = {}
    for k in ORDER:
        if k in links:
            out[k] = links[k]
    for k, v in links.items():
        if k not in out:
            out[k] = v
    return out


def scalar(value, indent):
    """Emit a YAML scalar that never introduces a '...' document terminator.

    yaml.dump() on a bare string appends an explicit end-of-document marker,
    which is illegal mid-mapping. We strip that marker only, so trailing
    punctuation in the prose survives untouched.
    """
    text = str(value)
    if "\n" in text:
        pad = " " * indent
        return "|-\n" + "\n".join(pad + ln for ln in text.splitlines())
    dumped = yaml.dump(text, allow_unicode=True, default_flow_style=True, width=10 ** 6)
    lines = dumped.splitlines()
    if lines and lines[-1].strip() == "...":
        lines.pop()
    return "\n".join(lines).strip()


def quoted(text):
    """Single-quoted YAML scalar, never wrapped; internal quotes doubled.

    Inside a flow mapping the characters `?`, `:`, `,`, `{`, `}` and `#` all
    carry syntax, so a bare URL such as `.../forum?id=8s8K2UZGTZ` would be
    re-read as a key indicator. Quoting unconditionally removes the whole
    class of bug at no readability cost at this scale.
    """
    return "'" + str(text).replace("'", "''") + "'"


def mapping(value):
    """Flow-style mapping with every key and value quoted.

    Hand-rolled rather than yaml.dump(flow_style=True) because we also need to
    suppress line wrapping: long URLs must stay on one line.
    """
    inner = ", ".join(f"{quoted(k)}: {quoted(v)}" for k, v in value.items())
    return "{" + inner + "}"


def main():
    if not BAK.is_dir():
        sys.exit(f"missing v1 backup at {BAK}")

    # ---- load the v1 pool, keeping the first occurrence of each title
    pool, v1_sections = {}, {}
    for path in sorted(BAK.glob("*.yaml")):
        for block in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            sec = str(block["section"])
            v1_sections.setdefault(sec, [])
            for p in block["papers"] or []:
                rec = dict(
                    title=p["title"],
                    venue=p["venue"],
                    links=sort_links(p.get("links") or {}),
                    role=p["role"],
                    why=p["why"],
                )
                pool.setdefault(p["title"], rec)
                v1_sections[sec].append(p["title"])

    print(f"v1 pool: {len(pool)} unique works across {len(v1_sections)} sections")

    # ---- assemble the v2 sections
    sections = {}

    for sec, titles in THEORY.items():
        sections[sec] = [dict(pool[t]) for t in titles if t in pool]
        missing = [t for t in titles if t not in pool]
        if missing:
            print(f"  ! {sec}: not in v1 pool: {missing}")

    for sec in CARRY_OVER:
        if sec not in v1_sections:
            print(f"  ! {sec}: absent from v1")
            continue
        sections[sec] = [dict(pool[t]) for t in v1_sections[sec] if t in pool]

    for sec, papers in NEW_PAPERS.items():
        sections.setdefault(sec, [])
        have = {p["title"] for p in sections[sec]}
        for p in papers:
            if p["title"] not in have:
                sections[sec].append(dict(p))

    # ---- apply venue corrections, then the tier facet
    fixed, tiered = 0, {}
    for sec, papers in sections.items():
        for p in papers:
            t = p["title"]
            if t in VENUE_FIX:
                p["venue"], p["links"] = VENUE_FIX[t]
                fixed += 1
            tier = DECK_TIER.get((sec, t)) or p.get("tier") or ROLE_TIER.get(p["role"], "D")
            p["tier"] = tier
            tiered[tier] = tiered.get(tier, 0) + 1

    # ---- write one file per chapter
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.yaml"):
        old.unlink()

    def chap(sid):
        return "ch" + sid.split(".")[0]

    files = {}
    for sec in sorted(sections, key=lambda s: [int(x) for x in s.split(".")]):
        files.setdefault(chap(sec), []).append(sec)

    total = 0
    for cname, secs in sorted(files.items(), key=lambda kv: int(kv[0][2:])):
        body = [f"# Bibliography: {cname} — see notes/taxonomy.yaml for the structure.",
                "# Each paper carries two facets:",
                "#   role  — what job the citation does in the argument",
                "#   tier  — D primary / A adjacent / B boundary / V others' survey / S own",
                ""]
        for sec in secs:
            body.append(f'- section: "{sec}"')
            body.append("  papers:")
            for p in sections[sec]:
                body.append(f'    - title: {scalar(p["title"], 8)}')
                body.append(f'      venue: {scalar(p["venue"], 8)}')
                body.append(f'      links: {mapping(p["links"])}')
                body.append(f'      role: {p["role"]}')
                body.append(f'      tier: {p["tier"]}')
                body.append(f'      why: {scalar(p["why"], 8)}')
                total += 1
            body.append("")
        (OUT / f"{cname}.yaml").write_text("\n".join(body) + "\n", encoding="utf-8")

    print(f"wrote {len(files)} files, {total} entries")
    print(f"venue corrections applied: {fixed}")
    print("tier distribution:", dict(sorted(tiered.items())))


if __name__ == "__main__":
    main()
