import os
import pickle
from typing import Dict, Tuple

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

FEATURE_COLS = [
    "Open",
    "High",
    "Low",
    "Volume",
    "ma_5",
    "ma_10",
    "ma_20",
    "return_1d",
    "return_5d",
    "volatility_10d",
    "rsi_14",
    "macd",
    "volume_ratio",
    "price_to_ma20",
]


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    feature_df = df.copy()
    feature_df["ma_5"] = feature_df["Close"].rolling(window=5).mean()
    feature_df["ma_10"] = feature_df["Close"].rolling(window=10).mean()
    feature_df["ma_20"] = feature_df["Close"].rolling(window=20).mean()
    feature_df["return_1d"] = feature_df["Close"].pct_change(1)
    feature_df["return_5d"] = feature_df["Close"].pct_change(5)
    feature_df["volatility_10d"] = feature_df["return_1d"].rolling(window=10).std()

    delta = feature_df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    feature_df["rsi_14"] = 100 - (100 / (1 + rs))

    ema_12 = feature_df["Close"].ewm(span=12, adjust=False).mean()
    ema_26 = feature_df["Close"].ewm(span=26, adjust=False).mean()
    feature_df["macd"] = ema_12 - ema_26

    feature_df["volume_ma_10"] = feature_df["Volume"].rolling(window=10).mean()
    feature_df["volume_ratio"] = feature_df["Volume"] / (feature_df["volume_ma_10"] + 1e-9)
    feature_df["price_to_ma20"] = feature_df["Close"] / (feature_df["ma_20"] + 1e-9)
    feature_df["target"] = feature_df["Close"].shift(-1)
    return feature_df.dropna().copy()


def _artifact_paths(symbol: str) -> Tuple[str, str]:
    safe_symbol = symbol.replace(".", "_")
    return (
        os.path.join(MODEL_DIR, f"{safe_symbol}_model.pkl"),
        os.path.join(MODEL_DIR, f"{safe_symbol}_scaler.pkl"),
    )


def train_model(df: pd.DataFrame, symbol: str) -> Dict[str, object]:
    dataset = create_features(df)
    if len(dataset) < 80:
        raise ValueError("Not enough historical rows to train the stock model.")

    X = dataset[FEATURE_COLS]
    y = dataset["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    scaler = MinMaxScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = RandomForestRegressor(
        n_estimators=250,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    predictions = model.predict(X_test_scaled)
    metrics = {
        "mae": round(mean_absolute_error(y_test, predictions), 2),
        "mape": round(mean_absolute_percentage_error(y_test, predictions) * 100, 2),
        "r2": round(r2_score(y_test, predictions), 3),
    }
    metrics["accuracy"] = round(max(0.0, 100.0 - metrics["mape"]), 2)

    model_path, scaler_path = _artifact_paths(symbol)
    with open(model_path, "wb") as model_file:
        pickle.dump(model, model_file)
    with open(scaler_path, "wb") as scaler_file:
        pickle.dump(scaler, scaler_file)

    return {
        "model": model,
        "scaler": scaler,
        "metrics": metrics,
        "dataset": dataset,
    }


def load_model(symbol: str):
    model_path, scaler_path = _artifact_paths(symbol)
    if not (os.path.exists(model_path) and os.path.exists(scaler_path)):
        return None, None

    with open(model_path, "rb") as model_file:
        model = pickle.load(model_file)
    with open(scaler_path, "rb") as scaler_file:
        scaler = pickle.load(scaler_file)
    return model, scaler
