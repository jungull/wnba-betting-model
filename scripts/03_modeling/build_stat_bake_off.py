import os
import pandas as pd
import numpy as np
from tqdm import tqdm
import glob
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Machine Learning imports
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import lightgbm as lgb

DATA_DIR = "data"

def load_normalized_data():
    """Load all normalized player data for modeling."""
    print("Loading normalized player data...")
    
    # Look for normalized data files
    normalized_files = [
        "player_phd_value.parquet",
        "player_refined_value.parquet", 
        "player_comprehensive_value.parquet",
        "player_possession_features.parquet"
    ]
    
    for file in normalized_files:
        file_path = os.path.join(DATA_DIR, file)
        if os.path.exists(file_path):
            print(f"Loading {file}...")
            df = pd.read_parquet(file_path)
            print(f"Loaded {len(df)} records with {len(df.columns)} columns")
            return df
    
    print("❌ No normalized player data found!")
    print("Please run one of the normalization scripts first:")
    print("- build_phd_refined_player_value.py")
    print("- build_refined_player_value.py") 
    print("- build_comprehensive_player_value.py")
    return pd.DataFrame()

def prepare_features(df):
    """Prepare features for modeling."""
    print("Preparing features for modeling...")
    
    # Identify potential feature columns (exclude target variables and metadata)
    exclude_cols = [
        'PLAYER_ID', 'GAME_ID', 'TEAM_ID', 'PLAYER_NAME', 'GAME_DATE',
        'normalization_method', 'minutes', 'offensive_value', 'defensive_value',
        'net_value', 'offensive_value_per_minute', 'defensive_value_per_minute',
        'net_value_per_minute', 'pda_total', 'pda_per_minute'
    ]
    
    # Get all columns that could be features
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Remove columns with too many missing values
    missing_threshold = 0.5
    valid_features = []
    for col in feature_cols:
        missing_pct = df[col].isnull().mean()
        if missing_pct < missing_threshold:
            valid_features.append(col)
        else:
            print(f"Dropping {col}: {missing_pct:.1%} missing values")
    
    print(f"Selected {len(valid_features)} feature columns")
    return valid_features

def identify_target_stats(df):
    """Identify which normalized stats to predict."""
    print("Identifying target statistics for prediction...")
    
    # Define the key normalized stats we want to predict
    target_stats = [
        # Offensive stats
        'normalized_offensive_ppp', 'scoring_value', 'three_pt_value', 
        'playmaking_value', 'ft_value', 'assist_value',
        
        # Defensive stats  
        'steal_value', 'block_value', 'defensive_rebound_value',
        
        # Component stats
        'offensive_possessions', 'offensive_points',
        
        # Advanced metrics
        'ts_pct', 'normalized_ppp'
    ]
    
    # Check which targets are available in the data
    available_targets = []
    for stat in target_stats:
        if stat in df.columns:
            available_targets.append(stat)
        else:
            print(f"Target stat '{stat}' not found in data")
    
    print(f"Found {len(available_targets)} target statistics to predict")
    return available_targets

def create_models():
    """Create a diverse set of models for the bake-off."""
    models = {
        'Linear Regression': LinearRegression(),
        'Ridge Regression': Ridge(alpha=1.0),
        'Lasso Regression': Lasso(alpha=0.1),
        'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42),
        'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
        'XGBoost': xgb.XGBRegressor(n_estimators=100, random_state=42),
        'LightGBM': lgb.LGBMRegressor(n_estimators=100, random_state=42),
        'SVR': SVR(kernel='rbf'),
        'Neural Network': MLPRegressor(hidden_layer_sizes=(100, 50), max_iter=500, random_state=42)
    }
    return models

def evaluate_model(model, X, y, cv_splits=5):
    """Evaluate a model using time series cross-validation."""
    try:
        # Use time series split for temporal data
        tscv = TimeSeriesSplit(n_splits=cv_splits)
        
        # Calculate multiple metrics
        mse_scores = -cross_val_score(model, X, y, cv=tscv, scoring='neg_mean_squared_error')
        mae_scores = -cross_val_score(model, X, y, cv=tscv, scoring='neg_mean_absolute_error')
        r2_scores = cross_val_score(model, X, y, cv=tscv, scoring='r2')
        
        return {
            'mse_mean': mse_scores.mean(),
            'mse_std': mse_scores.std(),
            'mae_mean': mae_scores.mean(),
            'mae_std': mae_scores.std(),
            'r2_mean': r2_scores.mean(),
            'r2_std': r2_scores.std(),
            'overall_score': r2_scores.mean() - mae_scores.mean() / 100  # Combined metric
        }
    except Exception as e:
        print(f"Error evaluating model: {e}")
        return {
            'mse_mean': float('inf'),
            'mse_std': 0,
            'mae_mean': float('inf'),
            'mae_std': 0,
            'r2_mean': -float('inf'),
            'r2_std': 0,
            'overall_score': -float('inf')
        }

