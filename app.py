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
    st.success("Computation complete. Review the Validation and VAT Return pages.")
    return res


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


def show_workings(res):
    st.subheader("🧮 Show All Workings — every number you can see")
    labels = {"ZIG": "ZiG", "USD": "USD"}
    for ccy, sched in res.schedules.items():
        L = labels.get(ccy, ccy)
        st.markdown(f"##### {ccy} schedule")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**STEP 1 — SALES**")
            st.dataframe(pd.DataFrame({
                "Category": ["Standard-rated", "Zero-rated", "Exempt", "TOTAL"],
                f"Value ({L})": [float(sched.std), float(sched.zr), float(sched.ex),
                                 float(sched.sales_value)]}), hide_index=True,
                use_container_width=True)
        with c2:
            st.markdown("**STEP 2 — OUTPUT VAT**")
            st.markdown(
                f"- Standard rated: {float(sched.out_std):,.2f}\n"
                f"- Adjustments (line 3): {float(sched.out_adj):,.2f}\n"
                f"- Reverse charge (line 4): {float(sched.rc_out):,.2f}\n"
                f"- **Total output tax = {float(sched.total_output):,.2f} {L}**")
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**STEP 3 — PURCHASES / INPUTS**")
            st.markdown(
                f"- Local purchases (line 6): {float(sched.in_local):,.2f}\n"
                f"- Imports of goods (line 7): {float(sched.in_import):,.2f}\n"
                f"- Reverse charge input (line 8): {float(sched.rc_in):,.2f}\n"
                f"- Mixed recovered after apportionment: "
                f"{float(sched.mixed_deductible):,.2f}\n"
                f"- Apportionment disallowed (line 9): "
                f"{float(sched.disallowed):,.2f}")
        with c4:
            st.markdown("**STEP 4 — INPUT VAT**")
            formula = (f"{float(sched.total_output):,.2f} − "
                       f"{float(sched.total_input):,.2f}")
            st.markdown(
                f"- **Total input tax allowable (line 10) = "
                f"{float(sched.total_input):,.2f} {L}**\n"
                f"- **STEP 5 — FINAL: Output − Input = {formula} "
                f"= {float(sched.net):,.2f} {L} ({sched.status})**")
    st.markdown("**STEP 6 — ADJUSTMENTS TRANSACTIONS**")
    adj = res.trail[res.trail["side"] == "Adjustment"][
        ["txn_id", "date", "description", "schedule", "vat_rate", "vat_amount",
         "vat_math"]]
    st.dataframe(adj, hide_index=True, use_container_width=True)
    st.markdown(
        "> <b>FORMULA</b>  Output VAT − Allowable Input VAT ± Adjustments = Net "
        "VAT position. Every figure above is traced to individual transactions "
        "in the Audit Trail below.")


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


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_dashboard():
    res = st.session_state.get("result")
    df = get_working_df()
    snap = st.session_state.get("fx") or load_fx()

    st.subheader("🏠 VAT Return Dashboard")
    st.caption(f"Filing view: **{period_label(df)}** · live exchange rates below "
               f"· source {snap.get('source')} · as at {snap.get('date_label')}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Transactions", (res.counts["n_txns"] if res else len(df)),
              "in current dataset")
    c2.metric("Output VAT", f"{res.total_output_tax:,.2f}" if res else "—",
              "charged on sales")
    c3.metric("Input VAT", f"{res.total_input_tax:,.2f}" if res else "—",
              "allowable")
    c4.metric("Net VAT", f"{res.net_vat:,.2f} · {res.status}" if res else "—",
              "payable / refundable")
    c5.metric("Compliance", f"{res.counts['n_pass']} ✅ · "
                            f"{res.counts['n_review']} 🟠 · "
                            f"{res.counts['n_fail']} ❌" if res else "—",
              "PASS / REVIEW / FAIL")

    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("🧪 Load Demo Data (Tri-Currency)", use_container_width=True):
            st.session_state.base_df = sample_data.load_sample(
                "Tri-Currency Traders (mixed USD+ZiG+ZAR)")
            st.session_state.pop("result", None)
            st.rerun()
    with q2:
        if st.button("✍️ Enter Transactions Manually", use_container_width=True):
            st.session_state.menu = "📥 Data & Validation"
            st.rerun()
    with q3:
        if st.button("🧮 Compute VAT Return", use_container_width=True,
                     disabled=df.empty):
            run_compute()
            st.session_state.menu = "🧮 VAT Return"
            st.rerun()

    st.markdown("### 💱 Currency & Exchange Rates used")
    st.dataframe(pd.DataFrame(fx.rates_table(snap)), hide_index=True,
                 use_container_width=True)
    st.caption("Rates are quoted per 1 USD. The rate actually applied to a "
               "transaction, its source and its date are also shown on every "
               "row of the Audit Trail.")

    if res is not None:
        st.markdown("### 📋 Draft VAT 7 schedules (per currency, never mixed)")
        tabs = st.tabs(["ZiG schedule"] if "ZIG" in res.schedules else [] +
                       (["USD schedule"] if "USD" in res.schedules else []))
        for tab, ccy in zip(tabs, ("ZIG", "USD")):
            if ccy in res.schedules:
                with tab:
                    render_schedule(ccy)


