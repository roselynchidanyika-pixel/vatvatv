"""pytest wrapper for the shared VAT test suite (TC01–TC21+)."""

import test_suite


def test_all_cases_pass():
    for row in test_suite.run_all():
        assert row["result"] == "PASS", (
            f"{row['id']} {row['name']}: {row['message']}")


def test_required_case_ids_present():
    ids = [r["id"] for r in test_suite.run_all()]
    required = {f"TC{str(i).zfill(2)}" for i in range(1, 17)}
    assert required.issubset(set(ids))