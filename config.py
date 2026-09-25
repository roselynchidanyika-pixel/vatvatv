"""config.py — Central configuration for the Zimbabwe VAT Return Automation System.

Every legal rate, threshold and rule is defined HERE (not scattered through
the code) so that a future change in Zimbabwe law can be updated in one place.
Each value records its effective date and source so the system is auditable.

NOTE: Values below were verified against authoritative sources on 25 September
2026. Verify again before any real filing — Zimbabwe tax law changes regularly.
"""

from decimal import Decimal

# ---------------------------------------------------------------------------
# Standard VAT rate
# ---------------------------------------------------------------------------
VAT_RATE_PCT = Decimal("15.5")      # 15.5% with effect 1 January 2026
VAT_RATE_DECIMAL = VAT_RATE_PCT / Decimal("100")
VAT_FRACTION = VAT_RATE_DECIMAL / (Decimal("1") + VAT_RATE_DECIMAL)   # 15.5/115.5
VAT_RATE_SOURCE = ("Finance Act (No. 7) of 2025, gazetted 29 December 2025; "
                   "ZIMRA Public Notice 07 of 2026. Raised from 15% (15/115 "
                   "inclusive fraction for pre-2026 periods).")
VAT_RATE_EFFECTIVE = "1 January 2026"

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
VAT_REGISTRATION_THRESHOLD_USD = Decimal("25000")   # compulsory registration
REGISTRATION_EFFECTIVE = "1 January 2024"
REGISTRATION_SOURCE = ("VAT Act [Chapter 23:12] read with Finance Act (No. 13) "
                       "of 2023; ZIMRA registration guidance — taxable supplies "
                       "exceeding US$25 000 (or ZiG equivalent) in any 12 months.")

# ---------------------------------------------------------------------------
# De minimis rules — TWO different rules, deliberately distinguished
# ---------------------------------------------------------------------------
# Rule A: INVOICING de minimis — a supplier is NOT required to issue a fiscal
# tax invoice where the amount is below this threshold. This does NOT make the
# supply exempt — the VAT treatment must still be determined separately.
DE_MINIMIS_INVOICE_USD = Decimal("10.00")
DE_MINIMIS_INVOICE_EFFECTIVE = "1 September 2022"
DE_MINIMIS_INVOICE_SOURCE = ("VAT Act [Chapter 23:12] s20; VAT (General) "
                             "Regulations (SI 273 of 2003); ZIMRA guidance — "
                             "fiscal invoice not required below US$10 (or ZiG "
                             "equivalent).")

# Rule B: APPORTIONMENT de minimis — where exempt supplies are a small share
# (<= 5%) of total turnover, mixed (overhead) input tax is deductible in full
# without turnover apportionment.
DE_MINIMIS_APPORTIONMENT_PCT = Decimal("0.05")      # 5%
DE_MINIMIS_APPORTIONMENT_EFFECTIVE = "Current VAT Act practice (reviewed 2026)"
DE_MINIMIS_APPORTIONMENT_SOURCE = ("VAT Act [Chapter 23:12] s16 input-tax "
                                   "apportionment practice for mixed suppliers; "
                                   "ZIMRA de minimis guidance (exempt turnover "
                                   "<= 5% allows full input recovery).")
DE_MINIMIS_APPORTIONMENT_NOTE = (
    "Exempt supplies = {share:.2f}% of total turnover (<= 5%). "
    "De minimis applied - input tax deductible in full.")

# ---------------------------------------------------------------------------
# Refunds / small balances
# ---------------------------------------------------------------------------
SMALL_REFUND_USD = Decimal("60.00")
SMALL_REFUND_SOURCE = ("ZIMRA practice (VAT Act s54 read with current guidance): "
                       "refunds below US$60 (or ZiG equivalent) are carried as a "
                       "credit until cumulative refunds reach US$60.")

# ---------------------------------------------------------------------------
# Claims & filing
# ---------------------------------------------------------------------------
INPUT_TAX_CLAIM_MONTHS = 12          # claim within 12 months of the invoice date
RETURN_NAME = "VAT 7"
PAYMENT_DAY = 15                     # payment due (per SI 81 of 2025/ZIMRA notices)
RETURN_DUE_DAY = 10                  # return filing due (per SI 81 of 2025)
FILING_NOTE = ("ZIMRA due dates (SI 81 of 2025 / ZIMRA Public Notices): the VAT "
               "return is generally due by the 10th and payment by the 15th of "
               "the month following the tax period. Historically the due date "
               "was the 25th. Confirm the current due date with ZIMRA.")

# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------
SUPPORTED_CURRENCIES = ("USD", "ZIG", "ZAR")
CURRENCY_LABELS = {
    "USD": "US Dollar",
    "ZIG": "Zimbabwe Gold (ZiG)",
    "ZAR": "South African Rand",
}
# Local / reporting legal tender currencies for the statutory schedules.
# ZIMRA requires a SEPARATE schedule per currency — USD and ZiG are never mixed.
LEGAL_TENDER = ("ZIG", "USD")
ZAR_CONVERT_TARGET = "USD"           # ZAR is converted into the USD schedule
DEFAULT_CURRENCY = "ZIG"

# Fallback / demo exchange rates (units per USD) — used ONLY when live feed and
# cache fail. Clearly labelled as a snapshot. Values: 1 USD = 26.6347 ZiG,
# 1 USD = 16.4314 ZAR (open.er-api.com, 25 Sep 2026). Never pass these off as
# live.
DEMO_RATES = {
    "USD": Decimal("1.0"),
    "ZIG": Decimal("26.6347"),
    "ZAR": Decimal("16.4314"),
}
DEMO_RATES_DATE = "25 September 2026"
DEMO_RATES_SOURCE = ("open.er-api.com live feed shadowing the RBZ official rate "
                     "(snapshot; verify against the Reserve Bank of Zimbabwe)")

# ---------------------------------------------------------------------------
# Legal references used across the app
# ---------------------------------------------------------------------------
REFERENCES = [
    ("Value Added Tax Act [Chapter 23:12]", "Primary VAT legislation (s8 time of "
     "supply, s10 zero-rated, s11 exempt, s12 output tax, s13A reverse charge on "
     "imported services, s16 input tax/apportionment, s20 tax invoices).",
     "https://www.zimra.co.zw/domestic-taxes/vat/mechanics-of-vat"),
    ("VAT (General) Regulations — SI 273 of 2003", "Invoice, de minimis and "
     "registration technical rules.", "https://www.zimra.co.zw/"),
    ("Finance Act (No. 7) of 2025", "Standard VAT rate 15.5% effective "
     "1 January 2026.", "https://www.veritaszim.net/node/3364"),
    ("ZIMRA Public Notice 07 of 2026", "Change of VAT rate from 15% to 15.5% on "
     "return submission in TaRMS.", "https://www.zimra.co.zw/public-notices"),
    ("Reserve Bank of Zimbabwe — Exchange Rates", "Official ZiG/USD exchange "
     "rates.", "https://www.rbz.co.zw/index.php/research/markets/exchange-rates"),
    ("ZIMRA — Mechanics of VAT", "ZIMRA's own VAT summary document.",
     "https://www.zimra.co.zw/domestic-taxes/vat/mechanics-of-vat"),
]

DISCLAIMER = ("EDUCATIONAL / DEMONSTRATION SYSTEM ONLY. This application is a "
              "university Financial Engineering project and does not replace "
              "professional tax advice, ZIMRA filing systems (TaRMS) or the "
              "primary law. All data is simulated; no real taxpayer data is "
              "used. Verify every rule and figure against the current ZIMRA "
              "publications before relying on it.")