def page_learn():
    st.subheader("📚 Understanding VAT")
    for title, (tech, grade7) in explanations.LEARN_SECTIONS.items():
        with st.expander(title, expanded=(title == "What is VAT?")):
            st.markdown(f"**Technical:** {tech}")
            st.info(f"**🧑‍🏫 In simple English:** {grade7}")
    st.markdown("### 🔄 How VAT flows through the supply chain")
    for step, text in explanations.VAT_FLOW:
        st.markdown(f"- **{step}** — {text}")
    st.markdown(
        f"### 🏛️ Who must register & file?\n"
        f"- Compulsory registration: taxable supplies > "
        f"**US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f}** (or ZiG "
        f"equivalent) in any 12-month period — effective {config.REGISTRATION_EFFECTIVE}.\n"
        f"- The standard VAT rate is **{float(config.VAT_RATE_PCT):g}%** "
        f"({config.VAT_RATE_EFFECTIVE}; Finance Act (No. 7) of 2025).\n"
        f"- The return (VAT 7) is due by the **{config.RETURN_DUE_DAY}th** and "
        f"payment by the **{config.PAYMENT_DAY}th** of the month after the tax "
        f"period (SI 81 of 2025 — verify with ZIMRA).")


def page_data():
    st.subheader("📥 Data Input — upload, demo or enter transactions")

    src = st.radio("Source", ["🧪 Load demo / sample data", "📁 Upload CSV / Excel",
                              "✍️ Manual entry & tablet"], horizontal=True)

    if src.startswith("🧪"):
        st.radio("Choose sample dataset", list(sample_data.SAMPLE_FILES.keys()),
                 key="demo_key", horizontal=True)
        st.info(sample_data.SAMPLE_DESCRIPTIONS.get(
            st.session_state.demo_key, ""))
        if st.button("📥 Load this demo dataset", type="primary"):
            st.session_state.base_df = sample_data.load_sample(
                st.session_state.demo_key)
            st.session_state.pop("result", None)
            st.success("Demo dataset loaded (simulated data).")
            st.rerun()

    elif src.startswith("📁"):
        up = st.file_uploader("Upload transactions (CSV or Excel)",
                              type=["csv", "xlsx", "xls"])
        if up is not None:
            df = read_uploaded(up)
            if df is not None:
                st.session_state.base_df = df
                st.session_state.pop("result", None)
                st.success(f"Uploaded {len(df)} rows from {up.name}.")
        with st.expander("Expected / accepted columns"):
            st.write("Accepted columns (friendly names OK, e.g. 'Transaction ID', "
                     "'Amount (USD)', 'VAT Category'): " +
                     ", ".join(validation.COLUMN_ALIASES.keys()))
            st.caption("Required: a transaction ID, date, transaction type, "
                       "amount, currency and VAT category. Everything else is "
                       "optional and freely named.")

    else:
        st.markdown("#### ✍️ Manual transaction entry tablet")
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
                m_cat = st.selectbox("VAT category",
                                     ["standard", "zero_rated", "exempt",
                                      "export"])
                m_cv = st.number_input("Customs value (imports)", value=0.0)
                m_cd = st.number_input("Customs duty (imports)", value=0.0)
            with c5:
                m_prohib = st.selectbox("Prohibited input?", ["", "entertainment",
                                       "passenger_motor_vehicle", "club_subscription"])
                m_mixed = st.checkbox("Mixed-supply (overhead) input", value=False)
                m_doc = st.checkbox("Supporting document available", value=True)
            with c6:
                m_adj = st.selectbox("Adjustment type",
                                     ["", "credit_note", "debit_note",
                                      "bad_debt_relief",
                                      "prior_period_correction"])
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

        st.markdown("#### 🧾 Tablet — edit rows directly")
        working = get_working_df()
        if working.empty:
            st.info("No rows yet. Add via the form above or load demo data.")
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
                "business_use_pct": st.column_config.NumberColumn("business_use_pct", min_value=0, max_value=100),
            }
            edited = st.data_editor(
                working, key="tablet", num_rows="dynamic", hide_index=True,
                use_container_width=True, height=400,
                column_config=cfg,
                disabled=["amount", "date", "description", "txn_id"])
            if st.button("💾 Apply the edited tablet to the return"):
                st.session_state.base_df = edited
                st.session_state.manual_rows = []
                st.session_state.pop("result", None)
                st.success("Tablet applied.")
                st.rerun()

    manual = st.session_state.get("manual_rows", [])
    if manual:
        st.caption(f"Manually added rows in the tablet: {len(manual)}")
        if st.button("🗑️ Clear all manually added rows"):
            st.session_state.manual_rows = []
            st.session_state.pop("result", None)
            st.rerun()


