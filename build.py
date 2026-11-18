#!/usr/bin/env python3
"""Build the README and the main figure from a single taxonomy source.

  notes/taxonomy.yaml   -> structure (levels, chapters, leaf sub-questions)
  notes/bib/*.yaml      -> papers (title, venue, links, role, why)

Outputs:
  README.md
  figures/figure1_taxonomy.svg

The figure's geometry is computed once in `layout()` and consumed by both the
SVG writer here and the PPTX writer in render.py, so the two can never drift.

Run:  python3 build.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
NOTES = ROOT / "notes"
BIB = NOTES / "bib"
FIGDIR = ROOT / "figures"

ROLE_ORDER = [
    "foundational", "representative", "contrast",
    "boundary", "benchmark", "positioning",
]
ROLE_BLURB = {
    "foundational": "Provides a definition, theoretical basis, or the original formulation.",
    "representative": "A representative method or technique — the technical workhorses.",
    "contrast": "A contrasting or competing result, often a negative one.",
    "boundary": "A boundary case, limitation, or null result.",
    "benchmark": "A measurement, benchmark, dataset, or metric.",
    "positioning": "A survey, position paper, or framing work.",
}

# Facet 2. The distinction the whole survey turns on: a paper that *studies*
# metacognition is not the same as a paper that supplies machinery metacognition
# can use, and neither is a paper that only probes where the mechanism breaks.
TIER_ORDER = ["D", "A", "B", "V", "S"]
TIER_BLURB = {
    "D": "**Primary metacognitive study.** Directly studies the stated "
         "metacognitive concept or mechanism. Only D-tier evidence may ground a "
         "positive claim about metacognition itself.",
    "A": "**Adjacent / enabling.** Supplies capability the metacognitive "
         "mechanism can be built on or measured with, without itself studying "
         "metacognition.",
    "B": "**Boundary.** Tests where the mechanism stops working — negative "
         "results, limitations, counterexamples.",
    "V": "**Other authors' survey, review, or position paper.** Maps a field "
         "rather than reporting a new result; cited for framing, not as "
         "evidence about metacognition.",
    "S": "**This survey's own proposal.** An analytical proposal, protocol, or "
         "accounting introduced here. Not a result claimed by any cited paper.",
}
LINK_ORDER = ["paper", "pdf", "acl", "proceedings", "code", "data", "repo", "book"]


# --------------------------------------------------------------------------- load

def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_all():
    tax = load(NOTES / "taxonomy.yaml")
    papers = {}
    for path in sorted(BIB.glob("*.yaml")):
        data = load(path)
        if not data:
            continue
        for block in data:
            sec = str(block["section"])
            if sec in papers:
                print(f"  ! duplicate section {sec} in {path.name}", file=sys.stderr)
            papers[sec] = block["papers"] or []
    return tax, papers


# --------------------------------------------------------------------------- helpers

def slug(text):
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text.strip())


def chap_heading(c):
    """The heading text, and the anchor GitHub derives from it."""
    return f"{c['num']}. {c['en']}"


def chap_anchor(c):
    return slug(chap_heading(c))


def sec_heading(s):
    return f"{s['id']} {s['en']}"


def sec_anchor(s):
    return slug(sec_heading(s))


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def wrap_words(text, width):
    """Greedy word wrap into at most `width` characters per line."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_w(s, size):
    """Rough advance width for Helvetica at `size` px."""
    return len(s) * size * 0.545


# --------------------------------------------------------------------------- README

def render_paper(p):
    links = p.get("links") or {}
    tier = p.get("tier", "D")
    parts = [f"**{p['title']}**", f"[{p['venue']}]"]
    for key in LINK_ORDER:
        if key in links:
            parts.append(f"[{key}]({links[key]})")
    for key, url in links.items():
        if key not in LINK_ORDER:
            parts.append(f"[{key}]({url})")
    return ("- " + " ".join(parts)
            + f"\n  - `{tier}` · `{p['role']}` — {p['why']}")


