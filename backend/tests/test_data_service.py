"""
Data Service Unit Tests

Tests:
- fetch_historical_data with known ticker (AAPL) → valid DataFrame
- preprocess_data produces correct log returns shape
- Error handling for invalid ticker → raises InvalidTickerError
- Error handling for network failure → raises DataFetchError
"""

# TODO: Generate with Claude Web — Prompt 6 (Tests)
# See developer_workflow_guide.md Section 3.3, Prompt 6
