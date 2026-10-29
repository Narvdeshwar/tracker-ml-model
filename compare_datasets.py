import pandas as pd

df_raw = pd.read_csv('IPO-PastIssue-01-01-2020-to-27-10-2026.csv')
df_raw.columns = [c.replace('\ufeff', '').replace('"', '').strip() for c in df_raw.columns]
print('Raw CSV columns:', df_raw.columns.tolist())
print('Raw sample:')
print(df_raw[['COMPANY NAME', 'SECURITY TYPE', 'ISSUE PRICE', 'Symbol', 'ISSUE START DATE', 'ISSUE END DATE', 'DATE OF LISTING']].head(5))

df_cohort = pd.read_csv('data_verified/ipo_cohort_verified.csv')
print('\nCohort board counts:\n', df_cohort['board_type'].value_counts())
print('\nCohort date range:', df_cohort['listing_date'].min(), 'to', df_cohort['listing_date'].max())
print('Cohort columns:', df_cohort.columns.tolist())
print(df_cohort[['issue_id', 'company_name', 'board_type', 'listing_date', 'issue_price_inr', 'listing_open_inr', 'listing_close_inr', 'return_pct']].head(5))
