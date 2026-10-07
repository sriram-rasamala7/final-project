# Profit Path: AIML Based Stock Market Investment Guide

Profit Path is a Flask-based mini investment assistant for long-term investors. It combines risk profiling, stock prediction, undervalued stock screening, SIP planning, portfolio allocation, mutual fund suggestions, and a simple exit signal.

## Folder Structure

```text
P/
|-- app.py
|-- model.py
|-- predictor.py
|-- risk_profile.py
|-- sip_calculator.py
|-- portfolio.py
|-- requirements.txt
|-- README.md
|-- data/
|   |-- mutual_funds.csv
|-- artifacts/
|   `-- (generated model files)
|-- static/
|   |-- app.js
|   `-- style.css
`-- templates/
    `-- index.html
```

## Features

- Stock price prediction using Random Forest and `yfinance`
- Undervalued stock recommendation using RSI and price-position logic
- Risk profiling into Low, Medium, and High
- SIP calculator based on salary, goal, and time horizon
- Portfolio allocation suggestion based on risk profile
- Mutual fund suggestion from a static sample dataset
- News sentiment based exit signal using a simple momentum proxy
- Long-term investment focused recommendations

## Sample Datasets

- `data/mutual_funds.csv`: Sample mutual fund recommendation dataset

## Run Instructions

1. Open a terminal in `c:\Users\shrey\Codes\P`
2. Create a virtual environment:

```powershell
python -m venv .venv
```

3. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Start the Flask app:

```powershell
python app.py
```

6. Open `http://127.0.0.1:5000`

## API Endpoints

- `POST /api/risk-profile`
- `POST /api/predict`
- `POST /api/undervalued`
- `POST /api/sip`
- `POST /api/portfolio`
- `POST /api/exit-signal`
- `POST /api/analyze`

## Notes

- If live Yahoo Finance data is unavailable, the app falls back to generated sample market data so the project still works.
- Trained model files are saved in `artifacts/`.
- This project is for academic/demo use only and not financial advice.
