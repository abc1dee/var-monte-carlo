import type { SimulateRequest, SimulateResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export async function runSimulation(req: SimulateRequest): Promise<SimulateResponse> {
  if (USE_MOCK) return mockSimulation(req);

  const res = await fetch(`${BASE_URL}/api/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Server error ${res.status}`);
  }

  return res.json();
}

// ── mock ─────────────────────────────────────────────────────────────────────
// Remove VITE_USE_MOCK=true from .env.development once the backend is live.

function normalRandom(): number {
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function mockSimulation(req: SimulateRequest): SimulateResponse {
  const mu = 0.00085;
  const sigma = 0.0167;
  const days = Array.from({ length: req.horizon_days + 1 }, (_, i) => i);
  const sampleCount = Math.min(req.num_simulations, 150);
  const paths: number[][] = [];

  for (let s = 0; s < sampleCount; s++) {
    const path = [req.initial_investment];
    for (let d = 1; d <= req.horizon_days; d++) {
      const r = mu + sigma * normalRandom();
      path.push(path[d - 1] * (1 + r));
    }
    paths.push(path);
  }

  const alpha = 1 - req.confidence_level / 100;
  const finals = paths.map(p => (p[p.length - 1] - req.initial_investment) / req.initial_investment);
  const sorted = [...finals].sort((a, b) => a - b);
  const varIdx = Math.floor(sorted.length * alpha);
  const varPct = sorted[varIdx];

  return {
    ticker: req.ticker.toUpperCase(),
    statistics: { mean_daily_return: mu, std_daily_return: sigma, skewness: -0.34, kurtosis: 4.21 },
    historical_var: { var_pct: varPct * 0.92, var_dollar: req.initial_investment * varPct * 0.92 },
    simulated_var: { var_pct: varPct, var_dollar: req.initial_investment * varPct },
    simulation_paths: { sample_count: sampleCount, days, paths },
  };
}