def build_readme(tax, papers):
    meta = tax["meta"]
    chapters = tax["chapters"]
    sections = tax["sections"]
    levels = {l["id"]: l for l in tax.get("levels", [])}
    by_chapter = {}
    for s in sections:
        by_chapter.setdefault(s["chapter"], []).append(s)

    # count citations, not distinct works: because a work can carry a different
    # tier at each place it is cited, "how many distinct works are tier D" is not
    # well defined once the facets are position-dependent.
    tier_counts = {}
    for plist in papers.values():
        for p in plist:
            t = p.get("tier", "D")
            tier_counts[t] = tier_counts.get(t, 0) + 1
    n_distinct = len({p["title"] for plist in papers.values() for p in plist})

    out = []
    out.append(f"# {meta['title']}\n")
    out.append(f"*{meta['subtitle']}*\n")
    out.append(
        "A curated reading list for a level-structured survey of metacognition in large "
        "language models. Unlike a flat paper list, every work carries two facets: the "
        "**logical role** it plays in the argument, and the **evidence tier** that says "
        "how far it can be trusted. The bibliography therefore doubles as an outline of "
        "the reasoning — and makes visible which claims rest on primary metacognitive "
        "evidence and which rest on adjacent work.\n"
    )

    n_papers = sum(len(v) for v in papers.values())
    n_sections = len(sections)
    out.append(
        f"**{n_papers} citations** of **{n_distinct} distinct works** across "
        f"**{n_sections} sub-questions**, grouped into **{len(chapters)} chapters** and "
        f"**{len(tax.get('levels', []))} level bands**.\n"
    )
    out.append(
        "| Tier | Citations | Meaning |\n|---|---|---|\n"
        + "\n".join(f"| `{t}` | {tier_counts.get(t, 0)} | {TIER_BLURB[t]} |"
                    for t in TIER_ORDER) + "\n"
    )

    out.append("## Overview\n")
    out.append("![Taxonomy of metacognition in LLMs](figures/figure1_taxonomy.svg)\n")
    out.append(
        "The figure is a nested taxonomy panel, read left to right. The masthead carries "
        "the **hierarchical relation** between the three levels — L0 cognitive execution, "
        "L1 monitoring and control, L2 learning — with information flowing up "
        "(`state / trace`, `outcomes / credit`) and intervention flowing down "
        "(`control action`, `policy update`). Below it, each **level band** is a container "
        "holding the chapter that belongs to that level; each **chapter card** branches "
        "into its **sub-questions**; and every sub-question carries a one-line citation "
        "string of its representative works, each prefixed by its evidence tier. The "
        "figure is generated from `notes/taxonomy.yaml`, the single source of truth, so "
        "each row below corresponds to exactly one node in the figure and structure can "
        "never drift.\n"
    )
    out.append(
        "Two claims the figure makes explicit, because they are the ones most easily "
        "smuggled past a reader: **evaluation is not a new cognitive level** — it spans "
        "levels, measuring signal validity at L0→L1, realized decision utility at L1→L0, "
        "and improvement gain at L2→L1; and **recursive self-improvement is a bounded "
        "extension, not Level 3**, since nothing in the current literature demonstrates a "
        "third level in the sense that L0, L1 and L2 are levels.\n"
    )
    out.append(
        "Editable sources: `figures/figure1_taxonomy.svg` (vector) and "
        "`figures/figure1_taxonomy.pptx` (native shapes) alongside the PNG.\n"
    )

    out.append("## How to read the two facets\n")
    out.append(
        "Every entry carries exactly one **role** and exactly one **tier**. Both are "
        "properties of the *citation*, not of the work: a paper that is primary "
        "metacognitive evidence in one sub-question can be adjacent or boundary "
        "evidence in another, and it is recorded as such at each place it appears. "
        "The role says what job the citation does; the tier says how much weight it "
        "can bear *here*. Roles:\n"
    )
    out.append("| Role | Meaning |")
    out.append("|---|---|")
    for role in ROLE_ORDER:
        out.append(f"| `{role}` | {ROLE_BLURB[role]} |")
    out.append("")
    out.append("Tiers:\n")
    out.append("| Tier | Meaning |")
    out.append("|---|---|")
    for tier in TIER_ORDER:
        out.append(f"| `{tier}` | {TIER_BLURB[tier]} |")
    out.append("")
    out.append(
        "> **Classification rule.** `D` directly studies the stated metacognitive "
        "concept/mechanism; `A` is adjacent/enabling; `B` tests a boundary; `V` is "
        "another author's survey or position paper, cited for framing; `S` is this "
        "survey's own analytical proposal (not a result claimed by cited papers).\n"
    )

    out.append("## Level framework\n")
    out.append("| Level | Description |")
    out.append("|---|---|")
    for lv in tax.get("levels", []):
        out.append(f"| **{lv['en']}** | {lv['desc']} |")
    out.append("")

    rel = tax.get("relation") or {}
    if rel:
        out.append("## Hierarchical relation\n")
        out.append(f"*{rel.get('note', '')}*\n")
        out.append(f"**{rel.get('statement', '')}**\n")
        for e in rel.get("edges", []):
            out.append(f"- `{e.get('label', e)}`")
        out.append("")
        out.append(f"> {rel.get('caveat', '')}\n")

    out.append("## Table of contents\n")
    for c in chapters:
        lv = levels.get(c["level"], {})
        band = f" · {lv['en']}" if lv else ""
        out.append(f"- [**{chap_heading(c)}**](#{chap_anchor(c)}){band}")
        out.append("")
        for s in by_chapter.get(c["id"], []):
            out.append(f"  - [{s['en']}](#{sec_anchor(s)})")
        out.append("")

    for c in chapters:
        lv = levels.get(c["level"], {})
        out.append(f"## {chap_heading(c)}")
        out.append("")
        if lv:
            out.append(f"*{lv['en']} — {lv['desc']}*\n")
        if c.get("tag"):
            out.append(f"*{c['tag']}*\n")
        out.append(f"[](#{chap_anchor(c)})\n")
        for s in by_chapter.get(c["id"], []):
            out.append(f"### {sec_heading(s)}")
            out.append("")
            out.append(f"*{s.get('question', '')}*\n")
            out.append(f"[](#{sec_anchor(s)})\n")
            plist = papers.get(s["id"], [])
            if not plist:
                out.append("_No entries yet._\n")
                continue
            plist = sorted(plist, key=lambda p: (
                p.get("deck_rank", 999),
                TIER_ORDER.index(p.get("tier", "D")) if p.get("tier") in TIER_ORDER else 9,
            ))
            for p in plist:
                out.append(render_paper(p))
                out.append("")

    out.append("## Reference\n")
    out.append("```bibtex")
    out.append("@misc{metacognitionLLMs2026,")
    out.append(f"  title  = {{{meta['title']}: {meta['subtitle']}}},")
    out.append("  author = {stevie1023},")
    out.append("  year   = {2026},")
    out.append("  note   = {Companion reading list}")
    out.append("}")
    out.append("```\n")

    out.append("## Contributing\n")
    out.append(
        "The taxonomy and this list share a single source of truth, so structure can "
        "never drift between the figure and the entries.\n"
    )
    out.append("```")
    out.append("notes/taxonomy.yaml     structure: levels, chapters, sub-questions, relation")
    out.append("notes/bib/ch*.yaml      papers: title, venue, links, role, tier, why")
    out.append("        |")
    out.append("        v")
    out.append("     build.py    ->  README.md, figures/figure1_taxonomy.svg")
    out.append("     render.py   ->  figures/figure1_taxonomy.png, .pptx")
    out.append("```\n")
    out.append(
        "Do not edit `README.md` directly — it is generated. To add a work, add it to "
        "the relevant `notes/bib/ch*.yaml` with a `role`, a `tier` and a one-line `why`, "
        "then run:\n"
    )
    out.append("```sh")
    out.append("python3 build.py     # README + SVG")
    out.append("python3 render.py    # PNG + editable PPTX")
    out.append("```\n")
    out.append("## Status\n")
    out.append(
        "Draft. Papers were individually verified against arXiv, ACL Anthology, "
        "OpenReview, DBLP, PMLR, NeurIPS proceedings, Nature, and publisher DOIs "
        "during compilation. This revision (v0.2) reclassifies the structure and the "
        "citations against a corrected taxonomy: eight level bands instead of seven, "
        "an explicit hierarchical-relation diagram, and the evidence-tier facet "
        "(`D`/`A`/`B`/`S`) applied to every entry.\n"
    )
    out.append("## License\n")
    out.append("Released under the MIT License. See `LICENSE`.\n")

    return "\n".join(out)


# --------------------------------------------------------------------------- figure
#
# Publication-style nested taxonomy panel, read left to right:
#
#   [ level gutter |  chapter card  |  sub-question rows + representative works ]
#   \_______________________ band container ___________________________________/
#
# Containment carries the hierarchy: a band container holds the chapters that
# belong to that level; a chapter card carries a stub into a leaf group; each
# leaf row pairs its sub-question with a compact citation string. The reference
# taxonomy figures in the field use exactly this grammar — nested rounded
# panels with dense citation text at the right — which reads far faster than a
# matrix of full-width stripes.
#
# Geometry is computed once here and rendered by both the SVG writer below and
# the PPTX writer in render.py.

