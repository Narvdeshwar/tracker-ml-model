import pandas as pd

df_raw = pd.read_csv('IPO-PastIssue-01-01-2020-to-27-10-2026.csv')
df_raw.columns = [c.replace('\ufeff', '').replace('"', '').strip() for c in df_raw.columns]
df_raw['listing_dt'] = pd.to_datetime(df_raw['DATE OF LISTING'], errors='coerce', format='%d-%b-%Y')
recent_eq = df_raw[(df_raw['listing_dt'] > pd.to_datetime('2026-10-06')) & (df_raw['SECURITY TYPE'].isin(['EQ', 'SME']))]
print(f"Equity issues listed between 2026-10-07 and 2026-10-27: {len(recent_eq)}")
print(recent_eq[['COMPANY NAME', 'SECURITY TYPE', 'ISSUE PRICE', 'Symbol', 'DATE OF LISTING']])
