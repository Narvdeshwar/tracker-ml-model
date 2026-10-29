import pandas as pd

df_raw = pd.read_csv('IPO-PastIssue-01-01-2020-to-27-10-2026.csv')
df_raw.columns = [c.replace('\ufeff', '').replace('"', '').strip() for c in df_raw.columns]

# parse dates
df_raw['listing_dt'] = pd.to_datetime(df_raw['DATE OF LISTING'], errors='coerce', format='%d-%b-%Y')
print("Recent listings in raw NSE CSV (after Oct 06, 2026):")
recent = df_raw[df_raw['listing_dt'] > pd.to_datetime('2026-10-06')]
print(recent[['COMPANY NAME', 'SECURITY TYPE', 'ISSUE PRICE', 'Symbol', 'DATE OF LISTING', 'PRICE RANGE']])