FIG_CH_LABEL = {
    "ch1": "1 · Foundations",
    "ch2": "2 · Hierarchical Framework",
    "ch3": "3 · Metacognitive Monitoring",
    "ch4": "4 · Decision & Control",
    "ch5": "5 · Evaluation of Utility",
    "ch6": "6 · Meta-Regulation",
    "ch7": "7 · Toward RSI",
    "ch8": "8 · Open Challenges",
}

FIG_CH_BAND = {
    "ch1": "theory", "ch2": "framework", "ch3": "represent",
    "ch4": "regulate", "ch5": "evaluation", "ch6": "learn",
    "ch7": "recursive", "ch8": "gaps",
}

# Palette key per band, in chapter order. Eight bands, one per chapter, in the
# corrected taxonomy's own words; the names and descriptions are read from
# notes/taxonomy.yaml so the figure and the README cannot disagree. Evaluation
# is a band rather than a level, and its gloss says so out loud: the deck is
# explicit that it spans levels instead of adding one.
FIG_BAND_PAL = ["slate", "teal", "blue", "indigo", "amber", "violet", "plum", "rose"]

#   rail      panel      border     title      body
FIG_PALETTE = {
    "slate":  ("#7E7A6B", "#F1F0EA", "#DAD5C9", "#33312B", "#6E6A60"),
    "teal":   ("#3E8A87", "#E9F5F4", "#C4E0DE", "#1D5350", "#568480"),
    "blue":   ("#3B7DC4", "#EAF3FC", "#C7DCF0", "#1B4F79", "#557896"),
    "indigo": ("#4056A8", "#ECF0FA", "#C6CFEA", "#25326E", "#5A6791"),
    "amber":  ("#B78A3C", "#FBF4E4", "#EBDABA", "#6F5314", "#8A7240"),
    "violet": ("#6A5AC4", "#F1EFFC", "#D5CFEF", "#3A2E82", "#6A5CAC"),
    "plum":   ("#94407E", "#FAEDF6", "#EBCDE2", "#5E2050", "#8E5A80"),
    "rose":   ("#B2524D", "#FCEDEC", "#EFD2D1", "#752724", "#985A56"),
}

FIG_INK = "#26251F"
FIG_MUTE = "#9B978C"

# geometry (px; 2x supersampled on PNG export)
FIG_W = 2380
MAST_H = 340          # masthead + relation strip; bands begin here
LEAF_ROW = 41
CH_GAP = 12
CH_H = 40
PAD_Y = 9           # padding above/below the leaf rows inside a group

RAIL_X = 62
RAIL_W = 5
LVL_TXT_X = 84

CH_X, CH_W = 404, 292
DOT_X = 742
LEAF_X = 758
WORKS_X = 1188

BAND_X = 44
BAND_W = FIG_W - 88
LEFT_INSET = 18
RIGHT_INSET = 44
CIT_BUDGET = BAND_X + BAND_W - RIGHT_INSET - WORKS_X   # px for one citation line
CIT_MIN_LABELS = 2                   # never fall below this many labels

# ---- hierarchical relation strip (deck "HIERARCHICAL RELATION", analytical
# synthesis). Nodes are placed from notes/taxonomy.yaml; adjacent nodes carry
# two reciprocal edges: information flows up, intervention flows down.
REL_LABEL_Y = 124
REL_TOP, REL_BOT = 106, 292          # container extent
REL_NODE_Y, REL_NODE_H = 146, 68
REL_STMT_Y = 262
REL_PAD = 25                         # inset of the node row from the container
REL_GAP = 82                         # horizontal gap between adjacent nodes
REL_NODE_PAL = {"L0": "slate", "L1": "blue", "L2": "violet"}
REL_STATEMENT = (
    "EVALUATION SPANS LEVELS:   signal validity   |   realized decision utility   "
    "|   compute-matched \u0394U1 (L1\u2192L0)   |   improvement gain \u0394U2 (L2\u2192L1)"
    "      \u2022      RSI is a recursive extension, not Level 3."
)


# --------------------------------------------------------------------------- citations

FIG_ROLE_RANK = ["representative", "foundational", "benchmark",
                 "contrast", "boundary", "positioning"]

# Evidence tiers, in the deck's own words. The tier prefix is printed on every
# citation label because the difference between "a paper that studies
# metacognition" and "a paper that supplies machinery metacognition can use" is
# the single most load-bearing distinction in the survey.
FIG_TIER_ORDER = ["D", "A", "B", "V", "S"]
FIG_TIER_RANK = {"D": 0, "A": 1, "B": 2, "V": 3, "S": 4}
FIG_TIER_BLURB = {
    "D": "primary metacognitive study",
    "A": "adjacent / enabling",
    "B": "boundary",
    "V": "other authors' survey",
    "S": "this survey's own proposal",
}

VENUE_ABBR = [
    ("Journal of Experimental Psychology: Learning, Memory, and Cognition", "JEP:LMC"),
    ("Psychology of Learning and Motivation", "Psych. Learn. Motiv."),
    ("American Psychologist", "Am. Psychol."),
    ("Psychological Review", "Psychol. Rev."),
    ("Trends in Cognitive Sciences", "TiCS"),
    ("Annual Review of Psychology", "Annu. Rev. Psychol."),
    ("Annual Review of Neuroscience", "Annu. Rev. Neurosci."),
    ("Behavioral and Brain Sciences", "Behav. Brain Sci."),
    ("Frontiers in Human Neuroscience", "Front. Hum. Neurosci."),
    ("Neuroscience of Consciousness", "Neurosci. Conscious."),
    ("Journal of Logic and Computation", "J. Log. Comput."),
    ("Nature Machine Intelligence", "Nat. Mach. Intell."),
    ("Artificial Intelligence", "Artif. Intell."),
    ("Foundations and Trends in Machine Learning", "FnT ML"),
]

FIG_GENERIC_PREFIX = [
    r"^On the\s+", r"^Toward[s]?\s+", r"^Do(es)? NOT\s+", r"^Do(es)?\s+",
    r"^Can\s+", r"^Is\s+", r"^Are\s+", r"^What\s+", r"^How\s+", r"^Why\s+",
    r"^When\s+", r"^Where\s+", r"^Large Language Models\s+", r"^LLMs?\s+",
    r"^Language Models\s+", r"^A Survey of\s+", r"^An?\s+", r"^The\s+",
]
FIG_BAD_TAIL = re.compile(
    r"\b(and|of|the|for|with|in|on|to|a|an|is|are|its|their|from|by|as)$", re.I)
