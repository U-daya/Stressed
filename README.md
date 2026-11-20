# RU Stressed?: IE 320 Group 12 (Vercel version)

Web application for the IE 320 Engineering Statistics group project *"What Makes People Stressed?"*
(Project + Exam II option). Team: **Udaya Raja (leader)**, Dhruv Nagpal, Akshita Krishnakumar, Poorvi Shekar.

| Page | What it does |
|---|---|
| `/` **Take the Survey** | The 10 questions. Each response is saved, and the student instantly sees **Under Stress** or **Stress-Free** |
| `/results` **Results & Analysis** | Every statistical analysis, recomputed live from all responses, with tables and charts |
| `/methodology` | Questionnaire, classification rule, and methods |
| `/admin` **Team / Admin** | Password-protected CSV download of the dataset |

---

## Deploy to Vercel (about 10 minutes, free)

You need a GitHub account and a Vercel account (sign up at vercel.com **with GitHub**).

### 1. Put the code on GitHub
1. On github.com click **New repository**, name it `ie320-stress-survey`, choose **Public**, and click **Create**.
2. Click **uploading an existing file**, drag in **everything inside this folder**
   (`api/`, `public/`, `tests/` and all the `.py`, `.json` and `.txt` files), then click **Commit changes**.

### 2. Import it into Vercel
1. On vercel.com click **Add New… → Project**, then **Import** next to `ie320-stress-survey`.
2. Leave **Framework Preset = Other** and the other settings as they are.
3. Open **Environment Variables** and add  
   `ADMIN_PASSWORD` = a password your team chooses (protects the CSV download).
4. Click **Deploy**. The first deploy takes 1–2 minutes.

### 3. Add the database
1. In the new project, open the **Storage** tab, click **Create Database**, choose **Neon** (Serverless Postgres),
   pick the **Free** plan and a US East region, and click **Create / Connect** to this project.  
   This adds a `DATABASE_URL` environment variable automatically.
2. Go to **Deployments**, open the **⋯** menu on the latest deployment, and click **Redeploy**
   (environment variables only take effect after a redeploy).

### 4. Check it
1. Open `https://<your-project>.vercel.app/api/health`. It should show `"ok": true, "storage": "Postgres database"`.
2. Submit one test response on the survey page, then check `/results`.
3. **Delete your test responses before you share the link:** in Vercel → **Storage** → your Neon database →
   **Open in Neon** → **SQL Editor**, run `DELETE FROM responses;`.
4. Share `https://<your-project>.vercel.app` (you can rename the project in Settings to get a nicer URL).

If anything shows an error: Vercel → your project → **Logs** shows the exact message.

---

## The questionnaire (edit in `config.py` only, before collecting data)

| # | Question | Scale | Role |
|---|---|---|---|
| Q1 | Which academic school/department is your major in? | SOE, SAS, RBS, SEBS, Pharmacy, Nursing, Other | Grouping |
| Q2 | Over the past two weeks, how would you rate your overall stress level? | 1 (no stress) – 10 (extreme) | Stress |
| Q3 | Over the past two weeks, how often have you felt overwhelmed or unable to cope? | 1 Never – 5 Very often | Stress |
| Q4 | Average hours of sleep per night | 0–14 | Factor |
| Q5 | Credits this semester | 0–24 | Factor |
| Q6 | Hours per week studying outside class | 0–80 | Factor |
| Q7 | Days per week exercising ≥ 30 min | 0–7 | Factor |
| Q8 | Eating habits (regular, balanced meals) | 1 Very poor – 5 Excellent | Factor |
| Q9 | How much financial concerns worry you | 1 Not at all – 5 Extremely | Factor |
| Q10 | Age | years | Factor |

**Classification:** `Stress Index SI = 100 × [ (Q2 − 1)/9 + (Q3 − 1)/4 ] / 2`; **Under Stress if SI ≥ 50**,
otherwise Stress-Free. 50 is where both answers sit at the middle of their scales.

## Statistical methods (α = 0.05)

| Research question | Method(s) |
|---|---|
| RQ1 Overall stress | x̄, s, p̂; t-CI for μ; χ²-CI for σ²; one-sample t test (H₀: μ = 50); z-CI and z test for the proportion Under Stress |
| RQ2 Department differences | Single-factor ANOVA, department means with pooled-variance CIs, Tukey HSD |
| RQ3 Strongest factors | Correlation t tests; multiple linear regression (F test, coefficient t tests, CIs, standardized β, VIF, residual plots) |
| RQ4 Factors by department | Partial (extra-sum-of-squares) F test of factor × department interactions; within-department correlations and regressions; ANOVA on each factor |
| RQ5 Significance | ANOVA F test, χ² test of independence, Bartlett/Levene, Kruskal–Wallis |

## Files

| File | Purpose |
|---|---|
| `config.py` | Questions, departments, Stress Index formula, threshold, α |
| `stats_engine.py`, `ols.py` | All statistics. `ols.py` is least-squares regression in plain numpy (textbook matrix formulas); `tests/check_against_statsmodels.py` confirms it matches statsmodels exactly |
| `storage.py` | Saves and loads responses (Postgres on Vercel, CSV on a laptop) |
| `views.py`, `charts.py` | Builds the results page content and charts |
| `api/index.py` | Backend API (FastAPI): `/api/questions`, `/api/submit`, `/api/results`, `/api/export`, `/api/health` |
| `public/` | The web pages (HTML/CSS/JS + plotly.js) |
| `report_analysis.py` | Makes the report figures and tables from the downloaded CSV |
| `dev_server.py` | Runs the whole app on your own computer |
| `tests/make_test_data.py` | **Fake** data for testing only. Never put it in the report |

## Making the report figures and tables
1. On `/admin`, enter the team password and download the CSV.
2. On your computer:
   ```bash
   pip install -r requirements-report.txt
   python report_analysis.py stress_survey_responses.csv
   ```
   `report_output/` will contain 8 figures (300 dpi), every table as CSV, and `results_summary.md` with all test statistics.

## Running locally (optional)
```bash
pip install -r requirements-report.txt
python dev_server.py        # http://localhost:8000, saves to data/responses.csv
```
