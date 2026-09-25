"""app.py — ZIMBABWE VAT RETURN AUTOMATION & EXPLAINABLE VAT SYSTEM.

Streamlit front end. The system is:
    LEARN → ENTER → CHECK → CONVERT → CALCULATE → EXPLAIN → VISUALISE
          → AUDIT → REPORT

Every important calculation is shown on the screen: formula → values used →
substitution → answer → plain-language explanation → rule → PASS/FAIL. Nothing
happens invisibly. ZiG and USD VAT schedules are kept fully separate because
ZIMRA requires it — they are never mixed on a single schedule.
"""

from __future__ import annotations

import datetime as _dt
import io
import pathlib

import pandas as pd
import streamlit as st

import config
import exchange_rates as fx
import explanations
import graphs
import report_generator
import sample_data
import share
import test_suite
import validation
import vat_engine as ve

st.set_page_config(page_title="Zimbabwe VAT Return Assistant", page_icon="🇿🇼",
                   layout="wide")

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
LOGO_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='90' height='90' viewBox='0 0 90 90'>"
    "<circle cx='45' cy='45' r='44' fill='#12315E'/>"
    "<circle cx='45' cy='45' r='38' fill='#F2B705'/>"
    "<circle cx='45' cy='45' r='38' fill='none' stroke='#0D2A52' stroke-width='3'/>"
    "<g fill='#12315E'><circle cx='31' cy='33' r='10'/><circle cx='59' cy='33' r='10'/>"
    "<rect x='31' y='45' width='28' height='13'/></g>"
    "<text x='45' y='70' font-size='12' font-family='Arial' text-anchor='middle' "
    "font-weight='bold' fill='#12315E'>ZIMRA</text></svg>"
)
LOGO_DATA_URI = "data:image/svg+xml;utf8," + LOGO_SVG.replace(" ", "%20").replace("#", "%23")