FIG_STOP_PREFIX = {"a survey", "position", "metacognition", "metacognitive",
                   "metamemory", "a position", "metareasoning"}

# Titles that do not reduce to a self-evident label by rule alone. Every entry
# is the name the survey body itself uses for the work, so the figure and the
# prose stay legible together.
FIG_LABEL_OVERRIDE = {
    # This survey's own proposals. short_title() would truncate all three
    # "Survey …" proposals to the same string, leaving 5.3 and 5.4
    # indistinguishable in the figure; name what each one proposes instead.
    "Survey protocol: compare Q estimates to outcomes":
        "Protocol: Q vs. realized gain",
    "Survey protocol: matched-state action ablations":
        "Protocol: matched-state ablations",
    "Survey accounting: ΔU1 (L1→L0) and ΔU2 (L2→L1)":
        "Accounting: ΔU1 / ΔU2",
    "Intervention-based value-of-information tests":
        "Protocol: intervention-based VoI tests",
    "Metacognition and Cognitive Monitoring: A New Area of Cognitive-Developmental Inquiry":
        "Metacognition",
    "Metacognition in Computation: A Selected Research Review": "Metacognition in Computation",
    "Metacognition and Confidence: A Review and Synthesis": "Metacognition and Confidence",
    "Metacognition and Uncertainty Communication in Humans and Large Language Models":
        "Metacognition and Uncertainty Communication",
    "Common Computations for Metacognition and Meta-Metacognition": "Common Computations",
    "Large Language Models as Tool Makers": "LLMs as Tool Makers",
    "Large Language Models as Optimizers (OPRO)": "OPRO",
    "s1: Simple Test-Time Scaling": "s1",
    "Metareasoning: Thinking about Thinking": "Metareasoning",
    "How to Measure Metacognition": "Measuring Metacognition",
    "Toward a Rational and Mechanistic Account of Mental Effort": "Mental Effort",
    "Language Models Are Capable of Metacognitive Monitoring and Control of Their Internal Activations":
        "Monitoring of Internal Activations",
    "LLMs Have Intrinsic Meta-Cognition, but Need a Good Lens": "Intrinsic Meta-Cognition",
    "Do Large Language Models Know How Much They Know?": "Know How Much They Know",
    "Do Large Language Models Know What They Are Capable Of?": "Capability Awareness",
    "Do Large Language Models Know What They Don't Know? (SelfAware)": "SelfAware",
    "What Large Language Models Know and What People Think They Know":
        "What People Think They Know",
    "Large Language Models Cannot Self-Correct Reasoning Yet": "Cannot Self-Correct Yet",
    "Language Models (Mostly) Know What They Know": "(Mostly) Know What They Know",
    "Language Models Fail to Introspect About Their Knowledge of Language":
        "Fail to Introspect Language Knowledge",
    "LLM Evaluators Recognize and Favor Their Own Generations": "Evaluators Favor Own Output",
    "Emergent Introspective Awareness in Large Language Models":
        "Emergent Introspective Awareness",
    "Know Your Limits: A Survey of Abstention in Large Language Models": "Abstention Survey",
    "Looking Inward: Language Models Can Learn About Themselves by Introspection":
        "Looking Inward",
    "On the Statistical Limits of Self-Improving Agents": "Statistical Limits",
    "Risks from Learned Optimization in Advanced Machine Learning Systems":
        "Risks from Learned Optimization",
    "The Danger of Overthinking: Examining the Reasoning-Action Dilemma in Agentic Tasks":
        "Danger of Overthinking",
    "The Internal State of an LLM Knows When It's Lying": "Internal State Knows It's Lying",
    "To CoT or Not to CoT? Chain-of-Thought Helps Mainly on Math and Symbolic Reasoning":
        "To CoT or Not to CoT?",
    "Process Reward Models That Think (ThinkPRM)": "ThinkPRM",
    "Training Language Models to Self-Correct via Reinforcement Learning (SCoRe)": "SCoRe",
    "Scaling LLM Test-Time Compute Optimally Can Be More Effective than Scaling Model Parameters":
        "Test-Time Compute vs. Parameters",
    "Self-Taught Optimizer (STOP): Recursively Self-Improving Code Generation": "STOP",
    "Beyond Meta-Reasoning: Metacognitive Consolidation for Self-Improving LLM Reasoning (MC-squared)":
        "MC\u00b2 Consolidation",
    "A Self-Improving Coding Agent (SICA)": "SICA",
    "A Signal Detection Theoretic Approach for Estimating Metacognitive Sensitivity from Confidence Ratings":
        "Meta-d\u2032 / Signal Detection",
    "AI Models Collapse When Trained on Recursively Generated Data": "Model Collapse",
    "Automated Design of Agentic Systems (Meta Agent Search)": "Meta Agent Search",
    "Discovering Latent Knowledge in Language Models Without Supervision (CCS)": "CCS",
    "Calibrated Language Models Must Hallucinate": "Calibration Implies Hallucination",
    "G\u00f6del Machines: Fully Self-Referential Optimal Universal Self-Improvers":
        "G\u00f6del Machines",
    "G\u00f6del Agent: A Self-Referential Agent Framework for Recursive Self-Improvement":
        "G\u00f6del Agent",
    "Inference Scaling Laws: An Empirical Analysis of Compute-Optimal Inference for Problem-Solving with Language Models":
        "Inference Scaling Laws",
    "Least-to-Most Prompting Enables Complex Reasoning in Large Language Models":
        "Least-to-Most Prompting",
    "Teaching Large Language Models to Self-Debug": "Self-Debug",
    "Position: LLMs Need a Bayesian Meta-Reasoning Framework": "Bayesian Meta-Reasoning",
    "Position: Truly Self-Improving Agents Require Intrinsic Metacognitive Learning":
        "Truly Self-Improving Agents",
    "Do NOT Think That Much for 2+3=? On the Overthinking of o1-Like LLMs":
        "Overthinking of o1-Like LLMs",
    "Self-Rewarding Language Models": "Self-Rewarding LMs",
    "Meta-Rewarding Language Models: Self-Improving Alignment with LLM-as-a-Meta-Judge":
        "Meta-Rewarding LMs",
    "Metamemory: A Theoretical Framework and New Findings": "Metamemory",
    "Does It Make Sense to Speak of Introspection in Large Language Models?":
        "Introspection in LLMs?",
    "How Overconfidence in Initial Choices and Underconfidence Under Criticism Modulate Change of Mind in Large Language Models":
        "Overconfidence in Initial Choices",
    # ---- labels that the generic reducer truncated mid-phrase. Each is the
    # name the deck or the survey prose uses, so figure and text agree.
    "Do I Know This Entity? Knowledge Awareness and Hallucinations in Language Models":
        "Do I Know This Entity?",
    "Teaching Models to Express Their Uncertainty in Words":
        "Express Uncertainty in Words",
    "Reducing Conversational Agents' Overconfidence Through Linguistic Calibration":
        "Linguistic Calibration",
    "Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from LLMs":
        "Just Ask for Calibration",
    "Knowledge of Knowledge: Exploring Known-Unknowns Uncertainty (KUQ)":
        "Knowledge of Knowledge",
    "Reasoning Models Generate Societies of Thought": "Societies of Thought",
    "Overclocking LLM Reasoning: Monitoring and Controlling Thinking Path Lengths":
        "Overclocking Reasoning",
    "Dynamic Early Exit in Reasoning Models": "Dynamic Early Exit",
    "Entropy After the Thinking Marker for Reasoning Model Early Exiting":
        "Entropy After Thinking",
    "Phi-Decoding: Adaptive Foresight Sampling for Balanced Inference-Time Exploration and Exploitation":
        "Phi-Decoding",
    "Adaptive Inference-Time Compute: LLMs Can Predict if They Can Do Better, Even Mid-Generation":
        "Adaptive Inference-Time Compute",
    "GLoRe: When, Where, and How to Improve LLM Reasoning via Global and Local Refinements":
        "GLoRe",
    "Uncertainty of Thoughts: Uncertainty-Aware Planning Enhances Information Seeking in LLMs":
        "Uncertainty of Thoughts",
    "Learning When to Plan: Efficiently Allocating Test-Time Compute for LLM Agents":
        "Learning When to Plan",
    "Reasoning in Token Economies: Budget-Aware Evaluation of LLM Reasoning Strategies":
        "Reasoning in Token Economies",
    "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models":
        "Plan-and-Solve",
    "Graph of Thoughts: Solving Elaborate Problems with Large Language Models":
        "Graph of Thoughts",
    "Maieutic Prompting: Logically Consistent Reasoning with Recursive Explanations":
        "Maieutic Prompting",
    "Automatic Chain of Thought Prompting in Large Language Models":
        "Auto CoT",
    "HuggingGPT: Solving AI Tasks with ChatGPT and its Friends in Hugging Face":
        "HuggingGPT",
    "Chain of Code: Reasoning with a Language Model-Augmented Code Emulator":
        "Chain of Code",
    "Active Retrieval Augmented Generation (FLARE)": "FLARE",
    "Recursive Introspection: Teaching Language Model Agents How to Self-Improve":
        "Recursive Introspection",
    "Improving Factuality and Reasoning in Language Models through Multiagent Debate":
        "Multiagent Debate",
    "Token-Budget-Aware LLM Reasoning": "Token-Budget-Aware Reasoning",
    "Scaling LLM Inference with Optimized Sample Compute Allocation":
        "Optimized Sample Allocation",
    "Compressed Chain of Thought: Efficient Reasoning Through Dense Representations":
        "Compressed CoT",
    "AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions":
        "AbstentionBench",
    "SELF-[IN]CORRECT: LLMs Struggle with Discriminating Self-Generated Responses":
        "SELF-[IN]CORRECT",
    "On the Self-Verification Limitations of Large Language Models on Reasoning and Planning Tasks":
        "Self-Verification Limits",
    "When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs":
        "When Can LLMs Self-Correct?",
    "LLMs Know More Than They Show: On the Intrinsic Representation of LLM Hallucinations":
        "Know More Than They Show",
    "Process-Based Self-Rewarding Language Models": "Process-Based Self-Rewarding",
    "Metacognitive Capabilities of LLMs: An Exploration in Mathematical Problem Solving":
        "Mathematical Problem Solving",
    "Reliable Weak-to-Strong Monitoring of LLM Agents": "Weak-to-Strong Monitoring",
    "Metacognition and Uncertainty Communication in Humans and Large Language Models":
        "Uncertainty Communication",
    "Voyager: An Open-Ended Embodied Agent with Large Language Models": "Voyager",
    "TextGrad: Automatic Differentiation via Text": "TextGrad",
    "DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines":
        "DSPy",
    "Large Language Models as Optimizers (OPRO)": "OPRO",
    "Agent Workflow Memory": "Agent Workflow Memory",
    "Buffer of Thoughts: Thought-Augmented Reasoning": "Buffer of Thoughts",
    "Robust Agents Learn Causal World Models": "Causal World Models",
    "Self-Recognition in Language Models": "Self-Recognition",
    "Emergent Introspective Awareness in Large Language Models":
        "Emergent Introspective Awareness",
    "Reasoning Models Generate Societies of Thought": "Societies of Thought",
    "AI Control: Improving Safety Despite Intentional Subversion": "AI Control",
    "Weak-to-Strong Generalization: Eliciting Strong Capabilities with Weak Supervision":
        "Weak-to-Strong",
    "AI Safety via Debate": "AI Safety via Debate",
    "Measuring Progress on Scalable Oversight for Large Language Models":
        "Scalable Oversight",
    "Constitutional AI: Harmlessness from AI Feedback": "Constitutional AI",
    "Sleeper Agents: Training Deceptive LLMs That Persist Through Safety Training":
        "Sleeper Agents",
    "Alignment Faking in Large Language Models": "Alignment Faking",
    "Sycophancy to Subterfuge: Investigating Reward-Tampering in Large Language Models":
        "Reward-Tampering",
    "AI Awareness": "AI Awareness",
    "Recursive Self-Improvement in AI": "RSI in AI",
    "Stop Overthinking: A Survey on Efficient Reasoning for Large Language Models":
        "Efficient Reasoning Survey",
    "A Survey of Confidence Estimation and Calibration in Large Language Models":
        "Confidence & Calibration Survey",
    "A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve":
        "Self-Evolving Agents Survey",
    "Self-Improvement in Multimodal Large Language Models: A Survey":
        "Multimodal Self-Improvement Survey",
    "Cognitive Architectures for Language Agents (CoALA)": "CoALA",
    "Generative Agents: Interactive Simulacra of Human Behavior": "Generative Agents",
    "STaR: Bootstrapping Reasoning with Reasoning": "STaR",
    "Evidence for Limited Metacognition in Large Language Models":
        "Evidence for Limited Metacognition",
    "Decoupling Metacognition from Cognition: A Framework for Evaluating Metacognition in LLMs":
        "Decoupling Metacognition",
    "LLMs Have Intrinsic Meta-Cognition, but Need a Good Lens":
        "Intrinsic Meta-Cognition",
}


