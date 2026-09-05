import os
import re
import sys
from enum import Enum

sys.stdout.reconfigure(encoding="utf-8")

import anthropic
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

# Judge model: deliberately NOT one of the generation models used in Task 2
# (local Qwen2.5-0.5B, claude-haiku-4-5) to reduce self-enhancement bias --
# a model shouldn't grade its own family's homework.
JUDGE_MODEL = "claude-sonnet-5"

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SAMPLE_ID_RE = re.compile(r"S-\d{5}")


# ---------------------------------------------------------------------------
# Output schema
#
# `explanation` is declared before `verdict` on every criterion. The judge
# is an autoregressive model: each output token is conditioned only on the
# tokens already emitted (plus the input), never on tokens still to come.
# With explanation-then-verdict, the verdict token is generated *after* the
# model has already written out its reasoning, so it's conditioned on that
# reasoning and tends to actually follow from it. With verdict-then-
# explanation, the model would have to commit to good/ok/bad before it had
# "thought out loud" in the output, and the explanation that follows would
# just be a post-hoc rationalization of an already-fixed verdict rather than
# the process that produced it -- closer to asking someone to blurt out a
# grade and then invent a justification for it, which weakens exactly the
# thing an explanation is for (letting you check the verdict against the
# reasoning that led to it).
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    good = "good"
    ok = "ok"
    bad = "bad"


class CriterionScore(BaseModel):
    explanation: str
    verdict: Verdict


class JudgeVerdict(BaseModel):
    fluency: CriterionScore
    grammar: CriterionScore
    tone: CriterionScore
    length: CriterionScore
    grounding: CriterionScore


# ---------------------------------------------------------------------------
# Judge prompt -- rubric definitions copied verbatim from rubric.md (Task 1)
# so the judge is held to exactly the standard used for the manual scoring
# in Task 3. Latency (and cost) are excluded: those are measured
# programmatically, not judged by an LLM.
# ---------------------------------------------------------------------------

RUBRIC_TEXT = """\
### Fluency — does the Hebrew read naturally?

| Rating | Definition |
|---|---|
| good | Reads the way a native Hebrew speaker would write it. No literal-translation artifacts, no unnatural word order. |
| ok | 1–2 phrases feel stiff or translated, but the meaning is immediately clear without re-reading. |
| bad | 3+ awkward phrases, or any sentence that requires re-reading to parse, or Hebrew vocabulary forced into non-Hebrew (e.g. English) sentence structure. |

### Grammar — spelling, punctuation, agreement?

| Rating | Definition |
|---|---|
| good | No spelling, punctuation, gender/number agreement, or סמיכות (construct-state) errors. |
| ok | 1–2 minor errors (e.g. one gender-agreement slip, a missing comma) that don't obscure meaning. |
| bad | 3+ errors, or any single error that changes or obscures the meaning (e.g. a number/unit garbled by punctuation). |

### Tone — calm, precise, professional lab-assistant voice?

| Rating | Definition |
|---|---|
| good | States facts plainly and professionally. No sales/marketing language, no unnecessary hedging, apologizing, or alarm. |
| ok | One lapse — e.g. an overly casual phrase, an unneeded hedge/apology, or a hint of enthusiasm that doesn't belong. |
| bad | 2+ lapses, or any tone that undermines trust in the result (jokey about an OOS/abnormal value, alarmist/panic-inducing language, editorializing on a medical result). |

### Length — is the answer a direct, appropriately short response?

| Rating | Definition |
|---|---|
| good | 1–3 sentences that directly state the value/status/range the question asked for, no padding. |
| ok | Directly answers but padded to 4–5 sentences, OR answers within 1–3 sentences but with a noticeable irrelevant aside. |
| bad | Exceeds 5 sentences, or never actually states the direct answer (buries it, or answers a different question). |

### Grounding — sticks to the supplied knowledge base? (safety criterion)

| Rating | Definition |
|---|---|
| good | Every factual claim (numeric value, Pass/OOS status, reference range, SOP rule) is traceable to `samples.csv` / `reference_ranges.csv` / `lab_regulatory_procedures.md`. Paraphrasing, reasonable rounding, and restating in different words is acceptable — it isn't required to quote verbatim. |
| ok | A factual claim is stated imprecisely (e.g. rounds 82.16 to "כ-82") without changing the substantive answer, or the reply adds a generic non-factual caveat not drawn from the KB (e.g. "מומלץ להתייעץ עם רופא") that doesn't misstate anything. |
| bad | Any invented, wrong, or contradicted value, status, range, or SOP rule — i.e. any hallucination. |

Filler policy (decided explicitly, per the assignment's note that this has no
universal answer): **paraphrase is fine, invention is not.** A restated or
rounded fact is at worst `ok`; a fact that isn't in the KB at all, or
contradicts it, is `bad` regardless of how well it's phrased.\
"""

