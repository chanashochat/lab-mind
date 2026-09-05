import sys

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from judge import build_context, build_grounding_source, judge_description

INPUT_FILE = "assignment_02_exp3_haiku.xlsx"
ROWS = [0, 1, 4]  # human: Tone=ok, Length=ok (padding); row 4 also Grammar=ok


def main():
    samples, ranges, sop_text = build_context()
    df = pd.read_excel(INPUT_FILE)

    for i in ROWS:
        row = df.iloc[i]
        grounding_source = build_grounding_source(
            row["question"], row["expected_sample_id"], samples, ranges, sop_text
        )
        verdict = judge_description(
            row["question"], row["category"], row["generated_description"], grounding_source
        )

        print(f"=== Row {i} ({row['category']}) ===")
        print(f"Q: {row['question']}")
        print(f"A: {row['generated_description']}")
        print(f"Human scores (Task 3): Fluency={row['Fluency']} Grammar={row['Grammar']} "
              f"Tone={row['Tone']} Length={row['Length']} Grounding={row['Grounding']}")
        print()
        for criterion in ("fluency", "grammar", "tone", "length", "grounding"):
            score = getattr(verdict, criterion)
            print(f"  [judge] {criterion.capitalize()}: {score.verdict.value}")
            print(f"    {score.explanation}")
        print()


if __name__ == "__main__":
    main()