def short_venue(venue):
    v = str(venue).strip()
    for long, short in VENUE_ABBR:
        if v.startswith(long):
            rest = v[len(long):].strip()
            return f"{short} {rest}".strip()
    return v


def short_title(title):
    """Compact citation label for the figure, e.g. 'Tree of Thoughts'."""
    t = str(title).strip()
    if t in FIG_LABEL_OVERRIDE:
        return FIG_LABEL_OVERRIDE[t]
    m = re.match(r"^([A-Za-z][A-Za-z0-9\-.'+* ]{0,26}?)\s*[:(]", t)
    if m:
        cand = m.group(1).strip()
        if 1 <= len(cand.split()) <= 4 and cand.lower() not in FIG_STOP_PREFIX:
            return cand
    s = t
    for g in FIG_GENERIC_PREFIX:
        s2 = re.sub(g, "", s, flags=re.I)
        if s2 != s and len(s2.split()) >= 2:
            s = s2
            break
    out = []
    for w in s.split():
        if out and len(" ".join(out + [w])) > 26:
            break
        out.append(w)
        if len(out) >= 4:
            break
    cand = re.sub(r"[\s,;:]+$", "", " ".join(out))
    cand = FIG_BAD_TAIL.sub("", cand).strip()
    return cand or t.split()[0]


