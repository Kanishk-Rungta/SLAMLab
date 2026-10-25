import { cloneElement, useState, type ReactElement, type ReactNode } from 'react';
type Snapshot = { settings: string; result: string; graphic: ReactNode; bounds?: number[] };
export function useExperimentComparison(current: Snapshot) {
  const [saved, setSaved] = useState<Snapshot | null>(null);
  const sharedBounds =
    saved?.bounds && current.bounds
      ? [
          Math.min(saved.bounds[0], current.bounds[0]),
          Math.min(saved.bounds[1], current.bounds[1]),
          Math.max(saved.bounds[2], current.bounds[2]),
          Math.max(saved.bounds[3], current.bounds[3]),
        ]
      : undefined;
  return {
    saved: Boolean(saved),
    save: () => setSaved(current),
    panel: saved && (
      <section
        id="experiment-comparison"
        className="panel saved-comparison"
        aria-label="Saved experiment comparison"
      >
        <div className="panel-heading">
          <h2>Before and after</h2>
          <button className="text-link" onClick={() => setSaved(null)}>
            Clear comparison
          </button>
        </div>
        <p className="help">
          The saved example stays fixed while you change the current one. Settings and playback
          moment are recorded below each picture.
          {sharedBounds && ' Both pictures use the same coordinate bounds.'}
        </p>
        <div className="comparison-pair">
          {[
            ['Saved before', saved],
            ['Current', current],
          ].map(([label, snapshot]) => {
            const value = snapshot as Snapshot;
            return (
              <figure key={label as string}>
                <figcaption>
                  <strong>{label as string}</strong>
                  <p>{value.result}</p>
                  <span className="help">{value.settings}</span>
                </figcaption>
                {sharedBounds
                  ? cloneElement(value.graphic as ReactElement<{ bounds: number[] }>, {
                      bounds: sharedBounds,
                    })
                  : value.graphic}
              </figure>
            );
          })}
        </div>
      </section>
    ),
  };
}
export function ExperimentTools({
  examples,
  save,
  saved,
}: {
  examples: { label: string; run: () => void }[];
  save: () => void;
  saved: boolean;
}) {
  return (
    <div className="experiment-tools">
      <span className="eyebrow">ONE-CLICK EXAMPLES</span>
      <div className="example-buttons">
        {examples.map((example) => (
          <button className="button secondary" key={example.label} onClick={example.run}>
            {example.label}
          </button>
        ))}
      </div>
      <button className="text-link" onClick={save}>
        Save current example for comparison
      </button>
      {saved && (
        <p className="help" aria-live="polite">
          Saved. Change the current settings, then{' '}
          <a href="#experiment-comparison">view the comparison</a>.
        </p>
      )}
    </div>
  );
}
