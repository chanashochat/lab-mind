# Task 6 — Judge run and analysis

## 1. Sanity check (5 rows) and the prompt fix it forced

Ran `judge.py` on 5 clean rows from `assignment_02_exp4_haiku_scoped.xlsx`
(all single-fact, human-scored `good` across every criterion) — the judge
matched exactly, with explanations that cited specific KB values
("matches the samples.csv row for S-10038 exactly"), not general knowledge.

That sample was too easy to be a real test, so a second sanity pass used 3
rows from `assignment_02_exp3_haiku.xlsx` where the human scorer had marked
`Length=ok` / `Tone=ok` for a known, already-documented failure mode
(Experiment 3/4: the model volunteers a second, true, grounded fact beyond
what the question asked). The judge scored all three `Length=good`,
disagreeing with the human on all three — a real bug, not noise:

> *"The answer is two sentences, directly stating the Pass status **and the
> supporting value/range**, with no padding."*

The judge counted sentences correctly (≤3) but treated an accurate,
grounded-but-unrequested fact as "supporting detail" rather than the
"noticeable irrelevant aside" the rubric's `ok` band names. It had the
rubric text verbatim and still resolved the ambiguity in "irrelevant" the
wrong way. Fixed by adding an explicit scope clause to the judge prompt
(*"judge Length by scope — did it answer only what was asked — not by
whether the extra content happens to be accurate"*). Re-ran both sanity
batches after the fix: the 3 padded rows flipped to `Length=ok` (matching
the human), and the 5 clean rows stayed `Length=good` (no regression).

## 2. Full run

Ran the fixed judge on all 40 rows of `assignment_02_exp4_haiku_scoped.xlsx`
(the shipped configuration from Task 4). Every row: `final_score=pass`.
Results written to `judge_<criterion>_verdict` / `judge_<criterion>_explanation`
columns (plus `judge_latency_verdict`, computed programmatically from
`latency_ms` against the Task 1 thresholds, and `judge_final_score`) —
kept fully separate from the existing human-scored columns. Wall-clock:
230.5s (~3.8 min) for 40 sequential, single-threaded calls.

## 3. Agreement with human scoring

The 11 human-scored rows in the exp4 file are **all `good` on every
criterion** — comparing against just that sample would give a trivially
uninformative 100% agreement everywhere. Instead, the judge was also run on
every human-scored row from the earlier experiment files (baseline, exp1,
exp2, exp3), which carry real `good`/`ok`/`bad` diversity from the weaker
local-model outputs. Combined: **52 human-scored rows** across 5 files.

| Criterion | Agreement | Bias (judge − human, good=2/ok=1/bad=0) |
|---|---:|---:|
| Grounding | 90.4% | +0.02 |
| Fluency   | 88.5% | −0.04 |
| Length    | 82.7% | +0.13 |
| Grammar   | 80.8% | +0.06 |
| **Tone**  | **57.7%** | **+0.60 (systematic, not noise)** |

Grounding and Fluency agree most; Grammar and Length are mid-table; Tone is
a clear outlier — both in raw disagreement rate and in having a strong,
one-directional bias (the judge is essentially always *more generous* on
Tone, never harsher).

### Where the judge was right and I was inconsistent

Two `Grounding` misses on my own part, both on the safety-critical
criterion: `exp1` row 3 answered "82.16 mg/dL" for a **"TFT"** test that
the KB lists as **Glucose** (invented test name) — I scored `good`, the
judge caught it and scored `bad`. `exp1` row 9 stated the WBC_Count range
in **mg/dL** instead of the correct `10^3/uL` (wrong unit = a factual
contradiction) — same pattern, I missed it, the judge didn't. Also one
clear `Length` scoring slip on my part: a bare, maximally terse
`"125.0 mg/dL"` answer that I scored `bad` and the judge scored `good` —
this matches the rater-drift issue already documented in Experiment 2.

### Where the rubric itself was ambiguous (the Tone finding)

Nearly every Tone disagreement is the same pattern: a garbled, barely
coherent answer (Chinese characters, stray French/English words, broken
Hebrew) that I scored `bad`/`ok` and the judge scored `good`, with
explanations like:

> *"Aside from the garbled language, the tone itself is calm and factual...
> There's no marketing language, hedging, or alarm."*

The judge is applying the Tone rubric **literally** — its `bad` band names
specific lapses (hedging, apology, sales language, jokey/alarmist framing
of a result) and says nothing about incoherence. I was, apparently,
letting "this answer is a mess" bleed into every criterion including Tone,
even though incoherence is really a Fluency/Grounding problem. The written
rubric never says whether Tone is scored in isolation from the rest of the
answer's quality or as a partial proxy for "does this answer inspire
confidence" — we each resolved that gap differently, and did so
consistently enough to produce a systematic +0.60 bias rather than random
noise. **This is the rubric-fix, not a judge-fix or a me-fix**: the Tone
band needs an explicit sentence stating whether "the answer is otherwise
garbled/wrong" counts toward Tone or is out of scope for it.

## 4. Analysis

### a. Trade-offs (real numbers from this project)

| | Human (me) | LLM judge (Claude Sonnet 5) |
|---|---|---|
| Time, 52 rows | **30 min** (~35 sec/row) | **~14 min** sequential, single-threaded (~16 sec/row) — includes 5 calls that hit a `max_tokens` truncation bug and needed a retry; parallelizable to seconds at scale since calls are independent |
| Time, 40 rows (full production file) | not measured, but at my own per-row rate ≈ 23 min extrapolated | 3.8 min measured, sequential |
| Cost per row | $0 marginal (my time) | ≈ $0.0135/row (5,287 input + 293 output tokens on one sampled call, Sonnet 5 intro pricing $2/$10 per MTok) — **not yet using prompt caching**, so the ~4,700-token fixed system prompt + KB context (rubric + full SOP doc) is paid in full on every single call; caching that stable prefix would cut this significantly at volume |
| Consistency | Not consistent with myself — 3+ confirmed scoring drifts across sessions in this project alone (this analysis, plus the one already documented in Experiment 2) | Highly consistent — same prompt, same rubric text, every call; not perfectly deterministic (Sonnet 5 doesn't accept a fixed `temperature`), but nowhere near human session-to-session drift |
| Accuracy (vs. ground truth, i.e. the actual KB) | Missed 2 real hallucinations (wrong test name, wrong unit) that were exactly the kind of thing Grounding exists to catch | Caught both of those; independently, the judge under-detects the "answered more than asked" nuance without a prompt fix — the sanity check phase exists precisely to find and fix problems like that before spending money at scale |

The headline tension: **consistency and accuracy pull in opposite
directions.** I am the nominal gold standard for the *intent* behind the
rubric, but demonstrably inconsistent applying it session to session
(scoring drift is a known, recurring finding in this project, not a one-off).
The judge is far more consistent, but its consistency is only as good as
the prompt — the Tone bias above is the judge being *consistently* wrong in
one direction, which is arguably worse than random noise because it won't
average out over a larger sample.

### b. Recommendation

For a production system generating thousands of descriptions/day, pure
manual evaluation doesn't scale (30 min for 52 rows extrapolates to ~29
hours for 5,000 rows/day — not viable as a daily gate) and pure LLM-judge
evaluation inherits whatever systematic blind spot the prompt has (Tone,
here) at full volume, silently, forever, unless someone is checking.

**Recommended split, not a single choice:**

- **LLM judge as the default gate on every row.** At ~$0.0135/row (before
  caching optimizations) this is cheap at any realistic volume and fast
  enough to run inline before an answer ships.
- **Hard escalation to a human whenever `Grounding != good`.** This mirrors
  the Task 1 go/no-go rule exactly, and it's the one criterion where this
  project's own data shows the judge is *more* reliable than the human at
  catching the failure mode that matters most (invented test names, wrong
  units) — so trust the judge here, but still route it to a human for the
  final call, since a false Grounding failure blocking a correct answer is
  cheap, while a Grounding miss reaching a user is not.
- **Periodic human re-audit of a random sample (not just escalations)** —
  specifically sized to catch systematic bias like the Tone finding here,
  which no per-row escalation rule would surface on its own (every
  individual garbled-but-plain-toned answer looks locally fine to the
  judge; only aggregating across many rows reveals the +0.60 skew). A
  weekly sample of ~50-100 rows, scored blind by a human and diffed against
  the judge the same way this task just did, is what actually catches
  prompt drift or rubric gaps before they compound at scale.
- **Treat every human/judge disagreement from that audit as a rubric bug
  report first**, not an automatic override in either direction — as this
  task's own findings show, roughly a third of the disagreements traced
  back to an ambiguous rubric line, not to either evaluator being "wrong."
