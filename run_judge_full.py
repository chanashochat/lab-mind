import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from judge import build_context, build_grounding_source, judge_description

INPUT_FILE = "assignment_02_exp4_haiku_scoped.xlsx"
OUTPUT_FILE = "assignment_02_exp4_haiku_scoped.xlsx"  # write back into the same spreadsheet

CRITERIA = ("fluency", "grammar", "tone", "length", "grounding")

# Latency rubric bands from rubric.md, Task 1 -- Latency is measured
# programmatically (never handed to the LLM judge), same as the assignment
# instructs. Thresholds were set in Task 1 from timed calls on this
# dataset/prompt shape.
def latency_verdict(latency_ms: float) -> str:
    if latency_ms <= 2500:
        return "good"
    elif latency_ms <= 6000:
        return "ok"
    else:
        return "bad"


def compute_final_score(verdicts: dict) -> str:
    """rubric.md 1b: pass bar is >=4 of 6 criteria `good` and <=1 `bad`,
    with a go/no-go override -- Grounding not `good` fails the row outright
    regardless of every other rating."""
    if verdicts["grounding"] != "good":
        return "fail"
    good_count = sum(1 for v in verdicts.values() if v == "good")
    bad_count = sum(1 for v in verdicts.values() if v == "bad")
    if good_count >= 4 and bad_count <= 1:
        return "pass"
    return "fail"


def main():
    samples, ranges, sop_text = build_context()
    df = pd.read_excel(INPUT_FILE)

    # New columns, clearly separated from the human-scored ones (Fluency,
    # Grammar, Tone, Length, Grounding, Latency, final_score) by the
    # judge_ prefix.
    for c in CRITERIA:
        df[f"judge_{c}_verdict"] = ""
        df[f"judge_{c}_explanation"] = ""
    df["judge_latency_verdict"] = ""
    df["judge_final_score"] = ""

    n = len(df)
    for i, row in df.iterrows():
        start = time.perf_counter()
        try:
            grounding_source = build_grounding_source(
                row["question"], row["expected_sample_id"], samples, ranges, sop_text
            )
            verdict = judge_description(
                row["question"], row["category"], row["generated_description"], grounding_source
            )
            verdicts = {}
            for c in CRITERIA:
                score = getattr(verdict, c)
                df.at[i, f"judge_{c}_verdict"] = score.verdict.value
                df.at[i, f"judge_{c}_explanation"] = score.explanation
                verdicts[c] = score.verdict.value

            lat_verdict = latency_verdict(row["latency_ms"])
            df.at[i, "judge_latency_verdict"] = lat_verdict
            verdicts["latency"] = lat_verdict

            df.at[i, "judge_final_score"] = compute_final_score(verdicts)
            status = df.at[i, "judge_final_score"]
        except Exception as e:
            for c in CRITERIA:
                df.at[i, f"judge_{c}_verdict"] = "ERROR"
                df.at[i, f"judge_{c}_explanation"] = str(e)
            df.at[i, "judge_latency_verdict"] = "ERROR"
            df.at[i, "judge_final_score"] = "ERROR"
            status = f"ERROR: {e}"

        elapsed = time.perf_counter() - start
        print(f"[{i + 1}/{n}] {row['category']:<17} {elapsed:.1f}s  {status}")

    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSaved {n} judged rows to {OUTPUT_FILE}")
    print(df["judge_final_score"].value_counts())


if __name__ == "__main__":
    main()
