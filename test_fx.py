"""Tests for the live exchange-rate module."""

import exchange_rates as fx


def test_rates_have_all_currencies():
    snap = fx.get_rates()
    for ccy in ("USD", "ZIG", "ZAR"):
        assert ccy in snap["rates"]
        assert snap["rates"][ccy] > 0


def test_convert_usd_zig():
    snap = fx.get_rates()
    zig = fx.convert(1, "USD", "ZIG", snap["rates"])
    assert zig is not None and zig > 0
    back = fx.convert(zig, "ZIG", "USD", snap["rates"])
    assert back is not None and abs(back - 1.0) < 0.001


def test_cross_rate_zar_usd():
    snap = fx.get_rates()
    zar_per_usd = fx.cross_rate("USD", "ZAR", snap["rates"])
    one_usd = fx.convert(1, "USD", "ZAR", snap["rates"])
    assert zar_per_usd == one_usd


def test_convert_row_to_schedule_zar_to_usd():
    snap = fx.get_rates()
    conv, rate, math, ok, err = fx.convert_row_to_schedule(
        16431.4, "ZAR", "USD", snap["rates"])
    assert ok and err is None
    assert abs(conv - 1000.0) < 5.0
    assert "USD" in math and "ZAR" in math


def test_unavailable_rate_returns_fail():
    rates = {"USD": 1.0, "ZIG": 26.0}     # no ZAR
    conv, rate, math, ok, err = fx.convert_row_to_schedule(100, "ZAR", "USD", rates)
    assert not ok
    assert "exchange rate" in err.lower()


def test_rates_table_statuses():
    snap = fx.get_rates()
    table = fx.rates_table(snap)
    assert len(table) == 3
    assert all("PASS" in t["Status"] for t in table)