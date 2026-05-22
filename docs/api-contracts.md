# API Contracts — Shared Source of Truth

> **Status:** Draft v1 — Needs review by Backend + Frontend  
> **Last Updated:** 2026-05-21  
> **Owned By:** Backend Developer (maintains), Frontend Developer (co-reviews)

> [!IMPORTANT]
> This file is the **binding agreement** between Frontend and Backend. Both sides build to these exact JSON shapes.  
> **If you need to change anything here, notify the other developer first.**

---

## How to Use This Document

- **Backend Developer:** Your Pydantic response models must produce JSON matching these schemas exactly.
- **Frontend Developer:** Your TypeScript interfaces (`src/types/api.ts`) must match these schemas exactly.
- **Change Process:** Propose change → both agree → update this file → both update code → commit together.

---

## Base URL

| Environment | URL |
|:---|:---|
| Local Development | `http://localhost:8000` |
| Production (Render) | TBD — will be added when deployed |

---

## 1. `GET /api/health` — Health Check

**Description:** Simple health check to verify the backend is running.

**Request:** No parameters.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 2. `GET /api/tickers` — List Available Tickers

**Description:** Returns the list of predefined stock tickers available for selection.

**Request:** No parameters.

**Response (200 OK):**
```json
{
  "tickers": [
    { "symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology" },
    { "symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Technology" },
    { "symbol": "SPY", "name": "S&P 500 ETF", "sector": "Index Fund" },
    { "symbol": "TSLA", "name": "Tesla Inc.", "sector": "Automotive" },
    { "symbol": "MSFT", "name": "Microsoft Corp.", "sector": "Technology" },
    { "symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology" }
  ]
}
```

**TypeScript Type:**
```typescript
interface TickerInfo {
  symbol: string;
  name: string;
  sector: string;
}

interface TickersResponse {
  tickers: TickerInfo[];
}
```

---

## 3. `GET /api/validate-ticker/{symbol}` — Validate Custom Ticker

**Description:** Checks if a user-typed ticker symbol is valid in Yahoo Finance.

**Request:** Path parameter `symbol` (string).

**Response (200 OK):**
```json
{
  "valid": true,
  "symbol": "NVDA"
}
```

**Response (200 OK — invalid ticker):**
```json
{
  "valid": false,
  "symbol": "XYZFAKE"
}
```

**TypeScript Type:**
```typescript
interface ValidateTickerResponse {
  valid: boolean;
  symbol: string;
}
```

---

## 4. `POST /api/simulate` — Run Monte Carlo Simulation

**Description:** The main endpoint. Fetches historical data, runs the simulation, and returns results.

### Request Body

```json
{
  "ticker": "AAPL",
  "horizon_days": 30,
  "confidence_level": 95,
  "num_simulations": 10000,
  "initial_investment": 100000
}
```

| Field | Type | Required | Default | Validation |
|:---|:---|:---|:---|:---|
| `ticker` | `string` | ✅ | — | Predefined ticker OR valid yfinance symbol |
| `horizon_days` | `integer` | ✅ | — | 1 ≤ value ≤ 252 |
| `confidence_level` | `float` | ❌ | `95.0` | 80 ≤ value ≤ 99.9 |
| `num_simulations` | `integer` | ❌ | `10000` | 100 ≤ value ≤ 100,000 |
| `initial_investment` | `float` | ❌ | `100000` | value > 0 |

**TypeScript Type:**
```typescript
interface SimulationRequest {
  ticker: string;
  horizon_days: number;
  confidence_level?: number;   // default 95.0
  num_simulations?: number;    // default 10000
  initial_investment?: number; // default 100000
}
```

### Response Body (200 OK)

