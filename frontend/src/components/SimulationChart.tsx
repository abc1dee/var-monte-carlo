import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import type { SimulationPaths } from '../types';

interface Props {
  paths: SimulationPaths;
  initialInvestment: number;
  ticker: string;
  confidenceLevel: number;
}

export default function SimulationChart({ paths, initialInvestment, ticker, confidenceLevel }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;

    const { days, paths: allPaths } = paths;
    const alpha = 1 - confidenceLevel / 100;

    // compute percentile and mean paths
    const meanPath = days.map((_, d) => {
      const vals = allPaths.map(p => p[d]);
      return vals.reduce((a, b) => a + b, 0) / vals.length;
    });

    const pLow = days.map((_, d) => {
      const vals = [...allPaths.map(p => p[d])].sort((a, b) => a - b);
      return vals[Math.floor(vals.length * alpha)] ?? vals[0];
    });

    const p1 = days.map((_, d) => {
      const vals = [...allPaths.map(p => p[d])].sort((a, b) => a - b);
      return vals[Math.floor(vals.length * 0.01)] ?? vals[0];
    });

    // sample paths traces (grey)
    const sampleTraces: Plotly.Data[] = allPaths.slice(0, 100).map((path, i) => ({
      x: days,
      y: path,
      type: 'scatter',
      mode: 'lines',
      line: { color: 'rgba(160,160,160,0.12)', width: 1 },
      showlegend: false,
      hoverinfo: 'skip',
      name: `path_${i}`,
    }));

    const namedTraces: Plotly.Data[] = [
      {
        x: days, y: meanPath, type: 'scatter', mode: 'lines',
        name: 'Mean Path',
        line: { color: '#1a56db', width: 2.5 },
      },
      {
        x: days, y: pLow, type: 'scatter', mode: 'lines',
        name: `${confidenceLevel}th Pctile`,
        line: { color: '#f59e0b', width: 2, dash: 'dashdot' },
      },
      {
        x: days, y: p1, type: 'scatter', mode: 'lines',
        name: '1st Pctile',
        line: { color: '#e02424', width: 2, dash: 'dot' },
      },
      {
        x: [days[0], days[days.length - 1]],
        y: [initialInvestment, initialInvestment],
        type: 'scatter', mode: 'lines',
        name: 'Starting Value',
        line: { color: '#374151', width: 1.5, dash: 'dash' },
      },
    ];

    const layout: Partial<Plotly.Layout> = {
      title: { text: `${ticker} — Monte Carlo Simulation (${allPaths.length} paths, ${days.length - 1} days)`, font: { size: 14, color: '#111827' } },
      xaxis: { title: { text: 'Trading Days Forward' }, gridcolor: '#f3f4f6', zeroline: false },
      yaxis: {
        title: { text: 'Portfolio Value ($)' },
        gridcolor: '#f3f4f6',
        zeroline: false,
        tickformat: '$,.0f',
      },
      legend: { orientation: 'h', y: -0.15 },
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
      margin: { t: 50, r: 20, b: 60, l: 80 },
      hovermode: 'x unified',
    };

    const config: Partial<Plotly.Config> = {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
    };

    Plotly.react(ref.current, [...sampleTraces, ...namedTraces], layout, config);
  }, [paths, initialInvestment, ticker, confidenceLevel]);

  return (
    <section className="chart-section">
      <div ref={ref} style={{ width: '100%', maxWidth: '900px', height: '560px', margin: '0 auto' }} />
    </section>
  );
}
