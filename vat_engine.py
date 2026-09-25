"""vat_engine.py — Core Zimbabwe VAT calculation engine (explainable).

Computes a Zimbabwe VAT 7 return from accounting transactions and produces:
  * per-currency SEPARATE schedules (ZiG and USD are never mixed — ZIMRA rule)
  * output VAT, allowable input VAT, adjustments, imports, reverse charge
  * turnover apportionment with the 5% de minimis rule
  * invoicing de minimis check (US$10/US$50-RaZ threshold — does NOT exempt)
  * a per-row PASS / REVIEW / FAIL audit trail with the formula, values,
    substitution, answer, explanation and rule for every number.

The engine is pure Python/pandas — it does NOT import streamlit — so the same
code is used by the web app, the report generator and the pytest suite.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

import config
import exchange_rates as fx
from explanations import RULES

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
CURRENCY_ALIASES = {
    "USD": "USD", "US$": "USD", "DOL": "USD", "DOLLAR": "USD",
    "ZIG": "ZIG", "ZWG": "ZIG", "ZW$": "ZIG", "ZWL": "ZIG", "ZIG$": "ZIG",
    "ZAR": "ZAR", "R": "ZAR", "RAND": "ZAR",
}
CATEGORY_ALIASES = {
    "standard": "standard", "std": "standard", "standard rated": "standard",
    "standard-rated": "standard", "taxable": "standard",
    "zero rated": "zero_rated", "zero-rated": "zero_rated", "zero": "zero_rated",
    "zero_rated": "zero_rated", "0%": "zero_rated", "export": "export",
    "exports": "export", "exempt": "exempt", "exempted": "exempt",
    "prohibited": "prohibited", "entertainment": "prohibited",
    "mixed": "mixed", "mixed supply": "mixed", "mixed supplies": "mixed",
    "import_goods": "import_goods", "imported goods": "import_goods",
    "import goods": "import_goods", "import": "import_goods",
    "imported_service": "imported_service", "imported service": "imported_service",
    "import services": "imported_service", "reverse charge": "imported_service",
}
DIRECTION_ALIASES = {
    "sale": "sale", "sales": "sale", "standard sale": "sale",
    "purchase": "purchase", "purchases": "purchase", "local purchase": "purchase",
    "expense": "purchase", "buy": "purchase",
    "import_goods": "import_goods", "import goods": "import_goods",
    "import": "import_goods", "imported goods": "import_goods",
    "imported_service": "imported_service", "imported service": "imported_service",
    "service import": "imported_service",
    "adjustment": "adjustment", "adjustments": "adjustment",
    "credit note": "adjustment", "debit note": "adjustment",
}
ADJUSTMENT_TYPES = {
    "credit_note": "credit_note", "credit": "credit_note",
    "credit_note": "credit_note", "discount": "credit_note",
    "debit_note": "debit_note", "debit": "debit_note",
    "bad_debt_relief": "bad_debt_relief", "bad debt": "bad_debt_relief",
    "prior_period_correction": "prior_period_correction",
    "prior period": "prior_period_correction",
}

TRAIL_COLUMNS = [
    "txn_id", "date", "description", "counterparty", "side", "category",
    "currency", "schedule", "amount", "fx_rate", "fx_source", "fx_date",
    "fx_math", "converted_amount", "vat_rate", "vat_amount", "vat_math",
    "explanation", "grade7", "status", "reason", "reference",
    "invoice_number", "supporting_document",
]


def r2(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _norm_text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(value)
    return re.sub(r"\s+", " ", s).strip()


def _norm_currency(value, default="ZIG"):
    v = _norm_text(value).upper()
    if not v:
        return default
    return CURRENCY_ALIASES.get(v, default)


def _norm_category(value):
    v = _norm_text(value).lower()
    if not v:
        return "standard"
    return CATEGORY_ALIASES.get(v, "standard")


def _norm_direction(value):
    v = _norm_text(value).lower()
    if not v:
        return ""
    return DIRECTION_ALIASES.get(v, value.strip().lower())


def _norm_adjustment(value):
    v = _norm_text(value).lower()
    return ADJUSTMENT_TYPES.get(v, v)


def _num(value, default=Decimal("0")):
    if value is None or value == "":
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return Decimal(str(value).replace(",", "").replace(" ", ""))
    except Exception:
        return default


def _bool(value):
    if value is True or value == 1:
        return True
    s = _norm_text(value).upper()
    return s in ("TRUE", "1", "YES", "Y", "PASS", "AVAILABLE", "AVAIL")


def _pct(value, default=100):
    v = _num(value, None)
    if v is None:
        return Decimal("100")
    if v > 1:                       # stored as 70 -> 70%
        v = v / Decimal("100")
    return min(Decimal("1"), max(Decimal("0"), v))


def _date_month(date_val):
    s = _norm_text(date_val)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            d = datetime.strptime(s[:10] if len(s) > 10 else s, fmt)
            return f"{d.year}-{d.month:02d}"
        except Exception:
            continue
    return "unknown"


# ---------------------------------------------------------------------------
# De minimis INVOICING check (Rule A — note it does NOT exempt the supply)
# ---------------------------------------------------------------------------
def _invoice_deminimis(converted_usd):
    """Return (pass: bool, note: str) for the US$10 invoicing de minimis."""
    if converted_usd is None:
        return False, "Invoicing de minimis check: amount unavailable."
    if Decimal(str(converted_usd)) < config.DE_MINIMIS_INVOICE_USD:
        return True, (
            f"Below the US${float(config.DE_MINIMIS_INVOICE_USD):,.2f} invoicing "
            "de minimis — no fiscal invoice required. This does NOT make the "
            "transaction exempt; its VAT treatment is still determined "
            "separately.")
    return False, (
        f"Amount is US$ {converted_usd:,.2f}, at/above the "
        f"US${float(config.DE_MINIMIS_INVOICE_USD):,.2f} de minimis — normal "
        "invoicing rules apply.")


# ---------------------------------------------------------------------------
# Schedule (13-line ZIMRA VAT 7) builder
# ---------------------------------------------------------------------------
SCHEDULE_LINES = [
    ("1", "Total value of supplies / sales"),
    ("2", "Output tax on standard-rated supplies"),
    ("3", "Adjustments (credit/debit notes, bad-debt relief)"),
    ("4", "Reverse charge output tax (imported services)"),
    ("5", "Total output tax payable (2+3+4)"),
    ("6", "Input tax - local purchases"),
    ("7", "Input tax - imports of goods"),
    ("8", "Reverse charge input tax (imported services)"),
    ("9", "Apportionment disallowance (mixed supplies)"),
    ("10", "Total input tax allowable (6+7+8 + mixed recovered -9)"),
    ("11", "Net VAT payable / refundable (5-10)"),
    ("12", "Status"),
    ("13", "VAT due for the period"),
]


class Schedule:
    """One fully-segregated per-currency VAT schedule."""

    def __init__(self, currency):
        self.currency = currency
        self.std = Decimal("0")
        self.zr = Decimal("0")
        self.ex = Decimal("0")
        self.out_std = Decimal("0")
        self.out_adj = Decimal("0")
        self.rc_out = Decimal("0")
        self.in_local = Decimal("0")
        self.in_import = Decimal("0")
        self.rc_in = Decimal("0")
        self.mixed = Decimal("0")
        self.mixed_deductible = Decimal("0")
        self.disallowed = Decimal("0")
        self.exempt_share = Decimal("0")
        self.de_minimis_applied = False
        self.apport_note = ""

    # -- totals --------------------------------------------------------------
    @property
    def total_output(self):
        return self.out_std + self.out_adj + self.rc_out

    @property
    def total_input(self):
        return self.in_local + self.in_import + self.rc_in + self.mixed_deductible

    @property
    def net(self):
        return self.total_output - self.total_input

    @property
    def status(self):
        if self.net > 0:
            return "PAYABLE"
        if self.net < 0:
            return "REFUNDABLE"
        return "NIL"

    @property
    def sales_value(self):
        return self.std + self.zr + self.ex

    def taxable_value(self):
        return self.std + self.zr

    # -- apportionment -------------------------------------------------------
    def run_apportionment(self, de_minimis=True):
        if self.mixed > 0 and (self.std + self.zr) == 0 and self.ex == 0:
            self.mixed_deductible = self.mixed
        if self.ex > 0 and self.mixed > 0:
            total = self.sales_value
            if total <= 0:
                return
            self.exempt_share = self.ex / total
            if de_minimis and self.exempt_share <= config.DE_MINIMIS_APPORTIONMENT_PCT:
                self.de_minimis_applied = True
                self.mixed_deductible = self.mixed
                self.apport_note = config.DE_MINIMIS_APPORTIONMENT_NOTE.format(
                    share=self.exempt_share * 100)
            else:
                ratio = self.taxable_value() / total
                self.disallowed = r2(self.mixed * (Decimal("1") - ratio))
                self.mixed_deductible = self.mixed - self.disallowed
                self.apport_note = (
                    f"Exempt supplies = {self.exempt_share * 100:.2f}% of total "
                    f"turnover (> 5%). Mixed input tax apportioned: recovery "
                    f"ratio {ratio * 100:.2f}%; disallowed "
                    f"{self.disallowed:,.2f} {self.currency}.")

    # -- 13-line confirmation ------------------------------------------------
    def lines(self):
        net = self.net
        out = self.total_output
        rows = [
            ("1", "Total value of supplies / sales", self.sales_value, False),
            ("2", "Output tax on standard-rated supplies", self.out_std, False),
            ("3", "Adjustments (credit/debit notes, bad-debt relief)", self.out_adj, True),
            ("4", "Reverse charge output tax (imported services)", self.rc_out, False),
            ("5", "Total output tax payable (2+3+4)", out, True),
            ("6", "Input tax - local purchases", self.in_local, False),
            ("7", "Input tax - imports of goods", self.in_import, False),
            ("8", "Reverse charge input tax (imported services)", self.rc_in, False),
            ("9", "Apportionment disallowance (mixed supplies)", self.disallowed, True),
            ("10", "Total input tax allowable (6+7+8 + mixed recovered -9)",
             self.total_input, True),
            ("11", "Net VAT payable / refundable (5-10)", net, True),
            ("12", "Status: PAYABLE / REFUNDABLE / NIL", 0, False),
            ("13", "VAT due for the period", abs(net), True),
        ]
        labelled = []
        for no, desc, amt, emph in rows:
            if no == "12":
                desc = f"Status: {self.status}"
                amt = {"PAYABLE": "PAYABLE", "REFUNDABLE": "REFUNDABLE",
                       "NIL": "NIL"}[self.status]
            labelled.append((no, desc, amt, emph))
        return labelled


class VATResult:
    def __init__(self, schedules, trail, warnings, counts, rate_snapshot,
                 de_minimis_invoice_rows, apport_notes, combined=None):
        self.schedules = schedules            # {ccy_code: Schedule}
        self.trail = trail                    # DataFrame
        self.warnings = warnings
        self.counts = counts                  # dict
        self.rate_snapshot = rate_snapshot    # fx snapshot dict
        self.de_minimis_invoice_rows = de_minimis_invoice_rows
        self.apport_notes = apport_notes      # per-currency note
        self.combined = combined              # informational ZiG-equivalent

    # -- convenience ---------------------------------------------------------
    @property
    def std_sales(self):
        return sum((s.std for s in self.schedules.values()), Decimal("0"))

    @property
    def zr_sales(self):
        return sum((s.zr for s in self.schedules.values()), Decimal("0"))

    @property
    def ex_sales(self):
        return sum((s.ex for s in self.schedules.values()), Decimal("0"))

    @property
    def total_output_tax(self):
        return sum((s.total_output for s in self.schedules.values()), Decimal("0"))

    @property
    def total_input_tax(self):
        return sum((s.total_input for s in self.schedules.values()), Decimal("0"))

    @property
    def net_vat(self):
        return sum((s.net for s in self.schedules.values()), Decimal("0"))

    @property
    def status(self):
        if self.net_vat > 0:
            return "PAYABLE"
        if self.net_vat < 0:
            return "REFUNDABLE"
        return "NIL"

    def schedule_lines(self, ccy):
        sched = self.schedules.get(ccy)
        if sched is None:
            return []
        return sched.lines()

    def chart_sales_by_category(self):
        rows = []
        for ccy, s in self.schedules.items():
            rows += [{"Schedule": ccy, "Category": "Standard-rated", "Value": float(s.std)},
                     {"Schedule": ccy, "Category": "Zero-rated", "Value": float(s.zr)},
                     {"Schedule": ccy, "Category": "Exempt", "Value": float(s.ex)}]
        return pd.DataFrame(rows)

    def chart_output_vs_input(self):
        rows = []
        for ccy, s in self.schedules.items():
            rows.append({"Schedule": ccy, "Component": "Output VAT", "Amount": float(s.total_output)})
            rows.append({"Schedule": ccy, "Component": "Allowable Input VAT", "Amount": float(s.total_input)})
            rows.append({"Schedule": ccy, "Component": "Net VAT", "Amount": float(s.net)})
        return pd.DataFrame(rows)

    def chart_vat_by_currency(self):
        rows = []
        for ccy, s in self.schedules.items():
            rows.append({"Currency": ccy, "Output VAT": float(s.total_output),
                         "Input VAT": float(s.total_input),
                         "Net VAT": float(s.net)})
        return pd.DataFrame(rows)

    def chart_pass_fail(self):
        c = self.counts
        return pd.DataFrame([
            {"Status": "PASS", "Transactions": c.get("n_pass", 0)},
            {"Status": "REVIEW", "Transactions": c.get("n_review", 0)},
            {"Status": "FAIL", "Transactions": c.get("n_fail", 0)},
        ])

    def chart_monthly(self):
        df = self.trail.copy()
        if df.empty:
            return pd.DataFrame(columns=["month", "schedule", "Output VAT", "Input VAT"])
        df["month"] = df["date"].map(_date_month)
        df["ov"] = df.apply(lambda r: float(r["vat_amount"]) if r["side"] == "Output" else 0.0, axis=1)
        df["iv"] = df.apply(lambda r: float(r["vat_amount"]) if r["side"] == "Input" else 0.0, axis=1)
        g = df.groupby(["month", "schedule"])[["ov", "iv"]].sum().reset_index()
        g.columns = ["month", "schedule", "Output VAT", "Input VAT"]
        return g

    def management(self):
        c = self.counts
        return {
            "total_sales": float(self.std_sales + self.zr_sales + self.ex_sales),
            "taxable_sales": float(self.std_sales),
            "zero_sales": float(self.zr_sales),
            "exempt_sales": float(self.ex_sales),
            "output_vat": float(self.total_output_tax),
            "input_vat": float(self.total_input_tax),
            "imports_vat": float(sum((s.in_import for s in self.schedules.values()), Decimal("0"))),
            "adjustments_vat": float(sum((s.out_adj for s in self.schedules.values()), Decimal("0"))),
            "net_vat": float(self.net_vat),
            "n_txns": c.get("n_txns", 0),
            "n_pass": c.get("n_pass", 0),
            "n_review": c.get("n_review", 0),
            "n_fail": c.get("n_fail", 0),
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Row-level explainable checks (PASS / REVIEW / FAIL)
# ---------------------------------------------------------------------------
def check_row(rec, rates, schedule):
    """Return (status, reason) performing the mandatory explainable checks."""
    status, reasons = "PASS", []

    tid = _norm_text(rec.get("txn_id"))
    if not tid:
        reasons.append("transaction ID is missing")
        status = "FAIL"
    date = _norm_text(rec.get("date"))
    if not date:
        reasons.append("transaction date is missing")
        status = "FAIL"

    direction = _norm_direction(rec.get("direction"))
    if not direction:
        reasons.append("transaction type is missing or invalid")
        status = "FAIL"

    amount = _num(rec.get("amount"), None)
    if amount is None:
        reasons.append("amount is not a valid number")
        status = "FAIL"
    elif amount < 0:
        reasons.append("negative amount where not permitted")
        status = "FAIL"

    ccy = _norm_currency(rec.get("currency"))
    if ccy not in ("USD", "ZIG", "ZAR"):
        reasons.append(f"unsupported currency '{rec.get('currency')}' (ZiG, USD or ZAR required)")
        status = "FAIL"

    # exchange rate availability for rows that need a conversion
    if ccy == "ZAR" or (ccy != schedule and schedule != "USD"):
        conv_ok = True
        if schedule == "USD" and ccy == "ZAR":
            conv_ok = rates and rates.get("ZAR")
        elif schedule == "ZIG" and ccy in ("USD", "ZAR"):
            conv_ok = rates and rates.get("ZIG")
        if not conv_ok:
            reasons.append("exchange rate unavailable for this conversion")
            status = "FAIL"

    cat = _norm_category(rec.get("category"))
    inv = _bool(rec.get("vat_inclusive"))
    if _num(rec.get("amount"), None) is not None and inv and cat == "standard" and amount <= 0:
        reasons.append("VAT-inclusive amount must be positive")
        status = "FAIL"

    # documentation expectations
    if direction == "sale" and cat == "export" and not _bool(rec.get("supporting_document_available")):
        reasons.append("export supply without proof of export (e.g. CD3 / bill of entry)")
        status = "REVIEW" if status == "PASS" else status
    if direction in ("import_goods", "imported_service") and not _bool(rec.get("supporting_document_available")):
        reasons.append("import without supporting documents (bill of entry / contract)")
        status = "REVIEW" if status == "PASS" else status
    if direction == "purchase" and not _bool(rec.get("supporting_document_available")):
        reasons.append("purchase input-tax claim without a supporting tax invoice")
        status = "REVIEW" if status == "PASS" else status
    if direction == "adjustment" and not _norm_text(rec.get("invoice_number")):
        reasons.append("adjustment without a referencing invoice / document number")
        status = "REVIEW" if status == "PASS" else status

    return status, "; ".join(reasons) if reasons else "All checks passed."


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------
def compute_vat_return(df, de_minimis=True, vat_rate=None, rates=None,
                       fx_snapshot=None, report_label="ZiG + USD (separate)"):
    """Compute the VAT return from a transaction DataFrame.

    Accepted (canonical) columns: txn_id, date, description, direction,
    counterparty, category, amount, vat_inclusive, customs_value, customs_duty,
    prohibited_reason, business_use_pct, adjustment_type, mixed_input,
    import_flag, invoice_number, supporting_document_available, currency,
    exchange_rate, exchange_rate_date, exchange_rate_source, notes.
    """
    if vat_rate is None:
        vat_rate = config.VAT_RATE_PCT
    rate_pct = Decimal(str(vat_rate))
    rate = rate_pct / Decimal("100")
    vat_fraction = rate / (Decimal("1") + rate)
    rate_label = f"{rate_pct:g}%"

    if rates is None:
        rates = dict(fx.get_rates()["rates"])
    if fx_snapshot is None:
        fx_snapshot = {"source": "embedded snapshot", "date_label": "period rate"}
    fx_source = fx_snapshot.get("source", "embedded snapshot")
    fx_date = fx_snapshot.get("date_label", "period rate")

    schedules = {ccy: Schedule(ccy) for ccy in ("ZIG", "USD")}
    trail = []
    warnings = []
    demin_rows = []
    apport_notes = {}

    recs = df.to_dict("records")
    seen_ids = set()

    for rec in recs:
        tid = _norm_text(rec.get("txn_id")) or f"ROW-{len(trail)+1}"
        date = _norm_text(rec.get("date"))
        desc = _norm_text(rec.get("description")) or "Untitled transaction"
        cpy = _norm_text(rec.get("counterparty"))
        direction = _norm_direction(rec.get("direction"))
        category = _norm_category(rec.get("category"))
        ccy = _norm_currency(rec.get("currency"))
        raw_ccy = _norm_text(rec.get("currency")).upper()
        amount = _num(rec.get("amount"), None)

        # schedule selection — ZAR converts into the USD schedule
        schedule = "ZIG" if ccy == "ZIG" else "USD"
        sched = schedules[schedule]

        status, reason = check_row(rec, rates, schedule)
        # Strict currency check: an explicit non-empty currency outside the
        # supported set must FAIL (never silently default to ZiG).
        if raw_ccy and raw_ccy not in ("USD", "US$", "ZIG", "ZWG", "ZW$", "ZWL", "ZAR", "R", "RAND"):
            status = "FAIL"
            reason = f"Currency '{rec.get('currency')}' is not supported - use ZiG, USD or ZAR."
        elif not raw_ccy and status == "PASS":
            status = "REVIEW"
            reason = "Currency was blank - assumed ZiG. Enter ZiG, USD or ZAR to confirm."
        dup = False
        if tid in seen_ids:
            dup = True
            status = "FAIL" if status != "FAIL" else status
            reason = ("duplicate transaction ID; " + reason) if reason != "All checks passed." else "duplicate transaction ID"
        seen_ids.add(tid)

        # conversion transparency ------------------------------------------
        conv_amt, fx_rate_used, fx_math, conv_ok, conv_fail = \
            fx.convert_row_to_schedule(amount if amount is not None else 0,
                                       ccy, schedule, rates)
        if not conv_ok:
            status = "FAIL"
            reason = conv_fail
            trail.append(_trail_row(rec, side=side_for(direction), category=category,
                                    schedule=schedule, status="FAIL", reason=conv_fail,
                                    fx_source=fx_source, fx_date=fx_date))
            warnings.append(f"{tid}: {conv_fail}")
            continue

        # invoicing de minimis note (educational) ----------------------------
        usd_eq = fx.convert(amount if amount is not None else 0, ccy, "USD", rates)
        dm_pass, dm_note = _invoice_deminimis(usd_eq)
        demin_rows.append({"txn_id": tid, "description": desc, "currency": ccy,
                           "original_amount": float(amount) if amount is not None else 0.0,
                           "usd_equivalent": usd_eq, "threshold": float(config.DE_MINIMIS_INVOICE_USD),
                           "check": "🟢 PASS — below de minimis" if dm_pass else "🔴 FAIL — above de minimis",
                           "status": "PASS" if dm_pass else "REVIEW",
                           "note": dm_note})
        if dm_pass and direction == "sale" and category == "standard":
            demin_rows[-1]["note"] += " (supply remains standard-rated.)"

        amt = Decimal(str(conv_amt)) if amount is not None else Decimal("0")
        vat_incl = _bool(rec.get("vat_inclusive"))

        # ---------------- SALE ---------------------------------------------
        if direction == "sale":
            if category == "zero_rated":
                sched.zr += amt
                trail.append(_trail_row(rec, side="Memo", category="zero_rated",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="0%", vat_amount=0,
                                        vat_math=f"0% x {conv_amt:,.2f} = 0.00 output tax",
                                        status=status, reason=reason,
                                        explanation=expl_of("zero_rated", "Zero-rated supply - no output VAT is charged, but input VAT on related costs is still claimable."),
                                        fx_source=fx_source, fx_date=fx_date))
            elif category == "exempt":
                sched.ex += amt
                trail.append(_trail_row(rec, side="Memo", category="exempt",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="-", vat_amount=0,
                                        vat_math="Exempt supply - no output VAT charged",
                                        status=status, reason=reason,
                                        explanation=expl_of("exempt", "Exempt supply recorded as a memo; it affects apportionment of mixed input VAT but carries no output tax."),
                                        fx_source=fx_source, fx_date=fx_date))
            elif category == "export":
                sched.zr += amt
                trail.append(_trail_row(rec, side="Memo", category="export",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="0%", vat_amount=0,
                                        vat_math="Export - zero-rated (0% x value = 0) with proof of export",
                                        status=status, reason=reason,
                                        explanation=expl_of("zero_rated", "Export of goods zero-rated under VAT Act s10 once proof of export (CD3) is held."),
                                        fx_source=fx_source, fx_date=fx_date))
            else:  # standard
                if amt <= 0:
                    status = "FAIL"
                    reason = "amount must be positive for a standard-rated sale"
                    warnings.append(f"{tid}: {reason}")
                vat = (r2(amt * vat_fraction) if vat_incl else r2(amt * rate))
                if status == "PASS":
                    sched.std += amt
                    sched.out_std += vat
                vmath = (f"{conv_amt:,.2f} x {rate_pct:g}/{Decimal('100')+rate_pct:g} "
                         f"(VAT-inclusive) = {float(vat):,.2f}" if vat_incl
                         else f"{conv_amt:,.2f} x {rate_label} = {float(vat):,.2f}")
                trail.append(_trail_row(rec, side="Output", category="standard",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate=rate_label, vat_amount=vat,
                                        vat_math=vmath, status=status, reason=reason,
                                        explanation=expl_of("standard", "Output VAT = taxable amount x standard rate."),
                                        fx_source=fx_source, fx_date=fx_date))

        # ---------------- PURCHASE -----------------------------------------
        elif direction == "purchase":
            if category in ("zero_rated",):
                trail.append(_trail_row(rec, side="Memo", category="zero_rated",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="0%", vat_amount=0,
                                        vat_math="0% x value = 0 input tax",
                                        status=status, reason=reason,
                                        explanation=expl_of("zero_rated", "Zero-rated purchase - no input VAT because no VAT was charged by the supplier."),
                                        fx_source=fx_source, fx_date=fx_date))
            elif category == "exempt":
                trail.append(_trail_row(rec, side="Memo", category="exempt",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="-", vat_amount=0,
                                        vat_math="Exempt purchase - no input VAT claim",
                                        status=status, reason=reason,
                                        explanation=expl_of("exempt", "Exempt purchase - input VAT is generally not claimable on costs attributable to exempt supplies."),
                                        fx_source=fx_source, fx_date=fx_date))
            else:
                raw_vat = (r2(amt * vat_fraction) if vat_incl else r2(amt * rate))
                gross_math = (f"{conv_amt:,.2f} x {rate_pct:g}/{Decimal('100')+rate_pct:g} "
                              f"(VAT-inclusive) = {float(raw_vat):,.2f}" if vat_incl
                              else f"{conv_amt:,.2f} x {rate_label} = {float(raw_vat):,.2f}")
                prohibited = _norm_text(rec.get("prohibited_reason"))
                if prohibited:
                    sched.in_local += 0
                    trail.append(_trail_row(rec, side="Input", category="prohibited",
                                            schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                            fx_math=fx_math, vat_rate=rate_label, vat_amount=0,
                                            vat_math=f"{gross_math}; claim = 0 (prohibited input: {prohibited})",
                                            status="REVIEW", reason=f"Prohibited input ({prohibited}) - input tax disallowed by law, no claim entered.",
                                            explanation=expl_of("prohibited", "VAT on prohibited inputs (entertainment, passenger motor vehicles, club subscriptions) cannot be claimed."),
                                            fx_source=fx_source, fx_date=fx_date))
                    warnings.append(f"{tid}: prohibited input ({prohibited}) - input tax disallowed")
                    continue
                pct = _pct(rec.get("business_use_pct"))
                claim = r2(raw_vat * pct)
                mixed = _bool(rec.get("mixed_input"))
                if mixed:
                    sched.mixed += raw_vat
                    trail.append(_trail_row(rec, side="Input", category="mixed",
                                            schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                            fx_math=fx_math, vat_rate=rate_label, vat_amount=raw_vat,
                                            vat_math=f"{gross_math}; held for apportionment",
                                            status=status, reason=reason,
                                            explanation=expl_of("mixed", "Mixed-supply (overhead) input held for turnover apportionment - only the taxable share is finally claimed."),
                                            fx_source=fx_source, fx_date=fx_date))
                else:
                    sched.in_local += claim
                    note = (f"Input tax claim ({pct*100:g}% business use)" if pct < 1
                            else "Input tax claim (fully allowable)")
                    trail.append(_trail_row(rec, side="Input", category="standard",
                                            schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                            fx_math=fx_math, vat_rate=rate_label, vat_amount=claim,
                                            vat_math=(f"{gross_math}; claim = {float(claim):,.2f} "
                                                      f"({pct*100:g}% business use)" if pct < 1
                                                      else gross_math),
                                            status=status, reason=reason,
                                            explanation=expl_of("standard", "Allowable input VAT = VAT charged on the purchase x business-use %, where valid for the business and supported by documents."),
                                            fx_source=fx_source, fx_date=fx_date))

        # ---------------- IMPORT GOODS -------------------------------------
        elif direction == "import_goods":
            cv = _num(rec.get("customs_value"), Decimal("0"))
            cd = _num(rec.get("customs_duty"), Decimal("0"))
            base_orig = cv + cd
            base_conv, _, base_math, ok2, fail2 = fx.convert_row_to_schedule(base_orig, ccy, schedule, rates)
            if not ok2 or base_conv is None or base_conv <= 0:
                warnings.append(f"{tid}: import has zero/invalid customs base - skipped")
                trail.append(_trail_row(rec, side="Input", category="import_goods",
                                        schedule=schedule, conv=0, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate=rate_label, vat_amount=0,
                                        vat_math="Import VAT not computed - invalid customs value",
                                        status="FAIL", reason="Import with zero or missing customs value/duty.",
                                        explanation=expl_of("import_goods", "Import VAT is charged on the customs value plus customs duty, not merely the invoice value."),
                                        fx_source=fx_source, fx_date=fx_date))
                continue
            vat = r2(Decimal(str(base_conv)) * rate)
            sched.in_import += vat
            trail.append(_trail_row(rec, side="Input", category="import_goods",
                                    schedule=schedule, conv=base_conv, fx_rate=fx_rate_used,
                                    fx_math=(fx_math + " | " + base_math if ccy != schedule else base_math),
                                    vat_rate=rate_label, vat_amount=vat,
                                    vat_math=(f"({cv:,.2f} CV + {cd:,.2f} duty) x {rate_label} "
                                              f"= {float(vat):,.2f}"),
                                    status=status, reason=reason,
                                    explanation=expl_of("import_goods", "VAT charged at import on customs value + duty; claimable as input VAT by the registered importer."),
                                    fx_source=fx_source, fx_date=fx_date))

        # ---------------- IMPORTED SERVICE (reverse charge) ----------------
        elif direction == "imported_service":
            raw_vat = (r2(amt * vat_fraction) if vat_incl else r2(amt * rate))
            pct = _pct(rec.get("business_use_pct"))
            claim = r2(raw_vat * pct)
            sched.rc_out += raw_vat
            sched.rc_in += claim
            vmath = f"Reverse charge: {conv_amt:,.2f} x {rate_label} = {float(raw_vat):,.2f}"
            trail.append(_trail_row(rec, side="Output", category="imported_service",
                                    schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                    fx_math=fx_math, vat_rate=rate_label, vat_amount=raw_vat,
                                    vat_math=vmath, status=status, reason=reason,
                                    explanation=expl_of("imported_service", "Reverse charge: the business accounts for OUTPUT VAT on the imported service as if it made the supply."),
                                    fx_source=fx_source, fx_date=fx_date))
            trail.append(_trail_row(rec, side="Input", category="imported_service",
                                    schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                    fx_math=fx_math, vat_rate=rate_label, vat_amount=claim,
                                    vat_math=f"Mirror input credit: {raw_vat:,.2f} x {pct*100:g}% = {claim:,.2f}",
                                    status=status, reason=reason,
                                    explanation=expl_of("imported_service", "Mirror input credit: the business may also claim input VAT to the extent the service supports its taxable supplies."),
                                    fx_source=fx_source, fx_date=fx_date))

        # ---------------- ADJUSTMENT ---------------------------------------
        elif direction == "adjustment":
            atype = _norm_adjustment(rec.get("adjustment_type"))
            ref = _norm_text(rec.get("invoice_number")) or _norm_text(rec.get("reference"))
            if atype == "credit_note":
                vat = r2(amt * vat_fraction) if vat_incl else r2(amt * rate)
                eff = -vat
                sched.out_adj += eff
                vmath = f"Credit note reduces output tax: {conv_amt:,.2f} x {rate_pct:g}/{Decimal('100')+rate_pct:g} (VAT-inclusive) = {eff:,.2f}" if vat_incl else f"Credit note reduces output tax: {conv_amt:,.2f} x {rate_label} = {eff:,.2f}"
                trail.append(_trail_row(rec, side="Adjustment", category="credit_note",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate=rate_label, vat_amount=eff,
                                        vat_math=vmath, status=status, reason=reason,
                                        explanation=expl_of("credit_note", "A credit note reduces the VAT charged on a sale. We subtract the VAT in the note from output tax."),
                                        fx_source=fx_source, fx_date=fx_date))
            elif atype == "debit_note":
                vat = r2(amt * vat_fraction) if vat_incl else r2(amt * rate)
                eff = vat
                sched.out_adj += eff
                vmath = f"Debit note increases output tax: {conv_amt:,.2f} x {rate_label} = {eff:,.2f}" if not vat_incl else f"Debit note increases output tax (VAT-inclusive): {conv_amt:,.2f} x {rate_pct:g}/{Decimal('100')+rate_pct:g} = {eff:,.2f}"
                trail.append(_trail_row(rec, side="Adjustment", category="debit_note",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate=rate_label, vat_amount=eff,
                                        vat_math=vmath, status=status, reason=reason,
                                        explanation=expl_of("debit_note", "A debit note increases the VAT charged on a sale. We add the VAT in the note to output tax."),
                                        fx_source=fx_source, fx_date=fx_date))
            elif atype == "bad_debt_relief":
                relief = r2(amt * vat_fraction)
                eff = -relief
                sched.out_adj += eff
                vmath = f"Bad-debt relief (amount treated as VAT-inclusive): {conv_amt:,.2f} x {rate_pct:g}/{Decimal('100')+rate_pct:g} = {relief:,.2f}"
                trail.append(_trail_row(rec, side="Adjustment", category="bad_debt_relief",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate=f"{rate_pct:g}/{Decimal('100')+rate_pct:g}",
                                        vat_amount=eff, vat_math=vmath, status=status, reason=reason,
                                        explanation=expl_of("bad_debt", "Bad-debt relief reverses the output VAT on a debt written off (>6 months), using the VAT-inclusive fraction of the debt."),
                                        fx_source=fx_source, fx_date=fx_date))
            elif atype == "prior_period_correction":
                eff = r2(amt)
                sched.out_adj += eff
                trail.append(_trail_row(rec, side="Adjustment", category="prior_period_correction",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="-", vat_amount=eff,
                                        vat_math=f"Signed VAT effect carried through: {eff:,.2f}",
                                        status=status, reason=reason,
                                        explanation=expl_of("credit_note", "Prior-period correction adjusts output VAT for an error from an earlier period; the amount is the signed VAT effect."),
                                        fx_source=fx_source, fx_date=fx_date))
            else:
                warnings.append(f"{tid}: unknown or missing adjustment_type - row skipped")
                trail.append(_trail_row(rec, side="Adjustment", category="adjustment",
                                        schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                        fx_math=fx_math, vat_rate="-", vat_amount=0,
                                        vat_math="Not processed - unknown adjustment type",
                                        status="FAIL", reason="Unknown or missing adjustment_type; expected credit_note, debit_note, bad_debt_relief or prior_period_correction.",
                                        explanation=expl_of("credit_note", "Adjustments must carry the correct adjustment_type before they can be processed."),
                                        fx_source=fx_source, fx_date=fx_date))
        else:
            trail.append(_trail_row(rec, side="Memo", category="standard",
                                    schedule=schedule, conv=conv_amt, fx_rate=fx_rate_used,
                                    fx_math=fx_math, vat_rate="-", vat_amount=0,
                                    vat_math="Not processed - transaction type not recognised",
                                    status="FAIL", reason=f"Unrecognised transaction type '{direction}'. Use sale, purchase, import_goods, imported_service or adjustment.",
                                    explanation=expl_of("standard", "A transaction must have a recognised type before it can be computed."),
                                    fx_source=fx_source, fx_date=fx_date))
            warnings.append(f"{tid}: unrecognised direction '{direction}'")

    # ---------------- apportionment / de minimis per schedule ---------------
    for ccy, sched in schedules.items():
        sched.run_apportionment(de_minimis=de_minimis)
        if sched.apport_note:
            apport_notes[ccy] = sched.apport_note
        elif sched.mixed > 0:
            apport_notes[ccy] = ("No exempt supplies in this currency - mixed input tax deductible in full (no apportionment needed).")

    # ---------------- combined informational view ---------------------------
    combined = combined_view(schedules, rates)

    # ---------------- counts -------------------------------------------------
    counts = {"n_txns": len(trail), "n_pass": 0, "n_review": 0, "n_fail": 0}
    for r in trail:
        s = str(r["status"]) if "status" in r else "PASS"
        if s == "REVIEW":
            counts["n_review"] += 1
        elif s == "FAIL":
            counts["n_fail"] += 1
        else:
            counts["n_pass"] += 1

    return VATResult(schedules, pd.DataFrame(trail, columns=TRAIL_COLUMNS),
                     warnings, counts, fx_snapshot, demin_rows, apport_notes,
                     combined=combined)


def side_for(direction):
    return {"sale": "Output", "purchase": "Input", "import_goods": "Input",
            "imported_service": "Output", "adjustment": "Adjustment"}.get(direction, "Memo")


def expl_of(key, extra=""):
    rule = RULES.get(key, "")
    return extra + (" | Rule: " + rule if rule else "")


def _trail_row(rec, side, category, schedule, conv=None, fx_rate=1.0,
               fx_math="", vat_rate="-", vat_amount=0, vat_math="", status="PASS",
               reason="", explanation="", fx_source="", fx_date=""):
    vat_d = Decimal(str(vat_amount))
    return {
        "txn_id": _norm_text(rec.get("txn_id")),
        "date": _norm_text(rec.get("date")),
        "description": _norm_text(rec.get("description")),
        "counterparty": _norm_text(rec.get("counterparty")),
        "side": side,
        "category": category,
        "currency": _norm_currency(rec.get("currency")),
        "schedule": schedule,
        "amount": _num(rec.get("amount"), Decimal("0")),
        "fx_rate": float(fx_rate) if fx_rate else 1.0,
        "fx_source": fx_source,
        "fx_date": fx_date,
        "fx_math": fx_math,
        "converted_amount": float(conv) if conv is not None else None,
        "vat_rate": vat_rate,
        "vat_amount": vat_d,
        "vat_math": vat_math,
        "explanation": explanation,
        "grade7": explanation,
        "status": status,
        "reason": reason,
        "reference": _norm_text(rec.get("invoice_number")) or _norm_text(rec.get("reference")),
        "invoice_number": _norm_text(rec.get("invoice_number")),
        "supporting_document": "Available" if _bool(rec.get("supporting_document_available")) else "Not available",
    }


def combined_view(schedules, rates):
    """Informational only — combines schedules into a ZiG-equivalent view.
    Never used to file the return: ZIMRA requires separate schedules."""
    if rates is None:
        rates = fx.get_rates()["rates"]
    zag = {}
    for ccy in schedules:
        factor = 1.0 if ccy == "ZIG" else float(rates.get("ZIG", 1.0) or 1.0)
        zag[ccy] = factor
    std = sum((float(s.std) * zag[c]) for c, s in schedules.items())
    zr = sum((float(s.zr) * zag[c]) for c, s in schedules.items())
    ex = sum((float(s.ex) * zag[c]) for c, s in schedules.items())
    out = sum((float(s.total_output) * zag[c]) for c, s in schedules.items())
    inp = sum((float(s.total_input) * zag[c]) for c, s in schedules.items())
    net = out - inp
    return {
        "std_sales_zig": std, "zr_sales_zig": zr, "ex_sales_zig": ex,
        "output_zig": out, "input_zig": inp, "net_zig": net,
        "note": "INFORMATIONAL ZiG-equivalent combine only — never used to file "
                "the return. ZIMRA requires a separate schedule per currency.",
    }