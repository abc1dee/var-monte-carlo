import type { VarResult } from '../types';

interface Props {
  historicalVar: VarResult;
  simulatedVar: VarResult;
  confidenceLevel: number;
  horizonDays: number;
}

function dollar(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}

function pct(n: number) {
  return (n * 100).toFixed(2) + '%';
}

interface VarCardProps {
  title: string;
  subtitle: string;
  varPct: number;
  varDollar: number;
}

function VarCard({ title, subtitle, varPct, varDollar }: VarCardProps) {
  return (
    <div className="var-card">
      <div className="var-card-header">
        <span className="var-card-title">{title}</span>
        <span className="var-card-sub">{subtitle}</span>
      </div>
      <div className="var-card-body">
        <div className="var-metric">
          <span className="var-metric-label">VaR %</span>
          <span className="var-metric-value negative">{pct(varPct)}</span>
        </div>
        <div className="var-metric">
          <span className="var-metric-label">VaR $</span>
          <span className="var-metric-value negative">{dollar(varDollar)}</span>
        </div>
      </div>
    </div>
  );
}

export default function VarCards({ historicalVar, simulatedVar, confidenceLevel, horizonDays }: Props) {
  return (
    <section className="cards-section">
      <h3 className="section-title">Value at Risk — {confidenceLevel}% Confidence</h3>
      <div className="var-grid">
        <VarCard
          title="Historical VaR"
          subtitle="Based on observed returns"
          varPct={historicalVar.var_pct}
          varDollar={historicalVar.var_dollar}
        />
        <VarCard
          title="Simulated VaR"
          subtitle={`Bootstrap MC · ${horizonDays}-day horizon`}
          varPct={simulatedVar.var_pct}
          varDollar={simulatedVar.var_dollar}
        />
      </div>
    </section>
  );
}
