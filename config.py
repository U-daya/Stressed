"""
config.py -- Questionnaire definition and project settings.

IE 320 Engineering Statistics, Group 12 -- "What Makes People Stressed?"

Everything the group may want to change (question wording, department list,
classification threshold, significance level) lives here, so the rest of the
code never needs editing.
"""

# ---------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------
APP_TITLE = "RU Stressed?"
GROUP_NAME = "IE 320 Group 12"
ALPHA = 0.05                 # significance level used in every test
STRESS_THRESHOLD = 50.0      # Stress Index >= this -> "Under Stress"

# Project requirements (Project + Exam II option)
REQ_TOTAL_N = 150
REQ_MIN_DEPTS = 4
REQ_PER_DEPT = 30

# Departments (Q1 choices). "Other" is collected but excluded from the
# between-department comparisons because it is not a single department.
DEPARTMENTS = [
    "Engineering (SOE)",
    "Arts & Sciences (SAS)",
    "Business (RBS)",
    "Environmental & Biological Sciences (SEBS)",
    "Pharmacy (EMSOP)",
    "Nursing",
    "Other",
]
OTHER_DEPT = "Other"

# ---------------------------------------------------------------------------
# The 10-question questionnaire
#   kind = "category" | "scale" | "number"
#   role = "group"   -> grouping variable (department)
#          "stress"  -> builds the Stress Index (response variable)
#          "factor"  -> candidate contributing factor (predictor)
# ---------------------------------------------------------------------------
LIKERT_FREQ = ["Never", "Rarely", "Sometimes", "Often", "Very often"]          # 1..5
LIKERT_AGREE = ["Not at all", "A little", "Moderately", "Quite a bit", "Extremely"]  # 1..5
LIKERT_QUALITY = ["Very poor", "Poor", "Fair", "Good", "Excellent"]                 # 1..5

QUESTIONS = [
    dict(key="q1_dept", num=1, kind="category", role="group",
         text="Which academic school/department is your major in?",
         options=DEPARTMENTS, short="Department"),

    dict(key="q2_stress", num=2, kind="scale", role="stress",
         text="Over the past two weeks, how would you rate your overall stress level?",
         lo=1, hi=10, lo_label="1 = no stress", hi_label="10 = extreme stress",
         short="Self-rated stress (1-10)"),

    dict(key="q3_overwhelm", num=3, kind="scale", role="stress",
         text="Over the past two weeks, how often have you felt overwhelmed or unable "
              "to cope with everything you had to do?",
         lo=1, hi=5, labels=LIKERT_FREQ, short="Feeling overwhelmed (1-5)"),

    dict(key="q4_sleep", num=4, kind="number", role="factor",
         text="On average, how many hours of sleep do you get per night?",
         lo=0.0, hi=14.0, step=0.5, default=7.0, unit="hours/night",
         short="Sleep (hrs/night)"),

    dict(key="q5_credits", num=5, kind="number", role="factor",
         text="How many credits are you taking this semester?",
         lo=0, hi=24, step=1, default=15, unit="credits", integer=True,
         short="Course load (credits)"),

    dict(key="q6_study", num=6, kind="number", role="factor",
         text="About how many hours per week do you spend studying or doing "
              "coursework OUTSIDE of class?",
         lo=0.0, hi=80.0, step=1.0, default=15.0, unit="hours/week",
         short="Study (hrs/week)"),

    dict(key="q7_exercise", num=7, kind="number", role="factor",
         text="On how many days per week do you exercise or work out for at least 30 minutes?",
         lo=0, hi=7, step=1, default=2, unit="days/week", integer=True,
         short="Exercise (days/week)"),

    dict(key="q8_nutrition", num=8, kind="scale", role="factor",
         text="How would you rate your eating habits (regular, balanced meals)?",
         lo=1, hi=5, labels=LIKERT_QUALITY, short="Nutrition (1-5)"),

    dict(key="q9_finance", num=9, kind="scale", role="factor",
         text="How much do money or financial concerns (tuition, rent, bills) worry you?",
         lo=1, hi=5, labels=LIKERT_AGREE, short="Financial worry (1-5)"),

    dict(key="q10_age", num=10, kind="number", role="factor",
         text="What is your age?",
         lo=16, hi=60, step=1, default=20, unit="years", integer=True,
         short="Age (years)"),
]

Q = {q["key"]: q for q in QUESTIONS}
DEPT_COL = "q1_dept"
STRESS_ITEMS = [q["key"] for q in QUESTIONS if q["role"] == "stress"]
FACTORS = [q["key"] for q in QUESTIONS if q["role"] == "factor"]
SHORT = {q["key"]: q["short"] for q in QUESTIONS}
SHORT["stress_index"] = "Stress Index (0-100)"

# Column order in the stored dataset
COLUMNS = ["timestamp", "response_id"] + [q["key"] for q in QUESTIONS] + [
    "stress_index", "classification"]


# ---------------------------------------------------------------------------
# Stress Index and classification rule
# ---------------------------------------------------------------------------
def stress_index(q2_stress: float, q3_overwhelm: float) -> float:
    """
    Stress Index (SI), 0-100.

    Each stress item is rescaled to 0-1 by min-max scaling and the two are
    averaged with equal weight:

        SI = 100 * [ (Q2 - 1)/9  +  (Q3 - 1)/4 ] / 2

    0  = lowest possible answer on both items (no stress, never overwhelmed)
    50 = exactly the midpoint of both scales
    100 = highest possible answer on both items
    """
    a = (float(q2_stress) - 1.0) / 9.0
    b = (float(q3_overwhelm) - 1.0) / 4.0
    return round(100.0 * (a + b) / 2.0, 2)


def classify(si: float) -> str:
    """Under Stress if SI >= 50 (answers sit at or above the scale midpoints)."""
    return "Under Stress" if si >= STRESS_THRESHOLD else "Stress-Free"
