"""validation.py — Data-quality and compliance checks (PASS / REVIEW / FAIL).

Before any amount is calculated, the system checks the uploaded or entered
transaction data. Every check returns a visible status with:
    what failed | why | financial impact | what the user should correct

Also normalises free-form user columns (from uploads / manual entry) into the
canonical columns the engine expects, so users can load CSVs with friendly
headers like "Transaction ID", "Amount (USD)" or "VAT Category".
"""

from __future__ import annotations

import io
import re
from decimal import Decimal

import pandas as pd

import config
import vat_engine as ve

VALID_CATEGORIES = {"standard", "zero_rated", "exempt", "export", "prohibited",
                    "mixed", "import_goods", "imported_service"}
VALID_DIRECTIONS = {"sale", "purchase", "import_goods", "imported_service",
                    "adjustment"}
VALID_CURRENCIES = {"USD", "ZIG", "ZAR"}

COLUMN_ALIASES = {
    "txn_id": ["txn_id", "transaction id", "transaction_id", "txnid", "id", "ref", "reference no", "transaction id no"],
    "date": ["date", "transaction date", "transaction_date", "txn date", "date of transaction"],
    "description": ["description", "particulars", "details", "narration", "item"],
    "direction": ["direction", "transaction type", "transaction_type", "type", "debit credit", "dr cr"],
    "counterparty": ["supplier customer", "supplier/customer", "supplier_customer", "counterparty", "supplier", "customer", "party", "trade partner"],
    "category": ["category", "vat category", "vat_category", "vat classification", "type of supply", "supply type"],
    "amount": ["amount", "original amount", "original_amount", "value", "amount excl vat", "net amount", "gross amount", "amount (usd)", "amount (zig)", "amount (zar)", "transaction amount"],
    "vat_inclusive": ["vat inclusive", "vat_inclusive", "inclusive", "vat incl"],
    "customs_value": ["customs value", "customs_value", "customs value (usd)", "cif value"],
    "customs_duty": ["customs duty", "customs_duty", "import duty"],
    "prohibited_reason": ["prohibited reason", "prohibited_reason", "prohibited", "disallowed reason"],
    "business_use_pct": ["business use pct", "business_use_pct", "business use", "business use %", "use %"],
    "adjustment_type": ["adjustment type", "adjustment_type", "adj type"],
    "mixed_input": ["mixed input", "mixed_input", "mixed", "overhead"],
    "import_flag": ["import flag", "import_flag", "is import", "import"],
    "invoice_number": ["invoice number", "invoice_number", "invoice no", "invoice"],
    "supporting_document_available": ["supporting document available", "supporting_document_available", "doc available", "supporting doc", "supporting documents", "has document"],
    "exchange_rate": ["exchange rate", "exchange_rate", "rate", "fx rate"],
    "exchange_rate_date": ["exchange rate date", "exchange_rate_date", "rate date", "fx date"],
    "exchange_rate_source": ["exchange rate source", "exchange_rate_source", "rate source", "fx source"],
    "notes": ["notes", "note", "comment", "remarks"],
}


def pick_col(df, canonical):
    """Find the actual column name for a canonical field using aliases."""
    lower = {str(c).strip().lower(): c for c in df.columns}
    for alias in COLUMN_ALIASES.get(canonical, [canonical]):
        if alias in lower:
            return lower[alias]
    return canonical


def normalize_columns(df):
    """Return a copy of df with canonical engine column names."""
    out = df.copy()
    mapping = {}
    for canonical in COLUMN_ALIASES:
        actual = pick_col(df, canonical)
        if actual in df.columns:
            mapping[actual] = canonical
    out = out.rename(columns=mapping)
    return out


def required_columns():
    return list(COLUMN_ALIASES.keys())


