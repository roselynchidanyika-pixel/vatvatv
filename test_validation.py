"""Tests for the data-validation layer (PASS / REVIEW / FAIL checks)."""

import pandas as pd
import validation


def _df(rows):
    return pd.DataFrame(rows)


def test_missing_currency_flagged_review():
    df = _df([{"txn_id": "A1", "date": "2026-01-01", "direction": "sale",
               "description": "x", "category": "standard", "amount": 500}])
    checks, norm = validation.validate(df)
    ccy = checks[checks["check_id"] == "CCY"]
    assert not ccy.empty
    assert ccy.iloc[0]["status"] == "REVIEW"


def test_non_numeric_amount_failed():
    df = _df([{"txn_id": "A2", "date": "2026-01-01", "direction": "sale",
               "description": "x", "category": "standard", "amount": "abc"}])
    checks, _ = validation.validate(df)
    amt = checks[checks["check_id"] == "AMOUNT"]
    assert amt.iloc[0]["status"] == "FAIL"
    assert "not numeric" in amt.iloc[0]["why"]

def test_duplicate_id_failed():
    df = _df([
        {"txn_id": "D1", "date": "2026-01-01", "direction": "sale",
         "description": "x", "category": "standard", "amount": 100},
        {"txn_id": "D1", "date": "2026-01-02", "direction": "sale",
         "description": "y", "category": "standard", "amount": 200},
    ])
    checks, _ = validation.validate(df)
    dup = checks[checks["check_id"] == "DUP"]
    assert len(dup) == 2
    assert (dup["status"] == "FAIL").all()


def test_column_aliases_normalised():
    df = _df([{"Transaction ID": "A", "Date": "2026-01-01", "Type": "sale",
               "Details": "x", "VAT Category": "standard",
               "Amount (USD)": 100, "Currency": "USD"}])
    norm = validation.normalize_columns(df)
    assert {"txn_id", "date", "direction", "description", "category", "amount"}\
        .issubset(set(norm.columns))


def test_unknown_currency_failed():
    df = _df([{"txn_id": "A3", "date": "2026-01-01", "direction": "sale",
               "description": "x", "category": "standard", "amount": 500,
               "currency": "EUR"}])
    checks, _ = validation.validate(df)
    ccy = checks[checks["check_id"] == "CCY"]
    assert ccy.iloc[0]["status"] == "FAIL"


def test_import_without_customs_info_failed():
    df = _df([{"txn_id": "A4", "date": "2026-01-01", "direction": "import_goods",
               "description": "x", "category": "standard", "amount": 0}])
    checks, _ = validation.validate(df)
    imp = checks[checks["check_id"] == "IMP"]
    assert not imp.empty
    assert imp.iloc[0]["status"] == "FAIL"