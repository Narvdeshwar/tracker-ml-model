import pandas as pd
import numpy as np

df_cohort = pd.read_csv('data_verified/ipo_cohort_verified.csv')
df_detail = pd.read_csv('data_verified/verification_detail.csv')

print("Cohort shape:", df_cohort.shape)
print("Detail shape:", df_detail.shape)

# Check join on issue_id
merged = pd.merge(df_cohort, df_detail, on='issue_id', suffixes=('', '_detail'), how='left')
print("Merged shape:", merged.shape)

# Check missing critical columns
print("\nMissing values in key fields:")
print(merged[['issue_id', 'company_name', 'board_type', 'listing_date', 'issue_price_inr', 'listing_open_inr', 'listing_close_inr', 'return_pct']].isnull().sum())

# Inspect return statistics
print("\nReturn stats (listing_close vs issue_price):")
print(merged['return_pct'].describe())

# Classification: Positive vs Flat/Negative listings
merged['is_positive_listing'] = merged['return_pct'] > 0
merged['is_multibagger_listing'] = merged['return_pct'] >= 100
merged['is_loss_listing'] = merged['return_pct'] < 0
merged['is_flat_listing'] = merged['return_pct'] == 0

print("\nListing Distribution:")
print("Total IPOs:", len(merged))
print("Positive Listings (> 0%):", merged['is_positive_listing'].sum(), f"({merged['is_positive_listing'].mean():.1%})")
print("Negative Listings (< 0%):", merged['is_loss_listing'].sum(), f"({merged['is_loss_listing'].mean():.1%})")
print("Flat Listings (0.0%):", merged['is_flat_listing'].sum(), f"({merged['is_flat_listing'].mean():.1%})")
print("Doubled on Listing Day (>= 100%):", merged['is_multibagger_listing'].sum(), f"({merged['is_multibagger_listing'].mean():.1%})")

# Breakdown by Board
print("\nBy Board Type:")
for b, grp in merged.groupby('board_type'):
    print(f"\n--- {b} (Total: {len(grp)}) ---")
    pos = (grp['return_pct'] > 0).sum()
    neg = (grp['return_pct'] < 0).sum()
    flat = (grp['return_pct'] == 0).sum()
    print(f"Positive: {pos} ({pos/len(grp):.1%}), Negative: {neg} ({neg/len(grp):.1%}), Flat: {flat} ({flat/len(grp):.1%})")
    print(f"Median Listing Return: {grp['return_pct'].median():.2f}%")
    print(f"Mean Listing Return: {grp['return_pct'].mean():.2f}%")
