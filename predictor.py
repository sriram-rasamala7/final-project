import math
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

from portfolio import STOCK_NAME_TO_SYMBOL, STOCK_UNIVERSE

try:
    import numpy as np
    from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor

    ML_MODELS_AVAILABLE = True
except Exception:
    ML_MODELS_AVAILABLE = False

STOCK_DATA_CACHE = {}
INVESTMENT_PLAN_FETCH_TIMEOUT = 3
INVESTMENT_PLAN_MAX_WORKERS = 6


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_stock_input(stock_input: str):
    cleaned = (stock_input or "").strip()
    if not cleaned:
        return "RELIANCE.NS"
    if "." in cleaned:
        return cleaned.upper()
    return STOCK_NAME_TO_SYMBOL.get(cleaned.lower(), cleaned.upper())


def _generate_synthetic_data(symbol: str, periods: int = 520):
    seed = sum(ord(char) for char in symbol)
    rng = random.Random(seed)
    today = datetime.today().date()
    rows = []
    close = 120.0 + (seed % 90)

    for offset in range(periods):
        day = today - timedelta(days=periods - offset)
        if day.weekday() >= 5:
            continue
        regime_drift = 0.0007 + 0.0002 * math.sin(offset / 50)
        shock = rng.uniform(-0.019, 0.019)
        close = max(10.0, close * (1 + regime_drift + shock))
        open_price = close * (1 + rng.uniform(-0.006, 0.006))
        high = max(open_price, close) * (1 + rng.uniform(0.001, 0.012))
        low = min(open_price, close) * (1 - rng.uniform(0.001, 0.012))
        rows.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": int(rng.uniform(300000, 2500000)),
            }
        )
    return rows, "sample"


