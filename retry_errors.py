import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from judge import build_context, build_grounding_source, judge_description
from run_judge_full import CRITERIA, compute_final_score, latency_verdict

FILES = [
    "assignment_02.xlsx",
    "assignment_02_exp1_fewshot.xlsx",
    "assignment_02_exp2_maxtokens70.xlsx",
    "assignment_02_exp3_haiku.xlsx",
    "assignment_02_exp4_haiku_scoped.xlsx",
]


def main():
    samples, ranges, sop_text = build_context()

    for path in FILES:
        df = pd.read_excel(path)
        error_idx = df.index[df["judge_fluency_verdict"] == "ERROR"]
        if len(error_idx) == 0:
            continue

        print(f"\n=== {path} ({len(error_idx)} rows to retry) ===")
        for i in error_idx:
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
                status = f"STILL ERROR: {e}"
                for c in CRITERIA:
                    df.at[i, f"judge_{c}_verdict"] = "ERROR"
                    df.at[i, f"judge_{c}_explanation"] = str(e)
                df.at[i, "judge_latency_verdict"] = "ERROR"
                df.at[i, "judge_final_score"] = "ERROR"

            elapsed = time.perf_counter() - start
            print(f"  [{i}] {row['category']:<17} {elapsed:.1f}s  {status}")

        df.to_excel(path, index=False)
        print(f"Saved to {path}")


if __name__ == "__main__":
    main()
