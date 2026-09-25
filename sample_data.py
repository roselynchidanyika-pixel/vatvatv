"""sample_data.py — DEMO / SIMULATED transaction datasets (no real taxpayer data).

Four embedded datasets + matching CSV files under data/:
  1. Amber Mart (ZiG worked example)      - single-currency ZiG, maps to the
                                            13-line VAT 7 summary in the brief
  2. Veritas Wholesale (USD only)         - single-currency USD
  3. Tri-Currency Traders (mixed)         - USD + ZiG + ZAR in one ledger
  4. QA — dataset with errors             - intentionally failing rows for PASS/FAIL
"""

import io

import pandas as pd

CANONICAL = ("txn_id,date,direction,description,counterparty,category,amount,"
             "vat_inclusive,customs_value,customs_duty,prohibited_reason,"
             "business_use_pct,adjustment_type,mixed_input,import_flag,"
             "invoice_number,supporting_document_available,currency,exchange_rate,"
             "exchange_rate_date,exchange_rate_source,notes")

_BLANK = "supporting_document_available=TRUE".replace("=", ",")  # placeholder, unused

# --------------------------------------------------------------------------
# 1. Single-currency (ZiG) worked example — "Amber Mart"
# --------------------------------------------------------------------------
AMBER_MART_CSV = """txn_id,date,direction,description,counterparty,category,amount,vat_inclusive,customs_value,customs_duty,prohibited_reason,business_use_pct,adjustment_type,mixed_input,import_flag,invoice_number,supporting_document_available,currency,exchange_rate,exchange_rate_date,exchange_rate_source,notes
S-A1,2026-05-06,sale,Retail sales - groceries,Walk-in customers,standard,23500.00,FALSE,0,0,,100,,FALSE,FALSE,INV-1001,TRUE,ZIG,,,,Standard-rated retail sales
S-A2,2026-05-09,sale,Sale of mealie meal (zero-rated foodstuff),Wholesale buyers,zero_rated,10000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-1002,TRUE,ZIG,,,,Zero-rated basic foodstuff
S-A3,2026-05-15,sale,Residential rent - Avondale flats,Tenant,exempt,750.00,FALSE,0,0,,100,,FALSE,FALSE,R-101,TRUE,ZIG,,,,Exempt residential accommodation
ADJ-A1,2026-05-22,adjustment,Credit note - returned goods (original invoice VAT-inclusive),Customer,standard,1341.29,TRUE,0,0,,100,credit_note,FALSE,FALSE,INV-1001,TRUE,ZIG,,,,Reduces output VAT by 180.00
IMP-S-A1,2026-05-25,imported_service,Cloud accounting subscription (non-resident),CloudCo (UK),standard,1935.48,FALSE,0,0,,100,,FALSE,FALSE,C-202,TRUE,ZIG,,,,Reverse charge on imported service
P-A1,2026-05-03,purchase,Purchase of trading stock (direct),Supplier A,standard,7000.00,FALSE,0,0,,100,,FALSE,FALSE,SP-501,TRUE,ZIG,,,,Directly-attributable stock
P-A2,2026-05-05,purchase,Commercial office rent,Landlord,standard,1000.00,FALSE,0,0,,100,,FALSE,FALSE,SP-502,TRUE,ZIG,,,,Rent for business premises
P-A3,2026-05-08,purchase,Electricity - ZESA,ZESA,standard,500.00,FALSE,0,0,,100,,FALSE,FALSE,SP-503,TRUE,ZIG,,,,Power for shop and office
P-A4,2026-05-10,purchase,Packaging materials,Supplier B,standard,1467.74,FALSE,0,0,,100,,FALSE,FALSE,SP-504,TRUE,ZIG,,,,Packaging for retail goods
P-A5,2026-05-12,purchase,Admin overheads (mixed-use - apportionment),Various,standard,1935.48,FALSE,0,0,,100,,TRUE,FALSE,SP-505,TRUE,ZIG,,,,Mixed overhead - de minimis recovery
IMP-G-A1,2026-05-18,import_goods,Machinery parts - import (CD3),Overseas supplier,standard,0,FALSE,5000.00,322.58,,100,,FALSE,TRUE,BL-607,TRUE,ZIG,,,,Import VAT on customs value + duty
"""