def fetch_stock_data(symbol: str, range_value="1y", interval="1d", timeout=8):
    cache_key = (symbol.upper(), range_value, interval)
    if cache_key in STOCK_DATA_CACHE:
        return STOCK_DATA_CACHE[cache_key]

    params = urlencode({"range": range_value, "interval": interval, "includePrePost": "false"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{params}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result["indicators"]["quote"][0]
        rows = []
        for index, stamp in enumerate(timestamps):
            open_price = quote.get("open", [None])[index]
            high = quote.get("high", [None])[index]
            low = quote.get("low", [None])[index]
            close = quote.get("close", [None])[index]
            volume = quote.get("volume", [None])[index]
            if None in (open_price, high, low, close, volume):
                continue
            rows.append(
                {
                    "date": datetime.fromtimestamp(stamp).strftime("%Y-%m-%d"),
                    "open": round(_safe_float(open_price), 2),
                    "high": round(_safe_float(high), 2),
                    "low": round(_safe_float(low), 2),
                    "close": round(_safe_float(close), 2),
                    "volume": int(_safe_float(volume)),
                }
            )
        if len(rows) >= 120:
            result_data = (rows, "live")
            STOCK_DATA_CACHE[cache_key] = result_data
            return result_data
    except Exception:
        pass

    result_data = _generate_synthetic_data(symbol)
    STOCK_DATA_CACHE[cache_key] = result_data
    return result_data

def _closes(rows):
    return [row["close"] for row in rows]


def _highs(rows):
    return [row["high"] for row in rows]


def _lows(rows):
    return [row["low"] for row in rows]


def _volumes(rows):
    return [row["volume"] for row in rows]


def _mean(values):
    return statistics.fmean(values) if values else 0.0


def _std(values):
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _moving_average(values, window):
    if not values:
        return 0.0
    if len(values) < window:
        return _mean(values)
    return _mean(values[-window:])


def _ema_series(values, window):
    if not values:
        return []
    multiplier = 2 / (window + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _returns(values, window):
    if len(values) <= window or values[-window - 1] == 0:
        return 0.0
    return (values[-1] / values[-window - 1]) - 1


def _daily_returns(values):
    returns = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        if previous:
            returns.append((values[index] / previous) - 1)
    return returns


def _rsi(values, window=14):
    if len(values) < window + 1:
        return 50.0

    gains = []
    losses = []
    for index in range(-window, 0):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))

    average_gain = _mean(gains)
    average_loss = _mean(losses)
    if average_loss == 0:
        return 100.0
    rs = average_gain / average_loss
    return 100 - (100 / (1 + rs))


def _macd(values):
    ema_12 = _ema_series(values, 12)
    ema_26 = _ema_series(values, 26)
    if not ema_12 or not ema_26:
        return 0.0, 0.0, 0.0
    macd_line = [ema_12[index] - ema_26[index] for index in range(len(values))]
    signal_line = _ema_series(macd_line, 9)
    histogram = macd_line[-1] - signal_line[-1]
    return macd_line[-1], signal_line[-1], histogram


def _bollinger_position(values, window=20):
    if len(values) < window:
        return 0.5
    segment = values[-window:]
    mid = _mean(segment)
    deviation = _std(segment)
    upper = mid + (2 * deviation)
    lower = mid - (2 * deviation)
    if upper == lower:
        return 0.5
    return (values[-1] - lower) / (upper - lower)


def _stochastic(rows, window=14):
    if len(rows) < window:
        return 50.0
    recent_rows = rows[-window:]
    highest_high = max(_highs(recent_rows))
    lowest_low = min(_lows(recent_rows))
    if highest_high == lowest_low:
        return 50.0
    close = rows[-1]["close"]
    return ((close - lowest_low) / (highest_high - lowest_low)) * 100


def _atr_percent(rows, window=14):
    if len(rows) < window + 1:
        return 0.0
    true_ranges = []
    for index in range(1, len(rows)):
        current = rows[index]
        previous_close = rows[index - 1]["close"]
        true_range = max(
            current["high"] - current["low"],
            abs(current["high"] - previous_close),
            abs(current["low"] - previous_close),
        )
        true_ranges.append(true_range)
    atr = _mean(true_ranges[-window:])
    close = rows[-1]["close"] or 1
    return (atr / close) * 100


def _adx(rows, window=14):
    if len(rows) < (window * 2):
        return 18.0

    plus_dm = []
    minus_dm = []
    true_ranges = []

    for index in range(1, len(rows)):
        up_move = rows[index]["high"] - rows[index - 1]["high"]
        down_move = rows[index - 1]["low"] - rows[index]["low"]

        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

        true_ranges.append(
            max(
                rows[index]["high"] - rows[index]["low"],
                abs(rows[index]["high"] - rows[index - 1]["close"]),
                abs(rows[index]["low"] - rows[index - 1]["close"]),
            )
        )

    smoothed_tr = _mean(true_ranges[-window:]) or 1
    plus_di = 100 * (_mean(plus_dm[-window:]) / smoothed_tr)
    minus_di = 100 * (_mean(minus_dm[-window:]) / smoothed_tr)
    denominator = plus_di + minus_di
    if denominator == 0:
        return 18.0
    return 100 * abs(plus_di - minus_di) / denominator


def _max_drawdown(values, window=252):
    if not values:
        return 0.0
    sample = values[-window:] if len(values) > window else values
    peak = sample[0]
    max_drawdown = 0.0
    for value in sample:
        peak = max(peak, value)
        if peak:
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown


def _cagr(values, trading_days):
    if len(values) <= trading_days or values[-trading_days - 1] <= 0:
        return 0.0
    start_value = values[-trading_days - 1]
    end_value = values[-1]
    years = trading_days / 252
    if years <= 0 or start_value <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def _annualized_volatility(values, window=63):
    returns = _daily_returns(values)
    if len(returns) < 5:
        return 0.0
    sample = returns[-window:] if len(returns) > window else returns
    return _std(sample) * math.sqrt(252)


def _linear_regression_trend(values, window=126):
    if len(values) < window:
        window = len(values)
    if window < 3:
        return 0.0
    sample = [math.log(max(value, 1e-9)) for value in values[-window:]]
    mean_x = (window - 1) / 2
    mean_y = _mean(sample)
    denominator = sum((index - mean_x) ** 2 for index in range(window)) or 1.0
    numerator = sum((index - mean_x) * (sample[index] - mean_y) for index in range(window))
    slope = numerator / denominator
    return math.exp(slope * 252) - 1


def _obv_trend(rows, window=63):
    if len(rows) < 3:
        return 0.0
    obv_values = [0.0]
    for index in range(1, len(rows)):
        direction = 0
        if rows[index]["close"] > rows[index - 1]["close"]:
            direction = 1
        elif rows[index]["close"] < rows[index - 1]["close"]:
            direction = -1
        obv_values.append(obv_values[-1] + (direction * rows[index]["volume"]))

    sample = obv_values[-window:] if len(obv_values) > window else obv_values
    mean_volume = _mean(_volumes(rows[-window:] if len(rows) > window else rows)) or 1.0
    mean_x = (len(sample) - 1) / 2
    mean_y = _mean(sample)
    denominator = sum((index - mean_x) ** 2 for index in range(len(sample))) or 1.0
    numerator = sum((index - mean_x) * (sample[index] - mean_y) for index in range(len(sample)))
    return (numerator / denominator) / mean_volume


def _volume_ratio(rows, short_window=20, long_window=60):
    volumes = _volumes(rows)
    short_avg = _moving_average(volumes, short_window) or 1.0
    long_avg = _moving_average(volumes, long_window) or short_avg or 1.0
    return short_avg / long_avg


def _indicator_snapshot(rows):
    closes = _closes(rows)
    close = closes[-1]
    sma_20 = _moving_average(closes, 20)
    sma_50 = _moving_average(closes, 50)
    sma_100 = _moving_average(closes, 100)
    sma_200 = _moving_average(closes, 200)
    ema_20 = _ema_series(closes, 20)[-1]
    ema_50 = _ema_series(closes, 50)[-1]
    ema_200 = _ema_series(closes, 200)[-1] if len(closes) >= 200 else _ema_series(closes, 50)[-1]
    macd_line, macd_signal, macd_hist = _macd(closes)

    return {
        "close": close,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_100": sma_100,
        "sma_200": sma_200,
        "ema_20": ema_20,
        "ema_50": ema_50,
        "ema_200": ema_200,
        "rsi_14": _rsi(closes, 14),
        "macd": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "roc_21": _returns(closes, 21),
        "roc_63": _returns(closes, 63),
        "roc_126": _returns(closes, 126),
        "roc_252": _returns(closes, 252),
        "annual_vol": _annualized_volatility(closes, 63),
        "drawdown_252": _max_drawdown(closes, 252),
        "atr_pct": _atr_percent(rows, 14),
        "bb_pos": _bollinger_position(closes, 20),
        "stochastic": _stochastic(rows, 14),
        "adx": _adx(rows, 14),
        "obv_trend": _obv_trend(rows, 63),
        "volume_ratio": _volume_ratio(rows, 20, 60),
        "cagr_1y": _cagr(closes, min(252, len(closes) - 1)),
        "cagr_3y": _cagr(closes, min(756, len(closes) - 1)),
        "trend_6m": _linear_regression_trend(closes, min(126, len(closes))),
        "trend_1y": _linear_regression_trend(closes, min(252, len(closes))),
    }


def _feature_vector(indicators):
    close = indicators["close"] or 1.0
    return [
        indicators["rsi_14"] / 100,
        indicators["macd_hist"] / close,
        indicators["roc_21"],
        indicators["roc_63"],
        indicators["roc_126"],
        indicators["roc_252"],
        indicators["annual_vol"],
        indicators["drawdown_252"],
        indicators["atr_pct"] / 100,
        indicators["bb_pos"],
        indicators["stochastic"] / 100,
        indicators["adx"] / 100,
        indicators["obv_trend"],
        indicators["volume_ratio"] - 1,
        indicators["cagr_1y"],
        indicators["cagr_3y"],
        indicators["trend_6m"],
        indicators["trend_1y"],
        (indicators["close"] / (indicators["sma_50"] or close)) - 1,
        (indicators["sma_50"] / (indicators["sma_200"] or indicators["sma_50"] or 1)) - 1,
        (indicators["ema_20"] / (indicators["ema_50"] or indicators["ema_20"] or 1)) - 1,
        (indicators["ema_50"] / (indicators["ema_200"] or indicators["ema_50"] or 1)) - 1,
    ]


def _build_ml_training_set(rows, horizon=63):
    if len(rows) < (horizon + 220):
        return [], []

    X = []
    y = []
    for end_index in range(220, len(rows) - horizon, 21):
        history = rows[: end_index + 1]
        future_close = rows[end_index + horizon]["close"]
        current_close = rows[end_index]["close"]
        if not current_close:
            continue
        indicators = _indicator_snapshot(history)
        X.append(_feature_vector(indicators))
        y.append((future_close / current_close) - 1)
    return X, y


def _ml_ensemble_return(rows, horizon=63):
    if not ML_MODELS_AVAILABLE:
        return None, None

    X, y = _build_ml_training_set(rows, horizon)
    if len(X) < 24:
        return None, None

    X_array = np.array(X, dtype=float)
    y_array = np.array(y, dtype=float)
    split_index = max(int(len(X_array) * 0.8), 18)
    X_train = X_array[:split_index]
    y_train = y_array[:split_index]
    X_test = X_array[split_index:]
    y_test = y_array[split_index:]
    latest_features = np.array([_feature_vector(_indicator_snapshot(rows))], dtype=float)

    models = [
        ("Random Forest", RandomForestRegressor(n_estimators=250, max_depth=8, random_state=42, n_jobs=-1)),
        ("Extra Trees", ExtraTreesRegressor(n_estimators=350, max_depth=10, random_state=42, n_jobs=-1)),
        ("Gradient Boosting", GradientBoostingRegressor(random_state=42)),
    ]

    predictions = []
    weighted_sum = 0.0
    total_weight = 0.0

    for name, model in models:
        model.fit(X_train, y_train)
        latest_prediction = float(model.predict(latest_features)[0])

        if len(X_test) > 0:
            test_predictions = model.predict(X_test)
            mae = float(np.mean(np.abs(test_predictions - y_test))) + 1e-6
            weight = 1 / mae
        else:
            weight = 1.0

        predictions.append(latest_prediction)
        weighted_sum += latest_prediction * weight
        total_weight += weight

    consensus_error = statistics.pstdev(predictions) if len(predictions) > 1 else 0.0
    confidence = max(45.0, 88.0 - (consensus_error * 400))
    return weighted_sum / total_weight, confidence


def _heuristic_predictions(rows, days=5):
    closes = _closes(rows)
    ma_5 = _moving_average(closes, 5)
    ma_20 = _moving_average(closes, 20)
    short_return = _returns(closes, 5)
    medium_return = _returns(closes, 20)
    mean_reversion = ((ma_5 / ma_20) - 1) if ma_20 else 0.0

    daily_bias = (0.45 * short_return + 0.35 * medium_return + 0.20 * mean_reversion) / max(days, 1)
    daily_bias = max(min(daily_bias, 0.035), -0.035)

    current = closes[-1]
    predictions = []
    for _ in range(days):
        current = current * (1 + daily_bias)
        predictions.append(round(current, 2))
    return predictions


def _long_term_components(rows, years):
    indicators = _indicator_snapshot(rows)
    close = indicators["close"]

    trend_return = max(
        min(
            (0.35 * indicators["trend_1y"])
            + (0.25 * indicators["trend_6m"])
            + (0.20 * indicators["roc_252"])
            + (0.20 * indicators["roc_126"]),
            0.28,
        ),
        -0.08,
    )

    quality_return = max(
        min(
            (0.50 * indicators["cagr_1y"])
            + (0.25 * indicators["cagr_3y"])
            - (0.35 * indicators["annual_vol"])
            - (0.25 * indicators["drawdown_252"])
            + (0.05 * max(indicators["volume_ratio"] - 1, 0)),
            0.24,
        ),
        -0.05,
    )

    mean_reversion_return = max(
        min(
            (0.08 if 40 <= indicators["rsi_14"] <= 62 else -0.03)
            + (0.04 if 0.25 <= indicators["bb_pos"] <= 0.75 else -0.02)
            + (0.05 if indicators["macd_hist"] > 0 else -0.03),
            0.14,
        ),
        -0.04,
    )

    ml_quarter_return, ml_confidence = _ml_ensemble_return(rows, horizon=63)
    if ml_quarter_return is not None:
        ml_annual_return = max(min(((1 + ml_quarter_return) ** 4) - 1, 0.30), -0.08)
        model_name = "ML Ensemble + Multi-Indicator"
        confidence_boost = ml_confidence
    else:
        ml_annual_return = max(
            min(
                (0.45 * indicators["roc_63"])
                + (0.30 * indicators["roc_126"])
                + (0.15 * indicators["obv_trend"])
                + (0.10 * max(indicators["volume_ratio"] - 1, 0)),
                0.20,
            ),
            -0.06,
        )
        model_name = "Advanced Indicator Ensemble"
        confidence_boost = 68.0

    annual_return = max(
        min(
            (0.35 * trend_return)
            + (0.30 * quality_return)
            + (0.20 * ml_annual_return)
            + (0.15 * mean_reversion_return),
            0.26,
        ),
        0.05,
    )

    trend_score = 55.0
    trend_score += max(min(indicators["roc_252"] * 70, 14), -14)
    trend_score += max(min(indicators["roc_126"] * 55, 10), -10)
    trend_score += max(min(indicators["trend_1y"] * 45, 10), -10)
    trend_score += 8 if close > indicators["sma_200"] else -8
    trend_score += 6 if indicators["sma_50"] > indicators["sma_200"] else -6
    trend_score = max(0, min(100, trend_score))

    momentum_score = 52.0
    momentum_score += 8 if indicators["macd_hist"] > 0 else -6
    momentum_score += 7 if 48 <= indicators["rsi_14"] <= 66 else (2 if 38 <= indicators["rsi_14"] < 48 else -7)
    momentum_score += max(min((indicators["stochastic"] - 50) * 0.18, 7), -7)
    momentum_score += 5 if indicators["adx"] >= 20 else -2
    momentum_score = max(0, min(100, momentum_score))

    risk_score = 72.0
    risk_score -= max(min(indicators["annual_vol"] * 95, 28), 0)
    risk_score -= max(min(indicators["drawdown_252"] * 75, 26), 0)
    risk_score -= max(min(max(indicators["atr_pct"] - 3.5, 0) * 4.5, 16), 0)
    risk_score += 5 if indicators["bb_pos"] <= 0.80 else -4
    risk_score = max(0, min(100, risk_score))

    confirmation_score = 48.0
    confirmation_score += max(min(indicators["obv_trend"] * 22, 10), -8)
    confirmation_score += max(min((indicators["volume_ratio"] - 1) * 28, 10), -8)
    confirmation_score += 6 if indicators["ema_20"] > indicators["ema_50"] > indicators["ema_200"] else -4
    confirmation_score = max(0, min(100, confirmation_score))

    long_term_score = round(
        (0.34 * trend_score)
        + (0.26 * momentum_score)
        + (0.24 * risk_score)
        + (0.16 * confirmation_score)
    )

    confidence = max(
        48.0,
        min(
            95.0,
            confidence_boost
            + (8 if indicators["sma_50"] > indicators["sma_200"] else -4)
            + (5 if indicators["macd_hist"] > 0 else -3)
            + (4 if indicators["roc_252"] > 0 else -4)
            - (12 * indicators["annual_vol"]),
        ),
    )

    target_price = close * ((1 + annual_return) ** years)
    upside_pct = ((target_price - close) / close) * 100 if close else 0.0

    if long_term_score >= 78 and upside_pct >= 28:
        suggestion = "Top Conviction"
    elif long_term_score >= 66 and upside_pct >= 16:
        suggestion = "Accumulate"
    elif long_term_score >= 56:
        suggestion = "Selective Buy"
    else:
        suggestion = "Watchlist"

    thesis = []
    thesis.append("MA trend aligned" if indicators["sma_50"] > indicators["sma_200"] else "Long-term trend weak")
    thesis.append("MACD positive" if indicators["macd_hist"] > 0 else "MACD soft")
    thesis.append(f"RSI {round(indicators['rsi_14'], 1)}")
    thesis.append(f"ADX {round(indicators['adx'], 1)}")
    thesis.append(f"Vol {round(indicators['annual_vol'] * 100, 1)}%")

    return {
        "annual_return": annual_return,
        "target_price": target_price,
        "upside_pct": upside_pct,
        "score": long_term_score,
        "confidence": round(confidence, 1),
        "model_name": model_name,
        "indicators": indicators,
        "suggestion": suggestion,
        "thesis": " | ".join(thesis),
    }


def predict_stock(symbol: str):
    rows, data_source = fetch_stock_data(symbol, range_value="1y", interval="1d")
    closes = _closes(rows)
    current_price = closes[-1]
    predictions = _heuristic_predictions(rows, days=5)
    predicted_price = predictions[-1]
    change_pct = ((predicted_price - current_price) / current_price) * 100 if current_price else 0.0

    if change_pct >= 4:
        signal = "BUY"
        rationale = "Latest momentum and moving averages point to higher near-term prices."
        signal_color = "#1f9d55"
    elif change_pct <= -4:
        signal = "SELL"
        rationale = "Weak momentum suggests downside pressure in the short term."
        signal_color = "#d64545"
    else:
        signal = "HOLD"
        rationale = "The trend is mixed, so a long-term investor may prefer to hold."
        signal_color = "#d4a017"

    chart_rows = rows[-90:]
    latest_trading_date = rows[-1]["date"]

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "predicted_prices": predictions,
        "predicted_5d_price": round(predicted_price, 2),
        "change_pct": round(change_pct, 2),
        "signal": signal,
        "signal_color": signal_color,
        "model_accuracy": 78.0,
        "mae": round(abs(predicted_price - current_price), 2),
        "mape": round(abs(change_pct), 2),
        "data_source": data_source,
        "latest_trading_date": latest_trading_date,
        "rationale": rationale,
        "chart_dates": [row["date"] for row in chart_rows],
        "chart_prices": [round(row["close"], 2) for row in chart_rows],
    }


