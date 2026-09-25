# 🇿🇼 Zimbabwe VAT Return Automation & Explainable VAT System

A **Streamlit** application that turns raw, multi-currency business transactions
into a **fully explained, auditable, ZIMRA-style VAT 7 return** — with
**ZiG and USD schedules always kept separate**, live exchange rates, graphical
storytelling, validation, a manual entry tablet, management reporting and
email/WhatsApp sharing.

> [EDUCATIONAL / DEMONSTRATION SYSTEM ONLY — error messages are simulated
> fixtures used to demonstrate, validate and prove the VAT engine. No real
> taxpayer data is required, expected or used.]

---

## 1. What it does — the 9 step workflow

**LEARN → ENTER → CHECK → CONVERT → CALCULATE → EXPLAIN → VISUALISE → AUDIT → REPORT**

1. **LEARN** — an embedded VAT module explains output/input VAT, zero-rated vs
   exempt supplies, reverse charge, imports and taxation in simple English, and
   a 10-question quiz tests the user.
2. **ENTER** — three ways to get data in: demo datasets (4), CSV/Excel upload
   (column aliases accepted), or a **manual transaction tablet** with a friendly
   per-row entry form.
3. **CHECK** — every transaction is validated (PASS / REVIEW / FAIL) with the
   reason, the impact on VAT, and how to fix it.
4. **CONVERT** — foreign currencies are converted at the **live** rate (ZWG/USD
   via open.er-api.com shadowing the RBZ official rate), with a manual RBZ
   override and — crucially — the rate, source and date shown on **every**
   affected audit row.
5. **CALCULATE** — a fully segregated, 13-line VAT 7 schedule is computed for
   **each currency used** (ZiG and USD schedules are never mixed, per ZIMRA).
   ZAR transactions are converted into the USD schedule.
6. **EXPLAIN** — every important number is built in front of the user:
   formula → values used → substitution → answer → plain-English explanation →
   rule → PASS/FAIL status.
7. **VISUALISE** — charts for sales by category, output vs input, net VAT by
   currency, monthly output vs input and PASS/REVIEW/FAIL — each chart carrying
   its own explanation (“what is happening”, “why it matters”, Grade-7 English).
8. **AUDIT** — a complete audit/calculation trail: every transaction with its
   side, schedule, FX conversion, VAT calculation shown as maths, PASS/FAIL
   status, reason, reference and whether a supporting document exists.
9. **REPORT** — a professional management summary (per-currency and combined),
   downloadable as Markdown, **emailed** via SMTP (Streamlit secrets) and
   **shared via WhatsApp** with a one-click wa.me deep link.

## 2. Live exchange rates

- Source: `https://open.er-api.com/v6/latest/USD` — returns the **ZWG** (ZiG)
  and **ZAR** rates per USD (free, no API key).
- The feed is cached (6h) in `.fx_rates_cache.json`, refreshed at most every
  6 hours, hard-capped at 8 s worst case, and can be forced offline with the
  `FX_DISABLE_NETWORK=1` environment variable (used by the test suite).
- A **manual official RBZ ZiG rate** field overrides the live ZiG/USD feed.
- **If a rate cannot be obtained the affected transactions FAIL explicitly** —
  the engine never applies a silent or assumed rate.

## 3. The engine (production-quality, tested)

| Module | Responsibility |
|---|---|
| `vat_engine.py` | Normalisation, per-currency `Schedule` objects, 13-line schedules, output/input VAT, adjustments, reverse charge, imports, apportionment, de-minimis checks, audit/calculation trail, PASS/REVIEW/FAIL statuses, management summary. |
| `validation.py` | Data checks and column alias normalisation (e.g. “Transaction ID”, “Amount (USD)” map automatically), PASS/FAIL with reason + financial impact + fix. |
| `exchange_rates.py` | Live/cached rates, conversion, cross-rates, rate table, source labels. |
| `explanations.py` | Learn-VAT content, rules, Grade-7 explanations, calculation block renderers. |
| `graphs.py` | Plotly charts, each with a “what / why / Grade-7” explanation. |
| `report_generator.py` | Professional Markdown report + share text. |
| `share.py` | SMTP email (Streamlit secrets `[smtp]`) + WhatsApp `wa.me` link. |
| `sample_data.py` | 4 fictional datasets (incl. the worked example and deliberately broken one). |
| `test_suite.py` | TC01–TC21 shared by pytest **and** the in-app “Test Cases” page. |
| `app.py` | The Streamlit front end. |

