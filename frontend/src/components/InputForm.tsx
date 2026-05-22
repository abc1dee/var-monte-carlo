import { useState } from 'react';
import type { SimulateRequest } from '../types';

interface Props {
  onSubmit: (req: SimulateRequest) => void;
  loading: boolean;
}

const CONFIDENCE_OPTIONS = [90, 95, 99];
const SIM_OPTIONS = [
  { label: '5,000 (fast)', value: 5000 },
  { label: '10,000 (balanced)', value: 10000 },
  { label: '50,000 (precise)', value: 50000 },
  { label: '100,000 (slow)', value: 100000 },
];

export default function InputForm({ onSubmit, loading }: Props) {
  const [ticker, setTicker] = useState('SPY');
  const [horizonDays, setHorizonDays] = useState(21);
  const [confidenceLevel, setConfidenceLevel] = useState(95);
  const [numSimulations, setNumSimulations] = useState(10000);
  const [initialInvestment, setInitialInvestment] = useState(100000);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({ ticker, horizon_days: horizonDays, confidence_level: confidenceLevel, num_simulations: numSimulations, initial_investment: initialInvestment });
  }

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label>Stock Ticker</label>
        <input
          type="text"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="e.g. AAPL, SPY"
          required
          maxLength={10}
        />
        <span className="hint">Yahoo Finance symbol</span>
      </div>

      <div className="form-group">
        <label>Forecast Horizon</label>
        <div className="slider-row">
          <input
            type="range"
            min={5}
            max={252}
            step={1}
            value={horizonDays}
            onChange={e => setHorizonDays(Number(e.target.value))}
          />
          <span className="slider-value">{horizonDays}d</span>
        </div>
        <span className="hint">Trading days ahead</span>
      </div>

      <div className="form-group">
        <label>Confidence Level</label>
        <div className="button-group">
          {CONFIDENCE_OPTIONS.map(c => (
            <button
              key={c}
              type="button"
              className={confidenceLevel === c ? 'btn-option active' : 'btn-option'}
              onClick={() => setConfidenceLevel(c)}
            >
              {c}%
            </button>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label>Simulations</label>
        <select value={numSimulations} onChange={e => setNumSimulations(Number(e.target.value))}>
          {SIM_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label>Initial Investment ($)</label>
        <input
          type="number"
          value={initialInvestment}
          onChange={e => setInitialInvestment(Number(e.target.value))}
          min={1000}
          step={1000}
          required
        />
      </div>

      <button type="submit" className="btn-run" disabled={loading}>
        {loading ? 'Running...' : 'Run Simulation'}
      </button>
    </form>
  );
}
