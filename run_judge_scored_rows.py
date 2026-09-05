import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from judge import build_context, build_grounding_source, judge_description
from run_judge_full import CRITERIA, compute_final_score, latency_verdict

# Judge only the rows that already carry a human score in Task 3, in each of
# the earlier experiment files (exp4's full 40 rows were already judged by
# run_judge_full.py). This builds a human-comparison sample with real
# good/ok/bad diversity instead of exp4's all-good subsample.
FILES = [
    "assignment_02.xlsx",
    "assignment_02_exp1_fewshot.xlsx",
    "assignment_02_exp2_maxtokens70.xlsx",
    "assignment_02_exp3_haiku.xlsx",
]


def main():
    samples, ranges, sop_text = build_context()

    for path in FILES:
        df = pd.read_excel(path)
        scored_idx = df.index[df["Fluency"].notna()]

        for c in CRITERIA:
            if f"judge_{c}_verdict" not in df.columns:
                df[f"judge_{c}_verdict"] = ""
                df[f"judge_{c}_explanation"] = ""
        if "judge_latency_verdict" not in df.columns:
            df["judge_latency_verdict"] = ""
            df["judge_final_score"] = ""

        print(f"\n=== {path} ({len(scored_idx)} human-scored rows) ===")
        for i in scored_idx:
            row = df.loc[i]
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
            print(f"  [{i}] {row['category']:<17} {elapsed:.1f}s  {status}")

        df.to_excel(path, index=False)
        print(f"Saved judge columns to {path}")


if __name__ == "__main__":
    main()