def run_bake_off_for_stat(df, target_stat, feature_cols, models):
    """Run model bake-off for a specific target statistic."""
    print(f"\n=== Running Bake-Off for {target_stat} ===")
    
    # Prepare data
    data = df[feature_cols + [target_stat]].dropna()
    
    if len(data) < 100:
        print(f"❌ Insufficient data for {target_stat}: only {len(data)} samples")
        return None
    
    X = data[feature_cols]
    y = data[target_stat]
    
    # Handle categorical features
    X = pd.get_dummies(X, drop_first=True)
    
    # Scale features for models that need it
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Evaluate each model
    results = {}
    
    for model_name, model in tqdm(models.items(), desc=f"Testing models for {target_stat}"):
        try:
            # Use scaled data for models that benefit from it
            if model_name in ['Linear Regression', 'Ridge Regression', 'Lasso Regression', 'SVR', 'Neural Network']:
                X_use = X_scaled
            else:
                X_use = X
            
            # Evaluate model
            scores = evaluate_model(model, X_use, y)
            results[model_name] = scores
            
            print(f"{model_name}: R² = {scores['r2_mean']:.3f} ± {scores['r2_std']:.3f}, "
                  f"MAE = {scores['mae_mean']:.3f} ± {scores['mae_std']:.3f}")
            
        except Exception as e:
            print(f"❌ Error with {model_name}: {e}")
            results[model_name] = {
                'mse_mean': float('inf'),
                'mse_std': 0,
                'mae_mean': float('inf'),
                'mae_std': 0,
                'r2_mean': -float('inf'),
                'r2_std': 0,
                'overall_score': -float('inf')
            }
    
    # Find best model
    best_model_name = max(results.keys(), key=lambda x: results[x]['overall_score'])
    best_score = results[best_model_name]['overall_score']
    
    print(f"\n🏆 Best Model for {target_stat}: {best_model_name}")
    print(f"   R² = {results[best_model_name]['r2_mean']:.3f}")
    print(f"   MAE = {results[best_model_name]['mae_mean']:.3f}")
    
    return {
        'target_stat': target_stat,
        'best_model_name': best_model_name,
        'best_model': models[best_model_name],
        'results': results,
        'feature_cols': feature_cols,
        'scaler': scaler if best_model_name in ['Linear Regression', 'Ridge Regression', 'Lasso Regression', 'SVR', 'Neural Network'] else None,
        'n_samples': len(data)
    }

def save_bake_off_results(bake_off_results, output_dir):
    """Save bake-off results and winning models."""
    print(f"\nSaving bake-off results to {output_dir}...")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save summary results
    summary_data = []
    for result in bake_off_results:
        if result is not None:
            summary_data.append({
                'target_stat': result['target_stat'],
                'best_model': result['best_model_name'],
                'r2_score': result['results'][result['best_model_name']]['r2_mean'],
                'mae_score': result['results'][result['best_model_name']]['mae_mean'],
                'n_samples': result['n_samples']
            })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(os.path.join(output_dir, 'bake_off_summary.csv'), index=False)
    
    # Save detailed results
    detailed_results = {}
    for result in bake_off_results:
        if result is not None:
            detailed_results[result['target_stat']] = result['results']
    
    # Save as JSON for detailed analysis
    import json
    with open(os.path.join(output_dir, 'detailed_results.json'), 'w') as f:
        # Convert numpy types to native Python types for JSON serialization
        json_results = {}
        for stat, models in detailed_results.items():
            json_results[stat] = {}
            for model, scores in models.items():
                json_results[stat][model] = {
                    k: float(v) if isinstance(v, (np.float32, np.float64)) else v
                    for k, v in scores.items()
                }
        json.dump(json_results, f, indent=2)
    
    print(f"✅ Saved bake-off results to {output_dir}")
    return summary_df

def main():
    print("=== Model Bake-Off for Normalized Player Statistics ===")
    
    # Load normalized data
    df = load_normalized_data()
    if df.empty:
        return
    
    # Prepare features and targets
    feature_cols = prepare_features(df)
    target_stats = identify_target_stats(df)
    
    if not target_stats:
        print("❌ No target statistics found!")
        return
    
    # Create models
    models = create_models()
    print(f"Created {len(models)} models for bake-off")
    
    # Run bake-off for each target statistic
    bake_off_results = []
    
    for target_stat in target_stats:
        result = run_bake_off_for_stat(df, target_stat, feature_cols, models)
        bake_off_results.append(result)
    
    # Save results
    output_dir = os.path.join(DATA_DIR, "model_bake_off_results")
    summary_df = save_bake_off_results(bake_off_results, output_dir)
    
    # Print final summary
    print(f"\n=== BAKE-OFF SUMMARY ===")
    print(f"Target Statistics: {len(target_stats)}")
    print(f"Models Tested: {len(models)}")
    print(f"Successful Bake-Offs: {len([r for r in bake_off_results if r is not None])}")
    
    if not summary_df.empty:
        print(f"\nBest Models by Target Statistic:")
        for _, row in summary_df.iterrows():
            print(f"  {row['target_stat']}: {row['best_model']} (R² = {row['r2_score']:.3f})")
        
        # Show model performance distribution
        model_counts = summary_df['best_model'].value_counts()
        print(f"\nModel Performance Distribution:")
        for model, count in model_counts.items():
            print(f"  {model}: {count} wins")
    
    return summary_df

if __name__ == "__main__":
    main() 