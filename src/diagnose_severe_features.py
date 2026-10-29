import pandas as pd

df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')
df_ipo['listing_year'] = pd.to_datetime(df_ipo['listing_date']).dt.year
df_valid = df_ipo[(df_ipo['cutoff_status'] == 'verified') & (df_ipo['target_listing_open_return_pct'].notnull())].copy()
df_valid['target_B_severe_loss'] = (df_valid['target_listing_open_return_pct'] <= -10.0).astype(int)

for seg in ['Mainboard', 'SME']:
    tr = df_valid[(df_valid['board_type'] == seg) & (df_valid['listing_year'] <= 2024)]
    print(f"\n--- {seg} Train (2020-2024): N={len(tr)}, events={tr['target_B_severe_loss'].sum()} ---")
    for f in ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_mean_listing_open_return_pct']:
        sub = tr.dropna(subset=[f])
        sev = sub[sub['target_B_severe_loss'] == 1][f]
        non = sub[sub['target_B_severe_loss'] == 0][f]
        print(f"  {f}: severe_mean={sev.mean():.4f}, non_severe_mean={non.mean():.4f}")

    te = df_valid[(df_valid['board_type'] == seg) & (df_valid['listing_year'] == 2026)]
    print(f"\n--- {seg} Test (2026): N={len(te)}, events={te['target_B_severe_loss'].sum()} ---")
    for f in ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_mean_listing_open_return_pct']:
        sub = te.dropna(subset=[f])
        sev = sub[sub['target_B_severe_loss'] == 1][f]
        non = sub[sub['target_B_severe_loss'] == 0][f]
        print(f"  {f}: severe_mean={sev.mean():.4f}, non_severe_mean={non.mean():.4f}")
