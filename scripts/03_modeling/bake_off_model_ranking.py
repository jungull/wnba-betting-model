import pandas as pd
import os

summary_path = os.path.join("data", "model_bake_off_results", "bake_off_summary.csv")

if not os.path.exists(summary_path):
    print(f"❌ Could not find summary file at {summary_path}")
    print("Please run build_stat_bake_off.py first.")
    exit(1)

summary_df = pd.read_csv(summary_path)

total_stats = len(summary_df)
model_counts = summary_df['best_model'].value_counts()
model_percentages = (model_counts / total_stats * 100).round(1)

print("\nModel Ranking by % of Stats Won:")
print("---------------------------------")
for model, pct in model_percentages.items():
    print(f"{model}: {pct}% ({model_counts[model]}/{total_stats})") 