import type { MetricReport } from '../lab/data';
export function MetricComparison({ metrics }: { metrics: MetricReport }) {
  const baseline = metrics.odometry_baseline_ate_m?.rmse;
  if (baseline == null) return null;
  const estimate = metrics.ate_m.rmse,
    maximum = Math.max(baseline, estimate, 0.000001);
  return (
    <section className="panel metric-comparison" aria-label="Position error comparison">
      <div>
        <p className="eyebrow">WHAT DO THE NUMBERS MEAN?</p>
        <h2>How close was the estimated path?</h2>
        <p>
          Position error compares the robot’s estimate with separately recorded reference positions.
          Smaller bars mean a closer fit.
        </p>
      </div>
      <div className="comparison-bars">
        {[
          ['Wheel motion only', baseline],
          ['With landmark corrections', estimate],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{((value as number) * 100).toFixed(2)} cm</strong>
            <div className="comparison-track">
              <i style={{ width: ((value as number) / maximum) * 100 + '%' }} />
            </div>
          </div>
        ))}
        <p className="help">
          Position ATE, expressed as root mean square error (RMSE). Same wheel inputs and evaluation
          frame. This comparison applies to the selected recording.
        </p>
      </div>
    </section>
  );
}