```json
{
  "ticker": "AAPL",
  "period": "1y",
  "horizon_days": 30,
  "confidence_level": 95,
  "num_simulations": 10000,
  "initial_investment": 100000,
  "current_price": 198.45,

  "statistics": {
    "mean_daily_return": 0.00085,
    "std_daily_return": 0.0167,
    "annualized_return": 0.2142,
    "annualized_volatility": 0.2651,
    "skewness": -0.34,
    "kurtosis": 4.21
  },

  "historical_var": {
    "var_pct": -0.0312,
    "var_dollar": -3120.00
  },

  "simulated_var": {
    "var_pct": -0.0487,
    "var_dollar": -4870.00,
    "cvar_pct": -0.0723,
    "cvar_dollar": -7230.00
  },

  "simulation_paths": {
    "sample_count": 100,
    "days": [0, 1, 2, 3, "...up to horizon_days"],
    "paths": [
      [100000, 100234, 99870, "...values for each day"],
      [100000, 99812, 100456, "...values for each day"],
      "...100 sampled paths total"
    ]
  },

  "final_values_histogram": {
    "bin_edges": [85000, 87000, 89000, "..."],
    "counts": [12, 34, 67, "..."]
  }
}
```

> **Note:** Only 100 sampled paths are returned (not all 10,000) to keep the payload small (~200KB). The VaR/CVaR calculations use all simulations.

**TypeScript Types:**
```typescript
interface Statistics {
  mean_daily_return: number;
  std_daily_return: number;
  annualized_return: number;
  annualized_volatility: number;
  skewness: number;
  kurtosis: number;
}

interface HistoricalVarResult {
  var_pct: number;
  var_dollar: number;
}

interface SimulatedVarResult {
  var_pct: number;
  var_dollar: number;
  cvar_pct: number;
  cvar_dollar: number;
}

interface SimulationPaths {
  sample_count: number;
  days: number[];
  paths: number[][];
}

interface Histogram {
  bin_edges: number[];
  counts: number[];
}

interface SimulationResponse {
  ticker: string;
  period: string;
  horizon_days: number;
  confidence_level: number;
  num_simulations: number;
  initial_investment: number;
  current_price: number;
  statistics: Statistics;
  historical_var: HistoricalVarResult;
  simulated_var: SimulatedVarResult;
  simulation_paths: SimulationPaths;
  final_values_histogram: Histogram;
}
```

---

## 5. Error Responses

All errors follow this shape:

```json
{
  "detail": "Ticker 'XYZ' is not a valid stock symbol.",
  "error_code": "INVALID_TICKER"
}
```

| HTTP Status | When | Error Code |
|:---|:---|:---|
| `400` | Invalid input (passes type check but fails business logic) | `INVALID_TICKER`, `INVALID_PARAMS` |
| `422` | Pydantic validation failure (auto-generated by FastAPI) | *(FastAPI default format)* |
| `500` | Unexpected server error | `INTERNAL_ERROR` |
| `503` | yfinance API is unreachable | `DATA_SOURCE_UNAVAILABLE` |

**TypeScript Type:**
```typescript
interface ErrorResponse {
  detail: string;
  error_code: string;
}
```

---

## 6. Quant Engine Interface Contract

This section defines the interface between the Backend and the Quant Developer's `.py` module.

**Function Signature:**
```python
def run_simulation(
    log_returns: np.ndarray,
    num_simulations: int,
    horizon_days: int,
    confidence_level: float,
    initial_investment: float
) -> dict
```

**Input Parameters:**

| Parameter | Type | Description |
|:---|:---|:---|
| `log_returns` | `np.ndarray` | 1D array of historical log returns (preprocessed, no NaN) |
| `num_simulations` | `int` | Number of Monte Carlo paths to generate |
| `horizon_days` | `int` | Number of trading days to simulate forward |
| `confidence_level` | `float` | VaR confidence level (e.g., 95.0) |
| `initial_investment` | `float` | Starting portfolio value in USD |

**Return Value:** A Python `dict` with the exact structure matching the `statistics`, `historical_var`, `simulated_var`, `simulation_paths`, and `final_values_histogram` fields from the `/api/simulate` response above.

> **Quant Developer:** You can use any simulation model internally (GBM, GARCH, Student-t, etc.). The backend only cares that this function accepts these inputs and returns this dict structure.

---

## Changelog

| Date | Author | Change |
|:---|:---|:---|
| 2026-05-21 | Backend Dev | Initial draft based on implementation plan |
| | | |