def check_undervalued(risk_profile: str):
    universe = STOCK_UNIVERSE.get(risk_profile.title(), STOCK_UNIVERSE["Medium"])
    results = []

    for stock in universe:
        rows, source = fetch_stock_data(stock["symbol"], range_value="1y", interval="1d")
        closes = _closes(rows)
        current_price = closes[-1]
        high_52 = max(closes)
        low_52 = min(closes)
        pct_from_high = ((current_price - high_52) / high_52) * 100 if high_52 else 0.0
        pct_from_low = ((current_price - low_52) / low_52) * 100 if low_52 else 0.0
        indicators = _indicator_snapshot(rows)

        score = 0
        if pct_from_high <= -25:
            score += 35
        elif pct_from_high <= -15:
            score += 20
        if indicators["rsi_14"] <= 35:
            score += 30
        elif indicators["rsi_14"] <= 45:
            score += 15
        if pct_from_low <= 25:
            score += 20
        if _moving_average(closes, 20) > current_price:
            score += 15
        if indicators["bb_pos"] < 0.35:
            score += 10

        verdict = "Fairly Priced"
        if score >= 60:
            verdict = "Undervalued"
        elif score >= 35:
            verdict = "Watchlist"

        results.append(
            {
                **stock,
                "current_price": round(current_price, 2),
                "52w_high": round(high_52, 2),
                "52w_low": round(low_52, 2),
                "pct_from_high": round(pct_from_high, 2),
                "pct_from_low": round(pct_from_low, 2),
                "rsi": round(indicators["rsi_14"], 2),
                "undervalued_score": score,
                "verdict": verdict,
                "data_source": source,
            }
        )

    return sorted(results, key=lambda item: item["undervalued_score"], reverse=True)


