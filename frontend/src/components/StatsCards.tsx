import type { Statistics } from '../types';

interface Props {
  stats: Statistics;
  ticker: string;
}

function pct(n: number, decimals = 4) {
  return (n * 100).toFixed(decimals) + '%';
}

function fmt(n: number, decimals = 4) {
  return n.toFixed(decimals);
}

export default function StatsCards({ stats, ticker }: Props) {
  const cards = [
    { label: 'Mean Daily Return', value: pct(stats.mean_daily_return), positive: stats.mean_daily_return >= 0 },
    { label: 'Daily Volatility (σ)', value: pct(stats.std_daily_return), positive: null },
    { label: 'Skewness', value: fmt(stats.skewness), positive: stats.skewness >= 0 },
    { label: 'Excess Kurtosis', value: fmt(stats.kurtosis), positive: null },
  ];

  return (
    <section className="cards-section">
      <h3 className="section-title">{ticker} — Return Statistics</h3>
      <div className="cards-grid">
        {cards.map(c => (
          <div key={c.label} className="card">
            <span className="card-label">{c.label}</span>
            <span className={`card-value ${c.positive === true ? 'positive' : c.positive === false ? 'negative' : ''}`}>
              {c.value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
