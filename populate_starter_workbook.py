import pandas as pd
import openpyxl
from datetime import datetime

# Load verified cohort and detail
df_cohort = pd.read_csv('data_verified/ipo_cohort_verified.csv')
df_detail = pd.read_csv('data_verified/verification_detail.csv')

# Load raw NSE past issues for additional metadata (dates, symbols, etc.)
df_raw = pd.read_csv('IPO-PastIssue-01-01-2020-to-27-10-2026.csv')
df_raw.columns = [c.replace('\ufeff', '').replace('"', '').strip() for c in df_raw.columns]

# Index raw by Symbol and normalized company name
raw_by_symbol = {}
for _, row in df_raw.iterrows():
    sym = str(row.get('Symbol', '')).strip().upper()
    if sym and sym != '-':
        raw_by_symbol[sym] = row

# Merge cohort with detail
detail_map = {row['issue_id']: row for _, row in df_detail.iterrows()}

print(f"Loaded {len(df_cohort)} cohort records and {len(df_detail)} detail records.")

# Load Workbook
wb = openpyxl.load_workbook('Indian_IPO_ML_Research_Starter.xlsx')

# 1. Populate Source_Register
ws_sources = wb['Source_Register']
sources = [
    {
        'source_id': 'SRC_001',
        'dataset_area': 'IPO Listing & Exchange Verification',
        'source_name': 'IPO Performance Verification Dataset (bebhuvan)',
        'source_url': 'https://github.com/bebhuvan/ipo-performance-verification',
        'source_type': 'Curated GitHub Repository / Official Cross-Checked',
        'coverage_start': '2020-01-01',
        'coverage_end': '2026-10-06',
        'update_frequency': 'Periodic archive',
        'official_or_unofficial': 'Verified against official exchange records',
        'known_limitations': 'Covers completed listings up to 06-Oct-2026; 3 SME open prices require backfill',
        'retrieval_method': 'Direct CSV download',
        'terms_or_access_notes': 'Open research dataset with reproducible validation scripts',
        'last_checked_date': '2026-10-27',
        'status': 'Active'
    },
    {
        'source_id': 'SRC_002',
        'dataset_area': 'NSE Historical Issues',
        'source_name': 'NSE Past Issues Archive',
        'source_url': 'https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives',
        'source_type': 'Primary Exchange Archive',
        'coverage_start': '2020-01-01',
        'coverage_end': '2026-10-27',
        'update_frequency': 'Daily/Monthly',
        'official_or_unofficial': 'Official Exchange Record',
        'known_limitations': 'Contains debt & rights issues; issue prices not updated until listing completion',
        'retrieval_method': 'Exchange Portal Export (CSV)',
        'terms_or_access_notes': 'Public exchange report',
        'last_checked_date': '2026-10-27',
        'status': 'Active'
    },
    {
        'source_id': 'SRC_003',
        'dataset_area': 'SEBI Market Data Directory',
        'source_name': 'SEBI Primary Market Linkages',
        'source_url': 'https://www.sebi.gov.in/Curation_Links_for_Securities_Market_Data.html',
        'source_type': 'Regulatory Authority Directory',
        'coverage_start': '2020-01-01',
        'coverage_end': '2026-10-27',
        'update_frequency': 'Monthly / Periodic',
        'official_or_unofficial': 'Official Regulatory Record',
        'known_limitations': 'Provides directional links rather than high-frequency timeseries',
        'retrieval_method': 'Regulatory directory curation',
        'terms_or_access_notes': 'Statutory public guidance',
        'last_checked_date': '2026-10-27',
        'status': 'Active'
    }
]

# Clear existing rows beyond header in Source_Register
while ws_sources.max_row > 1:
    ws_sources.delete_rows(2)

src_headers = [c.value for c in ws_sources[1]]
for s in sources:
    row_vals = [s.get(col, '') for col in src_headers]
    ws_sources.append(row_vals)

# 2. Populate IPO_Master and Listing_Outcomes
ws_master = wb['IPO_Master']
while ws_master.max_row > 1:
    ws_master.delete_rows(2)
master_headers = [c.value for c in ws_master[1]]

ws_outcomes = wb['Listing_Outcomes']
while ws_outcomes.max_row > 1:
    ws_outcomes.delete_rows(2)
outcome_headers = [c.value for c in ws_outcomes[1]]

# 3. Populate Data_Quality_Log
ws_quality = wb['Data_Quality_Log']
while ws_quality.max_row > 1:
    ws_quality.delete_rows(2)
quality_headers = [c.value for c in ws_quality[1]]

quality_issues = []

