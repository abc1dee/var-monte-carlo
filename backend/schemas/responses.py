"""
Pydantic v2 Response Models

Models:
- SimulationResponse: Full response for POST /api/simulate
- Statistics: mean, std, annualized return/vol, skewness, kurtosis
- HistoricalVarResult: var_pct, var_dollar
- SimulatedVarResult: var_pct, var_dollar, cvar_pct, cvar_dollar
- SimulationPaths: sample_count, days[], paths[][]
- Histogram: bin_edges[], counts[]
- TickerInfo: symbol, name, sector
- HealthResponse: status, version
- ErrorResponse: detail, error_code
"""

# TODO: Generate with Claude Web — Prompt 2 (Pydantic Schemas)
# See developer_workflow_guide.md Section 3.3, Prompt 2
