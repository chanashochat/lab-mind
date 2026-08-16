"""
generate_lims_data.py

מחולל דאטהסט סינתטי למערכת LIMS (Laboratory Information Management System).
משמש כבסיס לפרויקט הקורס: Q&A -> Evaluations -> RAG -> Agent -> Multi-Agent.

מייצר 3 קבצי פלט:
1. samples.csv          - טבלת דגימות ותוצאות בדיקה (הנתון ה"מובנה" של ה-LIMS)
2. reference_ranges.csv - טבלת טווחי ייחוס לכל סוג בדיקה (משמש להערכת OOS)
3. golden_dataset.jsonl - שאלות-תשובות לצורך Eval Suite (שלב 2 בפרויקט)

הרצה: python3 generate_lims_data.py
"""

import csv
import json
import random
from datetime import datetime, timedelta

random.seed(42)  # לשחזוריות (reproducibility) - חשוב מאוד ל-Eval Suite

# ---------------------------------------------------------------------------
# 1. הגדרת סוגי בדיקות וטווחי ייחוס
# ---------------------------------------------------------------------------
# כל בדיקה: (שם, יחידה, ערך מינימלי תקין, ערך מקסימלי תקין, ממוצע, סטיית תקן)
TEST_DEFINITIONS = {
    "Glucose":        {"unit": "mg/dL", "low": 70,   "high": 100,  "mean": 85,   "std": 15},
    "Cholesterol_Total": {"unit": "mg/dL", "low": 125, "high": 200, "mean": 170,  "std": 30},
    "Hemoglobin":     {"unit": "g/dL", "low": 12.0, "high": 17.5, "mean": 14.5, "std": 1.5},
    "WBC_Count":      {"unit": "10^3/uL", "low": 4.0, "high": 11.0, "mean": 7.0, "std": 2.0},
    "Creatinine":     {"unit": "mg/dL", "low": 0.6, "high": 1.3, "mean": 0.9, "std": 0.2},
    "ALT":            {"unit": "U/L", "low": 7,   "high": 56,   "mean": 30,   "std": 12},
    "pH_Level":       {"unit": "pH", "low": 6.8, "high": 7.4, "mean": 7.1, "std": 0.15},
    "Sodium":         {"unit": "mmol/L", "low": 135, "high": 145, "mean": 140, "std": 4},
}

TECHNICIANS = ["ד. כהן", "מ. לוי", "ר. אברהם", "ט. גולן", "ש. פרץ"]
INSTRUMENTS = ["Analyzer-A200", "Analyzer-B450", "Chem-Master-3", "BioScan-Pro"]

STATUS_PASS = "Pass"
STATUS_OOS = "OOS"          # Out-of-Specification - חריגה מטווח הייחוס
STATUS_PENDING_REVIEW = "Pending-Review"


def generate_result_value(test_def, force_oos=False):
    """מייצר ערך תוצאה - רובם בטווח תקין, אחוז קטן חריג (OOS) בכוונה."""
    mean, std = test_def["mean"], test_def["std"]
    if force_oos:
        # חריגה מכוונת - מעל או מתחת לטווח
        direction = random.choice([-1, 1])
        offset = direction * (test_def["high"] - test_def["low"]) * random.uniform(0.3, 0.8)
        value = mean + offset
    else:
        value = random.gauss(mean, std)
    return round(value, 2)


def determine_status(value, test_def):
    if value < test_def["low"] or value > test_def["high"]:
        return STATUS_OOS
    return STATUS_PASS