# --------------------------------------------------------------------------
# 2. Single-currency (USD) — "Veritas Wholesale"
# --------------------------------------------------------------------------
VERITAS_CSV = """txn_id,date,direction,description,counterparty,category,amount,vat_inclusive,customs_value,customs_duty,prohibited_reason,business_use_pct,adjustment_type,mixed_input,import_flag,invoice_number,supporting_document_available,currency,exchange_rate,exchange_rate_date,exchange_rate_source,notes
S-V1,2026-05-07,sale,Wholesale sales of hardware,Retailers,standard,45000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-2001,TRUE,USD,,,,Standard-rated wholesale sales
S-V2,2026-05-11,sale,Exported hardware to Botswana (bill of entry held),Gaborone Ltd (BW),export,12000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-2002,TRUE,USD,,,,Zero-rated export with proof
ADJ-V1,2026-05-20,adjustment,Credit note - price reduction,Retailer,standard,2000.00,FALSE,0,0,,100,credit_note,FALSE,FALSE,INV-2001,TRUE,USD,,,,Reduces output VAT by 310.00
ADJ-V2,2026-05-23,adjustment,Debit note - additional charge on supply,Retailer,standard,1000.00,FALSE,0,0,,100,debit_note,FALSE,FALSE,INV-2003,TRUE,USD,,,,Increases output VAT by 155.00
IMP-S-V1,2026-05-26,imported_service,Software licence from non-resident,SaaS Ltd (US),standard,3000.00,FALSE,0,0,,100,,FALSE,FALSE,LC-210,TRUE,USD,,,,Reverse charge imported service
P-V1,2026-05-02,purchase,Trading stock - hardware lines,Shenzhen Trading,standard,20000.00,FALSE,0,0,,100,,FALSE,FALSE,SP-701,TRUE,USD,,,,Stock purchases
P-V2,2026-05-04,purchase,Warehouse rent,ProProp,standard,2500.00,FALSE,0,0,,100,,FALSE,FALSE,SP-702,TRUE,USD,,,,Warehouse rental
P-V3,2026-05-06,purchase,Local transport and freight,FreightCo,standard,1200.00,FALSE,0,0,,100,,FALSE,FALSE,SP-703,TRUE,USD,,,,Distribution costs
P-V4,2026-05-09,purchase,Utilities (mixed head-office overhead),City Council,standard,1500.00,FALSE,0,0,,100,,TRUE,FALSE,SP-704,TRUE,USD,,,,Mixed overhead - full recovery (no exempt supplies)
P-V5,2026-05-14,purchase,Client entertainment - restaurant,Restaurant,standard,800.00,FALSE,0,0,entertainment,100,,FALSE,FALSE,SP-705,TRUE,USD,,,,Prohibited input - no claim
IMP-G-V1,2026-05-17,import_goods,Imported stock from supplier (CD3),Overseas supplier,standard,0,FALSE,8000.00,750.00,,100,,FALSE,TRUE,BL-708,TRUE,USD,,,,Import VAT on customs value + duty
"""

# --------------------------------------------------------------------------
# 3. Mixed-currency — "Tri-Currency Traders" (USD + ZiG + ZAR)
# --------------------------------------------------------------------------
TRI_CSV = """txn_id,date,direction,description,counterparty,category,amount,vat_inclusive,customs_value,customs_duty,prohibited_reason,business_use_pct,adjustment_type,mixed_input,import_flag,invoice_number,supporting_document_available,currency,exchange_rate,exchange_rate_date,exchange_rate_source,notes
S-T1,2026-05-05,sale,Contract sales (USD),Customers,standard,60000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-3001,TRUE,USD,,,,USD-standard sales
S-T2,2026-05-08,sale,Export sales to regional markets,Regional buyer,export,20000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-3002,TRUE,USD,,,,Zero-rated USD export
S-T2Z,2026-05-10,sale,Consulting fees invoiced in ZAR,Botswana client (ZAR),standard,20000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-3003,TRUE,ZAR,,,,Converted to USD on the USD schedule
P-T1,2026-05-02,purchase,Trading stock (USD),Supplier,standard,30000.00,FALSE,0,0,,100,,FALSE,FALSE,SP-801,TRUE,USD,,,,USD stock
P-T2Z,2026-05-06,purchase,Packaging purchased in ZAR,ZA packaging,standard,10000.00,FALSE,0,0,,100,,FALSE,FALSE,SP-802,TRUE,ZAR,,,,Converted to USD on the USD schedule
IMP-G-T1,2026-05-14,import_goods,"Imported equipment (USD, CD3)",Overseas,standard,0,FALSE,10000.00,500.00,,100,,FALSE,TRUE,BL-803,TRUE,USD,,,,Import VAT on AV + duty
ADJ-T1,2026-05-21,adjustment,Credit note - sales return (USD),Customer,standard,4000.00,FALSE,0,0,,100,credit_note,FALSE,FALSE,INV-3001,TRUE,USD,,,,Reduces USD output tax
IMP-S-T1,2026-05-24,imported_service,"Marketing platform (non-resident, USD)",AdTech (US),standard,5000.00,FALSE,0,0,,100,,FALSE,FALSE,LC-804,TRUE,USD,,,,Reverse charge
S-T3,2026-05-03,sale,Local cash sales (ZiG),Walk-in customers,standard,15000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-3005,TRUE,ZIG,,,,ZiG-standard sales
S-T4,2026-05-16,sale,Residential rent (ZiG),Tenants,exempt,1000.00,FALSE,0,0,,100,,FALSE,FALSE,RT-101,TRUE,ZIG,,,,Exempt - ZiG schedule
P-T3,2026-05-11,purchase,Electricity - ZESA (ZiG),ZESA,standard,2000.00,FALSE,0,0,,100,,FALSE,FALSE,SP-805,TRUE,ZIG,,,,ZiG purchases
"""

