"""
FAKE data for TESTING THE CODE ONLY. Never use these numbers in the report.
Usage: python tests/make_test_data.py out.csv 180
"""
import sys, uuid
import numpy as np, pandas as pd
sys.path.insert(0, ".")
import config as C

out = sys.argv[1] if len(sys.argv) > 1 else "tests/FAKE_test_data.csv"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 180
rng = np.random.default_rng(320)
depts = rng.choice(C.DEPARTMENTS[:4] + ["Other"], n, p=[.25, .25, .22, .22, .06])
shift = {"Engineering (SOE)": 1.0, "Arts & Sciences (SAS)": 0, "Business (RBS)": .3,
         "Environmental & Biological Sciences (SEBS)": -.3, "Other": 0}
rows = []
for dpt in depts:
    sleep = np.clip(np.round(rng.normal(6.8, 1.1) * 2) / 2, 3, 11)
    credits = int(np.clip(rng.normal(15.5, 2), 9, 21))
    study = float(np.clip(np.round(rng.normal(14 + 3 * (dpt == "Engineering (SOE)"), 6)), 0, 50))
    ex = int(rng.integers(0, 8))
    nut = int(rng.integers(1, 6))
    fin = int(rng.integers(1, 6))
    age = int(np.clip(rng.normal(20, 1.4), 17, 28))
    lat = (5 + shift[dpt] - 0.6 * (sleep - 7) + 0.08 * (study - 14) - 0.2 * (ex - 3)
           - 0.25 * (nut - 3) + 0.5 * (fin - 3) + 0.1 * (credits - 15) + rng.normal(0, 1.3))
    q2 = int(np.clip(round(lat + 0.5), 1, 10))
    q3 = int(np.clip(round(1 + (lat - 1) / 9 * 4 + rng.normal(0, .6)), 1, 5))
    si = C.stress_index(q2, q3)
    rows.append(dict(timestamp="2026-11-20 12:00:00", response_id=uuid.uuid4().hex[:10],
                     q1_dept=dpt, q2_stress=q2, q3_overwhelm=q3, q4_sleep=sleep, q5_credits=credits,
                     q6_study=study, q7_exercise=ex, q8_nutrition=nut, q9_finance=fin, q10_age=age,
                     stress_index=si, classification=C.classify(si)))
pd.DataFrame(rows, columns=C.COLUMNS).to_csv(out, index=False)
print("wrote", out, n)
