export interface SimulateRequest {
  ticker: string;
  horizon_days: number;
  confidence_level: number;
  num_simulations: number;
  initial_investment: number;
}

export interface Statistics {
  mean_daily_return: number;
  std_daily_return: number;
  skewness: number;
  kurtosis: number;
}

export interface VarResult {
  var_pct: number;
  var_dollar: number;
}

export interface SimulationPaths {
  sample_count: number;
  days: number[];
  paths: number[][];
}

export interface SimulateResponse {
  ticker: string;
  statistics: Statistics;
  historical_var: VarResult;
  simulated_var: VarResult;
  simulation_paths: SimulationPaths;
}