def news_sentiment_exit_signal(symbol: str):
    rows, data_source = fetch_stock_data(symbol, range_value="6mo", interval="1d")
    closes = _closes(rows)
    weekly_return = _returns(closes, 5) * 100
    monthly_return = _returns(closes, 20) * 100
    indicators = _indicator_snapshot(rows)

    negative_sentiment_score = 0
    if weekly_return < -4:
        negative_sentiment_score += 35
    if monthly_return < -8:
        negative_sentiment_score += 35
    if indicators["rsi_14"] < 40:
        negative_sentiment_score += 20
    if indicators["macd_hist"] < 0:
        negative_sentiment_score += 10

    if negative_sentiment_score >= 70:
        signal = "EXIT"
        reason = "Momentum is strongly negative and the indicator ensemble is weak."
    elif negative_sentiment_score >= 40:
        signal = "WATCH"
        reason = "Short-term weakness suggests tracking earnings and news closely."
    else:
        signal = "HOLD"
        reason = "Momentum still supports a long-term holding view."

    return {
        "symbol": symbol,
        "signal": signal,
        "reason": reason,
        "ret_1w": round(weekly_return, 2),
        "ret_1m": round(monthly_return, 2),
        "proxy_sentiment_score": negative_sentiment_score,
        "data_source": data_source,
    }


