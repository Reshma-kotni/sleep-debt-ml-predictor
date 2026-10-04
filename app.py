import json
import os
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

app = FastAPI(title="Bedtime & Screentime Sleep Debt Analytics Workbench")

DATA_PATH = os.path.join(os.path.dirname(__file__), "bedtime_screentime_sleep_debt.csv")

def load_and_preprocess_data():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")
    
    df_raw = pd.read_csv(DATA_PATH)
    
    # Introduce small synthetic missing value markers if dataset is completely filled so raw view can demonstrate NaN handling
    df_raw_preview = df_raw.copy()
    
    # Preprocessing & Feature Engineering
    df_clean = df_raw.copy()
    
    # Handle missing values if any
    num_cols = df_clean.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        if df_clean[col].isnull().any():
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())
            
    cat_cols = df_clean.select_dtypes(include=['object']).columns
    for col in cat_cols:
        if df_clean[col].isnull().any():
            df_clean[col] = df_clean[col].fillna(df_clean[col].mode()[0])
            
    # Binary Target Formulation for ML: 1 = High Sleep Debt (Moderate/Severe), 0 = Low Sleep Debt (Mild/Optimal)
    df_clean['target_binary'] = df_clean['sleep_debt_category'].apply(
        lambda x: 1 if str(x).strip() in ['Moderate Debt', 'Severe Sleep Debt'] else 0
    )
    df_clean['target_label'] = df_clean['target_binary'].apply(
        lambda x: 'High Sleep Debt' if x == 1 else 'Good / Normal Sleep'
    )
    
    # Feature Engineering
    df_clean['screen_intensity'] = (df_clean['bedtime_phone_minutes'] * (df_clean['screen_brightness_pct'] / 100.0)).round(2)
    df_clean['sleep_efficiency'] = (df_clean['total_sleep_hours'] / (df_clean['total_sleep_hours'] + (df_clean['sleep_latency_min'] / 60.0))).round(3)
    
    # Binned features
    df_clean['age_group'] = pd.cut(df_clean['age'], bins=[0, 25, 40, 60, 100], labels=['Young (18-25)', 'Adult (26-40)', 'Middle-Aged (41-60)', 'Senior (60+)'])
    df_clean['screentime_tier'] = pd.cut(df_clean['bedtime_phone_minutes'], bins=[-1, 30, 60, 120, 500], labels=['Low (<30m)', 'Moderate (30-60m)', 'High (60-120m)', 'Extreme (>120m)'])
    
    # Scaling for preview display
    scaler_phone = StandardScaler()
    df_clean['screentime_scaled'] = scaler_phone.fit_transform(df_clean[['bedtime_phone_minutes']]).round(3)
    
    # Categorical Encoded representations
    df_clean['gender_code'] = df_clean['gender'].astype('category').cat.codes
    df_clean['app_code'] = df_clean['primary_bedtime_app'].astype('category').cat.codes
    df_clean['occupation_code'] = df_clean['occupation_type'].astype('category').cat.codes
    df_clean['chronotype_code'] = df_clean['chronotype'].astype('category').cat.codes

    return df_raw_preview, df_clean

# Global Data Cache
DF_RAW, DF_CLEAN = load_and_preprocess_data()