def leaf_citations(plist, budget_px=CIT_BUDGET, size=9.5):
    """One compact single-line 'D  Name (Venue), …' string per leaf.

    The reference taxonomies list representative works as one dense line beside
    each sub-question. We fit as many labels as the column allows, measured
    with the same advance-width estimate the renderers use, then append 'etc.'
    so the reader knows the list is a selection rather than the whole set.

    Each label is prefixed with its evidence tier (D/A/B/S). Works the corrected
    deck names for this leaf come first, in the deck's own order, so the figure's
    citation line reproduces the deck's column rather than inventing an order;
    the remaining works follow, strongest tier first.
    """
    if not plist:
        return ""
    ranked = sorted(
        plist,
        key=lambda p: (
            p.get("deck_rank", 999),
            FIG_TIER_RANK.get(p.get("tier", "D"), 9),
            FIG_ROLE_RANK.index(p["role"])
            if p.get("role") in FIG_ROLE_RANK else 9,
        ),
    )
    labels, used = [], set()
    for p in ranked:
        name = short_title(p["title"])
        key = name.lower()
        if key in used:
            continue
        tier = p.get("tier", "D")
        # An S entry is this survey's own proposal; its "venue" is a self-
        # reference, so appending it would render "This survey (this survey
        # (proposal))". Name the proposal only.
        if tier == "S" or str(p.get("venue", "")).strip().lower().startswith("this survey"):
            labels.append(f"{tier}  {name}")
        else:
            labels.append(f"{tier}  {name} ({short_venue(p['venue'])})")
        used.add(key)
    if not labels:
        return ""

    # grow the selection while it still fits the column on one line
    chosen = [labels[0]]
    for cand in labels[1:]:
        trial = chosen + [cand]
        tail = ", etc." if len(trial) < len(ranked) else ""
        if text_w(", ".join(trial) + tail, size) <= budget_px:
            chosen = trial
        else:
            break
    if len(chosen) < CIT_MIN_LABELS and len(labels) > 1:
        chosen = labels[:CIT_MIN_LABELS]
    text = ", ".join(chosen)
    if len(chosen) < len(ranked):
        text += ", etc."
    # hard trim, in case even the minimum overshoots the column
    if text_w(text, size) > budget_px:
        while chosen and text_w(", ".join(chosen) + " …, etc.", size) > budget_px:
            chosen.pop()
        text = ", ".join(chosen) + (" …, etc." if chosen else "")
    return text


# --------------------------------------------------------------------------- layout