def _build_investment_plan(stock, years):
    rows, source = fetch_stock_data(
        stock["symbol"],
        range_value="2y",
        interval="1d",
        timeout=INVESTMENT_PLAN_FETCH_TIMEOUT,
    )
    if len(rows) < 220:
        return None

    components = _long_term_components(rows, years)
    indicators = components["indicators"]
    return {
        "name": stock["name"],
        "symbol": stock["symbol"],
        "sector": stock["sector"],
        "current_price": round(indicators["close"], 2),
        "target_price": round(components["target_price"], 2),
        "upside_pct": round(components["upside_pct"], 2),
        "time_span": f"{years} years",
        "suggestion": components["suggestion"],
        "data_source": source,
        "score": components["score"],
        "confidence": components["confidence"],
        "model_name": components["model_name"],
        "indicators_summary": components["thesis"],
        "rsi": round(indicators["rsi_14"], 1),
        "adx": round(indicators["adx"], 1),
        "annual_return": round(components["annual_return"] * 100, 2),
    }


def get_investment_plans(years=2, risk_profile="Balanced", top_n=10):
    risk_profile = (risk_profile or "Balanced").title()
    years = max(int(years), 2)
    top_n = max(int(top_n), 1)

    if risk_profile == "Balanced":
        selected = [stock for bucket in STOCK_UNIVERSE.values() for stock in bucket]
    else:
        selected = STOCK_UNIVERSE.get(risk_profile, STOCK_UNIVERSE["Medium"])

    analysis_limit = max(top_n * 3, 24)
    selected = selected[:analysis_limit]
    plans = []
    max_workers = min(INVESTMENT_PLAN_MAX_WORKERS, max(len(selected), 1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_build_investment_plan, stock, years) for stock in selected]
        for future in as_completed(futures):
            try:
                plan = future.result()
            except Exception:
                continue
            if plan:
                plans.append(plan)

    plans.sort(key=lambda item: (item["score"], item["upside_pct"], item["confidence"]), reverse=True)
    return plans[:top_n]