def generate_samples(n_samples=200, oos_rate=0.08):
    """מייצר n_samples רשומות דגימה. oos_rate = אחוז הדגימות שיהיו חריגות בכוונה."""
    samples = []
    base_date = datetime(2026, 1, 1)
    test_names = list(TEST_DEFINITIONS.keys())

    for i in range(1, n_samples + 1):
        test_name = random.choice(test_names)
        test_def = TEST_DEFINITIONS[test_name]
        force_oos = random.random() < oos_rate
        value = generate_result_value(test_def, force_oos=force_oos)
        status = determine_status(value, test_def)

        sample_date = base_date + timedelta(days=random.randint(0, 200),
                                             hours=random.randint(0, 23))

        samples.append({
            "sample_id": f"S-{10000 + i}",
            "test_name": test_name,
            "result_value": value,
            "unit": test_def["unit"],
            "reference_low": test_def["low"],
            "reference_high": test_def["high"],
            "status": status,
            "technician": random.choice(TECHNICIANS),
            "instrument": random.choice(INSTRUMENTS),
            "collected_at": sample_date.strftime("%Y-%m-%d %H:%M"),
            "batch_id": f"B-{random.randint(1000, 1050)}",
        })
    return samples


def write_samples_csv(samples, path="samples.csv"):
    fieldnames = list(samples[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
    print(f"נכתב: {path} ({len(samples)} רשומות)")


def write_reference_ranges_csv(path="reference_ranges.csv"):
    fieldnames = ["test_name", "unit", "reference_low", "reference_high"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for name, d in TEST_DEFINITIONS.items():
            writer.writerow({
                "test_name": name,
                "unit": d["unit"],
                "reference_low": d["low"],
                "reference_high": d["high"],
            })
    print(f"נכתב: {path}")


# ---------------------------------------------------------------------------
# 2. בניית Golden Dataset (שאלות-תשובות) לצורך Eval Suite - שלב 2 בפרויקט
# ---------------------------------------------------------------------------
def build_golden_dataset(samples, n_questions=40, path="golden_dataset.jsonl"):
    """
    בונה זוגות שאלה-תשובה מבוססי-עובדות מתוך הדגימות שנוצרו.
    כל רשומה כוללת: question, expected_answer, expected_sample_id, category.
    ה-category מאפשר לפלח את הביצועים (breakdown) בעת הערכה - חשוב ל-EDD.
    """
    records = []
    chosen = random.sample(samples, min(n_questions, len(samples)))

    for s in chosen:
        q_type = random.choice(["lookup", "status_check", "range_check"])

        if q_type == "lookup":
            question = f"מה הייתה תוצאת בדיקת ה-{s['test_name']} עבור דגימה {s['sample_id']}?"
            answer = f"{s['result_value']} {s['unit']}"
            category = "value_lookup"

        elif q_type == "status_check":
            question = f"האם דגימה {s['sample_id']} עברה את הבדיקה (Pass) או שהתקבלה חריגה (OOS)?"
            answer = s["status"]
            category = "status_reasoning"

        else:  # range_check
            question = (f"מהו טווח הייחוס התקין לבדיקת {s['test_name']}, "
                        f"והאם התוצאה {s['result_value']} {s['unit']} של דגימה "
                        f"{s['sample_id']} נמצאת בטווח?")
            in_range = s["reference_low"] <= s["result_value"] <= s["reference_high"]
            answer = (f"טווח תקין: {s['reference_low']}-{s['reference_high']} {s['unit']}. "
                      f"התוצאה {'בטווח' if in_range else 'מחוץ לטווח (OOS)'}.")
            category = "range_reasoning"

        records.append({
            "question": question,
            "expected_answer": answer,
            "expected_sample_id": s["sample_id"],
            "category": category,
        })

    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"נכתב: {path} ({len(records)} שאלות)")
    return records


if __name__ == "__main__":
    samples = generate_samples(n_samples=200, oos_rate=0.08)
    write_samples_csv(samples)
    write_reference_ranges_csv()
    build_golden_dataset(samples, n_questions=40)

    n_oos = sum(1 for s in samples if s["status"] == STATUS_OOS)
    print(f"\nסיכום: {len(samples)} דגימות, מתוכן {n_oos} חריגות (OOS) - "
          f"{n_oos/len(samples)*100:.1f}%")
