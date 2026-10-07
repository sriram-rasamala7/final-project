from flask import Flask, jsonify, render_template, request

from portfolio import get_ipo_analysis, get_portfolio_suggestion, get_stock_options, get_top_sip_funds
from predictor import (
    check_undervalued,
    get_investment_plans,
    news_sentiment_exit_signal,
    predict_stock,
    resolve_stock_input,
)
from risk_profile import get_risk_profile
from sip_calculator import calculate_sip, get_sip_milestones

app = Flask(__name__)


def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/risk")
def risk_page():
    return render_template("risk.html")


@app.route("/predict")
def predict_page():
    return render_template("predict.html", stock_names=[stock["name"] for stock in get_stock_options()])


@app.route("/sip")
def sip_page():
    return render_template("sip.html")


@app.route("/portfolio")
def portfolio_page():
    return render_template("portfolio.html")


@app.route("/ipo")
def ipo_page():
    return render_template("ipo.html")


@app.route("/plans")
def plans_page():
    return render_template("plans.html")


@app.route("/api/health")
def health():
    return jsonify({"success": True, "message": "Profit Path API is running"})


@app.route("/api/stocks")
def api_stocks():
    return jsonify({"success": True, "data": get_stock_options()})


@app.route("/api/risk-profile", methods=["POST"])
def api_risk_profile():
    payload = request.get_json(silent=True) or {}
    try:
        result = get_risk_profile(
            age=int(payload["age"]),
            income=float(payload["income"]),
            investment_horizon=int(payload["horizon"]),
            risk_tolerance_score=int(payload["tolerance"]),
        )
        return jsonify({"success": True, "data": result})
    except KeyError as exc:
        return error_response(f"Missing field: {exc.args[0]}")
    except ValueError as exc:
        return error_response(str(exc))


@app.route("/api/sip", methods=["POST"])
def api_sip():
    payload = request.get_json(silent=True) or {}
    try:
        result = calculate_sip(
            monthly_salary=float(payload["salary"]),
            goal_amount=float(payload["goal"]),
            years=int(payload["years"]),
            expected_return_pct=float(payload.get("return_pct", 12.0)),
        )
        result["milestones"] = get_sip_milestones(
            monthly_sip=result["monthly_sip"],
            expected_return_pct=result["expected_return_pct"],
            years=result["years"],
        )
        result["recommended_funds"] = get_top_sip_funds()
        return jsonify({"success": True, "data": result})
    except KeyError as exc:
        return error_response(f"Missing field: {exc.args[0]}")
    except ValueError as exc:
        return error_response(str(exc))


@app.route("/api/predict", methods=["POST"])
def api_predict():
    payload = request.get_json(silent=True) or {}
    symbol = resolve_stock_input(payload.get("stock_name") or payload.get("symbol") or "Reliance Industries")
    try:
        return jsonify({"success": True, "data": predict_stock(symbol)})
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        return error_response(f"Prediction failed: {exc}", 500)


@app.route("/api/undervalued", methods=["POST"])
def api_undervalued():
    payload = request.get_json(silent=True) or {}
    risk_profile = str(payload.get("risk_profile", "Medium")).title()
    try:
        return jsonify({"success": True, "data": check_undervalued(risk_profile)})
    except Exception as exc:
        return error_response(f"Undervalued scan failed: {exc}", 500)


@app.route("/api/portfolio", methods=["POST"])
def api_portfolio():
    payload = request.get_json(silent=True) or {}
    try:
        result = get_portfolio_suggestion(
            risk_profile=str(payload["risk_profile"]).title(),
            investment_amount=float(payload["amount"]),
        )
        return jsonify({"success": True, "data": result})
    except KeyError as exc:
        return error_response(f"Missing field: {exc.args[0]}")
    except ValueError as exc:
        return error_response(str(exc))


@app.route("/api/ipo")
def api_ipo():
    try:
        return jsonify({"success": True, "data": get_ipo_analysis()})
    except Exception as exc:
        return error_response(f"IPO data loading failed: {exc}", 500)


@app.route("/api/investment-plans", methods=["POST"])
def api_investment_plans():
    payload = request.get_json(silent=True) or {}
    try:
        years = int(payload.get("years", 2))
        risk_profile = str(payload.get("risk_profile", "Balanced")).title()
        top_n = int(payload.get("top_n", 10))
        return jsonify({"success": True, "data": get_investment_plans(years=years, risk_profile=risk_profile, top_n=top_n)})
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        return error_response(f"Investment plan generation failed: {exc}", 500)


@app.route("/api/exit-signal", methods=["POST"])
def api_exit_signal():
    payload = request.get_json(silent=True) or {}
    symbol = resolve_stock_input(payload.get("stock_name") or payload.get("symbol") or "Reliance Industries")
    try:
        return jsonify({"success": True, "data": news_sentiment_exit_signal(symbol)})
    except Exception as exc:
        return error_response(f"Exit signal failed: {exc}", 500)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    payload = request.get_json(silent=True) or {}
    try:
        risk_result = get_risk_profile(
            age=int(payload["age"]),
            income=float(payload["income"]),
            investment_horizon=int(payload["horizon"]),
            risk_tolerance_score=int(payload["tolerance"]),
        )
        prediction = predict_stock(resolve_stock_input(payload.get("stock_name") or payload.get("symbol")))
        portfolio = get_portfolio_suggestion(
            risk_profile=risk_result["profile"],
            investment_amount=float(payload["investment_amount"]),
        )
        undervalued = check_undervalued(risk_result["profile"])[:3]
        return jsonify(
            {
                "success": True,
                "data": {
                    "risk_profile": risk_result,
                    "prediction": prediction,
                    "portfolio": portfolio,
                    "recommendations": undervalued,
                },
            }
        )
    except KeyError as exc:
        return error_response(f"Missing field: {exc.args[0]}")
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        return error_response(f"Analysis failed: {exc}", 500)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