def page_validation():
    st.subheader("🔍 Data Check & Validation")
    df = get_working_df()
    if df.empty:
        st.info("Load or enter transactions first (Data & Validation page).")
        return
    if st.button("🔍 Run the validation checks now", type="primary"):
        with st.spinner("Checking every transaction..."):
            checks, norm = validation.validate(df)
        st.session_state.checks = checks
        st.session_state.norm_df = norm
    checks = st.session_state.get("checks")
    if checks is None:
        st.info("The checks have not been run yet for the current data.")
        return
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
                 hide_index=True, use_container_width=True, height=420)
    fails = checks[checks["status"] == "FAIL"]
    if len(fails):
        st.error(f"{len(fails)} check(s) FAILED — fix these before filing.")
    elif (checks["status"] == "REVIEW").any():
        st.warning("No hard failures, but some rows need a manual review.")
    else:
        st.success("All checks passed.")


def page_return():
    res = st.session_state.get("result")
    if res is None:
        st.info("Compute the return first (Dashboard or Data & Validation page).")
        if st.button("Compute now"):
            run_compute()
        return
    st.subheader("📋 VAT Return — the schedules you file (never mixed)")
    tabs = st.tabs([f"{ccy} schedule" for ccy in res.schedules])
    for tab, ccy in zip(tabs, res.schedules):
        with tab:
            render_schedule(ccy)

    st.markdown("##### 📏 De minimis invoice check (US$10 threshold)")
    if res.de_minimis_invoice_rows:
        st.dataframe(pd.DataFrame(res.de_minimis_invoice_rows)[
            ["txn_id", "description", "currency", "usd_equivalent", "threshold",
             "check", "note"]].rename(columns={"txn_id": "Txn",
                "usd_equivalent": "US$ equivalent",
                "threshold": "Threshold (US$)", "check": "Result",
                "note": "Note"}), hide_index=True, use_container_width=True)
        st.caption("De minimis (invoicing) means a very small amount. A supply "
                   "below US$10 does not need a fiscal invoice, but it is NOT "
                   "automatically VAT-exempt — its VAT treatment is still "
                   "determined normally.")
    else:
        st.caption("No standard-rated transactions to check.")

    res_count = res.counts
    a, b, c = st.columns(3)
    a.metric("Transactions PASS", f"{res_count['n_pass']} ✅")
    b.metric("Transactions REVIEW", f"{res_count['n_review']} 🟠")
    c.metric("Transactions FAIL", f"{res_count['n_fail']} ❌")

    with st.expander("🧮 Show all workings (steps 1-6)", expanded=True):
        show_workings(res)
    with st.expander("🕵️ Complete audit / calculation trail", expanded=True):
        show_audit(res)

    st.markdown("##### 🧾 Final result")
    if res.status == "PAYABLE":
        emoji, text = "🟢", "VAT PAYABLE — the business must pay this amount to ZIMRA."
    elif res.status == "REFUNDABLE":
        emoji, text = "🟢", ("VAT REFUNDABLE / CREDIT — ZIMRA owes this amount "
                             "(small refunds below US$60 are held as a credit).")
    else:
        emoji, text = "⚪", "NIL — no VAT payable and nothing refundable."
    c1, c2 = st.columns([1, 2])
    c1.metric(f"{emoji} VAT POSITION — {res.status}",
              f"{res.net_vat:,.2f}", f"per combined view")
    c2.markdown(text + " **Net = Output VAT − Allowable Input VAT ± Adjustments.** "
                       "Full composition is shown above, per schedule, so a "
                       "reviewer can trace every number to a transaction.")


