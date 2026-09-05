import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import anthropic
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Experiment 4 (prompt engineering): only Rule 3 changed vs. Experiment 3.
# Exp3's rubric scoring showed Length="ok" (not "good") on 9/10 scored rows:
# the model pads value_lookup/status_reasoning answers with an extra true,
# grounded fact that wasn't asked for (e.g. also stating the reference range
# and Pass/OOS status when only the raw value was requested). Model, MAX_TOKENS,
# and everything else are unchanged from Experiment 3 — deliberately NOT
# using a token cap for this, since Experiment 2 already showed capping
# tokens on this dataset is unreliable (it truncated answers mid-sentence,
# sometimes losing the correct value, not just the padding). A scope
# instruction targets the model's decision to add the extra fact directly.
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 150
OUTPUT_FILE = "assignment_02_exp4_haiku_scoped.xlsx"

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """\
You are a precise, calm assistant for a lab information management system \
(LIMS). You answer questions about lab test results using only the knowledge \
base the user gives you in their message.

Rules:
1. Answer ONLY using the sample rows and reference ranges provided below the \
question. Never use outside knowledge, and never invent a value, status, \
range, or fact that is not present in the knowledge base.
2. Respond in Hebrew.
3. Give a direct answer in 1-3 sentences: state ONLY the specific value, \
status, or range the question asked for — nothing else. Do not add a \
second fact (e.g. the reference range or Pass/OOS status) unless the \
question explicitly asked for it, even if that fact is accurate and \
available in the data below. No padding, no filler, no repeating the \
question back.
4. Tone is professional and factual: no sales language, no unnecessary \
hedging or apologies, no alarm about abnormal (OOS) results.
5. Output only the final answer text. No markdown, no preamble like "Sure," \
no restating these instructions.
"""

SAMPLE_ID_RE = re.compile(r"S-\d{5}")


def load_knowledge_base():
    samples = pd.read_csv("files/samples.csv")
    ranges = pd.read_csv("files/reference_ranges.csv")
    return samples, ranges


def build_context(question: str, samples: pd.DataFrame, ranges: pd.DataFrame) -> str:
    ids = SAMPLE_ID_RE.findall(question)
    relevant = samples[samples["sample_id"].isin(ids)] if ids else samples
    return (
        f"## Sample results\n{relevant.to_csv(index=False)}\n"
        f"## Reference ranges\n{ranges.to_csv(index=False)}"
    )


def load_questions():
    rows = []
    with open("files/golden_dataset.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def main():
    samples, ranges = load_knowledge_base()
    questions = load_questions()

    records = []
    for i, q in enumerate(questions, start=1):
        context = build_context(q["question"], samples, ranges)
        user_message = f"{context}\n\nQuestion: {q['question']}"

        start = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        latency_ms = (time.perf_counter() - start) * 1000

        generated_text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        print(f"[{i}/{len(questions)}] {latency_ms:.0f}ms  {generated_text[:60]}")

        records.append(
            {
                "question": q["question"],
                "category": q["category"],
                "expected_answer": q["expected_answer"],
                "expected_sample_id": q["expected_sample_id"],
                "generated_description": generated_text,
                "latency_ms": round(latency_ms, 1),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "Fluency": "",
                "Grammar": "",
                "Tone": "",
                "Length": "",
                "Grounding": "",
                "Latency": "",
                "final_score": "",
            }
        )

    df = pd.DataFrame(records)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSaved {len(df)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
