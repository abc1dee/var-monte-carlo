import { useState } from 'react';
import { runSimulation } from './api/simulate';
import type { SimulateRequest, SimulateResponse } from './types';
import InputForm from './components/InputForm';
import StatsCards from './components/StatsCards';
import VarCards from './components/VarCards';
import SimulationChart from './components/SimulationChart';
import './App.css';

export default function App() {
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [lastReq, setLastReq] = useState<SimulateRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(req: SimulateRequest) {
    setLoading(true);
    setError(null);
    try {
      const data = await runSimulation(req);
      setResult(data);
      setLastReq(req);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Varity</h1>
        <p className="app-subtitle">Bootstrap Monte Carlo · Historical VaR/CVaR · Backtest</p>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <InputForm onSubmit={handleSubmit} loading={loading} />
        </aside>

        <div className="results">
          {error && <div className="error-banner">{error}</div>}

          {!result && !loading && !error && (
            <div className="empty-state">
              <p>Configure parameters and run a simulation to see results.</p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <p>Running simulation...</p>
            </div>
          )}

          {result && lastReq && (
            <>
              <StatsCards stats={result.statistics} ticker={result.ticker} />
              <VarCards
                historicalVar={result.historical_var}
                simulatedVar={result.simulated_var}
                confidenceLevel={lastReq.confidence_level}
                horizonDays={lastReq.horizon_days}
              />
              <SimulationChart
                paths={result.simulation_paths}
                initialInvestment={lastReq.initial_investment}
                ticker={result.ticker}
                confidenceLevel={lastReq.confidence_level}
              />
            </>
          )}
        </div>
      </main>
    </div>
  );
}
