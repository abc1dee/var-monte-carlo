"""
Pydantic v2 Request Models

Models:
- SimulationRequest: Input for POST /api/simulate
  - ticker (str, required)
  - horizon_days (int, required, 1-252)
  - confidence_level (float, optional, default 95.0)
  - num_simulations (int, optional, default 10000)
  - initial_investment (float, optional, default 100000)
"""

# TODO: Generate with Claude Web — Prompt 2 (Pydantic Schemas)
# See developer_workflow_guide.md Section 3.3, Prompt 2