def layout(tax, papers=None):
    """Compute every primitive of the figure.

    Returns panels (nested containers), boxes, texts and conns — consumed by
    both the SVG writer here and the PPTX writer in render.py.
    """
    papers = papers or {}
    chapters = tax["chapters"]
    by_chapter = {}
    for s in tax["sections"]:
        by_chapter.setdefault(s["chapter"], []).append(s)

    panels, boxes, texts, conns, arrows = [], [], [], [], []

    # ---- masthead + hierarchical relation strip
    rel = tax.get("relation") or {}
    rel_label = rel.get("title", "HIERARCHICAL RELATION")
    rel_note = rel.get("note", "analytical synthesis")

    panels.append(dict(x=BAND_X, y=REL_TOP, w=BAND_W, h=REL_BOT - REL_TOP,
                       fill="#FAFAF7", stroke="#E2DFD6", rx=13))

    texts.append(dict(x=BAND_X + REL_PAD, y=REL_LABEL_Y, s=rel_label,
                      size=11, color="#5A564B", weight=700, anchor="start"))
    texts.append(dict(x=BAND_X + REL_PAD + text_w(rel_label, 11) + 14,
                      y=REL_LABEL_Y, s=f"({rel_note})", size=9.5,
                      color=FIG_MUTE, weight=400, anchor="start"))

    # Nodes are laid out by weight, not equally: L1 carries the longest label
    # and the most machinery, so it gets the widest card.
    rel_nodes = rel.get("nodes") or []
    if rel_nodes:
        weights = {"L0": 0.62, "L1": 1.0, "L2": 0.55}
        span = BAND_W - 2 * REL_PAD
        avail = span - REL_GAP * (len(rel_nodes) - 1)
        wsum = sum(weights.get(n["id"], 0.7) for n in rel_nodes)
        npos, cx = {}, BAND_X + REL_PAD
        for n in rel_nodes:
            nw = avail * weights.get(n["id"], 0.7) / wsum
            npos[n["id"]] = (cx, nw)
            cx += nw + REL_GAP

        for n in rel_nodes:
            nx, nw = npos[n["id"]]
            _pal = REL_NODE_PAL.get(n["id"], "slate")
            rail, _pn, _bd, tcol, scol = FIG_PALETTE[_pal]
            boxes.append(dict(kind="box", x=nx, y=REL_NODE_Y, w=nw, h=REL_NODE_H,
                              fill="#FFFFFF", stroke="#DAD5C9", rx=10))
            boxes.append(dict(kind="bar", x=nx + 1, y=REL_NODE_Y + 13, w=4,
                              h=REL_NODE_H - 26, fill=rail, stroke=None, rx=2))
            texts.append(dict(x=nx + 20, y=REL_NODE_Y + 30, s=n["name"],
                              size=13.5, color=tcol, weight=600, anchor="start"))
            texts.append(dict(x=nx + 20, y=REL_NODE_Y + 51, s=n["desc"],
                              size=10.5, color=scol, weight=400, anchor="start"))

        # reciprocal edges: the up-edge sits above the down-edge on every pair
        for a, b in zip(rel_nodes, rel_nodes[1:]):
            ax, aw = npos[a["id"]]
            bx, _bw = npos[b["id"]]
            gap_x1, gap_x2 = ax + aw, bx
            mid = (gap_x1 + gap_x2) / 2
            up = next((e for e in (rel.get("edges") or [])
                       if e.get("from") == a["id"] and e.get("to") == b["id"]), None)
            down = next((e for e in (rel.get("edges") or [])
                         if e.get("from") == b["id"] and e.get("to") == a["id"]), None)
            if up:
                arrows.append(dict(x1=gap_x1, x2=gap_x2, y=160, color="#9A9488", fwd=True))
                texts.append(dict(x=mid, y=151, s=up.get("label", ""), size=9.5,
                                  color="#6E6A60", weight=500, anchor="middle"))
            if down:
                arrows.append(dict(x1=gap_x2, x2=gap_x1, y=216, color="#B9B2A2", fwd=False))
                texts.append(dict(x=mid, y=207, s=down.get("label", ""), size=9.5,
                                  color="#6E6A60", weight=500, anchor="middle"))

    stmt_y = REL_STMT_Y
    texts.append(dict(x=BAND_X + REL_PAD, y=stmt_y, s=rel.get("statement", REL_STATEMENT),
                      size=10, color="#5A564B", weight=500, anchor="start"))
    if rel.get("caveat"):
        texts.append(dict(x=BAND_X + REL_PAD, y=stmt_y + 20, s=rel["caveat"],
                          size=9.5, color="#8A7240", weight=600, anchor="start"))

    # ---- vertical placement of chapter blocks
    y = MAST_H
    placed = []
    for i, ch in enumerate(chapters):
        leaves = by_chapter.get(ch["id"], [])
        h = max(len(leaves), 1) * LEAF_ROW + 2 * PAD_Y
        placed.append({"ch": ch, "leaves": leaves, "y": y, "h": h})
        y += h + (CH_GAP if i < len(chapters) - 1 else 0)
    content_bottom = y

    # ---- group chapters into contiguous level bands.
    #
    # In the corrected taxonomy each chapter owns its own band, so this is 1:1
    # — but the grouping stays general in case two chapters ever share a level.
    levels = {l["id"]: l for l in tax.get("levels", [])}
    bands = []
    for p in placed:
        bid = FIG_CH_BAND[p["ch"]["id"]]
        if bands and bands[-1]["id"] == bid:
            bands[-1]["items"].append(p)
        else:
            bands.append({"id": bid, "items": [p]})
    if len(bands) != len(FIG_BAND_PAL):
        raise SystemExit(
            f"figure bands drifted: {len(bands)} runs vs {len(FIG_BAND_PAL)} palettes"
        )
    for b, pal in zip(bands, FIG_BAND_PAL):
        lv = levels.get(b["items"][0]["ch"]["level"], {})
        b["name"] = lv.get("short") or lv.get("en") or b["id"].upper()
        b["desc"] = lv.get("desc", "")
        b["pal"] = pal
    band_pal = {b["id"]: b["pal"] for b in bands}

    for b in bands:
        y0 = b["items"][0]["y"] - PAD_Y - 8
        y1 = b["items"][-1]["y"] + b["items"][-1]["h"] + 8
        b["y0"], b["y1"] = y0, y1
        rail, panel, border, tcol, scol = FIG_PALETTE[b["pal"]]

        # the band container — the outermost nested panel
        panels.append(dict(x=BAND_X, y=y0, w=BAND_W, h=y1 - y0,
                           fill=panel, stroke=border, rx=15))
        # saturated rail marking band identity
        boxes.append(dict(kind="bar", x=RAIL_X, y=y0 + 14, w=RAIL_W,
                          h=(y1 - y0) - 28, fill=rail, stroke=None, rx=2.5))

        # level name + description, vertically centred in the gutter.
        # The abbreviated band names run long ("CROSS-LEVEL EVAL"), so wrap on
        # character count sized to the gutter rather than a fixed word width.
        name_lines = wrap_words(b["name"], 26)
        desc_lines = wrap_words(b["desc"], 30)
        block = len(name_lines) * 17 + 6 + len(desc_lines) * 14
        ty = (y0 + y1) / 2 - block / 2 + 13
        for i, ln in enumerate(name_lines):
            texts.append(dict(x=LVL_TXT_X, y=ty + i * 17, s=ln, size=12.5,
                              color=tcol, weight=700, anchor="start"))
        dy = ty + (len(name_lines) - 1) * 17 + 6 + 11
        for i, ln in enumerate(desc_lines):
            texts.append(dict(x=LVL_TXT_X, y=dy + i * 14, s=ln, size=9.5,
                              color=scol, weight=400, anchor="start"))

    # ---- chapters, leaf groups, leaf rows
    for p in placed:
        ch, leaves = p["ch"], p["leaves"]
        y0, h = p["y"], p["h"]
        bid = FIG_CH_BAND[ch["id"]]
        pal = band_pal[bid]
        rail, panel, border, tcol, scol = FIG_PALETTE[pal]

        cy = y0 + h / 2

        # leaf group: an inner nested panel inset from the band container, so
        # the containment (band > chapter rows) is visible rather than implied
        panels.append(dict(x=LEAF_X - 26, y=y0,
                           w=BAND_X + BAND_W - RIGHT_INSET - (LEAF_X - 26),
                           h=h, fill="#FFFFFF", stroke=border, rx=12))
        # short stub from the chapter card into its leaf group
        conns.append(dict(x1=CH_X + CH_W, y1=cy, x2=LEAF_X - 26, y2=cy,
                          color=border))

        # chapter card
        boxes.append(dict(kind="box", x=CH_X, y=cy - CH_H / 2, w=CH_W, h=CH_H,
                          fill="#FFFFFF", stroke=border, rx=9))
        boxes.append(dict(kind="bar", x=CH_X + 1, y=cy - CH_H / 2 + 9,
                          w=3.5, h=CH_H - 18, fill=rail, stroke=None, rx=1.75))
        texts.append(dict(x=CH_X + 18, y=cy + 5, s=FIG_CH_LABEL[ch["id"]],
                          size=12.5, color=tcol, weight=600, anchor="start"))

        for i, s in enumerate(leaves):
            top = y0 + PAD_Y + i * LEAF_ROW
            ny = top + 16                      # sub-question baseline
            boxes.append(dict(kind="dot", x=DOT_X - 2.5, y=ny - 3.5,
                              w=5, h=5, fill=rail, stroke=None, rx=2.5))
            texts.append(dict(x=LEAF_X, y=ny, s=s["id"], size=11,
                              color=rail, weight=600, anchor="start"))
            texts.append(dict(x=LEAF_X + 25, y=ny, s=s["en"], size=11,
                              color=FIG_INK, weight=400, anchor="start"))

            cit = leaf_citations(papers.get(s["id"], []))
            if cit:
                texts.append(dict(x=WORKS_X, y=ny, s=cit, size=9.5,
                                  color=scol, weight=400, anchor="start"))

    # ---- masthead
    texts.append(dict(x=BAND_X, y=58, s=tax["meta"]["title"], size=25,
                      color="#232219", weight=600, anchor="start"))
    texts.append(dict(x=BAND_X, y=90, s=tax["meta"]["subtitle"], size=13.5,
                      color="#6E6A60", weight=400, anchor="start"))
    texts.append(dict(x=FIG_W - RIGHT_INSET, y=48, s="SURVEY TAXONOMY \u00b7 V2",
                      size=10, color=FIG_MUTE, weight=700, anchor="end"))
    texts.append(dict(x=FIG_W - RIGHT_INSET, y=66, s="Reclassified mechanisms & citations",
                      size=9.5, color=FIG_MUTE, weight=400, anchor="end"))
    for x, lbl in ((LVL_TXT_X, "LEVEL / ROLE"), (CH_X, "CHAPTER"),
                   (LEAF_X, "SUB-QUESTION / MECHANISM"),
                   (WORKS_X, "SELECTED WORKS  (D: primary   A: adjacent/enabling"
                             "   B: boundary   V: survey of others   S: this survey)")):
        a = "end" if x == WORKS_X else "start"
        xa = FIG_W - RIGHT_INSET if a == "end" else x
        texts.append(dict(x=xa, y=MAST_H - 12, s=lbl, size=9.5, color=FIG_MUTE,
                          weight=600, anchor=a))

    return dict(panels=panels, boxes=boxes, texts=texts, conns=conns,
                arrows=arrows, W=FIG_W, H=int(content_bottom + 36))


