import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { Point, Pose } from '../lab/models';
import { parseReplay, type Replay } from '../lab/data';

export const BASE = import.meta.env.BASE_URL;
export const REPO = 'https://github.com/Kanishk-Rungta/SLAMLab';
export const Navigation = createContext<(path: string) => void>(() => undefined);

export function Link({
  to,
  children,
  className = '',
  ...rest
}: {
  to: string;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  const navigate = useContext(Navigation);
  return (
    <a
      href={to.startsWith('http') ? to : BASE + to.replace(/^\//, '')}
      className={className}
      {...rest}
      onClick={(event) => {
        if (
          !to.startsWith('http') &&
          !event.metaKey &&
          !event.ctrlKey &&
          !event.shiftKey &&
          event.button === 0
        ) {
          event.preventDefault();
          navigate(to);
        }
      }}
    >
      {children}
    </a>
  );
}

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    home: (
      <>
        <path d="m3 10 9-7 9 7v10H3Z" />
        <path d="M9 20v-7h6v7" />
      </>
    ),
    learn: (
      <>
        <path d="M3 4h6l3 3 3-3h6v15h-6l-3 2-3-2H3Z" />
        <path d="M12 7v14" />
      </>
    ),
    lab: (
      <>
        <path d="M9 3h6m-5 0v7l-6 10h16l-6-10V3M7 15h10" />
        <circle cx="11" cy="17" r=".5" />
      </>
    ),
    algorithms: (
      <>
        <circle cx="5" cy="6" r="2" />
        <circle cx="19" cy="6" r="2" />
        <circle cx="12" cy="19" r="2" />
        <path d="M7 6h10M6 8l5 9m7-9-5 9" />
      </>
    ),
    simulation: (
      <>
        <path d="m12 2 9 5v10l-9 5-9-5V7Z" />
        <path d="m3 7 9 5 9-5m-9 5v10" />
      </>
    ),
    studio: (
      <>
        <path d="M3 3v17h18" />
        <path d="m6 15 4-7 4 3 5-6" />
        <circle cx="19" cy="5" r="1" />
      </>
    ),
    chart: (
      <>
        <path d="M3 3v17h18M7 16v-5m5 5V6m5 10v-8" />
      </>
    ),
    docs: (
      <>
        <path d="M5 3h10l4 4v14H5Z" />
        <path d="M14 3v5h5M8 12h8m-8 4h6" />
      </>
    ),
    about: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6m0-10v1" />
      </>
    ),
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    external: (
      <>
        <path d="M14 3h7v7m0-7L10 14" />
        <path d="M10 3H3v18h18v-7" />
      </>
    ),
    play: <path d="m8 4 12 8-12 8Z" />,
    pause: (
      <>
        <path d="M8 4v16M16 4v16" />
      </>
    ),
    reset: (
      <>
        <path d="M4 10a8 8 0 1 1 1 8M4 3v7h7" />
      </>
    ),
    moon: <path d="M20 15A9 9 0 0 1 9 4 9 9 0 1 0 20 15Z" />,
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 6 6" />
      </>
    ),
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    download: (
      <>
        <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4" />
      </>
    ),
    check: <path d="m4 12 5 5L20 6" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.lab}
    </svg>
  );
}

export function Range({
  label,
  value,
  min,
  max,
  step = 0.01,
  unit = '',
  help,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  help?: string;
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div className="range-field">
      <label htmlFor={id}>
        {label}
        <output>
          {value.toFixed(step < 0.01 ? 3 : step < 1 ? 2 : 0)}
          {unit && ' ' + unit}
        </output>
      </label>
      <input
        id={id}
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        aria-describedby={help ? id + '-help' : undefined}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {help && (
        <p className="control-help" id={id + '-help'}>
          {help}
        </p>
      )}
    </div>
  );
}

export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function Stat({
  label,
  value,
  unit,
  detail,
}: {
  label: string;
  value: string | number;
  unit?: string;
  detail?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>
        {value}
        <small>{unit}</small>
      </strong>
      {detail && <p>{detail}</p>}
    </div>
  );
}

export function usePlayback(total: number, initial = 0) {
  const [frame, setFrame] = useState(initial),
    [running, setRunning] = useState(false),
    [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!running) return;
    let previous = 0,
      handle = 0;
    const tick = (now: number) => {
      const dt = previous ? Math.min(0.1, (now - previous) / 1000) : 0;
      previous = now;
      setFrame((current) => {
        const next = current + dt * 15 * speed;
        if (next >= total - 1) {
          setRunning(false);
          return total - 1;
        }
        return next;
      });
      handle = requestAnimationFrame(tick);
    };
    handle = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(handle);
  }, [running, speed, total]);
  return {
    frame: Math.min(total - 1, Math.floor(frame)),
    setFrame,
    running,
    setRunning,
    speed,
    setSpeed,
    reset: () => {
      setRunning(false);
      setFrame(0);
    },
  };
}