CSS = """
<style>
.brand { display:flex; align-items:center; gap:16px; padding:8px 4px 4px 4px; }
.brand-title { color:#12315E; font-size:30px; font-weight:800; line-height:1.15; }
.brand-sub { color:#5A6B7E; font-size:14px; margin-top:3px; }
.raw-banner { border:2px solid #1565C0; border-radius:12px; padding:12px 16px;
  background:linear-gradient(90deg,#EAF2FB,#F7FAFD); margin:10px 0 6px 0; }
.rule-box { background:#FFF8E1; border:1px solid #F9A825; border-radius:10px;
  padding:10px 14px; margin:8px 0; }
.vat-table { width:100%; border-collapse:collapse; font-family:sans-serif; font-size:14px; }
.vat-table th, .vat-table td { border:1px solid #B9C7D6; padding:7px 10px; text-align:left; }
.vat-table th { background:#1565C0; color:#fff; }
.vat-table .net { background:#E8F1FB; font-weight:700; }
.vat-table .even { background:#FAFBFD; }
.pill { display:inline-block; background:#EAF2FB; border:1px solid #1565C0;
  border-radius:10px; padding:6px 10px; margin:3px 6px 3px 0; font-size:14px; }
.pill b { color:#1565C0; }
.kpi { border:1px solid #D6E0EA; border-radius:12px; padding:12px 14px;
  background:#fff; box-shadow:0 1px 3px rgba(18,49,94,.08); }
.ghost { color:#607B96; font-size:13px; }
.hero { border-radius:16px; padding:22px 26px; color:#fff;
  background:linear-gradient(120deg,#0D2A52 0%,#1565C0 55%,#1E88E5 100%);
  box-shadow:0 6px 18px rgba(18,49,94,.25); margin:6px 0 18px 0; }
.hero .big { font-size:34px; font-weight:800; line-height:1.15; }
.hero .sub { font-size:14px; opacity:.92; margin-top:4px; }
.pillstatus { display:inline-block; padding:5px 14px; border-radius:999px;
  font-weight:700; font-size:13px; margin-left:8px; }
.pill-b { background:#FFE082; color:#4E3500; }
.pill-g { background:#C8E6C9; color:#1B5E20; }
.pill-o { background:#FFE0B2; color:#BF360C; }
.tile { background:#fff; border-radius:14px; padding:16px 16px 12px 16px;
  box-shadow:0 2px 8px rgba(18,49,94,.10); border-top:5px solid #1565C0;
  height:100%; }
.tile.grn { border-top-color:#43A047; } .tile.org { border-top-color:#FB8C00; }
.tile.red { border-top-color:#E53935; } .tile.gld { border-top-color:#F9A825; }
.tile .lbl { color:#5A6B7E; font-size:12px; font-weight:700; letter-spacing:.4px;
  text-transform:uppercase; }
.tile .num { font-size:24px; font-weight:800; color:#12315E; margin-top:4px; }
.tile .foot { font-size:12px; color:#8AA0B6; margin-top:4px; }
.workbox { border-radius:12px; padding:12px 16px; margin:8px 0 14px 0;
  background:#F4F8FD; border:1px solid #CDE0F3; }
.workbox h4 { margin:0 0 4px 0; color:#12315E; }
.formula { background:#12315E; color:#fff; border-radius:10px; padding:10px 16px;
  font-size:15px; font-weight:600; margin:6px 0; }
.formula .hi { color:#FFD54F; }
.hint { color:#5A6B7E; font-size:13px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.markdown(
    f"<div class='brand'><img src='{LOGO_DATA_URI}' width='90' height='90'>"
    f"<div><div class='brand-title'>🇿🇼 ZIMBABWE VAT RETURN AUTOMATION SYSTEM</div>"
    f"<div class='brand-sub'>Explain • Calculate • Validate • Visualise • Audit — "
    f"VAT 7 Return Assistant (multi-currency, explained, auditable)</div></div></div>",
    unsafe_allow_html=True)
st.markdown(
    "<div class='raw-banner'>⚠️ <b>ZIMRA multi-currency rule:</b> <b>ZiG</b> and "
    "<b>USD</b> transactions are computed on <b>separate VAT 7 schedules</b> — "
    "they are never mixed. ZAR transactions are converted into the USD schedule "
    "at the applicable exchange rate. Every conversion shows its rate, source "
    "and date.</div>",
    unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def load_fx(refresh=False, manual_zig=None):
    force = refresh or "fx" not in st.session_state
    snap = fx.get_rates(refresh=force, manual_zig=manual_zig)
    st.session_state.fx = snap
    return snap


def get_working_df():
    """Working transactions = uploaded/loaded source + manually added rows."""
    base = st.session_state.get("base_df")
    parts = []
    if base is not None and len(base):
        parts.append(base)
    manual = st.session_state.get("manual_rows", [])
    if manual:
        parts.append(pd.DataFrame(manual, columns=ve.TRAIL_COLUMNS)[
            ["txn_id", "date", "direction", "description", "counterparty",
             "category", "amount", "vat_inclusive", "customs_value",
             "customs_duty", "prohibited_reason", "business_use_pct",
             "adjustment_type", "mixed_input", "import_flag", "invoice_number",
             "supporting_document_available", "currency", "exchange_rate",
             "exchange_rate_date", "exchange_rate_source", "notes"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def run_compute():
    df = get_working_df()
    if df.empty:
        st.error("No transactions to compute. Load demo data, upload a file, or "
                 "enter transactions manually.")
        return None
    checks, norm = validation.validate(df)
    snap = st.session_state.get("fx") or load_fx()
    de_minimis = st.session_state.get("de_minimis", True)
    with st.spinner("Computing the VAT return with a full auditable trail..."):
        res = ve.compute_vat_return(norm, de_minimis=de_minimis,
                                    rates=snap["rates"], fx_snapshot=snap)
    st.session_state.result = res
    st.session_state.norm_df = norm
    st.session_state.checks = checks
    st.success("Computation complete. Open the Return Summary to see the "
               "schedules, all workings and the audit trail.")
    return res


def run_checks():
    df = get_working_df()
    if df.empty:
        st.warning("Load or enter transactions before validating.")
        return
    with st.spinner("Checking every transaction..."):
        checks, norm = validation.validate(df)
    st.session_state.checks = checks
    st.session_state.norm_df = norm
    summ = validation.summary_of(checks)
    st.success(f"Checks complete: {summ['pass']} PASS · {summ['review']} REVIEW · "
               f"{summ['fail']} FAIL.")


def period_label(df):
    if df is None or len(df) == 0 or "date" not in df.columns:
        return "unnamed tax period"
    dates = [str(d) for d in df["date"].tolist() if str(d) != "" and str(d) != "nan"]
    if not dates:
        return "unnamed tax period"
    try:
        months = sorted({d[:7] for d in dates})
        period = months[0] if len(months) == 1 else f"{months[0]} to {months[-1]}"
        due = _dt.date(int(months[-1][:4]), int(months[-1][5:7]), 1)
        due += _dt.timedelta(days=31)
        return f"Tax period {period}"
    except Exception:
        return "current tax period"


def st_status(status):
    return {"PASS": "🟢 PASS", "REVIEW": "🟠 REVIEW", "FAIL": "🔴 FAIL"}.get(status, status)


CATEGORY_GUIDE = [
    ("standard", "Standard-rated — VAT is charged at 15.5% on the supply."),
    ("zero_rated", "Zero-rated — VAT at 0%; input VAT on related costs is still claimable."),
    ("exempt", "Exempt — no VAT charged, and input VAT on costs linked to it is generally not claimable."),
    ("export", "Export — zero-rated (0%) once proof of export is held."),
    ("import_goods", "Imported goods — VAT charged at customs on value + duty; claimable as input."),
    ("imported_service", "Imported service — reverse-charged (output + mirror input)."),
]
CATEGORY_GUIDE_DICT = dict(CATEGORY_GUIDE)


def category_legend():
    st.markdown(
        "<div class='rule-box'><b>Which supply type is it? (exempt / standard / "
        "zero-rated)</b><br>" +
        "<br>".join(f"• <b>{k}</b> — {v}" for k, v in CATEGORY_GUIDE) +
        "</div>", unsafe_allow_html=True)


def vat_definition_box():
    st.markdown(
        "<div class='workbox'><h4>💡 What is VAT?</h4>" + config.VAT_DEFINITION +
        "</div>", unsafe_allow_html=True)


def read_uploaded(uploaded):
    name = (uploaded.name or "").lower()
    try:
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded)
        return pd.read_csv(io.BytesIO(uploaded.getvalue()), encoding="utf-8-sig")
    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")
        return None


# ---------------------------------------------------------------------------
# Schedule rendering (13-line ZIMRA VAT 7 table)
# ---------------------------------------------------------------------------
def render_schedule(ccy):
    res = st.session_state.get("result")
    if res is None or ccy not in res.schedules:
        return
    sched = res.schedules[ccy]
    rows = sched.lines()
    legend = {"ZIG": "ZiG", "USD": "US Dollar"}.get(ccy, ccy)
    html = (f"<table class='vat-table'><thead><tr><th>Line</th><th>Description</th>"
            f"<th style='text-align:right'>Amount ({legend})</th></tr></thead><tbody>")
    for i, (no, desc, amt, emph) in enumerate(rows):
        cls = "net" if no in ("5", "10", "11", "13") else ("even" if i % 2 else "")
        val = f"{amt:,.2f}" if not isinstance(amt, str) else amt
        html += (f"<tr class='{cls}'><td>{no}</td><td>{desc}</td>"
                 f"<td style='text-align:right'>{val}</td></tr>")
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    if sched.apport_note:
        st.info("**Apportionment note:** " + sched.apport_note)
    st.caption(
        f"{ccy} schedule net = {float(sched.net):,.2f} {legend} — "
        f"status **{sched.status}**. This schedule is filed separately from the "
        "other currency schedule (ZIMRA requirement).")


def _work_rows(t, side=None, categories=None):
    m = t
    if side:
        m = m[m["side"] == side]
    if categories:
        m = m[m["category"].isin(categories)]
    if m.empty:
        return pd.DataFrame()
    return m[["txn_id", "description", "category", "vat_math", "vat_amount"]].copy()


def _detail_table(m, L):
    if m.empty:
        st.caption("No transactions feed this line.")
        return
    view = m.copy()
    view["vat_amount"] = view["vat_amount"].map(lambda v: f"{float(v):,.2f}")
    view["category"] = view["category"].map(
        lambda c: f"{c} — {CATEGORY_GUIDE_DICT.get(c, '')}")
    st.dataframe(view.rename(columns={"txn_id": "Txn", "description": "Description",
                                      "category": "Category", "vat_math": "VAT calculation",
                                      "vat_amount": f"VAT ({L})"}),
                 hide_index=True, use_container_width=True)


def _step(title, hint):
    st.markdown(
        f"<div class='workbox'><h4>{title}</h4>"
        f"<span class='hint'>{hint}</span></div>", unsafe_allow_html=True)


def _formula(expr, answer, note=""):
    st.markdown(
        f"<div class='formula'>{expr} = <span class='hi'>{answer}</span>"
        f"{(' · ' + note) if note else ''}</div>", unsafe_allow_html=True)


def show_workings(res):
    st.subheader("🧮 Show All Workings — every schedule line traced to transactions")
    labels = {"ZIG": "ZiG", "USD": "USD"}
    for ccy, sched in res.schedules.items():
        L = labels.get(ccy, ccy)
        t = res.trail[res.trail["schedule"] == ccy]

        st.markdown(f"#### {ccy} schedule ({L}), filed separately")
        _step("STEP 1 — Sales: what kind of supply is it? (line 1)",
              "Each sale falls into one supply category. The category decides the "
              "VAT treatment: standard, zero-rated or exempt.")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='tile'><div class='lbl'>Standard-rated</div>"
                    f"<div class='num'>{float(sched.std):,.2f} {L}</div>"
                    f"<div class='foot'>VAT charged at 15.5%.</div></div>",
                    unsafe_allow_html=True)
        c2.markdown(f"<div class='tile grn'><div class='lbl'>Zero-rated</div>"
                    f"<div class='num'>{float(sched.zr):,.2f} {L}</div>"
                    f"<div class='foot'>0% VAT — input VAT still claimable.</div></div>",
                    unsafe_allow_html=True)
        c3.markdown(f"<div class='tile org'><div class='lbl'>Exempt</div>"
                    f"<div class='num'>{float(sched.ex):,.2f} {L}</div>"
                    f"<div class='foot'>No VAT — input VAT generally not claimable.</div></div>",
                    unsafe_allow_html=True)
        _formula("Line 1 (total sales) = Standard + Zero-rated + Exempt",
                 f"{float(sched.sales_value):,.2f} {L}")

        _step("STEP 2 — Output VAT: VAT the business charges on sales (lines 2–4 → line 5)",
              "Output VAT is collected from customers and paid to ZIMRA.")
        _formula("Line 2 (output tax on standard sales) = Standard sale value × 15.5%",
                 f"{float(sched.out_std):,.2f} {L}")
        _detail_table(_work_rows(t, side="Output", categories=["standard"]), L)
        _formula("Line 3 (adjustments) = credit notes (−) + debit notes (+) + bad-debt relief (−)",
                 f"{float(sched.out_adj):,.2f} {L}")
        _detail_table(_work_rows(t, side="Adjustment"), L)
        _formula("Line 4 (reverse charge, imported services) = Service value × 15.5%",
                 f"{float(sched.rc_out):,.2f} {L}")
        _detail_table(_work_rows(t, side="Output", categories=["imported_service"]), L)
        _formula("Line 5 (total output tax) = Line 2 + Line 3 + Line 4",
                 f"{float(sched.total_output):,.2f} {L}")

        _step("STEP 3 — Input VAT: VAT the business paid and can deduct (lines 6–9 → line 10)",
              "Input VAT is deducted from output VAT before paying the net amount.")
        _formula("Line 6 (local purchases) = Σ Purchase VAT × business-use %",
                 f"{float(sched.in_local):,.2f} {L}")
        _detail_table(_work_rows(t, side="Input", categories=["standard"]), L)
        _formula("Line 7 (imports of goods) = Σ (Customs value + duty) × 15.5%",
                 f"{float(sched.in_import):,.2f} {L}")
        _detail_table(_work_rows(t, side="Input", categories=["import_goods"]), L)
        _formula("Line 8 (reverse-charge mirror input) = Σ Mirror credit",
                 f"{float(sched.rc_in):,.2f} {L}")
        _detail_table(_work_rows(t, side="Input", categories=["imported_service"]), L)
        mixed_rows = _work_rows(t, side="Input", categories=["mixed"])
        if not mixed_rows.empty:
            st.markdown(
                "**Mixed (overhead) inputs** — held for apportionment: "
                f"recovered {float(sched.mixed_deductible):,.2f} {L}, "
                f"disallowed (line 9) {float(sched.disallowed):,.2f} {L}. "
                "Prohibited inputs (entertainment, passenger cars, clubs) are "
                "excluded — claim = 0.")
            _detail_table(mixed_rows, L)
        prohib = _work_rows(t, side="Input", categories=["prohibited"])
        if not prohib.empty:
            st.caption("Excluded traces (input VAT legally blocked, claim = 0):")
            _detail_table(prohib, L)
        _formula("Line 10 (total allowable input tax) = L6 + L7 + L8 + mixed recovered − L9",
                 f"{float(sched.total_input):,.2f} {L}")

        _step("STEP 4 — THE FINAL ANSWER", "Net VAT is output tax minus input tax.")
        _formula(f"Line 11 = Line 5 − Line 10 = {float(sched.total_output):,.2f} − "
                 f"{float(sched.total_input):,.2f}",
                 f"{float(sched.net):,.2f} {L} ({sched.status})")
        st.markdown(f"**Line 13 = |Line 11| = {abs(float(sched.net)):,.2f} {L}** "
                    "— the VAT due for the period.")
        st.divider()

    st.markdown(
        "> <b>MASTER FORMULA:</b> Output VAT − Allowable Input VAT ± Adjustments = "
        "Net VAT position. Every figure above is traced to individual "
        "transactions in the Audit Trail below.")


def show_audit(res):
    st.subheader("🕵️ Audit Trail — trace every number back to its transaction")
    cols = ["txn_id", "date", "description", "side", "currency", "schedule",
            "fx_rate", "fx_math", "converted_amount", "vat_rate", "vat_amount",
            "vat_math", "status", "reason", "reference", "supporting_document"]
    view = res.trail[cols].copy()
    view["status"] = view["status"].map(st_status)
    view["converted_amount"] = view["converted_amount"].map(
        lambda v: f"{v:,.2f}" if v is not None and v == v else "")
    view["vat_amount"] = view["vat_amount"].map(
        lambda v: f"{float(v):,.2f}")
    view.columns = ["Txn ID", "Date", "Description", "Side", "Currency",
                    "Schedule", "FX rate", "FX conversion (shown)", "≡ Schedule",
                    "VAT rate", "VAT amount", "VAT calculation", "Status",
                    "Why", "Ref", "Supporting doc"]
    st.dataframe(view, hide_index=True, use_container_width=True, height=430)
    with st.expander("📖 Explanations for why each transaction is treated this way"):
        expl = res.trail[["txn_id", "description", "explanation"]].copy()
        st.dataframe(expl, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Download audit trail (CSV)",
                       res.trail.to_csv(index=False).encode("utf-8"),
                       "vat_audit_trail.csv", "text/csv")


def render_graphs(res):
    st.subheader("📊 Graphs — every graph is explained")
    g_defs = [
        ("Grouped bar: sales by category", *graphs.sales_by_category(res)),
        ("Grouped bar: output vs input vs net", *graphs.output_vs_input(res)),
        ("Bar: net VAT by currency schedule", *graphs.vat_by_currency(res)),
        ("Bar: monthly output vs input", *graphs.monthly(res)),
        ("Bar: PASS vs REVIEW vs FAIL", *graphs.pass_fail(res)),
    ]
    for title, fig, explanation in g_defs:
        st.markdown(f"#### {title}")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            f"<div class='rule-box'><b>📊 What does this graph show?</b> "
            f"{explanation['x']} {explanation['y']}</div>",
            unsafe_allow_html=True)
        st.markdown(f"**📈 What is happening?** {explanation['happening']}")
        st.markdown(f"**💡 Why it matters:** {explanation['why']}")
        st.markdown(f"**🧑‍🏫 In simple English:** {explanation['grade7']}")
        st.divider()


def show_validation_summary(checks):
    summ = validation.summary_of(checks)
    a, b, c = st.columns(3)
    a.metric("🟢 PASS checks", summ["pass"])
    b.metric("🟠 REVIEW checks", summ["review"])
    c.metric("🔴 FAIL checks", summ["fail"])
    st.dataframe(checks[["check_id", "txn_id", "field", "status", "what_failed",
                         "why", "financial_impact", "how_to_fix"]]
                 .rename(columns={"check_id": "Check", "txn_id": "Txn",
                                  "what_failed": "What failed", "why": "Why",
                                  "financial_impact": "Financial impact",
                                  "how_to_fix": "How to fix"}),
                 hide_index=True, use_container_width=True, height=340)
    fails = checks[checks["status"] == "FAIL"]
    if len(fails):
        st.error(f"{len(fails)} check(s) FAILED — fix these before filing.")
    elif (checks["status"] == "REVIEW").any():
        st.warning("No hard failures, but some rows need a manual review.")
    else:
        st.success("All checks passed.")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_data():
    st.subheader("📤 Data Input")
    df = get_working_df()
    n = len(df)
    label = st.session_state.get("src_label", "No dataset loaded yet")
    if n:
        st.success(f"📄 Loaded dataset: **{label}** ({n} transactions)")
    else:
        st.info("Choose a data source in the sidebar — Upload CSV, the "
                "**Harare Traders** sample or the **Mixed Supplies** sample.")

    if n:
        cols = [c for c in ("txn_id", "date", "direction", "description",
                            "counterparty", "currency", "category", "amount")
                if c in df.columns]
        st.dataframe(df[cols].head(15), hide_index=True, use_container_width=True,
                     height=330)
        st.caption("Preview — first 15 transactions. The full calculation trail "
                   "is in the Audit Trail page.")

    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("🔍 Run validation checks", use_container_width=True,
                     disabled=df.empty):
            run_checks()
    with b2:
        if st.button("🧮 Compute VAT Return", type="primary", use_container_width=True,
                     disabled=df.empty):
            run_compute()
            st.session_state.menu = "📊 Return Summary"
            st.rerun()

    checks = st.session_state.get("checks")
    if checks is not None:
        st.divider()
        st.markdown("#### Validation checks on this dataset")
        show_validation_summary(checks)

    st.divider()
    with st.expander("➕ Add a transaction manually"):
        with st.form("manual_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                m_tid = st.text_input("Transaction ID", value="")
                m_dir = st.selectbox("Transaction type",
                                     ["sale", "purchase", "import_goods",
                                      "imported_service", "adjustment"])
                m_date = st.text_input("Date (YYYY-MM-DD)",
                                       value=_dt.date.today().isoformat())
            with c2:
                m_desc = st.text_input("Description")
                m_party = st.text_input("Customer / Supplier")
                m_inv = st.text_input("Invoice / reference number")
            with c3:
                m_amt = st.number_input("Amount", min_value=0.0, value=1000.0,
                                        step=100.0)
                m_ccy = st.selectbox("Currency", ["ZIG", "USD", "ZAR"])
                m_incl = st.checkbox("Amount is VAT-inclusive", value=False)
            c4, c5, c6 = st.columns(3)
            with c4:
                m_cat = st.selectbox(
                    "VAT category", ["standard", "zero_rated", "exempt",
                                     "export"],
                    help="standard = 15.5% VAT · zero_rated = 0% (input still "
                         "claimable) · exempt = no VAT, input generally not claimable")
                st.caption("standard = VAT at 15.5% · zero_rated = 0% (input "
                           "still claimable) · exempt = no VAT, input generally "
                           "not claimable")
                m_cv = st.number_input("Customs value (imports)", value=0.0)
                m_cd = st.number_input("Customs duty (imports)", value=0.0)
            with c5:
                m_prohib = st.selectbox("Prohibited input?",
                                        ["", "entertainment",
                                         "passenger_motor_vehicle", "club_subscription"])
                m_mixed = st.checkbox("Mixed-supply (overhead) input", value=False)
                m_doc = st.checkbox("Supporting document available", value=True)
            with c6:
                m_adj = st.selectbox("Adjustment type",
                                     ["", "credit_note", "debit_note",
                                      "bad_debt_relief", "prior_period_correction"])
                m_use = st.slider("Business-use %", 0, 100, 100)
                m_notes = st.text_input("Notes")
            sent = st.form_submit_button("➕ Add transaction to the tablet",
                                         type="primary")
        if sent:
            row = {
                "txn_id": m_tid.strip() or f"MAN-{len(st.session_state.get('manual_rows', []))+1}",
                "date": m_date, "direction": m_dir, "description": m_desc,
                "counterparty": m_party, "category": m_cat, "amount": m_amt,
                "vat_inclusive": m_incl, "customs_value": m_cv,
                "customs_duty": m_cd, "prohibited_reason": m_prohib or None,
                "business_use_pct": m_use, "adjustment_type": m_adj or None,
                "mixed_input": m_mixed, "import_flag": m_dir == "import_goods",
                "invoice_number": m_inv, "supporting_document_available": m_doc,
                "currency": m_ccy, "exchange_rate": None,
                "exchange_rate_date": "", "exchange_rate_source": "", "notes": m_notes,
            }
            st.session_state.setdefault("manual_rows", []).append(row)
            st.success("Transaction added to the tablet.")

    with st.expander("🧾 Edit rows directly with the tablet"):
        working = get_working_df()
        if working.empty:
            st.info("No rows yet. Add via the form above or load a dataset.")
        else:
            cfg = {
                "direction": st.column_config.SelectboxColumn(
                    "direction", options=["sale", "purchase", "import_goods",
                                          "imported_service", "adjustment"]),
                "category": st.column_config.SelectboxColumn(
                    "category", options=["standard", "zero_rated", "exempt",
                                         "export", "import_goods",
                                         "imported_service"]),
                "currency": st.column_config.SelectboxColumn(
                    "currency", options=["ZIG", "USD", "ZAR"]),
                "business_use_pct": st.column_config.NumberColumn(
                    "business_use_pct", min_value=0, max_value=100),
            }
            edited = st.data_editor(
                working, key="tablet", num_rows="dynamic", hide_index=True,
                use_container_width=True, height=400, column_config=cfg,
                disabled=["amount", "date", "description", "txn_id"])
            if st.button("💾 Apply the edited tablet to the return"):
                st.session_state.base_df = edited
                st.session_state.manual_rows = []
                st.session_state.pop("result", None)
                st.session_state.pop("checks", None)
                st.success("Tablet applied.")
                st.rerun()

    if st.session_state.get("manual_rows"):
        st.caption(f"Manually added rows in the tablet: "
                   f"{len(st.session_state['manual_rows'])}")
        if st.button("🗑️ Clear all manually added rows"):
            st.session_state.manual_rows = []
            st.session_state.pop("result", None)
            st.session_state.pop("checks", None)
            st.rerun()


def page_summary():
    res = st.session_state.get("result")
    df = get_working_df()
    if res is None:
        if df.empty:
            st.info("No return yet — load a dataset from the sidebar first.")
        else:
            st.info("The return has not been computed yet for this dataset.")
            if st.button("🧮 Compute the VAT return now", type="primary"):
                run_compute()
                st.session_state.menu = "📊 Return Summary"
                st.rerun()
        return

    status = res.status
    if status == "PAYABLE":
        pill, word = "pill-b", "VAT payable to ZIMRA"
    elif status == "REFUNDABLE":
        pill, word = "pill-g", "VAT refundable / held as a credit"
    else:
        pill, word = "pill-o", "Nil VAT position"
    chips = " ".join(
        f"<span class='pillstatus {pill}'>{ccy}: {float(s.net):,.2f} · "
        f"{s.status}</span>" for ccy, s in res.schedules.items())
    st.markdown(
        f"<div class='hero'><div class='sub'>ZIMBABWE VAT 7 · "
        f"{period_label(df)} · {res.counts['n_txns']} transactions · "
        f"{res.counts['n_pass']} PASS / {res.counts['n_review']} REVIEW / "
        f"{res.counts['n_fail']} FAIL</div>"
        f"<div class='big'>Net VAT {res.net_vat:,.2f}</div>"
        f"<div class='sub'><span class='pillstatus {pill}'>{word}</span>"
        f"&nbsp;&nbsp;{chips}</div></div>", unsafe_allow_html=True)

    tab_s, tab_w, tab_g, tab_r = st.tabs(
        ["📋 Detailed Schedules", "🧮 All Workings", "📊 Graphs",
         "📋 Management Report"])

    with tab_s:
        category_legend()
        subtabs = st.tabs([f"{ccy} schedule" for ccy in res.schedules])
        for sub_tab, ccy in zip(subtabs, res.schedules):
            with sub_tab:
                render_schedule(ccy)
        st.markdown("##### 📏 De minimis invoice check (US$10 threshold)")
        if res.de_minimis_invoice_rows:
            st.dataframe(pd.DataFrame(res.de_minimis_invoice_rows)[
                ["txn_id", "description", "currency", "usd_equivalent",
                 "threshold", "check", "note"]].rename(
                columns={"txn_id": "Txn", "usd_equivalent": "US$ equivalent",
                         "threshold": "Threshold (US$)", "check": "Result",
                         "note": "Note"}), hide_index=True, use_container_width=True)
            st.caption("De minimis (invoicing) means a very small amount. A "
                       "supply below US$10 does not need a fiscal invoice, but "
                       "it is NOT automatically VAT-exempt — its VAT treatment "
                       "is still determined normally.")
        if status == "PAYABLE":
            vtext = "VAT PAYABLE — the business must pay this amount to ZIMRA."
        elif status == "REFUNDABLE":
            vtext = ("VAT REFUNDABLE / CREDIT — ZIMRA owes this amount (small "
                     "refunds below US$60 are held as a credit).")
        else:
            vtext = "NIL — no VAT payable and nothing refundable."
        fc1, fc2 = st.columns([1, 2])
        fc1.metric(f"Final position — {status}", f"{res.net_vat:,.2f}")
        fc2.markdown(vtext + " **Net = Output VAT − Allowable Input VAT ± "
                             "Adjustments.**")

    with tab_w:
        show_workings(res)

    with tab_g:
        render_graphs(res)

    with tab_r:
        report_content(res)


def report_content(res):
    st.markdown("#### 📊 Management Summary")
    m = res.management()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total sales", f"{m['total_sales']:,.2f}")
    c1.metric("Taxable sales", f"{m['taxable_sales']:,.2f}")
    c2.metric("Zero-rated sales", f"{m['zero_sales']:,.2f}")
    c2.metric("Exempt sales", f"{m['exempt_sales']:,.2f}")
    c3.metric("Output VAT", f"{m['output_vat']:,.2f}")
    c3.metric("Allowable input VAT", f"{m['input_vat']:,.2f}")
    c4.metric("Net VAT", f"{m['net_vat']:,.2f} ({m['status']})")
    c4.metric("Transactions", f"{m['n_txns']} (✅{m['n_pass']} 🟠{m['n_review']} ❌{m['n_fail']})")

    st.markdown(
        f"We processed **{m['n_txns']}** transactions. Sales were worth "
        f"**{m['total_sales']:,.2f}** (taxable {m['taxable_sales']:,.2f}, "
        f"zero-rated {m['zero_sales']:,.2f}, exempt {m['exempt_sales']:,.2f}). "
        f"Output VAT is **{m['output_vat']:,.2f}** and allowable input VAT is "
        f"**{m['input_vat']:,.2f}**, so the net VAT position is "
        f"**{m['net_vat']:,.2f} ({m['status']})**.")

    git_url = st.text_input("GitHub repository URL (for the report)", value="")
    app_url = st.text_input("Live Streamlit URL (for the report)", value="")
    report_md = report_generator.build_markdown_report(res, git_url, app_url)
    st.download_button("⬇️ Download the full professional report (Markdown)",
                       report_md.encode("utf-8"),
                       "Zimbabwe_VAT_Report.md", "text/markdown")

    st.divider()
    st.markdown("#### 📤 Share the final report")
    st.markdown("**✉️ Send by email (SMTP)**")
    if share.smtp_configured():
        recipients = st.text_input("Recipient email(s), comma-separated")
        subject = st.text_input("Subject",
                                "Zimbabwe VAT 7 return — management summary")
        if st.button("Send email", type="primary"):
            ok, msg = share.send_email(subject, report_md, recipients)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
    else:
        st.warning(
            "SMTP is not configured. To enable email, add an **[smtp]** section "
            "to your Streamlit secrets (host, port, user, password, sender) — "
            "never commit credentials to the repository.")
    st.markdown("**💬 Send by WhatsApp (no API key needed)**")
    phone = st.text_input("WhatsApp number (international digits, e.g. 2637... )")
    wa_text = report_generator.share_text(res)
    st.code(wa_text, language=None)
    if phone:
        link = share.whatsapp_link(phone, wa_text)
        st.link_button("📲 Open WhatsApp with the summary", link,
                       use_container_width=True)
    else:
        st.caption("Enter a WhatsApp number to build the share link.")


def page_audit():
    st.subheader("🔍 Audit Trail")
    checks = st.session_state.get("checks")
    if checks is not None:
        show_validation_summary(checks)
        st.divider()
    else:
        st.caption("Run the validation checks on the **Data Input** page to see "
                   "the summary here.")
    res = st.session_state.get("result")
    if res is None:
        st.info("Compute the return first — the full calculation trail for "
                "every transaction is built then.")
        return
    show_audit(res)


def page_tests():
    st.subheader("🧪 Built-in automated tests (pytest + in-app)")
    if st.button("▶️ Run the full test suite now", type="primary"):
        st.session_state.test_results = test_suite.run_all()
    results = st.session_state.get("test_results")
    if results is None:
        st.info("Click 'Run the full test suite' to execute TC01–TC21 against "
                "the engine with the current verified rates.")
        return
    df = pd.DataFrame(results)
    n_fail = int((df["result"] != "PASS").sum())
    if n_fail == 0:
        st.success(f"All {len(df)} tests PASS.")
    else:
        st.error(f"{n_fail} test(s) FAILED — see table below.")
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Download test results (CSV)",
                       df.to_csv(index=False).encode("utf-8"),
                       "vat_test_results.csv", "text/csv")


QUIZ = [
    ("What is VAT?", ["A tax on company profit",
                      "An indirect tax on consumption",
                      "A tax on salaries", "A customs duty"], 1,
     "VAT is an indirect consumption tax charged on supplies and imports."),
    ("What is output VAT?", ["VAT on purchases", "VAT on sales",
                             "VAT paid to suppliers", "VAT refunded by ZIMRA"], 1,
     "Output VAT is the VAT the business charges on its taxable sales."),
    ("What is input VAT?", ["VAT on purchases", "VAT on sales",
                            "VAT on exports", "VAT on salaries"], 0,
     "Input VAT is the VAT the business pays on qualifying purchases."),
    ("A zero-rated supply means:", ["Nothing is stated",
        "0% VAT, input tax still claimable", "No tax at all",
        "VAT at the standard rate"], 1,
     "Zero-rated = 0% rate with input-tax credit preserved."),
    ("An exempt supply means:", ["0% VAT like zero-rated",
        "No VAT, and input tax generally not claimable",
        "VAT is charged twice", "Input tax is fully claimable"], 1,
     "Exempt supplies carry no VAT and generally no input-tax credit."),
    ("Who generally bears VAT?", ["The Government", "The final consumer",
                                  "The bank", "The logistics company"], 1,
     "The final consumer bears the economic cost; the business collects and accounts for it."),
    ("A credit note on a standard supply:", ["Increases output VAT",
        "Reduces output VAT", "Creates output VAT", "Has no effect"], 1,
     "A credit note reduces the VAT charged on the original supply."),
    ("The invoicing de minimis rule means:", ["Supplies below US$10 are exempt",
        "No fiscal invoice needed below US$10 — but VAT treatment still applies",
        "No VAT below US$10", "All supplies below US$10 are zero-rated"], 1,
     "Below US$10 a fiscal invoice is not required, but the supply is NOT automatically exempt."),
    ("Imported services are treated as:", ["Exempt", "Zero-rated",
        "Reverse-charged (output + mirror input)", "Not taxable"], 2,
     "Imported services are reverse-charged under VAT Act s13A."),
    ("An exchange rate is used to:", ["Change the VAT rate",
        "Convert foreign-currency amounts into the schedule currency",
        "Round VAT", "Set the tax period"], 1,
     "Exchange rates convert ZAR/USD/ZiG amounts so each transaction lands on the correct schedule."),
]


def page_quiz():
    st.markdown("### 🧠 Quick VAT quiz")
    score = 0
    for i, (q, opts, correct, explain) in enumerate(QUIZ):
        with st.form(f"quiz_{i}"):
            st.markdown(f"**Q{i+1}. {q}**")
            answer = st.radio("Choose an answer", opts, key=f"q{i}")
            submit = st.form_submit_button("Check answer")
        if submit:
            if answer == opts[correct]:
                score += 1
                st.success("🟢 PASS — " + explain)
            else:
                st.error("🔴 FAIL — " + explain + " (correct answer: "
                         + opts[correct] + ")")
    if score:
        st.metric("Your score", f"{score}/{len(QUIZ)}")


def ve_assumptions_text():
    return (f"**Standard VAT rate:** {float(config.VAT_RATE_PCT):g}% effective "
            f"{config.VAT_RATE_EFFECTIVE} — {config.VAT_RATE_SOURCE}\n\n"
            f"**Registration threshold:** US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f} "
            f"— {config.REGISTRATION_SOURCE}\n\n"
            f"**Invoicing de minimis:** US${float(config.DE_MINIMIS_INVOICE_USD):,.2f} "
            f"— {config.DE_MINIMIS_INVOICE_SOURCE}\n\n"
            f"**Apportionment de minimis:** {float(config.DE_MINIMIS_APPORTIONMENT_PCT*100):g}% "
            f"exempt — {config.DE_MINIMIS_APPORTIONMENT_SOURCE}")


def page_assumptions():
    st.subheader("📚 Assumptions & Law")
    vat_definition_box()

    st.markdown("### 🎓 Learn VAT")
    for title, (tech, grade7) in explanations.LEARN_SECTIONS.items():
        with st.expander(title, expanded=(title == "What is VAT?")):
            st.markdown(f"**Technical:** {tech}")
            st.info(f"**🧑‍🏫 In simple English:** {grade7}")
    st.markdown("### 🔄 How VAT flows through the supply chain")
    for step, text in explanations.VAT_FLOW:
        st.markdown(f"- **{step}** — {text}")

    st.markdown("### 🏛️ Who must register & file?")
    st.markdown(
        f"- Compulsory registration: taxable supplies > "
        f"**US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f}** (or ZiG "
        f"equivalent) in any 12-month period — effective {config.REGISTRATION_EFFECTIVE}.\n"
        f"- The standard VAT rate is **{float(config.VAT_RATE_PCT):g}%** "
        f"({config.VAT_RATE_EFFECTIVE}; Finance Act (No. 7) of 2025).\n"
        f"- The return (VAT 7) is due by the **{config.RETURN_DUE_DAY}th** and "
        f"payment by the **{config.PAYMENT_DAY}th** of the month after the tax "
        f"period (SI 81 of 2025 — verify with ZIMRA).")

    page_quiz()

    st.markdown("### ⚖️ Legal & computational assumptions used")
    doc = pathlib.Path(__file__).parent / "docs" / "LEGAL_ASSUMPTIONS.md"
    if doc.exists():
        st.markdown(doc.read_text(encoding="utf-8"))
    else:
        st.markdown(ve_assumptions_text())

    st.markdown("### 🔗 Official sources")
    for ref, desc, url in config.REFERENCES:
        st.markdown(f"- **{ref}** — {desc}  \n  {url}")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
MAIN_SAMPLES = [
    "Harare Traders (21 transactions)",
    "Tri-Currency Traders (mixed USD+ZiG+ZAR)",
]
OTHER_SAMPLES = [
    "Amber Mart (ZiG worked example)",
    "Veritas Wholesale (USD only)",
    "QA — dataset with errors (PASS/FAIL demo)",
]

with st.sidebar:
    st.markdown("### 💱 Currency Converter")
    snap = st.session_state.get("fx") or load_fx()
    r = snap["rates"]
    c_from = st.selectbox("From", ("USD", "ZIG", "ZAR"), index=0)
    c_to = st.selectbox("To", ("ZIG", "USD", "ZAR"), index=1)
    famt = st.number_input("Amount", value=1000.0, min_value=0.0, step=100.0)
    rate = fx.convert(1, c_from, c_to, r)
    converted = fx.convert(famt, c_from, c_to, r)
    st.markdown(
        f"<div class='workbox'><b>1 {c_from} = {rate:,.4f} {c_to}</b><br>"
        f"<span style='font-size:20px;font-weight:700;color:#12315E'>"
        f"{famt:,.2f} {c_from} → {converted:,.2f} {c_to}</span></div>",
        unsafe_allow_html=True)
    st.caption(f"{snap['source']} · as at {snap['date_label']}"
               + (" · live" if snap.get("live") else " · cached"))
    if st.button("🔃 Refresh rates", use_container_width=True):
        load_fx(refresh=True)
        st.rerun()

    st.markdown("### 📂 Data Source")
    src_choice = st.radio(
        "Choose data source",
        ["📄 Sample: Harare Traders", "📄 Sample: Mixed Supplies",
         "📁 Upload CSV / Excel"],
        index=0)
    if src_choice.startswith("📄"):
        key = MAIN_SAMPLES[0] if src_choice.endswith("Harare Traders") else MAIN_SAMPLES[1]
        if st.session_state.get("src_key") != key:
            try:
                dfx = sample_data.load_sample(key)
            except (KeyError, ValueError) as exc:
                st.error(f"Sample dataset could not be loaded: {exc}")
                st.stop()
            st.session_state.base_df = dfx
            st.session_state.src_key = key
            st.session_state.src_label = sample_data.SAMPLE_NAMES.get(key, key)
            st.session_state.pop("result", None)
            st.session_state.pop("checks", None)
    else:
        up = st.file_uploader("Upload transactions (CSV or Excel)",
                              type=["csv", "xlsx", "xls"])
        if up is not None:
            dfx = read_uploaded(up)
            if dfx is not None:
                st.session_state.base_df = dfx
                st.session_state.src_key = "upload"
                st.session_state.src_label = up.name
                st.session_state.pop("result", None)
                st.session_state.pop("checks", None)
        with st.expander("Expected columns"):
            st.write("Accepted columns (friendly names OK, e.g. 'Transaction ID', "
                     "'Amount (USD)', 'VAT Category'): " +
                     ", ".join(validation.COLUMN_ALIASES.keys()))
            st.caption("Required: a transaction ID, date, transaction type, "
                       "amount, currency and VAT category. Everything else is "
                       "optional and freely named.")
    with st.expander("Other demo datasets"):
        st.radio("Load", OTHER_SAMPLES, key="other_demo")
        if st.button("Load selected"):
            key2 = st.session_state.other_demo
            try:
                dfx = sample_data.load_sample(key2)
            except (KeyError, ValueError) as exc:
                st.error(f"Sample dataset could not be loaded: {exc}")
                st.stop()
            st.session_state.base_df = dfx
            st.session_state.src_key = key2
            st.session_state.src_label = sample_data.SAMPLE_NAMES.get(key2, key2)
            st.session_state.pop("result", None)
            st.session_state.pop("checks", None)

    st.markdown("### ⚙️ Advanced options")
    st.session_state.de_minimis = st.checkbox(
        "Apply apportionment de minimis (≤5% exempt → full input recovery)",
        value=st.session_state.get("de_minimis", True))
    st.caption(f"Standard VAT rate: {float(config.VAT_RATE_PCT):g}% "
               f"({config.VAT_RATE_EFFECTIVE}). Blank currencies are assumed ZiG.")

    st.markdown("### 🧭 Navigation")
    _nav = ["🏠 Data Input", "📊 Return Summary", "🔍 Audit Trail",
            "🧪 Test Cases", "📚 Assumptions & Law"]
    menu = st.radio("Go to", _nav,
                    index=_nav.index(st.session_state.get("menu", "🏠 Data Input")))
    st.session_state.menu = menu

st.divider()

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
if menu == "🏠 Data Input":
    page_data()
elif menu == "📊 Return Summary":
    page_summary()
elif menu == "🔍 Audit Trail":
    page_audit()
elif menu == "🧪 Test Cases":
    page_tests()
elif menu == "📚 Assumptions & Law":
    page_assumptions()

vat_definition_box()
st.caption("Zimbabwe VAT Return Automation & Explainable VAT System — LEARN → ENTER → "
           "CHECK → CONVERT → CALCULATE → EXPLAIN → VISUALISE → AUDIT → REPORT.")