# Value-at-Risk (VaR) Monte Carlo Simulation

This project is a web application that estimates potential investment losses using Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR) computed with Monte Carlo simulations over historical stock data.

## 🚀 Project Overview

The core purpose of this tool is to provide risk management insights for single-asset portfolios. It fetches real-time historical market data, runs thousands of simulation paths to project future prices, and statistically determines the maximum expected loss at a given confidence level.

### Key Features
- **Real Market Data:** Integrates with Yahoo Finance (`yfinance`) to fetch live historical adjusted close prices.
- **Robust Simulation Engine:** Uses **Bootstrap Resampling** from empirical historical returns, which preserves real-world fat tails and skewness, providing a more realistic risk assessment than standard Normal distribution models (like GBM).
- **Comprehensive Risk Metrics:** Calculates both Historical VaR/CVaR and Simulated VaR/CVaR.
- **RESTful API:** Clean, documented FastAPI endpoints for seamless frontend integration.

## 🏗️ Architecture

- **Backend:** Python 3.12+, FastAPI, Uvicorn (ASGI)
- **Data & Math:** `numpy`, `pandas`, `scipy`, `yfinance`
- **Validation:** Pydantic v2
- **Frontend (TBD):** React + Vite + TypeScript

## 📂 Key Documentation

- **API Contracts:** Check `docs/api-contracts.md` for the exact JSON request/response shapes required by the frontend and backend.
- **Quant Logic PoC:** Check the `notebooks/` folder for the original Jupyter notebooks validating the Bootstrap Monte Carlo methodology.

## 💻 Running the Backend Locally

### 1. Setup Virtual Environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Mac/Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Server
```bash
uvicorn main:app --reload
```
The server will start at `http://localhost:8000`.

### 4. Interactive API Documentation (Swagger UI)
Once the server is running, navigate to:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

From there, you can test all endpoints, including the main simulation engine (`POST /api/simulate`).

## 🔄 API Endpoints Summary

- `GET /api/health`: Lightweight health check.
- `GET /api/tickers`: Returns a list of predefined supported tickers.
- `GET /api/validate-ticker/{symbol}`: Validates if a custom ticker symbol exists in Yahoo Finance.
- `POST /api/simulate`: The main Monte Carlo simulation engine. Accepts ticker, horizon days, investment amount, and simulation parameters.

---
*Developed for internal portfolio risk assessment.*