def page_graphs():
    res = st.session_state.get("result")
    if res is None:
        st.info("Compute the return first to see the graphs.")
        return
    render_graphs(res)


def page_report():
    res = st.session_state.get("result")
    if res is None:
        st.info("Compute the return first.")
        return
    st.subheader("📊 Management Summary")
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
    st.subheader("📤 Share the final report")
    st.markdown("### ✉️ Send by email (SMTP)")
    if share.smtp_configured():
        recipients = st.text_input("Recipient email(s), comma-separated")
        subject = st.text_input("Subject", "Zimbabwe VAT 7 return — management summary")
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
    st.markdown("### 💬 Send by WhatsApp (no API key needed)")
    phone = st.text_input("WhatsApp number (international digits, e.g. 2637... )")
    wa_text = report_generator.share_text(res)
    st.code(wa_text, language=None)
    if phone:
        link = share.whatsapp_link(phone, wa_text)
        st.link_button("📲 Open WhatsApp with the summary", link,
                       use_container_width=True)
    else:
        st.caption("Enter a WhatsApp number to build the share link.")


QUIZ = [
    ("What is VAT?", ["A tax on company profit", "An indirect tax on consumption",
                      "A tax on salaries", "A customs duty"], 1,
     "VAT is an indirect consumption tax charged on supplies and imports."),
    ("What is output VAT?", ["VAT on purchases", "VAT on sales",
                             "VAT paid to suppliers", "VAT refunded by ZIMRA"], 1,
     "Output VAT is the VAT the business charges on its taxable sales."),
    ("What is input VAT?", ["VAT on purchases", "VAT on sales",
                            "VAT on exports", "VAT on salaries"], 0,
     "Input VAT is the VAT the business pays on qualifying purchases."),
    ("A zero-rated supply means:", ["Nothing is stated", "0% VAT, input tax still claimable",
                                    "No tax at all", "VAT at the standard rate"], 1,
     "Zero-rated = 0% rate with input-tax credit preserved."),
    ("An exempt supply means:", ["0% VAT like zero-rated", "No VAT, and input tax generally not claimable",
                                 "VAT is charged twice", "Input tax is fully claimable"], 1,
     "Exempt supplies carry no VAT and generally no input-tax credit."),
    ("Who generally bears VAT?", ["The Government", "The final consumer",
                                  "The bank", "The logistics company"], 1,
     "The final consumer bears the economic cost; the business collects and accounts for it."),
    ("A credit note on a standard supply:", ["Increases output VAT", "Reduces output VAT",
                                             "Creates output VAT", "Has no effect"], 1,
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
    st.subheader("🧠 Test your VAT knowledge")
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


def page_assumptions():
    st.subheader("⚙️ Legal & Computational Assumptions — Sources")
    doc = pathlib.Path(__file__).parent / "docs" / "LEGAL_ASSUMPTIONS.md"
    if doc.exists():
        st.markdown(doc.read_text(encoding="utf-8"))
    else:
        st.markdown(ve_assumptions_text())
    st.divider()
    st.subheader("🔗 Official sources")
    for ref, desc, url in config.REFERENCES:
        st.markdown(f"- **{ref}** — {desc}  \n  {url}")
    st.divider()
    st.info(config.DISCLAIMER)


def ve_assumptions_text():
    return (f"**Standard VAT rate:** {float(config.VAT_RATE_PCT):g}% effective "
            f"{config.VAT_RATE_EFFECTIVE} — {config.VAT_RATE_SOURCE}\n\n"
            f"**Registration threshold:** US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f} "
            f"— {config.REGISTRATION_SOURCE}\n\n"
            f"**Invoicing de minimis:** US${float(config.DE_MINIMIS_INVOICE_USD):,.2f} "
            f"— {config.DE_MINIMIS_INVOICE_SOURCE}\n\n"
            f"**Apportionment de minimis:** {float(config.DE_MINIMIS_APPORTIONMENT_PCT*100):g}% "
            f"exempt — {config.DE_MINIMIS_APPORTIONMENT_SOURCE}")


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


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 💱 Live Exchange Rate")
    snap = st.session_state.get("fx") or load_fx()
    r = snap["rates"]
    usd_zig = fx.convert(1, "USD", "ZIG", r)
    zar_zig = fx.convert(1, "ZAR", "ZIG", r)
    st.markdown(
        f"<span class='pill'><b>1 USD = {usd_zig:,.4f} ZiG</b></span> "
        f"<span class='pill'><b>1 ZAR = {zar_zig:,.4f} ZiG</b></span>",
        unsafe_allow_html=True)
    st.caption(f"{(snap['source'])} · as at {snap['date_label']} "
               f"({'🟢 LIVE' if snap.get('live') else '🟠 cached/offline'})")
    if not snap.get("live"):
        st.warning("Not live — using cached/fallback rates. Click Refresh.")
    manual_zig = st.number_input("Manual RBZ official ZiG rate (0 = auto)",
                                 value=0.0, step=0.01,
                                 help="Enter the current RBZ official rate to "
                                      "override the live feed (e.g. 26.63).")
    if st.button("🔃 Refresh/apply rates", use_container_width=True):
        load_fx(refresh=True, manual_zig=manual_zig or None)
        st.rerun()

    st.markdown("### ⚙️ Options")
    st.session_state.de_minimis = st.checkbox(
        "Apply apportionment de minimis (≤5% exempt → full input recovery)",
        value=st.session_state.get("de_minimis", True))
    st.caption(f"Standard VAT rate: {float(config.VAT_RATE_PCT):g}% "
               f"({config.VAT_RATE_EFFECTIVE}).")

    st.markdown("### 🧭 Navigation")
    menu = st.radio("Go to", [
        "🏠 Dashboard", "📚 Learn VAT", "📥 Data & Validation",
        "🧮 VAT Return", "📊 Graphs", "📋 Report & Share",
        "🧠 VAT Quiz", "⚙️ Assumptions & Sources", "🧪 Test Cases"],
        index=["🏠 Dashboard", "📚 Learn VAT", "📥 Data & Validation",
               "🧮 VAT Return", "📊 Graphs", "📋 Report & Share",
               "🧠 VAT Quiz", "⚙️ Assumptions & Sources", "🧪 Test Cases"]
        .index(st.session_state.get("menu", "🏠 Dashboard")))
    st.session_state.menu = menu

st.divider()

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
if menu == "🏠 Dashboard":
    page_dashboard()
elif menu == "📚 Learn VAT":
    page_learn()
elif menu == "📥 Data & Validation":
    page_data()
    page_validation()
elif menu == "🧮 VAT Return":
    page_return()
elif menu == "📊 Graphs":
    page_graphs()
elif menu == "📋 Report & Share":
    page_report()
elif menu == "🧠 VAT Quiz":
    page_quiz()
elif menu == "⚙️ Assumptions & Sources":
    page_assumptions()
elif menu == "🧪 Test Cases":
    page_tests()

st.markdown("---")
st.caption("ZIMBABWE VAT RETURN AUTOMATION & EXPLAINABLE VAT SYSTEM — DEMO/SIMULATED "
           "DATA ONLY — NO REAL TAXPAYER DATA. Educational project; does not "
           "replace professional tax advice or ZIMRA TaRMS filing. " +
           config.DISCLAIMER)