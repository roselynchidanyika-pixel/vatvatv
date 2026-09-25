"""report_generator.py — Professional management report (Markdown) built from a
computed VATResult. Sections follow the project brief. Also builds shorter
email / WhatsApp message text for sharing the final summary.
"""

from __future__ import annotations

import re
from datetime import datetime

import config


def _period_str(result):
    dates = [d for d in result.trail["date"].dropna().tolist() if str(d) != ""]
    if not dates:
        return "current period"
    try:
        months = sorted({str(d)[:7] for d in dates})
        return months[0] if len(months) == 1 else f"{months[0]} to {months[-1]}"
    except Exception:
        return "current period"


def _table(headers, rows):
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    return "\n".join([head, sep, body]) + "\n"


def build_markdown_report(result, git_url="", streamlit_url=""):
    """Full professional report as a Markdown string."""
    period = _period_str(result)
    m = result.management()
    lines = []

    lines.append("# Zimbabwe VAT Return Automation System — Management Report")
    lines.append("")
    lines.append(f"**Period covered:** {period}  ")
    lines.append(f"**Generated:** {datetime.now().strftime('%d %B %Y %H:%M')}  ")
    lines.append(f"**System:** Explainable Zimbabwe VAT 7 Return Assistant")
    lines.append("")
    lines.append("> DEMO / SIMULATED DATA — NOT REAL TAXPAYER DATA. ")
    lines.append(config.DISCLAIMER)
    lines.append("")

    # -- Executive Summary -----------------------------------------------
    lines.append("## 1. Executive Summary")
    net_word = "payable to ZIMRA" if m["net_vat"] > 0 else ("refundable / held as a credit" if m["net_vat"] < 0 else "a nil position")
    lines.append(
        f"This automated system processed **{m['n_txns']}** transactions "
        f"({m['n_pass']} PASS, {m['n_review']} review, {m['n_fail']} FAIL). "
        f"Total output tax is **{m['output_vat']:,.2f}** and allowable input "
        f"tax is **{m['input_vat']:,.2f}**, giving a net VAT position of "
        f"**{m['net_vat']:,.2f}** — **{m['status']}** ({net_word}). "
        "Because Zimbabwe requires **separate schedules per currency**, the "
        "ZiG schedule and the USD schedule are reported and filed separately "
        "and are never mixed.")
    lines.append("")

    lines.append("## 2. Introduction & Objectives")
    lines.append(
        "The project builds a working automated system that calculates a "
        "Zimbabwe VAT (VAT 7) return from accounting transaction data. It "
        "computes output VAT and allowable input VAT, processes adjustments, "
        "imports, reverse-charge and multi-currency transactions, applies "
        "zero-rated and exempt treatment, and produces a clear, auditable "
        "calculation trail — with every formula, value substitution and "
        "PASS/FAIL check visible to the user.")
    lines.append("")

    lines.append("## 3. Zimbabwe VAT Background")
    lines.append(
        f"Value Added Tax was introduced in Zimbabwe in 2004 (replacing the "
        f"former sales tax). The standard rate is **{float(config.VAT_RATE_PCT):g}%** "
        f"with effect from {config.VAT_RATE_EFFECTIVE} (Finance Act (No. 7) of "
        f"2025). Compulsory registration applies where taxable supplies exceed "
        f"**US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f}** in any "
        f"12-month period ({config.REGISTRATION_EFFECTIVE}). Zero-rated supplies "
        f"(VAT Act s10) carry a 0% rate with input-tax credit preserved; exempt "
        f"supplies (VAT Act s11) carry no output tax and generally no input-tax "
        "credit. Imported goods are taxed on the customs value plus duty, and "
        "imported services are reverse-charged (VAT Act s13A).")
    lines.append("")

    lines.append("## 4. Results by Currency Schedule (separate, never mixed)")
    lines.append("")
    for ccy, sched in result.schedules.items():
        lines.append(f"### {ccy} schedule")
        lines.append("")
        rows = [(no, desc, (f"{amt:,.2f}" if not isinstance(amt, str) else amt))
                for no, desc, amt, _ in sched.lines()]
        lines.append(_table(["Line", "Description", f"Amount ({ccy})"], rows))
        if sched.apport_note:
            lines.append(f"\n**Apportionment note:** {sched.apport_note}\n")
    lines.append("")

    if result.combined:
        c = result.combined
        lines.append("### Informational combined view (ZiG equivalent)")
        lines.append("")
        lines.append(
            f"Net position ≈ **{c['net_zig']:,.2f} ZiG** (informational only — "
            "the return is filed on the separate schedules above).")
        lines.append("")
        lines.append(f"> {c['note']}")
        lines.append("")

    lines.append("## 5. Management Summary")
    lines.append("")
    lines.append(_table(
        ["Measure", "Value"],
        [["Total sales value", f"{m['total_sales']:,.2f}"],
         ["Taxable (standard-rated) sales", f"{m['taxable_sales']:,.2f}"],
         ["Zero-rated sales", f"{m['zero_sales']:,.2f}"],
         ["Exempt sales", f"{m['exempt_sales']:,.2f}"],
         ["Output VAT", f"{m['output_vat']:,.2f}"],
         ["Allowable input VAT", f"{m['input_vat']:,.2f}"],
         ["Import VAT (goods)", f"{m['imports_vat']:,.2f}"],
         ["Output adjustments", f"{m['adjustments_vat']:,.2f}"],
         ["Net VAT", f"{m['net_vat']:,.2f} ({m['status']})"],
         ["Transactions processed", m["n_txns"]],
         ["PASS / REVIEW / FAIL", f"{m['n_pass']} / {m['n_review']} / {m['n_fail']}"]]))
    lines.append("")
    lines.append("### Plain-English explanation")
    lines.append(
        f"We looked at {m['n_txns']} transactions. The business sold taxable "
        f"goods worth {m['taxable_sales']:,.2f} plus zero-rated sales of "
        f"{m['zero_sales']:,.2f}. The VAT collected on sales (output VAT) is "
        f"{m['output_vat']:,.2f}. VAT paid on its own purchases that is "
        f"allowable (input VAT) is {m['input_vat']:,.2f}. After subtracting "
        f"input VAT from output VAT, the net amount is {m['net_vat']:,.2f} — "
        f"which means the business must **{net_word}** this VAT period.")
    lines.append("")

    lines.append("## 6. Legal Assumptions")
    lines.append("")
    for ref, desc, url in config.REFERENCES:
        lines.append(f"- **{ref}** — {desc} ({url})")
    lines.append("")
    lines.append(_table(
        ["Rule", "Value", "Effective", "Source"],
        [["Standard VAT rate", f"{float(config.VAT_RATE_PCT):g}%",
          config.VAT_RATE_EFFECTIVE, "Finance Act (No. 7) of 2025"],
         ["Registration threshold", f"US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f}",
          config.REGISTRATION_EFFECTIVE, "VAT Act / Finance Act (No. 13) of 2023"],
         ["Invoicing de minimis", f"US${float(config.DE_MINIMIS_INVOICE_USD):,.2f}",
          config.DE_MINIMIS_INVOICE_EFFECTIVE, "VAT Act s20"],
         ["Apportionment de minimis", f"{config.DE_MINIMIS_APPORTIONMENT_PCT*100:g}% exempt",
          config.DE_MINIMIS_APPORTIONMENT_EFFECTIVE, "VAT Act s16 practice"],
         ["Input-tax claim window", f"{config.INPUT_TAX_CLAIM_MONTHS} months",
          "current", "VAT Act s16"]]))
    lines.append("")

    lines.append("## 7. Computational Assumptions")
    lines.append("")
    lines.append("- VAT-inclusive amounts carry the fraction "
                 f"{float(config.VAT_RATE_PCT):g}/{100+float(config.VAT_RATE_PCT):g}.")
    lines.append("- Imports: VAT = rate x (customs value + customs duty).")
    lines.append("- Imported services: reverse charge with a mirror input credit "
                 "proportionate to business use for taxable supplies.")
    lines.append("- Credit notes reduce output VAT; debit notes increase it; "
                 "bad-debt relief uses the VAT-inclusive fraction of the debt.")
    lines.append("- ZAR transactions are converted into the **USD** schedule at "
                 "the applicable exchange rate; ZiG and USD schedules are kept "
                 "**fully separate**.")
    lines.append("- Rounding: half-up to 2 decimal places in the schedule "
                 "currency.")
    lines.append("- Exchange rates: live feed from open.er-api.com shadowing the "
                 "RBZ official ZiG/USD rate; an official RBZ rate can be entered "
                 "manually as an override. Rates and their source/date are shown "
                 "on every conversion.")
    lines.append("")

    lines.append("## 8. Limitations")
    lines.append(
        "1. Educational/demonstration system — it is not tax advice and does not "
        "replace TaRMS filing.\n"
        "2. Results depend on the accuracy and VAT classification of the "
        "transaction data entered.\n"
        "3. Exchange rates depend on the live feed / manual official rate.\n"
        "4. Zimbabwe VAT law changes frequently; legal values must be re-verified "
        "before periods under new legislation.\n"
        "5. Apportionment uses the simple turnover-based method.")
    lines.append("")

    lines.append("## 9. Recommendations")
    lines.append(
        "1. Re-verify rates and thresholds against current ZIMRA publications "
        "before each filing period.\n"
        "2. Keep proper fiscal tax invoices and bills of entry for every "
        "input-tax claim.\n"
        "3. Reconcile output VAT to sales and input VAT to purchases monthly.\n"
        "4. Manually review every REVIEW/FAIL row before submission.\n"
        "5. Update the official RBZ exchange rate when filing a period.\n"
        "6. Re-run the automated test suite whenever a rule changes.")
    lines.append("")

    lines.append("## 10. Conclusion")
    lines.append(
        "The system demonstrates a transparent, explainable approach to "
        "computing a Zimbabwe VAT return: it separates the ZiG and USD "
        "schedules as ZIMRA requires, exposes every calculation with its "
        "formula, values and result, validates the data with PASS/FAIL checks, "
        "and produces an auditable trail from individual transactions to the "
        "final VAT payable or refundable position.")
    lines.append("")

    lines.append("## 11. References & Submission Links")
    lines.append("")
    for ref, desc, url in config.REFERENCES:
        lines.append(f"- {ref}: {url}")
    if git_url:
        lines.append(f"- GitHub repository: {git_url}")
    if streamlit_url:
        lines.append(f"- Live Streamlit application: {streamlit_url}")
    lines.append("")
    lines.append("---")
    lines.append("_END OF REPORT — DEMO / SIMULATED DATA — NOT REAL TAXPAYER DATA_")
    return "\n".join(lines)