## 4. Multi-currency: ZIMRA’s separation rule

> **ZiG and USD schedules are computed and shown completely separately. They
> are never mixed on one schedule.** ZAR is converted into the USD schedule.

- You will always see a **ZiG schedule** and a **USD schedule** as two distinct
  tabs, each with its own 13 lines and its own PAYABLE / REFUNDABLE / NIL
  conclusion.
- A combined (informational) “ZiG-equivalent” view is offered purely for
  management understanding and is labelled **“never used to file”**.

## 5. The 13-line VAT 7 schedule

| Line | Description | Fill |
|---|---|---|
| 1 | Total value of supplies / sales | ✔ |
| 2 | Output tax on standard-rated supplies | ✔ |
| 3 | Adjustments (credit/debit notes, bad-debt relief) | ✔ |
| 4 | Reverse charge output tax (imported services) | ✔ |
| 5 | Total output tax payable (2+3+4) | auto |
| 6 | Input tax – local purchases | ✔ |
| 7 | Input tax – imports of goods | ✔ |
| 8 | Reverse charge input tax (imported services) | ✔ |
| 9 | Apportionment disallowance (mixed supplies) | ✔ |
| 10 | Total input tax allowable (6+7+8+mixed minus 9) | auto |
| 11 | Net VAT payable / refundable (5−10) | auto |
| 12 | Status | auto |
| 13 | VAT due for the period | auto |

## 6. Worked example (Amber Mart — ZiG, single-currency)

A retailer files its VAT 7 in ZiG for the tax period:

| Date | Description | Amount (ZiG) | Treatment |
|---|---|---|---|
| 2026-01-05 | Standard sales – cash | 20,000 | output VAT = 3,412.07 (inclusive) |
| 2026-01-12 | Standard sales – credit | 10,000 | output VAT = 1,354.55 (inclusive) |
| 2026-01-20 | Standard sales – POS | 4,250 | output VAT = 575.88 (inclusive) |
| 2026-01-18 | Credit note issued | −1,020 | reduces output VAT by 180.00 |
| 2026-01-05 | Imported software service (RC) | 2,000 | reverse charge: output = input = 300.00 |
| 2026-01-10 | Purchase: totems (barcodes) | 800 | input VAT 104.00 |
| 2026-01-22 | Purchase: office shelving | 1,900 | input VAT 247.00 |
| 2026-01-28 | Purchase: promotional citrus | 1,310 | input VAT 170.30 |

Net position = **792.50 payable** (+55.71 ZiG from a mixed-supply recovery).
Load the “Amber Mart” demo file to see every line of this example recomputed.

## 7. Legal & computational assumptions

See **`docs/LEGAL_ASSUMPTIONS.md`** for the complete list with sources:
15.5% rate, US$25,000 registration threshold, US$10 invoicing de minimis, 5%
input-tax apportionment de minimis, reverse charge, 12-month input claim limit,
small refunds, and due dates. **Official sources** are also listed in the app’s
“Assumptions & Sources” page.

## 8. Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

Run the test suite:

```bash
python -m pytest tests/ -q
```

(Set `FX_DISABLE_NETWORK=1` to run fully offline.)

### Email sharing (optional)

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in
your SMTP details. Without it every other feature still works.

## 9. Deploy on Streamlit Cloud (free)

1. Push this folder to a GitHub repository (see §10).
2. Go to https://share.streamlit.io (or streamlit.io → Create app).
3. Point it at the repo, main branch, file **`app.py`**.
4. Deploy. The live exchange-rate feed and everything else works with no keys —
   only email sharing (optional) requires secrets.

## 10. Push to GitHub from this machine

`git` is currently **not installed** on this machine. Either install Git for
Windows, or use the GitHub web upload:

```bash
# after installing Git:
git init
git add .
git commit -m "Zimbabwe VAT Return Automation & Explainable VAT System"
git branch -M main
git remote add origin https://github.com/<YOU>/<REPO>.git
git push -u origin main
```

---

## Disclaimer

EDUCATIONAL / DEMONSTRATION SYSTEM ONLY — SIMULATED FIXTURE AND DATA. Nothing
here is legal advice; confirm all rates, thresholds, treatments and due dates
with ZIMRA and a qualified tax professional before filing.

*Project developed September 2026. All sample data is fictional.*