export function Playback({
  player,
  total,
  label,
}: {
  player: ReturnType<typeof usePlayback>;
  total: number;
  label?: string;
}) {
  return (
    <div className="playback">
      <button
        className="button small primary"
        onClick={() => {
          if (player.frame >= total - 1) player.setFrame(0);
          player.setRunning(!player.running);
        }}
      >
        <Icon name={player.running ? 'pause' : 'play'} size={16} />
        {player.running ? 'Pause' : 'Play'}
      </button>
      <button className="icon-button" aria-label="Reset playback" onClick={player.reset}>
        <Icon name="reset" size={17} />
      </button>
      <input
        type="range"
        aria-label="Playback position"
        min="0"
        max={total - 1}
        value={player.frame}
        onChange={(e) => {
          player.setRunning(false);
          player.setFrame(Number(e.target.value));
        }}
      />
      <span className="time-label">{label || `${player.frame + 1} / ${total}`}</span>
      <label className="sr-only" htmlFor="playback-speed">
        Playback speed
      </label>
      <select
        id="playback-speed"
        value={player.speed}
        onChange={(e) => player.setSpeed(Number(e.target.value))}
      >
        {[0.5, 1, 2, 4].map((speed) => (
          <option key={speed} value={speed}>
            {speed}×
          </option>
        ))}
      </select>
    </div>
  );
}

export function PathLine({
  points,
  color = 'var(--teal)',
  dashed = false,
  width = 0.04,
}: {
  points: (Pose | Point)[];
  color?: string;
  dashed?: boolean;
  width?: number;
}) {
  return (
    <path
      d={points.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ')}
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={dashed ? '.12 .1' : undefined}
    />
  );
}

export function Robot({
  pose,
  color = 'var(--teal)',
  size = 0.16,
}: {
  pose: Pose;
  color?: string;
  size?: number;
}) {
  return (
    <g transform={`translate(${pose[0]} ${pose[1]}) rotate(${(pose[2] * 180) / Math.PI})`}>
      <circle r={size * 1.7} fill={color} opacity=".1" />
      <path
        d={`M${size * 1.3} 0L${-size} ${size}L${-size * 0.5} 0L${-size} ${-size}Z`}
        fill={color}
        stroke="var(--surface)"
        strokeWidth=".025"
      />
    </g>
  );
}

export function Plot({
  children,
  label,
  bounds = [-4, -4, 4, 4],
  interactive = false,
  className = '',
}: {
  children: ReactNode;
  label: string;
  bounds?: number[];
  interactive?: boolean;
  className?: string;
}) {
  const [zoom, setZoom] = useState(1),
    [pan, setPan] = useState<Point>([0, 0]);
  const drag = useRef<{ x: number; y: number; pan: Point } | null>(null),
    svg = useRef<SVGSVGElement>(null);
  const [xmin, ymin, xmax, ymax] = bounds,
    width = xmax - xmin,
    height = ymax - ymin;
  const id = useId().replaceAll(':', '');
  return (
    <div className={'plot ' + className}>
      <svg
        ref={svg}
        viewBox={`${xmin} ${-ymax} ${width} ${height}`}
        role="img"
        aria-label={label}
        tabIndex={interactive ? 0 : undefined}
        style={{ touchAction: interactive ? 'none' : 'auto' }}
        onPointerDown={(e) => {
          if (!interactive) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          drag.current = { x: e.clientX, y: e.clientY, pan };
        }}
        onPointerMove={(e) => {
          if (!drag.current || !svg.current) return;
          const rect = svg.current.getBoundingClientRect();
          setPan([
            drag.current.pan[0] + ((e.clientX - drag.current.x) / rect.width) * width,
            drag.current.pan[1] - ((e.clientY - drag.current.y) / rect.height) * height,
          ]);
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
        onKeyDown={(e) => {
          if (!interactive) return;
          const shifts: Record<string, Point> = {
            ArrowLeft: [-0.2, 0],
            ArrowRight: [0.2, 0],
            ArrowUp: [0, 0.2],
            ArrowDown: [0, -0.2],
          };
          if (shifts[e.key]) {
            e.preventDefault();
            setPan([pan[0] + shifts[e.key][0], pan[1] + shifts[e.key][1]]);
          }
        }}
      >
        <defs>
          <pattern id={id} width=".5" height=".5" patternUnits="userSpaceOnUse">
            <path d="M.5 0H0V.5" fill="none" stroke="var(--grid)" strokeWidth=".009" />
          </pattern>
        </defs>
        <rect x={xmin} y={-ymax} width={width} height={height} fill="var(--canvas)" />
        <rect x={xmin} y={-ymax} width={width} height={height} fill={`url(#${id})`} />
        <g transform={`scale(1 -1) translate(${pan[0]} ${pan[1]}) scale(${zoom})`}>{children}</g>
      </svg>
      <span className="plot-unit">x / y · metres</span>
      {interactive && (
        <div className="plot-tools">
          <button aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(8, z * 1.3))}>
            +
          </button>
          <button aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(0.4, z / 1.3))}>
            −
          </button>
          <button
            onClick={() => {
              setZoom(1);
              setPan([0, 0]);
            }}
          >
            Fit view
          </button>
        </div>
      )}
    </div>
  );
}

export function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="legend">
      {items.map(([label, color]) => (
        <span key={label}>
          <i style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}

export function useReplay(name = 'landmark-reference') {
  const [data, setData] = useState<Replay | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch(BASE + 'generated/' + name + '.json', { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error('The sample could not be loaded. Try a local replay file.');
        return r.text();
      })
      .then((text) => {
        setData(parseReplay(text));
        setError('');
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => controller.abort();
  }, [name]);
  return { data, error };
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