def md_to_text(md):
    """Crude Markdown -> plain text for email/WhatsApp bodies."""
    text = re.sub(r"\|[-| ]*\|", "", md)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"(-|\*) ", "- ", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def share_text(result):
    """Short management summary for email / WhatsApp."""
    period = _period_str(result)
    m = result.management()
    lines = [
        f"ZIMBABWE VAT 7 — {period.upper()}",
        "=" * 50,
        f"Transactions processed : {m['n_txns']} (PASS {m['n_pass']} / "
        f"REVIEW {m['n_review']} / FAIL {m['n_fail']})",
        f"Output VAT            : {m['output_vat']:,.2f}",
        f"Allowable input VAT   : {m['input_vat']:,.2f}",
        f"Import VAT (goods)    : {m['imports_vat']:,.2f}",
        f"Output adjustments    : {m['adjustments_vat']:,.2f}",
        f"NET VAT POSITION      : {m['net_vat']:,.2f}  ({m['status']})",
        "=" * 50,
    ]
    for ccy, sched in result.schedules.items():
        net = float(sched.net)
        lines.append(f"{ccy} schedule net: {net:,.2f} {ccy} ({sched.status})")
    lines.append("")
    lines.append("ZIMRA rule applied: USD and ZiG schedules are kept separate "
                 "and never mixed.")
    lines.append(config.DISCLAIMER)
    return "\n".join(lines)