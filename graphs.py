"""graphs.py — Chart builders + MANDATORY plain-language explanation for every
graph (what the axes mean, what is happening, why it matters, Grade-7 version).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def _base_layout(title, ytitle, xtitle=None):
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16)),
        xaxis_title=xtitle, yaxis_title=ytitle,
        template="plotly_white", height=380, margin=dict(l=60, r=20, t=60, b=40),
    )
    return fig


def sales_by_category(result):
    data = result.chart_sales_by_category()
    fig = _base_layout("Sales by VAT category and currency schedule",
                       "Value of sales", "Schedule / category")
    for cat in ("Standard-rated", "Zero-rated", "Exempt"):
        sub = data[data["Category"] == cat]
        fig.add_bar(x=sub["Schedule"], y=sub["Value"], name=cat)
    if data.empty:
        fig.update_layout(title="No sales to display")
    return fig, {
        "x": "The x-axis shows each currency schedule (ZiG and USD) split into "
             "the three sale categories.",
        "y": "The y-axis shows the value of sales in each category.",
        "happening": _describe_sales(data),
        "why": "It shows how much VAT base sits in each category and currency, "
               "which drives the output-tax line on each schedule.",
        "grade7": "The bars show how much you sold in each type. Bigger bars "
                  "mean more sales in that category and currency.",
    }


def _describe_sales(data):
    if data.empty:
        return "No sales recorded."
    total = data["Value"].sum()
    std = float(data.loc[data["Category"] == "Standard-rated", "Value"].sum())
    zr = float(data.loc[data["Category"] == "Zero-rated", "Value"].sum())
    ex = float(data.loc[data["Category"] == "Exempt", "Value"].sum())
    lines = []
    if total:
        lines.append(f"Standard-rated sales are {std:,.2f} "
                     f"({std/total*100:.1f}% of turnover).")
        if zr:
            lines.append(f"Zero-rated sales are {zr:,.2f} ({zr/total*100:.1f}%).")
        if ex:
            lines.append(f"Exempt sales are {ex:,.2f} ({ex/total*100:.1f}%), "
                         "which may trigger input-tax apportionment.")
    return " ".join(lines) or "Sales were recorded outside the standard categories."


def output_vs_input(result):
    data = result.chart_output_vs_input()
    fig = _base_layout("Output VAT vs allowable input VAT (per schedule)",
                       "Amount", "Currency schedule")
    for comp in ("Output VAT", "Allowable Input VAT", "Net VAT"):
        sub = data[data["Component"] == comp]
        fig.add_bar(x=sub["Schedule"], y=sub["Amount"], name=comp)
    ex = _describe_out_in(data)
    return fig, {
        "x": "Each group shows one currency schedule (ZiG or USD).",
        "y": "The y-axis shows the amount of VAT in the return's currency.",
        "happening": ex,
        "why": "The gap between output VAT and input VAT is exactly the net VAT "
               "the business must pay or will be refunded.",
        "grade7": "The blue bars are the VAT you collected, the red/orange bars "
                  "are the VAT you paid on purchases, and the green is the "
                  "difference you must pay or may get back.",
    }


def _describe_out_in(data):
    if data.empty:
        return "No data to display."
    out = float(data.loc[data["Component"] == "Output VAT", "Amount"].sum())
    inp = float(data.loc[data["Component"] == "Allowable Input VAT", "Amount"].sum())
    net = out - inp
    verdict = ("more than" if net > 0 else "less than")
    return (f"Across both schedules, output VAT is {out:,.2f} and allowable "
            f"input VAT is {inp:,.2f}. Net VAT is therefore {net:,.2f} "
            f"({verdict} the input tax claimed).")


def monthly(result):
    data = result.chart_monthly()
    fig = _base_layout("Monthly output vs input VAT", "VAT amount",
                       "Tax period (year-month)")
    if data.empty:
        fig.update_layout(title="No dated transactions to display")
        return fig, {"x": "Month of the transaction.", "y": "VAT amount.",
                     "happening": "No data.", "why": "Nothing to analyse.",
                     "grade7": "No bars because there are no dates."}
    for comp, col in (("Output VAT", "Output VAT"), ("Input VAT", "Input VAT")):
        sub = data[["month", "schedule", col]] if not data.empty else data
        sub = data.copy()
        sub["label"] = sub["month"] + " " + sub["schedule"]
        fig.add_bar(x=sub["label"], y=sub[col], name=comp)
    return fig, {
        "x": "Each label shows the tax period (year-month) and currency schedule.",
        "y": "The VAT amount for that period.",
        "happening": _describe_monthly(data),
        "why": "It shows when VAT is being created, which helps with cash-flow "
               "planning and spotting unusual spikes.",
        "grade7": "This chart shows how much VAT you collected and paid each "
                  "month in each currency.",
    }


def _describe_monthly(data):
    if data.empty:
        return "No dated transactions to display."
    out = float(data["Output VAT"].sum())
    inp = float(data["Input VAT"].sum())
    return (f"Monthly output VAT totals {out:,.2f} and input VAT "
            f"{inp:,.2f} across the periods shown.")


def pass_fail(result):
    data = result.chart_pass_fail()
    fig = _base_layout("Transactions: PASS vs REVIEW vs FAIL",
                       "Number of transactions", "Compliance status")
    sub = data[data["Status"].isin(["PASS", "REVIEW", "FAIL"])]
    if sub.empty:
        fig.update_layout(title="No transactions to display")
        return fig, {"x": "Status category.", "y": "Count.",
                     "happening": "No data.", "why": "No data.",
                     "grade7": "No bars yet."}
    colors = {"PASS": "#1B5E20", "REVIEW": "#F9A825", "FAIL": "#C62828"}
    fig.add_bar(x=sub["Status"], y=sub["Transactions"],
                marker_color=[colors.get(s, "#1565C0") for s in sub["Status"]])
    return fig, {
        "x": "The x-axis shows the three possible transaction statuses.",
        "y": "The number of transactions with that status.",
        "happening": (_describe_pf(data)),
        "why": "FAIL/REVIEW rows are the ones to fix before filing; they flag "
               "data errors and missing documents.",
        "grade7": "Green bars are transactions that passed all checks. Yellow "
                  "bars need a closer look. Red bars have errors to fix.",
    }


def _describe_pf(data):
    n_pass = int(data.loc[data["Status"] == "PASS", "Transactions"].sum())
    n_review = int(data.loc[data["Status"] == "REVIEW", "Transactions"].sum())
    n_fail = int(data.loc[data["Status"] == "FAIL", "Transactions"].sum())
    return (f"{n_pass} transaction(s) passed all checks, {n_review} need "
            f"review, and {n_fail} failed and must be fixed.")


def vat_by_currency(result):
    data = result.chart_vat_by_currency()
    fig = _base_layout("Net VAT by currency schedule", "Amount")
    if data.empty:
        fig.update_layout(title="No data to display")
        return fig, {"x": "Currency schedule.", "y": "Amount.",
                     "happening": "No data.", "why": "No data.",
                     "grade7": "No bars yet."}
    fig.add_bar(x=data["Currency"], y=data["Output VAT"], name="Output VAT")
    fig.add_bar(x=data["Currency"], y=data["Input VAT"], name="Input VAT")
    fig.add_bar(x=data["Currency"], y=data["Net VAT"], name="Net VAT")
    return fig, {
        "x": "Each bar group is one currency schedule.",
        "y": "VAT amount in that currency.",
        "happening": _describe_ccy(data),
        "why": "Because ZIMRA keeps ZiG and USD schedules separate, this view "
               "shows where the balance sits per currency.",
        "grade7": "This shows how much VAT belongs to the USD books versus the "
                  "ZiG books.",
    }


def _describe_ccy(data):
    if data.empty:
        return "No data."
    parts = []
    for _, r in data.iterrows():
        parts.append(f"{r['Currency']}: output {r['Output VAT']:,.2f}, "
                     f"input {r['Input VAT']:,.2f}, net {r['Net VAT']:,.2f}.")
    return " ".join(parts)