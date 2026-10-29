import pandas as pd

df_cohort = pd.read_csv('data_verified/ipo_cohort_verified.csv')
missing_open = df_cohort[df_cohort['listing_open_inr'].isnull()]
print("Missing listing open rows:")
print(missing_open[['issue_id', 'company_name', 'board_type', 'listing_date', 'issue_price_inr', 'listing_close_inr', 'note']])