def build_figure_svg(tax, papers=None):
    L = layout(tax, papers)
    o = []
    o.append(f'<svg viewBox="0 0 {L["W"]} {L["H"]}" width="100%" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'font-family="Helvetica, Arial, sans-serif" role="img">')
    o.append("<title>Metacognition in large language models: a level-structured taxonomy</title>")
    o.append('<desc>A nested taxonomy panel. The masthead carries a hierarchical relation '
             'diagram linking L0 cognitive execution, L1 monitoring and control, and L2 '
             'learning. Below it, each level band is a rounded container holding the '
             'chapter that belongs to it; every chapter branches into its sub-questions, '
             'each of which carries a compact citation string of its representative works, '
             'prefixed by evidence tier D (primary metacognitive study), A (adjacent or '
             'enabling), B (boundary), V (another author survey or position paper), or '
             'S (this survey own proposal). The bands run from '
             'theoretical foundations through the L0-L2 framework, Level 1 representation, '
             'Level 1 regulation, cross-level evaluation, Level 2 learning, and the '
             'recursive extension, ending in research gaps.</desc>')
    o.append(f'<rect x="0" y="0" width="{L["W"]}" height="{L["H"]}" fill="#FFFFFF"/>')

    # nested containers, outermost first
    for p in L["panels"]:
        stroke = f' stroke="{p["stroke"]}" stroke-width="1"' if p["stroke"] else ""
        o.append(f'<rect x="{p["x"]}" y="{p["y"]:.1f}" width="{p["w"]}" '
                 f'height="{p["h"]:.1f}" rx="{p["rx"]}" fill="{p["fill"]}"{stroke}/>')

    # connectors next so nodes paint over them
    for c in L["conns"]:
        o.append(f'<path d="M {c["x1"]} {c["y1"]:.1f} H {c["x2"]}" fill="none" '
                 f'stroke="{c["color"]}" stroke-width="1"/>')

    # hierarchical-relation edges: a shaft plus a small head at the target end
    for a in L.get("arrows", []):
        x1, x2, ay = a["x1"], a["x2"], a["y"]
        tip = x2 - 7 if a["fwd"] else x2 + 7
        o.append(f'<path d="M {x1} {ay:.1f} H {tip}" fill="none" '
                 f'stroke="{a["color"]}" stroke-width="1.2"/>')
        d = "\u25b6" if a["fwd"] else "\u25c0"
        o.append(f'<text x="{x2:.1f}" y="{ay + 3.6:.1f}" font-size="10" '
                 f'font-weight="400" fill="{a["color"]}" '
                 f'text-anchor="middle">{d}</text>')

    for b in L["boxes"]:
        stroke = f' stroke="{b["stroke"]}" stroke-width="0.8"' if b["stroke"] else ""
        o.append(f'<rect x="{b["x"]:.1f}" y="{b["y"]:.1f}" width="{b["w"]:.1f}" '
                 f'height="{b["h"]:.1f}" rx="{b["rx"]}" fill="{b["fill"]}"{stroke}/>')

    for t in L["texts"]:
        anchor = f' text-anchor="{t["anchor"]}"' if t["anchor"] != "start" else ""
        o.append(f'<text x="{t["x"]:.1f}" y="{t["y"]:.1f}" font-size="{t["size"]}" '
                 f'font-weight="{t["weight"]}" fill="{t["color"]}"{anchor}>'
                 f'{esc(t["s"])}</text>')
    o.append("</svg>")
    o.append("")
    return "\n".join(o)


# --------------------------------------------------------------------------- main

def main():
    tax, papers = load_all()

    missing = [s["id"] for s in tax["sections"] if not papers.get(s["id"])]
    if missing:
        print(f"  ! sections with no entries: {', '.join(missing)}", file=sys.stderr)

    (ROOT / "README.md").write_text(build_readme(tax, papers), encoding="utf-8")
    if not FIGDIR.is_dir():
        FIGDIR.mkdir(parents=True)
    (FIGDIR / "figure1_taxonomy.svg").write_text(
        build_figure_svg(tax, papers), encoding="utf-8")

    n_papers = sum(len(v) for v in papers.values())
    print(f"README.md written  ({n_papers} works, {len(tax['sections'])} sub-questions)")
    print("figures/figure1_taxonomy.svg written")


if __name__ == "__main__":
    main()