def fmt_value(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def is_num(v):
    s = fmt_value(v).replace(",", "").replace(" ", "")
    if s == "":
        return False
    try:
        Decimal(s)
        return True
    except Exception:
        return False


def validate(df, rate_available=True):
    """Return (checks_df, normalized_df).

    Runs one check row per transaction per applicable rule. GLOBAL checks
    (duplicates) produce one row per duplicated transaction.
    """
    norm = normalize_columns(df)
    checks = []
    seen = {}

    for idx, row in norm.iterrows():
        tid = fmt_value(row.get("txn_id"))
        date = fmt_value(row.get("date"))
        direction_raw = fmt_value(row.get("direction"))
        direction = ve._norm_direction(direction_raw) if direction_raw else ""
        category_raw = fmt_value(row.get("category"))
        category = ve._norm_category(category_raw) if category_raw else ""
        currency_raw = fmt_value(row.get("currency"))
        currency = ve._norm_currency(currency_raw) if currency_raw else ""
        currency_raw_upper = currency_raw.strip().upper()
        VALID_CCY_ALIASES = {"USD", "US$", "ZIG", "ZWG", "ZW$", "ZWL", "ZAR", "R", "RAND"}
        amount = row.get("amount")

        # -- txn id -------------------------------------------------------
        _check(checks, "ID", tid, "Transaction ID", tid,
               "missing" if not tid else None,
               "A transaction ID is required to trace every number back to a transaction.",
               "PASS" if tid else "FAIL",
               "Every transaction needs a unique reference.",
               "The record cannot be individually traced in the audit trail.",
               "Enter a unique Transaction ID (e.g. S-001, ADJ-002).")

        # -- date ---------------------------------------------------------
        _check(checks, "DATE", tid, "Date", date,
               "missing" if not date else None,
               "The date fixes the tax period and the exchange-rate date.",
               "PASS" if date else "FAIL",
               "Every transaction needs a date.",
               "The period and rate-date cannot be determined.",
               "Enter the transaction date (YYYY-MM-DD).")

        # -- direction / type ---------------------------------------------
        if not direction:
            _check(checks, "TYPE", tid, "Transaction Type", direction_raw,
                   "missing or invalid", "A sale, purchase, import, imported "
                   "service or adjustment must be identified.",
                   "FAIL", "The transaction type is unrecognised.",
                   "The transaction cannot be classified for VAT.",
                   "Choose sale / purchase / import_goods / imported_service / adjustment.")
        else:
            _check(checks, "TYPE", tid, "Transaction Type", direction,
                   None, "Recognised transaction type.",
                   "PASS", "The transaction type is valid.", "", "")

        # -- amount --------------------------------------------------------
        if amount is None or fmt_value(amount) == "":
            _check(checks, "AMOUNT", tid, "Amount", fmt_value(amount),
                   "missing", "The amount is required to compute VAT.",
                   "FAIL", "Amount is missing.",
                   "No VAT can be computed for this transaction.",
                   "Enter the transaction amount.")
        elif not is_num(amount):
            _check(checks, "AMOUNT", tid, "Amount", fmt_value(amount),
                   "not numeric", "The amount is not numeric.",
                   "FAIL", "Amount is not numeric.",
                   "The VAT cannot be computed from a non-numeric amount.",
                   "Enter a numeric amount (e.g. 2500.00).")
        elif Decimal(str(amount).replace(",", "")) < 0:
            _check(checks, "AMOUNT", tid, "Amount", fmt_value(amount),
                   "negative", "Negative amounts are not permitted here; use "
                   "credit/debit notes for reductions.",
                   "FAIL", "Amount is negative.",
                   "Negative values distort the VAT base.",
                   "Use an adjustment row for reductions.")
        else:
            _check(checks, "AMOUNT", tid, "Amount", fmt_value(amount),
                   None, "Amount is a valid positive number.",
                   "PASS", "Amount is valid.", "", "")

        # -- currency -------------------------------------------------------
        if not currency:
            _check(checks, "CCY", tid, "Currency", currency_raw,
                   "missing", "Only ZiG, USD and ZAR are supported; blank "
                   "defaults to ZiG.",
                   "REVIEW", "Currency is missing (assumed ZiG).",
                   "Conversions to the schedule currency may be wrong.",
                   "Enter ZiG, USD or ZAR.")
        elif currency_raw_upper not in VALID_CCY_ALIASES:
            _check(checks, "CCY", tid, "Currency", currency_raw,
                   "unsupported", f"Supported currencies: {', '.join(sorted(VALID_CURRENCIES))}.",
                   "FAIL", "Currency is not supported.",
                   "The amount cannot be converted or placed on a schedule.",
                   "Use ZiG, USD or ZAR.")
        else:
            _check(checks, "CCY", tid, "Currency", currency,
                   None, "Supported currency.",
                   "PASS", "Currency is valid.", "", "")

        # -- vat category ---------------------------------------------------
        valid_cat = category in VALID_CATEGORIES or (direction == "adjustment" and category in ("standard",) or (category in ("credit_note", "debit_note", "bad_debt_relief", "prior_period_correction")))
        if not category:
            _check(checks, "CAT", tid, "VAT Category", category_raw,
                   "missing", "The VAT category determines the rate applied.",
                   "FAIL", "VAT category missing.",
                   "Wrong (or no) rate could be applied.",
                   "Choose standard / zero_rated / exempt / export / import_goods / imported_service.")
        elif not valid_cat:
            _check(checks, "CAT", tid, "VAT Category", category_raw,
                   "invalid", "The VAT category is not recognised.",
                   "FAIL", "VAT category invalid.",
                   "The wrong VAT rate could be applied to the transaction.",
                   "Use a recognised category (standard, zero_rated, exempt, export, import_goods, imported_service).")
        elif category == "prohibited":
            _check(checks, "CAT", tid, "VAT Category", category_raw,
                   "prohibited input", "Input tax is disallowed by law on this "
                   "category.", "REVIEW",
                   "Prohibited input - input tax disallowed.",
                   "VAT on prohibited inputs is NOT claimable.",
                   "Confirm the purchase is truly a prohibited input; otherwise reclassify.")
        else:
            _check(checks, "CAT", tid, "VAT Category", category,
                   None, "Valid VAT category.",
                   "PASS", "VAT category is valid.", "", "")

        # -- exchange rate / rate date --------------------------------------
        er = row.get("exchange_rate")
        if er is not None and fmt_value(er) != "" and not is_num(er):
            _check(checks, "FX", tid, "Exchange Rate", fmt_value(er),
                   "not numeric", "An uploaded exchange rate must be numeric.",
                   "FAIL", "Exchange rate is not numeric.",
                   "The conversion amount would be wrong.",
                   "Enter a number, or leave blank to use the live system rate.")
        elif currency in ("USD", "ZAR") and not rate_available:
            _check(checks, "FX", tid, "Exchange Rate", "",
                   "unavailable", "No live or cached exchange rate is available.",
                   "FAIL", "Exchange rate unavailable.",
                   "The transaction cannot be converted into its schedule currency.",
                   "Refresh the rates or enter the official RBZ rate.")
        else:
            _check(checks, "FX", tid, "Exchange Rate",
                   fmt_value(er) or "system live rate",
                   None, "Conversion rate available.",
                   "PASS", "Exchange rate available.", "", "")

        # -- supporting documents -------------------------------------------
        doc = fmt_value(row.get("supporting_document_available"))
        has_doc = ve._bool(str(doc)) if fmt_value(doc) != "" else None
        need_doc = (direction == "sale" and category == "export") or \
                   direction in ("import_goods", "imported_service") or \
                   direction == "purchase"
        if need_doc and has_doc is False:
            _check(checks, "DOC", tid, "Supporting Document", fmt_value(doc),
                   "missing", "Required supporting documentation is missing.",
                   "REVIEW" if direction == "purchase" else "REVIEW",
                   "Supporting document missing.",
                   "The input-tax claim (or export zero-rating / import credit) may be disallowed on audit.",
                   "Retain the tax invoice / bill of entry / export (CD3) proof.")
        else:
            _check(checks, "DOC", tid, "Supporting Document",
                   "Available" if has_doc else "Not required",
                   None, "Documentation position is acceptable.",
                   "PASS", "Supporting document check passed.", "", "")

        # -- import information ----------------------------------------------
        if direction == "import_goods":
            cv = fmt_value(row.get("customs_value"))
            cd = fmt_value(row.get("customs_duty"))
            if cv == "" and cd == "":
                _check(checks, "IMP", tid, "Import information", "",
                       "missing", "Imports need a customs value and duty to "
                       "compute import VAT.",
                       "FAIL", "Import customs value/duty missing.",
                       "Import VAT cannot be computed; input credit may be lost.",
                       "Enter the customs value and customs duty.")
            else:
                _check(checks, "IMP", tid, "Import information",
                       f"CV={cv or '-'}, duty={cd or '-'}",
                       None, "Import VAT base available.",
                       "PASS" if cv != "" else "REVIEW",
                       "Import VAT base present.",
                       "", "")

        # -- adjustment information -------------------------------------------
        if direction == "adjustment":
            atype = fmt_value(row.get("adjustment_type"))
            invno = fmt_value(row.get("invoice_number"))
            if atype == "":
                _check(checks, "ADJ", tid, "Adjustment type", "",
                       "missing", "Adjustments require credit_note, debit_note, "
                       "bad_debt_relief or prior_period_correction.",
                       "FAIL", "Adjustment type missing.",
                       "The adjustment cannot be processed.",
                       "Choose an adjustment type.")
            else:
                _check(checks, "ADJ", tid, "Adjustment type", atype,
                       None, "Recognised adjustment type.",
                       "PASS", "Adjustment type valid.", "", "")
            if invno == "":
                _check(checks, "ADJREF", tid, "Adjustment reference", "",
                       "missing", "Adjustments should reference the original invoice.",
                       "REVIEW", "No original-invoice reference.",
                       "The adjustment cannot be traced to its original transaction.",
                       "Enter the original invoice number.")

        # -- duplicate IDs ----------------------------------------------------
        if tid:
            seen.setdefault(tid, []).append(idx)

    # duplicate rows (global)
    for tid, idxs in seen.items():
        if len(idxs) > 1:
            for idx in idxs:
                checks.append({
                    "check_id": "DUP", "txn_id": tid, "field": "Transaction ID",
                    "rule": "Transaction IDs must be unique.",
                    "value": tid, "status": "FAIL",
                    "what_failed": "Duplicate transaction ID.",
                    "why": f"'{tid}' appears {len(idxs)} times.",
                    "financial_impact": "The same transaction could be counted twice, "
                                        "inflating output or input VAT.",
                    "how_to_fix": "Rename the duplicate IDs so each is unique.",
                    "row_index": idx,
                })

    checks_df = pd.DataFrame(checks)
    return checks_df, norm


def _check(checks, cid, tid, field, value, problem, rule, status, what, impact, fix,
           why=None, row_index=None):
    checks.append({
        "check_id": cid, "txn_id": tid, "field": field, "rule": rule,
        "value": value, "status": (status if status in ("PASS", "REVIEW", "FAIL") else "REVIEW"),
        "what_failed": what if status == "FAIL" else ("Review needed: " + what if status == "REVIEW" else "Check passed"),
        "why": why or problem or "No problem detected.",
        "financial_impact": impact,
        "how_to_fix": fix,
        "row_index": row_index,
    })


def summary_of(checks_df):
    if checks_df.empty:
        return {"pass": 0, "review": 0, "fail": 0, "total": 0}
    return {
        "pass": int((checks_df["status"] == "PASS").sum()),
        "review": int((checks_df["status"] == "REVIEW").sum()),
        "fail": int((checks_df["status"] == "FAIL").sum()),
        "total": len(checks_df),
    }


def read_uploaded(uploaded):
    """Read an uploaded file (CSV or Excel) into a DataFrame."""
    name = (uploaded.name or "").lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded)
    raw = uploaded.getvalue()
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")