for idx, row in df_cohort.iterrows():
    issue_id = str(row['issue_id']).strip()
    cname = str(row['company_name']).strip()
    board = 'Mainboard' if 'Main' in str(row['board_type']) else 'SME'
    ldate = str(row['listing_date']).strip()
    issue_price = float(row['issue_price_inr']) if pd.notnull(row['issue_price_inr']) else None
    open_price = float(row['listing_open_inr']) if pd.notnull(row['listing_open_inr']) else None
    close_price = float(row['listing_close_inr']) if pd.notnull(row['listing_close_inr']) else None
    
    det = detail_map.get(issue_id, {})
    nse_sym = str(row['nse_symbol']).strip() if pd.notnull(row['nse_symbol']) and str(row['nse_symbol']).strip() != '-' else None
    bse_sym = str(row['bse_symbol']).strip() if pd.notnull(row['bse_symbol']) and str(row['bse_symbol']).strip() != '-' else None
    isin = str(det.get('nse_isin', '') or det.get('bse_isin', '')).strip()
    if isin in ['nan', '-', 'None', '']:
        isin = None

    venue = str(row.get('venue', '')).strip()
    exchange_used = str(row.get('price_exchange', venue)).strip()

    # Calculate returns
    close_ret_pct = round(((close_price - issue_price) / issue_price) * 100, 2) if issue_price and close_price is not None else None
    open_ret_pct = round(((open_price - issue_price) / issue_price) * 100, 2) if issue_price and open_price is not None else None

    # Check matching raw NSE issue info for start/end dates
    raw_match = raw_by_symbol.get(nse_sym) if nse_sym else None
    open_dt = raw_match.get('ISSUE START DATE', '') if raw_match is not None else None
    close_dt = raw_match.get('ISSUE END DATE', '') if raw_match is not None else None
    price_range = raw_match.get('PRICE RANGE', '') if raw_match is not None else None

    # IPO_Master row
    master_row_dict = {
        'ipo_id': issue_id,
        'company_name': cname,
        'nse_symbol': nse_sym,
        'bse_code': bse_sym,
        'isin': isin,
        'board_type': board,
        'sector': None,
        'issue_open_date': open_dt,
        'issue_close_date': close_dt,
        'allotment_date': None,
        'listing_date': ldate,
        'issue_price_inr': issue_price,
        'price_band_low_inr': None,
        'price_band_high_inr': None,
        'issue_size_cr': None,
        'fresh_issue_cr': None,
        'ofs_cr': None,
        'lot_size_shares': None,
        'min_application_inr': None,
        'lead_manager': None,
        'final_rhp_url': None,
        'source_url': 'https://github.com/bebhuvan/ipo-performance-verification',
        'source_asof_date': '2026-10-27',
        'verification_status': 'Verified against NSE/BSE official Bhavcopy',
        'notes': str(row.get('note', '') or '')
    }
    ws_master.append([master_row_dict.get(col, '') for col in master_headers])

    # Listing_Outcomes row
    outcome_row_dict = {
        'ipo_id': issue_id,
        'listing_exchange_used': exchange_used,
        'listing_open_inr': open_price,
        'listing_high_inr': None,
        'listing_low_inr': None,
        'listing_close_inr': close_price,
        'issue_price_inr': issue_price,
        'listing_open_return_pct': open_ret_pct,
        'listing_close_return_pct': close_ret_pct,
        'day5_date': None,
        'day5_close_inr': None,
        'day5_return_pct': None,
        'day10_date': None,
        'day10_close_inr': None,
        'day10_return_pct': None,
        'day20_date': None,
        'day20_close_inr': None,
        'day20_return_pct': None,
        'max_drawdown_20d_pct': None,
        'lower_circuit_events_20d': None,
        'listing_volume_shares': None,
        'listing_turnover_inr': None,
        'exit_liquidity_status': 'Liquid' if board == 'Mainboard' else 'SME Lot Constrained',
        'outcome_source_url': 'Official NSE/BSE Bhavcopy cross-check',
        'verified_by': 'bebhuvan / Exchange Bhavcopy',
        'verification_status': 'Verified',
        'notes': str(row.get('close_basis', '') or '')
    }
    ws_outcomes.append([outcome_row_dict.get(col, '') for col in outcome_headers])

    # Log data quality discrepancies
    if open_price is None:
        quality_issues.append({
            'issue_id': f"DQ_{len(quality_issues)+1:04d}",
            'table_name': 'Listing_Outcomes',
            'ipo_id_or_date': issue_id,
            'field_name': 'listing_open_inr',
            'issue_type': 'Missing Value',
            'severity': 'Medium',
            'description': f"Listing open price missing for SME IPO {cname} on {ldate}",
            'proposed_resolution': 'Backfill from exchange morning trade log / pre-open quote',
            'resolution_status': 'Pending Verification',
            'source_url': 'NSE/BSE Bhavcopy',
            'checked_by': 'Automated Pipeline',
            'checked_at': '2026-10-27'
        })

# Append quality issues
for q in quality_issues:
    ws_quality.append([q.get(col, '') for col in quality_headers])

# Save workbook
output_wb = 'Indian_IPO_ML_Research_Starter.xlsx'
wb.save(output_wb)
print(f"Successfully populated {output_wb}:")
print(f"  - IPO_Master: {ws_master.max_row - 1} records")
print(f"  - Listing_Outcomes: {ws_outcomes.max_row - 1} records")
print(f"  - Source_Register: {ws_sources.max_row - 1} sources")
print(f"  - Data_Quality_Log: {ws_quality.max_row - 1} flagged items")
