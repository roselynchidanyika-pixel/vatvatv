# LEGAL & COMPUTATIONAL ASSUMPTIONS — ZIMBABWE VAT 7 RETURN AUTOMATION SYSTEM

This document records every legal and computational assumption implemented in
the system, the legal source relied on, and the date it applies from. It is
maintained for transparency: every number produced by the app can be traced to
an assumption below and, in turn, to a source.

> **[DISCLAIMER]** This is an educational/demonstration system. It does **not**
> replace professional tax advice or the ZIMRA TaRMS online-filing platform.
> ZIMRA guidance changes over time — always confirm rates, thresholds and due
> dates against current ZIMRA practice before filing.

---

## 1. Standard VAT rate

| Item | Value |
|---|---|
| Standard rate | **15.5%** |
| Effective from | 1 January 2026 |
| Source | Finance Act (No. 7) of 2025 (gazetted 29 December 2025); ZIMRA Public Notice 07 of 2026. |

Implementation note: tax-exclusive VAT is `amount × 15.5%`. Tax-inclusive VAT
(VAT-inclusive prices) uses the fraction `15.5/115.5` = 0.1341991... rounded to
2 decimals (`VAT_FRACTION` in `config.py`).

## 2. Zero-rated and exempt supplies

- **Zero-rated supplies** (0% output VAT, input VAT still claimable): exports and
  supplies specified in the VAT Act (Chapter 23:12) Second Schedule.
- **Exempt supplies** (no output VAT, generally no input VAT credit): specified
  in the VAT Act Second Schedule; e.g. certain financial services and
  residential accommodation.
- The app uses the categories `standard`, `zero_rated`, and `exempt` (plus
  `export`, treated as zero-rated for sale purposes).

## 3. Compulsory registration threshold

| Item | Value |
|---|---|
| Threshold | **US$25,000** taxable supplies in any 12-month period (or ZiG equivalent) |
| Effective from | 1 January 2024 |
| Source | VAT Act [Chapter 23:12], read with the Finance Act (No. 13) of 2023. |

## 4. Invoicing de minimis (fiscal invoice threshold)

| Item | Value |
|---|---|
| Threshold | **US$10 per invoice** (or ZiG equivalent) |
| Effective from | 1 September 2022 |
| Source | VAT Act s20; VAT (General) Regulations; ZIMRA guidance on fiscal invoices. |
| Effect | A sale below US$10 does **not** require a fiscal invoice. **It is NOT automatically exempt** — the VAT treatment of the supply is still determined normally (a US$8 standard-rated supply still attracts output VAT; it simply need not be recorded on a fiscal invoice). |

## 5. Input-tax apportionment de minimis (mixed / overhead supplies)

| Item | Value |
|---|---|
| De minimis | Exempt supplies **≤ 5%** of total turnover |
| Effect | If exempt supplies ≤ 5%, the registered operator may reclaim **all** input tax on mixed (overhead) supplies. Above 5%, input tax on mixed supplies is apportioned by the ratio `taxable turnover / total turnover` and the disallowed portion is added to line 9 of the return. |
| Source | Input-tax credit rules (VAT Act s16) and current ZIMRA practice. |

## 6. Reverse charge (imported services)

- Imported services fall under the reverse charge (VAT Act s13A).
- When the (estimated) VAT on the imported service would exceed the monetary
  threshold in force, the operator must self-assess:
  - **Output side (line 4 of the schedule)**: VAT charged as if it supplied the
    service itself, and
  - **Mirror input side (line 8)**: the same amount as a notional input credit
    (subject to normal deduction rules and the apportionment rules above).
- The app records both sides of the reverse-charge with the identical amount and
  a clear explanation.

## 7. Imported goods (customs-cleared imports)

- Input VAT on imported goods is the VAT paid at the point of importation.
- The app computes import VAT on (customs value + customs duty) at the 15.5%
  rate (or on `amount` when only the amount is supplied), unless a
  `vat_account_vat` value is provided, in which case that value is used as
  stated.
- Currency conversion of import values follows the rules in section 9.

## 8. Time limit for claiming (physical evidence)

- Input VAT must be claimed within **12 months** of the date of the invoice /
  import document (VAT Act s16; ZIMRA guidance). The app records this 12-month
  limit as an audit note.

## 9. Currency rules — the heart of multi-currency VAT

| Rule | Detail |
|---|---|
| ZiG vs USD separation | **ZIMRA requires ZiG and USD schedules to be prepared and filed separately. They are never mixed on one schedule.** The app computes a fully separate 13-line schedule for each currency actually used. |
| ZAR treatment | ZAR-transactions are converted into the **USD schedule** at the applicable exchange rate (per ZIMRA practice for foreign currencies). |
| Conversion rate | The exchange rate applicable at the time of the transaction. Where no transaction-specific rate is supplied, the app uses the current/live rate snapshot and **states so on the audit trail**. |
| FX of the day | The app uses the **live** open.er-api.com feed (ZWG per USD) shadowing the RBZ official rate, with a manual RBZ override field. The rate actually applied — and its source and date — is shown on **every** affected audit-trail row. Rate source is never silent. |
| No rate, no VAT | If a rate is unavailable for a required conversion, the row is FAILed with the explicit reason "exchange rate unavailable" — never an assumed or silent rate. |

## 10. Due dates (SI 81 of 2025 notes)

| Item | Value |
|---|---|
| Return (VAT 7) | Due by the **10th** day of the month after the tax period. |
| Payment | Due by the **15th** day of the month after the tax period. |
| Note | Confirm with ZIMRA notices; periods/due dates are configurable in `config.py`. |

## 11. Small refunds

- Refunds below **US$60** (or ZiG equivalent) are normally **held as credit** by
  ZIMRA rather than refunded to the bank (VAT Act s54 read with current
  guidance). The management summary notes this.

## 12. Computations — mathematical formulas

- **Standard sale (exclusive):** `Output = Amount × 15.5%`
- **Standard sale (inclusive):** `Zimbabwe = Amount × (15.5 / 115.5)`
- **Import of goods:** `VAT = (Customs value + Customs duty) × 15.5%` (or stated
  `vat_account_vat` if provided)
- **Reverse charge:** `Output = Service value × 15.5%` AND `Mirror input = same`
- **Adjustment credit note:** reduces output VAT (`out_adj` negative)
- **Adjustment debit note:** increases output VAT (`out_adj` positive)
- **Apportionment:** `Recoverable = Mixed × (Taxable turnover / Total turnover)`;
  `Disallowed = Mixed − Recoverable`
- **Schedule totals:**
  - `Line 5  = Line 2 + Line 3 + Line 4`
  - `Line 10 = Line 6 + Line 7 + Line 8 + Mixed recovered − Line 9`
  - `Line 11 = Line 5 − Line 10`
- **Line 13** = |line 11| (the VAT due for the period).
- All arithmetic is performed in exact `Decimal`, rounded to 2 decimal places
  only at the point of writing the audit trail.

## 13. Data / sample files

All sample data files are synthetic (fictional businesses: Amber Mart, Veritas
Wholesale, Tri-Currency Traders, QA-demo). None contain real taxpayer
information. The Amber Mart file reproduces the worked example in the README.

---

*Reviewed: 25 September 2026. See `config.py` for the machine-readable values
and `README.md` for the full source list.*