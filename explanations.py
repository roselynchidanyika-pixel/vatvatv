"""explanations.py — Plain-language (Grade 7) explanations for every VAT step.

Every calculation in the system exposes:
    FORMULA -> VALUES USED -> SUBSTITUTION -> ANSWER -> EXPLANATION
                -> SOURCE/RULE -> PASS/FAIL

This module supplies the "EXPLANATION" layer — technical language plus a very
simple English version that a Grade 7 learner can follow.
"""

from __future__ import annotations

import config


# ---------------------------------------------------------------------------
# VAT education content (used by the "Learn VAT" page and explanations)
# ---------------------------------------------------------------------------
LEARN_SECTIONS = {
    "What is VAT?": (
        "Value Added Tax (VAT) is an indirect consumption tax. It is charged on "
        "the supply of goods and services, and on the importation of goods and "
        "services into Zimbabwe. It is called 'value added' because each "
        "business in the chain pays VAT on what it buys and charges VAT on what "
        "it sells — and pays over the difference.",
        "VAT is a small extra amount added to the price when you buy goods or "
        "services. It is a consumption tax because, in most cases, the final "
        "consumer bears the cost.",
    ),
    "Output vs Input VAT": (
        "OUTPUT VAT is the VAT your business charges on its taxable sales. "
        "INPUT VAT is the VAT your business pays on its qualifying purchases. "
        "On the VAT 7 return the business deducts allowable input VAT from "
        "output VAT to find the net VAT payable or refundable.",
        "Output VAT is the VAT you add to the price when you sell something "
        "taxable. Input VAT is the VAT you paid when you bought things for the "
        "business. The difference is what you pay to (or get back from) ZIMRA.",
    ),
    "Zero-rated vs Exempt": (
        "ZERO-RATED means the supply is taxable but the VAT rate applied is 0%. "
        "Input VAT on costs linked to zero-rated supplies is still claimable. "
        "EXEMPT means no VAT is charged at all and input VAT on costs "
        "attributable to exempt supplies is generally NOT claimable.",
        "Zero-rated is not the same as exempt. Zero-rated means the rate is 0% "
        "(exports, some foods) but you can still claim input VAT. Exempt means "
        "no VAT is charged AND you usually cannot claim input VAT on it "
        "(residential rent, financial services).",
    ),
    "Who must account for VAT?": (
        f"A person must register for VAT when taxable supplies exceed (or are "
        f"likely to exceed) **US${float(config.VAT_REGISTRATION_THRESHOLD_USD):,.0f}** "
        f"(or the ZiG equivalent) in any 12-month period (effective "
        f"{config.REGISTRATION_EFFECTIVE}). Registration can also be voluntary "
        f"below that threshold.",
        "If you sell taxable goods worth more than about US$25 000 in a year, "
        "you must register for VAT and start charging it.",
    ),
    "Who bears the VAT?": (
        "The registered business COLLECTS and ACCOUNTS FOR VAT; it does not "
        "keep all the VAT it collects as income. The final consumer generally "
        "bears the economic cost of the tax, ZIMRA receives the revenue, and "
        "the business is the 'collector' for the State, claiming back input VAT "
        "on its own business inputs.",
        "The customer really pays the VAT in the price. The business is like a "
        "post office: it collects the VAT, passes the input-tax part to its "
        "suppliers' claims, and sends the rest to ZIMRA.",
    ),
    "Benefits & challenges": (
        "Benefits: VAT generates revenue for public services; it is collected "
        "in small steps through the whole supply chain; the input-tax "
        "mechanism avoids tax on tax; and the invoice trail makes transactions "
        "traceable. Challenges: compliance and record-keeping costs, cash-flow "
        "pressure between collecting VAT and paying it over, the complexity of "
        "many different rules, and penalties for errors.",
        "VAT helps the government pay for services. But keeping the records, "
        "getting the rules right, and managing the money flows is real work for "
        "every business — mistakes can be costly.",
    ),
}

VAT_FLOW = [
    ("1. BUSINESS BUYS", "The business buys goods/services for its trade."),
    ("2. POTENTIAL INPUT VAT", "VAT paid on qualifying purchases is recorded "
     "as potential input VAT."),
    ("3. BUSINESS SELLS", "The business sells goods/services to its customers."),
    ("4. OUTPUT VAT", "VAT charged on taxable sales is output VAT."),
    ("5. ALLOWABLE INPUT VAT IS DEDUCTED", "Only allowable (qualifying + "
     "documented) input VAT is deducted."),
    ("6. ADJUSTMENTS", "Credit notes, debit notes and bad-debt relief change "
     "the totals."),
    ("7. NET VAT POSITION", "Output VAT − allowable input VAT ± adjustments."),
    ("8. VAT PAYABLE / REFUNDABLE", "Positive = payable to ZIMRA. Negative = "
     "refundable / carried forward."),
]


# ---------------------------------------------------------------------------
# Calculation-step explanation builders
# ---------------------------------------------------------------------------
def calc_block(step_name, formula, values, answer, tech, grade7, rule, status):
    """Build the visible explainable-calculation record for one step."""
    return {
        "step": step_name,
        "formula": formula,
        "values": values,
        "substitution": None,   # filled by the caller
        "answer": answer,
        "explanation_technical": tech,
        "explanation_grade7": grade7,
        "rule": rule,
        "status": status,
    }


RULES = {
    "standard": ("VAT Act [Chapter 23:12] s12 — output tax at the standard rate "
                 f"({config.VAT_RATE_PCT:g}%, effective {config.VAT_RATE_EFFECTIVE})."),
    "zero_rated": "VAT Act s10 — zero-rated supplies; 0% output VAT; input VAT on related costs still claimable.",
    "exempt": ("VAT Act s11 and First Schedule — exempt supplies; no output VAT; "
               "input VAT generally not claimable on costs attributable to exempt supplies."),
    "import_goods": "VAT charged at import = VAT rate x (customs value + customs duty); claimable as input VAT by the registered importer.",
    "imported_service": "VAT Act s13A — reverse charge: account output VAT and take a mirror input credit where used for taxable supplies.",
    "credit_note": "Credit note on a taxable supply reduces output VAT by the VAT included in the credit.",
    "debit_note": "Debit note on a taxable supply increases output VAT by the VAT included in the debit.",
    "bad_debt": "Bad-debt relief reverses output VAT on debts written off (>6 months), using the VAT-inclusive fraction.",
    "de_minimis_apportion": ("VAT Act s16 apportionment with de minimis — exempt "
                             f"turnover <= {config.DE_MINIMIS_APPORTIONMENT_PCT*100:g}% "
                             "allows full recovery of mixed input tax."),
    "de_minimis_invoice": ("Invoicing de minimis — no fiscal invoice required "
                           f"below US${float(config.DE_MINIMIS_INVOICE_USD):,.0f} "
                           "(or ZiG equivalent). Does NOT exempt the supply."),
    "currency": "Multi-currency: ZiG and USD schedules are kept separate (ZIMRA never mixes them); ZAR is converted at the applicable exchange rate.",
    "reverse_charge": "VAT Act s13A — imported services are reverse-charged.",
}


def side_title(side):
    return {
        "sale": "Output VAT",
        "purchase": "Allowable Input VAT",
        "import_goods": "Input VAT — imports of goods",
        "imported_service": "Reverse charge (imported services)",
        "adjustment": "Adjustment",
    }.get(side, side.title())


def grade7(t):
    return t