"""test_suite.py — Reusable VAT test cases (TC01–TC21+).

The same functions are used by BOTH the Streamlit "Test Cases" page and the
pytest suite in tests/, so the in-app status always matches `pytest`.

Expected values are derived from the configured rate (config.VAT_RATE_PCT) so
the suite stays correct if the law changes and the rate is updated in one place.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pandas as pd

import config
import exchange_rates as fx
import sample_data
import vat_engine as ve

RATE_D = config.VAT_RATE_PCT / Decimal("100")
FRACTION = config.VAT_RATE_DECIMAL / (Decimal("1") + config.VAT_RATE_DECIMAL)


def vat_excl(amount):
    return ve.r2(Decimal(amount) * RATE_D)


def vat_incl(amount):
    return ve.r2(Decimal(amount) * FRACTION)


def approx(actual, expected, tol=0.02):
    assert abs(float(actual) - float(expected)) <= tol, \
        f"{actual} != {expected} (tol {tol})"


_RATES = {"USD": 1.0, "ZIG": 26.6347, "ZAR": 16.4314}
_SNAP = {"source": "test-feed", "date_label": "01 Jan 2026"}


_ROW_DEFAULTS = {
    "amount": 0, "vat_inclusive": False, "customs_value": 0, "customs_duty": 0,
    "prohibited_reason": None, "business_use_pct": 100, "adjustment_type": None,
    "mixed_input": False, "invoice_number": "", "supporting_document_available": True,
    "currency": "ZIG", "exchange_rate": None, "exchange_rate_date": "",
    "exchange_rate_source": "", "notes": "",
}


def _df(rows):
    full = [{**dict(_ROW_DEFAULTS), **r} for r in rows]
    return pd.DataFrame(full)


def _run(rows, **kw):
    return ve.compute_vat_return(_df(rows), rates=dict(_RATES),
                                 fx_snapshot=_SNAP, **kw)


# ---------------------------------------------------------------------------
def tc01_standard_sale_excl():
    r = _run([{"txn_id": "T1", "date": "2026-01-01", "direction": "sale",
               "description": "Sale", "category": "standard", "amount": 1000}])
    approx(r.total_output_tax, vat_excl(1000))
    assert r.status == "PAYABLE"


def tc02_standard_sale_incl():
    r = _run([{"txn_id": "T2", "date": "2026-01-01", "direction": "sale",
               "description": "Sale", "category": "standard", "amount": 1155,
               "vat_inclusive": True}])
    approx(r.total_output_tax, vat_incl(1155))


def tc03_zero_rated_sale():
    r = _run([{"txn_id": "T3", "date": "2026-01-01", "direction": "sale",
               "description": "ZR", "category": "zero_rated", "amount": 1000}])
    approx(r.total_output_tax, 0)
    assert r.status == "NIL"


def tc04_exempt_sale():
    r = _run([{"txn_id": "T4", "date": "2026-01-01", "direction": "sale",
               "description": "EX", "category": "exempt", "amount": 1000}])
    approx(r.ex_sales, 1000)
    approx(r.total_output_tax, 0)


def tc05_import_goods():
    r = _run([{"txn_id": "T5", "date": "2026-01-01", "direction": "import_goods",
               "description": "IMP", "category": "standard",
               "customs_value": 1000, "customs_duty": 100}])
    # default currency ZiG -> import base 1 100 converted into ZiG schedule
    base_zig = 1100
    approx(r.schedules["ZIG"].in_import, vat_excl(base_zig))


def tc06_credit_note():
    r = _run([{"txn_id": "T6", "date": "2026-01-01", "direction": "adjustment",
               "description": "CN", "category": "standard", "amount": 500,
               "adjustment_type": "credit_note"}])
    approx(r.schedules["ZIG"].out_adj, -vat_excl(500))


def tc07_debit_note():
    r = _run([{"txn_id": "T7", "date": "2026-01-01", "direction": "adjustment",
               "description": "DN", "category": "standard", "amount": 300,
               "adjustment_type": "debit_note"}])
    approx(r.schedules["ZIG"].out_adj, vat_excl(300))


def tc08_zig_transaction():
    r = _run([{"txn_id": "T8", "date": "2026-01-01", "direction": "sale",
               "description": "ZIG sale", "category": "standard", "amount": 2000,
               "currency": "ZIG"}])
    assert "ZIG" in r.schedules
    approx(r.schedules["ZIG"].out_std, vat_excl(2000))
    assert abs(float(r.schedules["USD"].out_std)) < 0.01


def tc09_usd_transaction():
    r = _run([{"txn_id": "T9", "date": "2026-01-01", "direction": "sale",
               "description": "USD sale", "category": "standard", "amount": 2000,
               "currency": "USD"}])
    approx(r.schedules["USD"].out_std, vat_excl(2000))
    assert abs(float(r.schedules["ZIG"].out_std)) < 0.01


def tc10_zar_transaction():
    r = _run([{"txn_id": "T10", "date": "2026-01-01", "direction": "sale",
               "description": "ZAR sale", "category": "standard", "amount": 16431.4,
               "currency": "ZAR"}])
    # 1000 USD equivalent at 16.4314 ZAR/USD
    approx(r.schedules["USD"].out_std, vat_excl(1000.0), tol=0.05)


def tc11_missing_exchange_rate():
    r = ve.compute_vat_return(
        _df([{"txn_id": "T11", "date": "2026-01-01", "direction": "sale",
              "description": "ZAR", "category": "standard", "amount": 5000,
              "currency": "ZAR"}]),
        rates={"USD": 1.0, "ZIG": 26.0}, fx_snapshot=_SNAP)
    row = r.trail.iloc[0]
    assert row["status"] == "FAIL"
    assert "exchange rate" in str(row["reason"]).lower()


def tc12_invalid_currency():
    r = _run([{"txn_id": "T12", "date": "2026-01-01", "direction": "sale",
               "description": "EUR", "category": "standard", "amount": 500,
               "currency": "EUR"}])
    assert r.trail.iloc[0]["status"] in ("FAIL", "REVIEW")


def tc13_missing_documentation():
    r = _run([{"txn_id": "T13", "date": "2026-01-01", "direction": "sale",
               "description": "Export", "category": "export", "amount": 5000,
               "supporting_document_available": False}])
    row = r.trail.iloc[0]
    assert row["status"] == "REVIEW"
    assert "export" in str(row["reason"]).lower()


def tc14_deminimis_invoice_pass():
    r = _run([{"txn_id": "T14", "date": "2026-01-01", "direction": "sale",
               "description": "small", "category": "standard", "amount": 8,
               "currency": "USD"}])
    assert r.de_minimis_invoice_rows
    assert r.de_minimis_invoice_rows[0]["status"] == "PASS"
    assert r.de_minimis_invoice_rows[0]["usd_equivalent"] < 10


def tc15_deminimis_invoice_fail():
    r = _run([{"txn_id": "T15", "date": "2026-01-01", "direction": "sale",
               "description": "large", "category": "standard", "amount": 15,
               "currency": "USD"}])
    assert r.de_minimis_invoice_rows
    assert r.de_minimis_invoice_rows[0]["status"] == "REVIEW"
    assert r.de_minimis_invoice_rows[0]["usd_equivalent"] >= 10


def tc16_complete_return():
    df = sample_data.load_sample("Amber Mart (ZiG worked example)")
    r = ve.compute_vat_return(df, rates=dict(_RATES), fx_snapshot=_SNAP)
    z = r.schedules["ZIG"]
    approx(z.sales_value, 34250)
    approx(z.out_std, 3642.50)
    approx(z.out_adj, -180.00)
    approx(z.rc_out, 300.00)
    approx(z.in_local, 1545.00)
    approx(z.in_import, 825.00)
    approx(z.rc_in, 300.00)
    approx(z.total_input, 2970.00)
    approx(z.net, 792.50)
    assert z.status == "PAYABLE"
    assert "De minimis" in z.apport_note or "de minimis" in z.apport_note


def tc17_currency_separation():
    rows = [
        {"txn_id": "A", "date": "2026-01-01", "direction": "sale",
         "description": "USD", "category": "standard", "amount": 10000,
         "currency": "USD"},
        {"txn_id": "B", "date": "2026-01-01", "direction": "sale",
         "description": "ZIG", "category": "standard", "amount": 10000,
         "currency": "ZIG"},
    ]
    r = _run(rows)
    # USD values never leak into the ZiG schedule and vice versa
    assert abs(float(r.schedules["USD"].std) - 10000.0) < 0.01
    assert abs(float(r.schedules["ZIG"].std) - 10000.0) < 0.01
    assert set(r.schedules.keys()) == {"USD", "ZIG"}


def tc18_reverse_charge():
    r = _run([{"txn_id": "T18", "date": "2026-01-01", "direction": "imported_service",
               "description": "svc", "category": "standard", "amount": 2000}])
    approx(r.schedules["ZIG"].rc_out, vat_excl(2000))
    approx(r.schedules["ZIG"].rc_in, vat_excl(2000))
    assert r.status == "NIL"


def tc19_prohibited_input():
    r = _run([{"txn_id": "T19", "date": "2026-01-01", "direction": "purchase",
               "description": "ent", "category": "standard", "amount": 1000,
               "prohibited_reason": "entertainment"}])
    assert abs(float(r.schedules["ZIG"].in_local)) < 0.01
    assert r.counts["n_review"] >= 1


def tc20_partial_business_use():
    r = _run([{"txn_id": "T20", "date": "2026-01-01", "direction": "purchase",
               "description": "car", "category": "standard", "amount": 1000,
               "business_use_pct": 70}])
    approx(r.schedules["ZIG"].in_local, vat_excl(1000) * Decimal("0.7"))


def tc21_bad_debt_relief():
    r = _run([{"txn_id": "T21", "date": "2026-01-01", "direction": "adjustment",
               "description": "bad", "category": "standard", "amount": 1155,
               "vat_inclusive": True, "adjustment_type": "bad_debt_relief"}])
    approx(r.schedules["ZIG"].out_adj, -vat_incl(1155))


# ---------------------------------------------------------------------------
TEST_CASES = [
    ("TC01", "Standard-rated sale (VAT exclusive)", tc01_standard_sale_excl),
    ("TC02", "Standard-rated sale (VAT inclusive)", tc02_standard_sale_incl),
    ("TC03", "Zero-rated sale", tc03_zero_rated_sale),
    ("TC04", "Exempt sale excluded", tc04_exempt_sale),
    ("TC05", "Import goods — VAT on customs value + duty", tc05_import_goods),
    ("TC06", "Credit note adjustment", tc06_credit_note),
    ("TC07", "Debit note adjustment", tc07_debit_note),
    ("TC08", "ZiG transaction (ZIG schedule only)", tc08_zig_transaction),
    ("TC09", "USD transaction (USD schedule only)", tc09_usd_transaction),
    ("TC10", "ZAR transaction (converted to USD schedule)", tc10_zar_transaction),
    ("TC11", "Missing exchange rate → FAIL", tc11_missing_exchange_rate),
    ("TC12", "Invalid currency", tc12_invalid_currency),
    ("TC13", "Missing documentation → REVIEW", tc13_missing_documentation),
    ("TC14", "Invoicing de minimis PASS (< US$10)", tc14_deminimis_invoice_pass),
    ("TC15", "Invoicing de minimis FAIL (≥ US$10)", tc15_deminimis_invoice_fail),
    ("TC16", "Complete VAT return calculation (worked example)", tc16_complete_return),
    ("TC17", "Currency separation — USD & ZiG never mixed", tc17_currency_separation),
    ("TC18", "Reverse charge on imported services", tc18_reverse_charge),
    ("TC19", "Prohibited input — no input claim", tc19_prohibited_input),
    ("TC20", "Partial business use (70%)", tc20_partial_business_use),
    ("TC21", "Bad-debt relief", tc21_bad_debt_relief),
]


def run_all():
    """Run every test case; return list of {id, name, result, message}."""
    results = []
    for tc_id, name, fn in TEST_CASES:
        try:
            fn()
            results.append({"id": tc_id, "name": name, "result": "PASS",
                            "message": "Expected result matched actual result."})
        except AssertionError as e:
            results.append({"id": tc_id, "name": name, "result": "FAIL",
                            "message": f"AssertionError: {e}"})
        except Exception as e:
            results.append({"id": tc_id, "name": name, "result": "ERROR",
                            "message": f"{type(e).__name__}: {e}"})
    return results