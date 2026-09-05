import sys

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

CRITERIA = ["Fluency", "Grammar", "Tone", "Length", "Grounding"]

FILES = [
    "assignment_02.xlsx",
    "assignment_02_exp1_fewshot.xlsx",
    "assignment_02_exp2_maxtokens70.xlsx",
    "assignment_02_exp3_haiku.xlsx",
    "assignment_02_exp4_haiku_scoped.xlsx",
]

# Known typos in the hand-scored human columns (see run history) -- normalize
# for comparison purposes only; the source cells are left untouched.
TYPO_FIX = {"goood": "good", "bda": "bad"}

ORDINAL = {"bad": 0, "ok": 1, "good": 2}


def load_all():
    frames = []
    for path in FILES:
        df = pd.read_excel(path)
        scored = df[df["Fluency"].notna()].copy()
        scored["source_file"] = path
        frames.append(scored)
    return pd.concat(frames, ignore_index=True)


def main():
    df = load_all()
    print(f"Total human-scored rows across all files: {len(df)}\n")

    print(f"{'Criterion':<10} {'Agreement':>10} {'n':>4}  {'Judge-Human bias (avg)':>24}")
    disagreements = {}
    for c in CRITERIA:
        human = df[c].replace(TYPO_FIX)
        judge = df[f"judge_{c.lower()}_verdict"]

        valid = human.isin(ORDINAL) & judge.isin(ORDINAL)
        h, j = human[valid], judge[valid]

        agree = (h.values == j.values)
        agreement_rate = agree.mean()

        bias = (j.map(ORDINAL) - h.map(ORDINAL)).mean()  # >0: judge more generous

        print(f"{c:<10} {agreement_rate:>9.1%} {valid.sum():>4}  {bias:>+24.2f}")

        disagreements[c] = df[valid][~agree]

    for c in CRITERIA:
        rows = disagreements[c]
        if len(rows) == 0:
            continue
        print(f"\n=== Disagreements on {c} ({len(rows)} rows) ===")
        for _, row in rows.iterrows():
            human_v = TYPO_FIX.get(row[c], row[c])
            judge_v = row[f"judge_{c.lower()}_verdict"]
            print(f"\n[{row['source_file']}] human={human_v} judge={judge_v}")
            print(f"  Q: {row['question']}")
            print(f"  A: {row['generated_description'][:200]}")
            print(f"  judge explanation: {row[f'judge_{c.lower()}_explanation']}")


if __name__ == "__main__":
    main()
