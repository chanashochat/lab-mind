# Task 4 — Improvement cycle log

Baseline: `generate.py` (greedy decoding, `MAX_NEW_TOKENS=150`, original system
prompt) → `assignment_02.xlsx`. Rubric columns in that file are not yet
scored — score it first so there's a real baseline number to diff against.

Read from the raw generations before any scoring, three systemic failure
patterns are already visible by eye:

1. **`range_reasoning` (13/13 rows):** model writes the word "Pass"/"OOS"
   where the numeric reference range belongs, instead of stating
   `reference_low`–`reference_high`.
2. **`status_reasoning` (7/9 rows wrong):** model defaults to "OOS (תקלה)"
   regardless of the true status, instead of reading the literal `status`
   column already present in the data.
3. **Language leakage:** Chinese (上限, 底线, 基准), Russian (до), Spanish
   (resultat/Resultado), and raw English sentences ("Therefore, the answer
   to your question is...") appear inside otherwise-Hebrew answers.

Latency is a separate, structural issue: every baseline row is 27–54s
(rubric's "bad" threshold is >6000ms). That's fixed CPU overhead for running
a 0.5B model locally, not something a prompt or decoding change will move —
noting it now so it isn't mistaken for a lever failure later.

---

## Experiment 1 — Prompt engineering: few-shot examples + explicit column-mapping rule

**What changed:** In `generate.py`, `SYSTEM_PROMPT` gained one new rule
(Rule 6: "for status, copy the `status` column as-is; for range, always
state both numbers, never the word Pass/OOS") and a 3-example worked block
(one `value_lookup`, one `status_reasoning`, one `range_reasoning`) using a
fabricated `S-00001` row, in the same Hebrew phrasing as the real questions.
Rule 2 was tightened from "Respond in Hebrew" to explicitly ban
English/Chinese/Russian words. Nothing else changed — same model
(`Qwen2.5-0.5B-Instruct`), same decoding (`do_sample=False`,
`MAX_NEW_TOKENS=150`), same questions, same `build_context`.

**Why expected to help:** all three targeted failure modes are format/
instruction-following failures a small instruct model is known to fix more
reliably from a worked example than from a prose rule — the model was
already retrieving roughly the right row (see baseline row 15: it names ALT
but reports Glucose's 70–100 range), so the failure looks like "doesn't know
what shape the answer should take," not "can't find the data." A concrete
example anchors both the output shape and the language.

**Output:** `assignment_02_exp1_fewshot.xlsx` (same 15 columns as the
baseline file, rubric columns blank — score with the same rubric.md bands,
same 40 questions).

**Qualitative read of the raw text (before scoring), for context:** the
`range_reasoning` template did get fixed structurally in all 13 rows —
every one now outputs "טווח תקין: X-Y unit. התוצאה בטווח/OOS" instead of
putting "Pass"/"OOS" where the range belongs. But the model latched onto
the fabricated few-shot example's literal numbers (`95.40`, `70.0-100.0`,
`mg/dL`) and started echoing them for unrelated tests/units (e.g. pH_Level
range reported as "70.0-100.0 pH"; WBC_Count unit reported as `mg/dL`
instead of `10^3/uL`). `status_reasoning` regressed hard: 11/11 scored rows
now output a garbled non-answer built from the example's copied number
("ה doubted תוצאה 95.40 mg/dL") and never state Pass/OOS at all. New
non-Hebrew leakage appeared too ("doubted", "результат", "risultaat",
"TFT", "andalone") — different words than baseline's leakage, same rate,
despite Rule 2 being tightened to explicitly ban other languages.

**Result / delta (rows 0–10, the 11 rows scored so far in both files):**

| Criterion | Baseline good/ok/bad (n=11, Fluency n=10) | Exp 1 good/ok/bad (n=11) | Δ good |
|---|---|---|---|
| Fluency | 2 / 2 / 6 | 2 / 0 / 9 | 0 |
| Grammar | 3 / 0 / 8 | 2 / 0 / 9 | −1 |
| Tone | 4 / 1 / 6 | 2 / 0 / 9 | −2 |
| Length | 8 / 0 / 3 | 5 / 0 / 6 | −3 |
| Grounding | 3 / 0 / 8 | 4 / 0 / 7 | +1 |
| Latency | 1 / 0 / 10 | 0 / 0 / 11 | −1 |
| Rows passing (cumulative bar) | 1 / 11 (9%) | 1 / 11 (9%) | 0 |
| Avg latency (scored rows) | 37,515 ms | 54,002 ms | +44% (worse) |

**Verdict: not a win.** Fluency/Grammar/Tone/Length all went down or stayed
flat; only Grounding ticked up by one row, which is exactly the kind of
single-row swing on n=11 that the "don't ship noise as progress" rule warns
about — not defensible as a real effect on its own. The overall pass rate
is unchanged (1/11 both times), and it isn't even the same row passing:
baseline's one pass was a `value_lookup` row, exp1's one pass was a
`range_reasoning` row — consistent with the qualitative read that the fix
helped range-format rows specifically while breaking status_reasoning and
adding new language leakage elsewhere. Latency also got worse (+44% avg),
likely from the extra prompt tokens added by the few-shot block padding an
already CPU-bound generation.

**Takeaway for next experiment:** a fabricated, concrete-numbers few-shot
example is the wrong tool for a 0.5B model — it pattern-matches on the
example's literal digits instead of generalizing the lookup procedure. A
revision should either drop the invented numbers (describe the format in
words only) or use numbers that can't be mistaken for real values, before
prompt engineering is written off as a lever. Move to a decoding-parameter
experiment (Experiment 2) as an independent test in the meantime — do not
stack it on top of the current (regressed) prompt.

**Caveat:** only 11 of 40 rows are scored so far — treat all of the above
as a preliminary, small-sample read, not a final verdict. Scoring the
remaining 29 rows in both files would sharpen or overturn this.

---

## Experiment 2 — Decoding parameters: `MAX_NEW_TOKENS` 150 → 70

**What changed:** In `generate.py`, `SYSTEM_PROMPT` was reverted to the
exact original baseline text (Experiment 1's Rule 6 and few-shot block
removed) and `MAX_NEW_TOKENS` was lowered from 150 to 70. Nothing else
changed — same model, same greedy decoding (`do_sample=False`), same
questions, same `build_context`. This is a clean diff against **baseline**,
not against Experiment 1 (which is now a dead end per its own writeup).

**Why expected to help:** in the baseline run, the most grounding-broken
rows (7, 8, 17, 26 — raw English data-dump preambles, repeated/garbled
text, "Therefore, the answer to your question is...") were also the
longest (71-116 output tokens), while baseline's *correct* on-target
answers were almost all much shorter (9-45 tokens). Capping generation
lower should cut these runs off before they ramble past the direct answer
into invented extra claims and language drift — a deterministic,
post-generation-style control that doesn't touch the prompt at all.

**Output:** `assignment_02_exp2_maxtokens70.xlsx` (same 15 columns,
rubric columns blank — score with rubric.md, ideally the same 40
questions/rows as already scored for baseline and Experiment 1 so all
three stay comparable).

**Result:** a full text diff against baseline (`generated_description`,
all 40 rows) shows **only 3 rows changed at all — rows 8, 17, 26** (the
only baseline rows that had exceeded 70 output tokens; the other 37/40
already stopped on their own well under the new cap, so their output is
byte-identical to baseline). That already tells most of the story before
any rubric scoring: a cap this loose can only move ~7.5% of the dataset,
so no matter what the rubric says on those 3 rows, this run cannot show a
large aggregate delta from baseline by construction.

And on those 3 rows, the cap **made things worse, not better** — the
opposite of the hypothesis:

- **Row 17** (`value_lookup`, expected `137.46 mmol/L`): baseline rambled
  through an English data-dump but *did* end with the correct value —
  "...Therefore, the answer to your question is: Sodium, mmol/L, **137.46
  mg/dL**." Exp2 cuts off at "...Therefore, the answer to your question
  **is**" — right before the value would have appeared. Baseline stated
  the number (bad Fluency, but salvageable Grounding); exp2 states nothing
  at all.
- **Row 26** (`value_lookup`, expected `7.36 10^3/uL`): same pattern —
  baseline's rambling data-dump ends with "...is: **7.36** mg/dL." (wrong
  unit but the right number). Exp2 cuts off mid-token at "...is: **7.**" —
  doesn't even finish writing the number.
- **Row 8** (`status_reasoning`): both versions are garbled and never
  state a clear Pass/OOS verdict either way — roughly a wash, just less
  repetition in the truncated version.

**Why this happened:** the hypothesis assumed hallucination/rambling
happens *after* the correct answer, so cutting early would preserve the
answer and drop the noise. For these 3 rows, it was the reverse — the
model's correct value only surfaced at the very end of an English
data-dump preamble, so truncating removed the answer and kept the noise.

**Verdict: not a win — mildly negative, and mostly a non-event.** 37/40
rows are unaffected (their scores can be copied straight over from
baseline without rescoring). Of the 3 affected rows, 2 got strictly worse
(previously-correct values now missing entirely) and 1 is unchanged in
substance. This falsifies the "shorter cap = less rambling = better
grounding" hypothesis for this dataset/model/prompt combination — the
correlation between output length and hallucination in Task 3 doesn't hold
up when you actually intervene on length in isolation, which is exactly
the kind of thing this loop is supposed to catch before it becomes a false
"finding."

**Rubric scores (rows 0–9, the 10 rows scored so far in `assignment_02_exp2_maxtokens70.xlsx`):**

| Criterion | Baseline good/ok/bad (n=10) | Exp 2 good/ok/bad (n=10) | Δ good |
|---|---|---|---|
| Fluency | 2 / 2 / 6 | 2 / 2 / 6 | 0 |
| Grammar | 3 / 0 / 7 | 3 / 1 / 6 | 0 |
| Tone | 4 / 1 / 5 | 3 / 1 / 6 | −1 |
| Length | 7 / 0 / 3 | 2 / 0 / 8 | −5 |
| Grounding | 3 / 0 / 7 | 2 / 0 / 8 | −1 |
| Latency | 1 / 0 / 9 | 0 / 0 / 10 | −1 |
| Rows passing (cumulative bar) | 1 / 10 (10%) | 2 / 10 (20%) | +1 |

At face value that Length column looks like a real regression and the pass
rate looks like an improvement. Neither holds up:

**The rows scored here (0–9) only contain 1 of the 3 rows the actual code
change touches (row 8) — rows 17 and 26, where the diff above showed a
real, reproducible regression, are outside this scored range.** Row 8's
score is identical in both files (fail/fail, same bad ratings across the
board) — so **none of the movement in this table is caused by
`MAX_NEW_TOKENS`**. Rows 0, 1, 2, 3, 4, 5, 6, 7, 9 have **byte-identical
generated text** in both files (confirmed by diff), yet:

- Row 0: Tone `good→ok`, Length `good→bad`.
- Row 2: Length `good→bad`, Grounding `good→bad`.
- Row 3: Grammar `bad→ok`, Tone `ok→good`, Length `good→good` (unchanged) —
  this pair of upgrades is what flips row 3 from `fail` to `pass`.
- Row 4, 5, 7: Length `good→bad`.
- Row 1: Latency `good→bad` (27,786 ms in baseline, scored "good"; 30,231
  ms in exp2, scored "bad" — both are already "bad" by rubric.md's own
  ≤2500ms threshold, so neither score was a strict rubric read to begin
  with).

Every one of those is the **same generated text scored differently across
two rating sessions.** That's rater inconsistency, not a model effect —
and it's the entire explanation for both the apparent Length collapse and
the apparent pass-rate gain in this table. The one row genuinely affected
by the parameter change (row 8) shows zero score movement.

**Verdict, combining the text-diff and the rubric scores:** Experiment 2's
true, isolated effect (from the 3 rows it actually touches) is neutral-to-
negative, per the text diff above (rows 17/26 lost previously-correct
values; row 8 unchanged). The rubric-scored sample (rows 0–9) mostly
missed those touched rows and instead surfaced a second, unplanned finding:
**scoring drift on identical text was large enough to flip a fail to a
pass** (row 3) and swing Length from 7/10 good to 2/10 good with no
underlying text change at all. That is close to a textbook case of the
"don't ship noise as progress" warning — the apparent +1 pass here is not
attributable to the code change and should not be reported as one. Scoring
rows 8, 17, 26 specifically (where the real, text-level difference lives)
would give a cleaner read than continuing to score the unaffected rows.

---

## Interim conclusion after Experiments 1–2 (superseded — see Final conclusion)

Two single-variable experiments were run against the baseline
(`Qwen2.5-0.5B-Instruct`, greedy decoding, original prompt):

1. **Prompt engineering** (few-shot examples + explicit column-mapping
   rule): fixed the `range_reasoning` format bug in all 13 rows, but the
   model anchored on the fabricated example's literal numbers and broke
   `status_reasoning` in all 11 scored rows — net effect across 6 rubric
   criteria was flat-to-negative (Grounding +1/11, everything else flat or
   down), and latency got 44% worse from the longer prompt. **Not a win.**
2. **Decoding parameters** (`MAX_NEW_TOKENS` 150→70): only altered 3 of 40
   rows by construction (37 rows already stopped short of the cap on their
   own); of those 3, two lost a previously-correct value to truncation and
   one was an unaffected wash. Rubric scoring on rows 0–9 mostly missed the
   affected rows and instead demonstrated a second finding — human rating
   of identical text drifted enough between sessions to flip a fail to a
   pass on its own. **Not a win, and a live example of scoring noise.**

Neither lever beat baseline on this rubric and dataset. That is a valid
EDD outcome: both changes were cheap, reversible, individually attributable
(one variable each), honestly re-measured against the same baseline and
rubric, and neither is being reported as progress it can't defend. The
clearest actionable lead from both rounds is that the model's few genuinely
correct answers are short and near the start of generation, while its
worst failures are long, rambling, and language-inconsistent — a
deterministic **post-processing** step (strip non-Hebrew characters/words,
hard-trim to the first 1–3 sentences) is the untried lever most likely to
help next, since it can target that exact pattern without relying on a
0.5B model's fragile in-context instruction-following.

---

## Experiment 3 — Model choice: local Qwen2.5-0.5B-Instruct → Claude Haiku 4.5

**What changed:** `generate.py`'s inference backend only. `SYSTEM_PROMPT` is
back to the exact baseline text (same as Experiment 2 — no few-shot block),
and the output-token cap is back to the baseline's 150 (undoing Experiment
2's 70 → **only the model changed vs. baseline**). Local HF
`AutoModelForCausalLM.generate()` on `Qwen/Qwen2.5-0.5B-Instruct` (CPU) was
replaced with `client.messages.create(model="claude-haiku-4-5", ...)` via
the Anthropic API — same `build_context`, same 40 questions, same prompt,
same 150-token cap. (The installed SDK doesn't expose `temperature` on this
call, so decoding is left at the API default rather than approximated —
noted, not treated as a second variable, since it isn't a lever this dataset
can meaningfully control either way.)

**Why expected to help:** this is the "model choice" lever from the
assignment, deliberately run *last* — after two prompt/decoding experiments
on the 0.5B model came back negative, per the assignment's own instruction
not to reach for a bigger model first ("otherwise you learn nothing except
'bigger model is better'"). The specific failure modes from Experiments 1–2
(status_reasoning defaulting to the wrong verdict instead of reading the
`status` column, range_reasoning putting "Pass"/"OOS" where numbers belong,
non-Hebrew word leakage, raw data-dump preambles) all look like
instruction-following and retrieval failures a much larger, more capable
model should not make, rather than problems inherent to the prompt or the
knowledge base.

**Output:** `assignment_02_exp3_haiku.xlsx` (same 15 columns, rubric
columns blank).

**Single-row sanity check before the full run** (row 0, `status_reasoning`,
same question all three prior runs got wrong or garbled): Haiku answered
"דגימה S-10038 עברה את הבדיקה (Pass). ערך ה-WBC_Count הוא 6.38 10^3/uL,
אשר נמצא בטווח ההתייחסות של 4.0-11.0." — correct status, fluent Hebrew, and
an accurate supporting detail pulled correctly from the data (not
requested, but grounded — at worst "ok" under the rubric's paraphrase-is-
fine rule). This is already qualitatively different from every baseline/
Exp1/Exp2 answer to this exact question.

**Full-run qualitative read (before scoring):** all 40 rows were read
end-to-end. Every value_lookup answer states the correct number; every
status_reasoning answer states the correct Pass/OOS verdict; every
range_reasoning answer states the correct reference_low–reference_high pair
with the correct unit (no more `mg/dL` substituted for `10^3/uL`, no more
"Pass" printed in place of the range — the two systemic bugs Experiment 1's
few-shot approach couldn't fix). No non-Hebrew word leakage anywhere in the
sample — no Chinese/Russian/English/Spanish tokens, no raw data-dump
preambles, no "Therefore, the answer to your question is" artifacts. The
model frequently adds one extra grounded, accurate clause beyond what was
strictly asked (e.g. a `value_lookup` answer also naming the reference
range and Pass/OOS status) — not requested, but truthful and traceable to
the data, so at worst an `ok` under rubric.md's paraphrase-is-fine rule, not
a `bad`.

**Latency:** avg 1713ms across all 40 rows (vs. baseline's ~37,500ms on the
scored subset — roughly **20x faster**), with 38/40 rows under 2000ms
(rubric.md's "good" threshold is ≤2500ms) and two outliers (5,181ms and
11,275ms) that look like ordinary API latency variance, not a systematic
issue. This is the first experiment that actually moves Latency, since it's
the only one that changes where inference happens rather than what's asked
of the same local CPU-bound 0.5B model.

**Rubric scores (rows 0–9, all 10 rows scored):**

| Criterion | Baseline good/ok/bad (n=10) | Exp 3 good/ok/bad (n=10) | Δ good |
|---|---|---|---|
| Fluency | 2 / 2 / 6 | 10 / 0 / 0 | +8 |
| Grammar | 3 / 0 / 7 | 10 / 0 / 0 (1 typo "goood") | +7 |
| Tone | 4 / 1 / 5 | 1 / 9 / 0 | −3 (all "ok", 0 "bad") |
| Length | 7 / 0 / 3 | 0 / 10 / 0 | −7 (all "ok", 0 "bad") |
| Grounding | 3 / 0 / 7 | 10 / 0 / 0 | +7 |
| Latency | 1 / 0 / 9 | 9 / 1 / 0 | +8 |
| Rows passing (cumulative bar) | 1 / 10 (10%) | **10 / 10 (100%)** | +9 |

**Verdict: a clean, decisive win** — confirms the full-run qualitative read
above. Pass rate went from 10% to 100%. Fluency, Grammar, Grounding, and
Latency all moved to all-good. The only two columns that *look* like a
regression (Tone, Length) are actually **7–8 rows moving from a mix of
good/bad up to a uniform "ok"** — i.e. every row that was previously
outright wrong is now merely "not maximally terse," which is a strict
improvement even though the "good" count alone doesn't show it. This is
the exact padding pattern flagged when reviewing the raw text — Haiku
adds one true, grounded, unrequested clause (e.g. also stating the
reference range on a plain value lookup) — and it's costing every row a
notch on Length and Tone instead of a `bad`, without threatening the pass
bar (which only needs ≥4 good, ≤1 bad — this sample has 0 bad anywhere).
**This is the concrete evidence behind the padding issue Experiment 4
targets next.**

---

## Experiment 4 — Prompt engineering: forbid unrequested-but-true padding

**What changed:** Only Rule 3 of `SYSTEM_PROMPT`, vs. Experiment 3. Old:
"Give a direct answer in 1-3 sentences: state the specific value, status,
or range the question asked for. No padding, no filler, no repeating the
question back." New: explicitly states the model may not add a second fact
(e.g. the reference range or Pass/OOS status) unless the question asked for
it, even when that fact is accurate and present in the data. Model
(`claude-haiku-4-5`) and `MAX_TOKENS` (150, unchanged from baseline) are
identical to Experiment 3 — deliberately not touching the token cap, per
Experiment 2's finding that capping tokens on this dataset is unreliable
(it can truncate the correct answer along with the padding).

**Why expected to help:** Experiment 3's scores showed the model treating
"padding" narrowly — it avoids filler/repetition (Rule 3's original
wording) but still volunteers a second, true, grounded fact beyond what
was asked, which cost Length and Tone a notch on 7–9 of 10 scored rows
(good→ok, not good→bad, but a real, measurable gap short of "good"). The
original rule's examples of what to avoid (padding, filler, repeating the
question) didn't include "answering more than was asked," so the fix names
that failure mode explicitly instead of assuming the model would infer it
from "no padding."

**Output:** `assignment_02_exp4_haiku_scoped.xlsx` (same 15 columns,
rubric columns blank — score the same rows 0–9 against baseline/Exp3 for
a clean three-way comparison).

**Qualitative read (before scoring):** of the 27 `value_lookup` /
`status_reasoning` rows (the categories where a single fact is a complete
answer), **26/27 are now a single sentence stating exactly the requested
fact and nothing else** — e.g. row 0: Exp3 "דגימה S-10038 עברה את הבדיקה
(Pass). ערך WBC_Count היה 6.38 10^3/uL, בתוך טווח..." → Exp4 "דגימה
S-10038 עברה את הבדיקה (Pass)." The one exception is row 14
(`status_reasoning`, expected `OOS`): Exp4 still pads — "דגימה S-10021
התקבלה עם חריגה (OOS) בבדיקת Cholesterol_Total, כשהתוצאה הייתה 236.11
mg/dL מעל הטווח הנורמלי..." — same pattern as before, unfixed on this one
row. `range_reasoning` rows still correctly state both the range and the
in/out-of-range comparison, which is what the question actually asks for
in that category, not padding.

Avg output tokens dropped 77.6 → 49.2 (−37%) and avg latency dropped
1713ms → 1038ms (−39%, plausibly just an effect of generating fewer
tokens, not a separate improvement to attribute to the prompt change).

**Rubric scores (rows 0–10, 11 rows scored):**

| Criterion | Baseline good/ok/bad (n=11, Fluency n=10) | Exp 3 good/ok/bad (rows 0–9 only, n=10) | Exp 4 good/ok/bad (n=11) |
|---|---|---|---|
| Fluency | 2 / 2 / 6 | 10 / 0 / 0 | 11 / 0 / 0 |
| Grammar | 3 / 0 / 8 | 10 / 0 / 0 | 11 / 0 / 0 |
| Tone | 4 / 1 / 6 | 1 / 9 / 0 | 11 / 0 / 0 |
| Length | 8 / 0 / 3 | 1 / 9 / 0 | 11 / 0 / 0 |
| Grounding | 3 / 0 / 8 | 10 / 0 / 0 | 11 / 0 / 0 |
| Latency | 1 / 0 / 10 | 9 / 1 / 0 | 11 / 0 / 0 |
| Rows passing | 1 / 11 (9%) | 10 / 10 (100%) | **11 / 11 (100%)** |

**Verdict: confirmed, cleanly attributable.** Every row, every criterion,
`good` — no `ok`, no `bad`, anywhere in the scored sample. Isolating just
the Experiment 3 → 4 change (the 10 rows both runs scored, 0–9): Tone and
Length — the two criteria the padding was costing — move from 1/10 good
to **10/10 good**, while Fluency/Grammar/Grounding/Latency, already
all-good in Experiment 3, stay all-good. That's the cleanest single-
variable result of the whole cycle: one prompt-rule change, a full,
monotonic improvement on exactly the two criteria the hypothesis named,
and no regression anywhere else.

**Caveat:** the qualitative full-40-row read found one residual padding
case outside this scored range (row 14, `status_reasoning`) where the
scope instruction didn't take — so "fixed everywhere" would overclaim from
an 11-row sample. The direction and near-completeness of the fix are
solid; "100% eliminated" is not, without scoring further into the file.

---

## Final conclusion

Four single-variable experiments, run in order, each changing exactly one
thing from its predecessor and re-measured against the same rubric.md
bands on the same 40 questions:

| # | Lever | Change | Verdict |
|---|---|---|---|
| 1 | Prompt engineering | Few-shot examples + column-mapping rule (0.5B local model) | **Not a win** — fixed range-format bug, broke status_reasoning, new language leakage |
| 2 | Decoding parameters | `MAX_NEW_TOKENS` 150→70 (0.5B local model) | **Not a win** — touched only 3/40 rows; 2 got worse (truncated a correct value), 1 unchanged. Also surfaced a rater-consistency artifact as a side finding |
| 3 | Model choice | Local Qwen2.5-0.5B-Instruct → Claude Haiku 4.5 (API) | **Large win** — pass rate 9%→100% on the scored sample; Fluency/Grammar/Grounding/Latency all-good; Tone/Length still capped at "ok" by unrequested padding |
| 4 | Prompt engineering | Tightened Rule 3 to forbid answering beyond what was asked (Haiku) | **Confirmed win, cleanly attributable** — Tone/Length move from 1/10 good to 10/10 good with no change anywhere else; 11/11 rows all-good, all-pass |

The assignment's own ordering — cheap levers before reaching for a bigger
model — held up as a genuine constraint here, not just a rule to follow:
Experiments 1–2 established that the 0.5B model's failures (wrong
status/range logic, language leakage) were not fixable with prompt or
decoding tweaks alone, which is exactly the evidence needed to justify
Experiment 3 rather than assume it. Once on Haiku, going back to the
cheapest lever first (prompt engineering, Experiment 4) closed the one
remaining gap (padding) without needing a further model or decoding
change — the same discipline applied a second time, this time against a
much stronger baseline.

**Noise discipline held throughout:** Experiment 2's apparent "+1 pass"
was traced to rater-scoring drift on byte-identical text and explicitly
not reported as a win; Experiment 4's "100% eliminated" claim is
explicitly hedged against the one residual case (row 14) found outside the
scored sample. Every reported delta in this log is tied to either a text
diff, a rubric-score table, or both — not asserted from a single row.

**Open item:** row 14 and the remaining ~29 unscored rows of Experiment 4
would sharpen the padding-fix estimate further, but the core result — model
choice was the dominant lever, and a second, cheap prompt fix closed the
remaining gap it left — is already well-supported by the 11-row sample and
the full-40-row qualitative read.