def sanitize_json(val):
    if isinstance(val, (float, np.floating)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, dict):
        return {k: sanitize_json(v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_json(v) for v in val]
    if isinstance(val, np.ndarray):
        return [sanitize_json(v) for v in val.tolist()]
    return val

@app.get("/api/raw-data")
def get_raw_data(limit: int = 150):
    limit = min(limit, 150)
    df_sub = DF_RAW.head(limit).copy()
    
    # Convert dataframe to dictionary replacing NaN with None
    records = []
    columns = ["#"] + list(df_sub.columns)
    
    for idx, row in df_sub.iterrows():
        row_dict = {"#": idx}
        for col in df_sub.columns:
            val = row[col]
            if pd.isna(val):
                row_dict[col] = "NaN"
            else:
                row_dict[col] = val
        records.append(row_dict)
        
    return JSONResponse(content={
        "total_count": len(DF_RAW),
        "limit": limit,
        "columns": columns,
        "data": sanitize_json(records)
    })

@app.get("/api/cleaned-data")
def get_cleaned_data(limit: int = 150):
    limit = min(limit, 150)
    # Select key cleaned & engineered columns
    cols_to_show = [
        "user_id", "age", "age_group", "gender", "gender_code", "occupation_type", 
        "bedtime_phone_minutes", "screentime_scaled", "screentime_tier", "screen_brightness_pct", 
        "screen_intensity", "caffeine_post_5pm_mg", "sleep_latency_min", "total_sleep_hours", 
        "sleep_efficiency", "sleep_debt_category", "target_binary"
    ]
    df_sub = DF_CLEAN[cols_to_show].head(limit).copy()
    
    records = []
    columns = ["#"] + cols_to_show
    for idx, row in df_sub.iterrows():
        row_dict = {"#": idx}
        for col in cols_to_show:
            val = row[col]
            row_dict[col] = None if pd.isna(val) else str(val) if isinstance(val, (pd.CategoricalDtype, str)) else val
        records.append(row_dict)
        
    return JSONResponse(content={
        "total_count": len(DF_CLEAN),
        "limit": limit,
        "columns": columns,
        "data": sanitize_json(records)
    })

@app.get("/api/eda")
def get_eda_summary():
    total_records = len(DF_CLEAN)
    
    # Target Class Counts & Ratio
    target_counts = DF_CLEAN['sleep_debt_category'].value_counts().to_dict()
    binary_target_counts = DF_CLEAN['target_label'].value_counts().to_dict()
    
    total_binary = sum(binary_target_counts.values())
    binary_ratios = {k: round((v / total_binary) * 100, 2) for k, v in binary_target_counts.items()}
    
    # Key Numerical Averages
    key_averages = {
        "avg_screentime": round(DF_CLEAN['bedtime_phone_minutes'].mean(), 2),
        "avg_sleep_hours": round(DF_CLEAN['total_sleep_hours'].mean(), 2),
        "avg_fatigue": round(DF_CLEAN['next_day_fatigue_score'].mean(), 2),
        "avg_brightness": round(DF_CLEAN['screen_brightness_pct'].mean(), 2),
        "avg_latency": round(DF_CLEAN['sleep_latency_min'].mean(), 2),
        "avg_caffeine": round(DF_CLEAN['caffeine_post_5pm_mg'].mean(), 2)
    }
    
    # Summary Statistics Table
    num_cols = ['age', 'bedtime_phone_minutes', 'screen_brightness_pct', 'caffeine_post_5pm_mg',
                'physical_activity_min', 'sleep_latency_min', 'total_sleep_hours', 
                'deep_sleep_pct', 'rem_sleep_pct', 'morning_alarm_snoozes', 'next_day_fatigue_score',
                'screen_intensity', 'sleep_efficiency']
    
    desc = DF_CLEAN[num_cols].describe().round(2).T
    summary_stats = []
    for feature in desc.index:
        summary_stats.append({
            "feature": feature,
            "mean": desc.loc[feature, "mean"],
            "std": desc.loc[feature, "std"],
            "min": desc.loc[feature, "min"],
            "q25": desc.loc[feature, "25%"],
            "median": desc.loc[feature, "50%"],
            "q75": desc.loc[feature, "75%"],
            "max": desc.loc[feature, "max"]
        })
        
    overview_text = (
        f"Analyzed {total_records:,} dataset records. High Sleep Debt affects {binary_ratios.get('High Sleep Debt', 0)}% "
        f"of subjects. Screentime averages {key_averages['avg_screentime']} minutes before bedtime, strongly contributing to "
        f"an average sleep latency of {key_averages['avg_latency']} minutes and reduced sleep efficiency."
    )

    return JSONResponse(content=sanitize_json({
        "total_records": total_records,
        "target_counts": target_counts,
        "binary_target_counts": binary_target_counts,
        "binary_ratios": binary_ratios,
        "key_averages": key_averages,
        "summary_stats": summary_stats,
        "overview_text": overview_text
    }))

@app.get("/api/visualizations")
def get_visualizations_data():
    # 1. Pie Chart Data
    target_dist = DF_CLEAN['sleep_debt_category'].value_counts()
    gender_dist = DF_CLEAN['gender'].value_counts()
    pie_data = {
        "target": {"labels": list(target_dist.index), "values": [int(x) for x in target_dist.values]},
        "gender": {"labels": list(gender_dist.index), "values": [int(x) for x in gender_dist.values]}
    }
    
    # 2. Bar Chart Data (Sleep Debt Rate by App and Occupation)
    app_debt = DF_CLEAN.groupby('primary_bedtime_app')['target_binary'].mean().round(4) * 100
    occ_debt = DF_CLEAN.groupby('occupation_type')['target_binary'].mean().round(4) * 100
    bar_data = {
        "app": {"labels": list(app_debt.index), "rates": [float(x) for x in app_debt.values]},
        "occupation": {"labels": list(occ_debt.index), "rates": [float(x) for x in occ_debt.values]}
    }
    
    # 3. Scatterplot Data (Bedtime Phone Min vs Sleep Hours colored by Target Binary)
    # Downsample slightly to 400 points for quick responsive chart rendering
    sample_df = DF_CLEAN.sample(n=min(400, len(DF_CLEAN)), random_state=42)
    scatter_high = sample_df[sample_df['target_binary'] == 1]
    scatter_low = sample_df[sample_df['target_binary'] == 0]
    
    scatter_data = {
        "high_debt": [{"x": float(r['bedtime_phone_minutes']), "y": float(r['total_sleep_hours'])} for _, r in scatter_high.iterrows()],
        "good_sleep": [{"x": float(r['bedtime_phone_minutes']), "y": float(r['total_sleep_hours'])} for _, r in scatter_low.iterrows()]
    }
    
    # 4. Boxplot Distribution Data
    box_metrics = ['sleep_latency_min', 'next_day_fatigue_score', 'screen_brightness_pct']
    boxplot_data = {}
    for metric in box_metrics:
        high_vals = DF_CLEAN[DF_CLEAN['target_binary'] == 1][metric].values
        good_vals = DF_CLEAN[DF_CLEAN['target_binary'] == 0][metric].values
        
        def calc_quartiles(arr):
            q25, q50, q75 = np.percentile(arr, [25, 50, 75])
            iqr = q75 - q25
            min_val = float(np.min(arr[arr >= q25 - 1.5 * iqr]))
            max_val = float(np.max(arr[arr <= q75 + 1.5 * iqr]))
            return {"min": min_val, "q25": float(q25), "median": float(q50), "q75": float(q75), "max": max_val}
            
        boxplot_data[metric] = {
            "high_debt": calc_quartiles(high_vals),
            "good_sleep": calc_quartiles(good_vals)
        }
        
    # 5. Correlation Heatmap Data (Pearson r)
    heatmap_cols = ['age', 'bedtime_phone_minutes', 'screen_brightness_pct', 'caffeine_post_5pm_mg', 
                    'physical_activity_min', 'sleep_latency_min', 'total_sleep_hours', 
                    'deep_sleep_pct', 'next_day_fatigue_score', 'screen_intensity', 'target_binary']
    corr_df = DF_CLEAN[heatmap_cols].corr().round(2)
    heatmap_data = {
        "columns": heatmap_cols,
        "matrix": corr_df.values.tolist()
    }
    
    # 6. Line & Countplot Data
    # Trend of Avg Sleep Hours & Phone Min by Age Group
    age_trend = DF_CLEAN.groupby('age_group', observed=False)[['total_sleep_hours', 'bedtime_phone_minutes']].mean().round(2)
    
    # Countplot: Blue Light Filter Active vs Snoozes (>2 snoozes vs <=2 snoozes)
    DF_CLEAN['frequent_snoozer'] = DF_CLEAN['morning_alarm_snoozes'].apply(lambda x: 'High Snoozes (3+)' if x >= 3 else 'Low Snoozes (0-2)')
    blue_light_ct = pd.crosstab(DF_CLEAN['blue_light_filter_active'], DF_CLEAN['frequent_snoozer'])
    
    line_countplot_data = {
        "age_labels": [str(x) for x in age_trend.index],
        "sleep_by_age": [float(x) for x in age_trend['total_sleep_hours'].values],
        "phone_by_age": [float(x) for x in age_trend['bedtime_phone_minutes'].values],
        "blue_light_labels": ["Filter Disabled (0)", "Filter Enabled (1)"],
        "high_snoozes": [int(blue_light_ct.loc[0, 'High Snoozes (3+)']), int(blue_light_ct.loc[1, 'High Snoozes (3+)'])],
        "low_snoozes": [int(blue_light_ct.loc[0, 'Low Snoozes (0-2)']), int(blue_light_ct.loc[1, 'Low Snoozes (0-2)'])]
    }
    
    return JSONResponse(content=sanitize_json({
        "pie": pie_data,
        "bar": bar_data,
        "scatter": scatter_data,
        "boxplot": boxplot_data,
        "heatmap": heatmap_data,
        "line_countplot": line_countplot_data
    }))

def train_single_model(model_type: str, test_size: float = 0.2):
    features = [
        'age', 'bedtime_phone_minutes', 'screen_brightness_pct', 'blue_light_filter_active',
        'caffeine_post_5pm_mg', 'physical_activity_min', 'sleep_latency_min', 
        'total_sleep_hours', 'deep_sleep_pct', 'rem_sleep_pct', 'morning_alarm_snoozes', 
        'next_day_fatigue_score', 'screen_intensity', 'sleep_efficiency'
    ]
    
    X = DF_CLEAN[features]
    y = DF_CLEAN['target_binary']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42, stratify=y)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    if model_type == "rf":
        model = RandomForestClassifier(n_estimators=100, random_state=42)
    elif model_type == "knn":
        model = KNeighborsClassifier(n_neighbors=5)
    elif model_type == "svm":
        model = SVC(kernel='rbf', C=1.0, random_state=42)
    else:  # default logistic
        model = LogisticRegression(max_iter=1000, random_state=42)
        
    model.fit(X_train_scaled, y_train)
    y_pred = model.predict(X_test_scaled)
    
    # ROC AUC calculation
    if hasattr(model, "predict_proba"):
        y_proba = model.predict_proba(X_test_scaled)[:, 1]
    elif hasattr(model, "decision_function"):
        y_proba = model.decision_function(X_test_scaled)
    else:
        y_proba = y_pred
        
    acc = round(accuracy_score(y_test, y_pred), 4)
    prec = round(precision_score(y_test, y_pred, zero_division=0), 4)
    rec = round(recall_score(y_test, y_pred, zero_division=0), 4)
    f1 = round(f1_score(y_test, y_pred, zero_division=0), 4)
    auc = round(roc_auc_score(y_test, y_proba), 4)
    
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = [int(x) for x in cm.ravel()]
    
    # Feature Importances or Coefficients
    importances = []
    if hasattr(model, "feature_importances_"):
        raw_imp = model.feature_importances_
        for f, imp in zip(features, raw_imp):
            importances.append({"feature": f, "importance": round(float(imp), 4)})
    elif hasattr(model, "coef_"):
        raw_coef = np.abs(model.coef_[0])
        for f, coef in zip(features, raw_coef):
            importances.append({"feature": f, "importance": round(float(coef), 4)})
    else: # KNN fallback: correlation with predictions
        for f in features:
            corr = np.abs(np.corrcoef(X_test[f], y_pred)[0, 1])
            importances.append({"feature": f, "importance": round(float(0 if np.isnan(corr) else corr), 4)})
            
    importances = sorted(importances, key=lambda x: x["importance"], reverse=True)
    
    return {
        "model_type": model_type,
        "metrics": {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "roc_auc": auc
        },
        "confusion_matrix": {
            "tn": tn, "fp": fp, "fn": fn, "tp": tp,
            "grid": [[tn, fp], [fn, tp]]
        },
        "feature_importances": importances
    }

@app.get("/api/train-model")
def train_model(model_type: str = "logistic", test_size: float = 0.2):
    valid_models = ["logistic", "rf", "knn", "svm"]
    if model_type not in valid_models:
        model_type = "logistic"
    res = train_single_model(model_type, test_size)
    return JSONResponse(content=sanitize_json(res))

@app.get("/api/compare-models")
def compare_models(test_size: float = 0.2):
    models = ["logistic", "rf", "knn", "svm"]
    names_map = {
        "logistic": "⚡ Logistic Regression",
        "rf": "🌲 Random Forest",
        "knn": "🎯 K-Nearest Neighbors",
        "svm": "📈 Support Vector Machine"
    }
    
    results = {}
    best_model = None
    best_f1 = -1.0
    
    for m in models:
        res = train_single_model(m, test_size)
        res["display_name"] = names_map[m]
        results[m] = res
        if res["metrics"]["f1_score"] > best_f1:
            best_f1 = res["metrics"]["f1_score"]
            best_model = names_map[m]
            
    return JSONResponse(content=sanitize_json({
        "models": results,
        "best_model": best_model,
        "champion_f1": best_f1
    }))

# Serve static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Workbench HTML is initializing...</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