# --------------------------------------------------------------------------
# 4. QA — dataset with intentional errors (for PASS / FAIL demonstration)
# --------------------------------------------------------------------------
QA_CSV = """txn_id,date,direction,description,counterparty,category,amount,vat_inclusive,customs_value,customs_duty,prohibited_reason,business_use_pct,adjustment_type,mixed_input,import_flag,invoice_number,supporting_document_available,currency,exchange_rate,exchange_rate_date,exchange_rate_source,notes
S-Q1,2026-05-03,sale,Valid standard sale,Test customer,standard,5000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-4001,TRUE,ZIG,,,,Valid row
S-Q2,2026-05-04,sale,Amount is not numeric,Test customer,standard,abc,FALSE,0,0,,100,,FALSE,FALSE,,TRUE,ZIG,,,,FAIL: non-numeric amount
S-Q3,2026-05-05,sale,Missing transaction ID,Test customer,standard,3000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-4003,TRUE,ZIG,,,,FAIL: missing ID
S-Q1,2026-05-06,sale,Duplicate ID with S-Q1,Test customer,standard,800.00,FALSE,0,0,,100,,FALSE,FALSE,INV-4004,TRUE,ZIG,,,,FAIL: duplicate ID
S-Q5,2026-05-07,sale,Unsupported currency (EUR),Test customer,standard,2500.00,FALSE,0,0,,100,,FALSE,FALSE,INV-4005,TRUE,EUR,,,,FAIL: currency not supported
IMP-Q1,2026-05-08,import_goods,Import with no customs value,Overseas,standard,0,FALSE,0,0,,100,,FALSE,TRUE,BL-401,TRUE,USD,,,,FAIL: missing import info
S-Q7,2026-05-09,sale,Zero-rated export without proof of export,Foreign buyer,export,6000.00,FALSE,0,0,,100,,FALSE,FALSE,INV-4007,FALSE,ZIG,,,,REVIEW: export proof missing
P-Q8,2026-05-10,purchase,Purchase without tax invoice,Supplier,standard,1500.00,FALSE,0,0,,100,,FALSE,FALSE,SP-402,FALSE,ZIG,,,,REVIEW: input claim may be disallowed
"""

SAMPLE_FILES = {
    "Amber Mart (ZiG worked example)": AMBER_MART_CSV,
    "Veritas Wholesale (USD only)": VERITAS_CSV,
    "Tri-Currency Traders (mixed USD+ZiG+ZAR)": TRI_CSV,
    "QA — dataset with errors (PASS/FAIL demo)": QA_CSV,
}

SAMPLE_DESCRIPTIONS = {
    "Amber Mart (ZiG worked example)": ("Single-currency ZiG dataset. Produces the "
        "13-line VAT 7 schedule matching the worked example in the brief "
        "(sales 34 250, output tax 3 642.50, adjustments -180, net 792.50)."),
    "Veritas Wholesale (USD only)": ("Single-currency USD dataset. A clean, "
        "USD-only schedule with imports, zero-rated exports, prohibited inputs and "
        "adjustments."),
    "Tri-Currency Traders (mixed USD+ZiG+ZAR)": ("Mixed-currency dataset. USD and "
        "ZiG appear together; ZAR transactions are converted into the USD schedule. "
        "The app keeps the USD and ZiG schedules fully separate (ZIMRA rule)."),
    "QA — dataset with errors (PASS/FAIL demo)": ("Simulated poor-quality data "
        "with intentional errors: non-numeric amount, missing ID, duplicate ID, "
        "unsupported currency, missing import information and missing documents. "
        "Ideal for demonstrating the validation PASS/FAIL system."),
}


def load_sample(name):
    return pd.read_csv(io.StringIO(SAMPLE_FILES[name]))