JUDGE_SYSTEM_PROMPT = f"""\
You are an expert evaluator of a Hebrew-language, grounded lab-assistant \
question-answering system (a LIMS Q&A bot). You will be shown one question, \
the system's generated answer, and (for the Grounding criterion) the \
relevant excerpts from the system's knowledge base. Score the answer against \
the following rubric, which is the exact rubric a human evaluator used to \
score this same system by hand -- apply it exactly as written, do not \
substitute your own standards.

{RUBRIC_TEXT}

Score these five criteria: Fluency, Grammar, Tone, Length, Grounding. \
(Latency and cost are excluded -- those are measured programmatically, not \
judged from the text.)

For Fluency, Grammar, Tone, and Length, judge the generated answer on its \
own -- the question tells you what's being asked, which is enough context \
for those four. For Grounding, you MUST check every factual claim in the \
answer against the supplied knowledge-base excerpts (the sample row, the \
reference-range table, and the regulatory-procedures excerpt) -- do not \
guess or rely on general knowledge of what a "typical" lab value looks \
like. A claim that isn't supported by the supplied excerpts is not \
automatically wrong (the KB excerpt you were given may be incomplete), but \
weigh Grounding only on what you can actually verify against what's in \
front of you, and treat this as a safety-sensitive judgment: prefer `bad` \
over `good` when a claim can't be verified from the supplied excerpts.

For Length specifically: judge "irrelevant aside" against what the question \
itself asked for, not against whether the extra content happens to be true. \
A question that asks only for a Pass/OOS status is not also asking for the \
underlying numeric value or its reference range -- volunteering that value \
or range is exactly the kind of "noticeable irrelevant aside" the `ok` band \
describes, even though the added fact is accurate and grounded. Being \
truthful does not make an unrequested fact "supporting detail" that stays \
under `good`; judge Length by scope (did it answer only what was asked), \
not by accuracy (Grounding already covers accuracy separately).

For every criterion, write your explanation first, then your verdict --
the verdict should be a conclusion that follows from the explanation you \
just wrote, not a snap judgment you then justify.
"""


def build_context():
    samples = pd.read_csv("files/samples.csv")
    ranges = pd.read_csv("files/reference_ranges.csv")
    with open("files/lab_regulatory_procedures.md", "r", encoding="utf-8") as f:
        sop_text = f.read()
    return samples, ranges, sop_text


def build_grounding_source(
    question: str,
    expected_sample_id: str,
    samples: pd.DataFrame,
    ranges: pd.DataFrame,
    sop_text: str,
) -> str:
    """Everything the judge needs to verify Grounding: the sample row(s) the
    answer could truthfully draw from, the full reference-range table, and
    the full SOP corpus (all three are small enough to include in full --
    trimming the SOP corpus risks silently excluding the very rule an answer
    is grounded in)."""
    ids = SAMPLE_ID_RE.findall(question)
    if expected_sample_id and expected_sample_id not in ids:
        ids.append(expected_sample_id)
    relevant = samples[samples["sample_id"].isin(ids)] if ids else samples
    return (
        f"## Relevant sample row(s) (files/samples.csv)\n{relevant.to_csv(index=False)}\n"
        f"## Reference ranges (files/reference_ranges.csv)\n{ranges.to_csv(index=False)}\n"
        f"## Regulatory procedures (files/lab_regulatory_procedures.md)\n{sop_text}"
    )


def judge_description(
    question: str,
    category: str,
    generated_description: str,
    grounding_source: str,
) -> JudgeVerdict:
    user_message = (
        f"Category: {category}\n"
        f"Question: {question}\n"
        f"Generated answer: {generated_description}\n\n"
        f"{grounding_source}"
    )
    response = client.messages.parse(
        model=JUDGE_MODEL,
        max_tokens=4096,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_format=JudgeVerdict,
    )
    return response.parsed_output


def main():
    samples, ranges, sop_text = build_context()

    df = pd.read_excel("assignment_02_exp4_haiku_scoped.xlsx")
    row = df.iloc[0]

    grounding_source = build_grounding_source(
        row["question"], row["expected_sample_id"], samples, ranges, sop_text
    )
    verdict = judge_description(
        row["question"], row["category"], row["generated_description"], grounding_source
    )

    print(f"Question: {row['question']}")
    print(f"Generated: {row['generated_description']}\n")
    for criterion in ("fluency", "grammar", "tone", "length", "grounding"):
        score = getattr(verdict, criterion)
        print(f"{criterion.capitalize()}: {score.verdict.value}")
        print(f"  {score.explanation}\n")


if __name__ == "__main__":
    main()
