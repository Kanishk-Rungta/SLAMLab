export function MissionDiagram({
  step,
  compact = false,
  label,
}: {
  step: number;
  compact?: boolean;
  label?: string;
}) {
  const actual = step === 0 ? [70, 125] : [135, 115];
  const estimate = step === 1 ? [165, 97] : actual;
  const landmarks = [
    [200, 55],
    [195, 180],
    [65, 180],
  ];
  const onMap = ([x, y]: number[]) => [260 + (x - 25) * 0.62, 58 + (y - 20) * 0.62];
  const mapStart = onMap([70, 125]),
    mapRobot = onMap(estimate);
  const mapped = (index: number) => {
    const point = onMap(landmarks[index]);
    return [
      point[0] + (step === 1 && index > 0 ? (estimate[0] - actual[0]) * 0.62 : 0),
      point[1] + (step === 1 && index > 0 ? (estimate[1] - actual[1]) * 0.62 : 0),
    ];
  };
  return (
    <svg
      className={'concept-diagram mission-diagram' + (compact ? ' compact' : '')}
      viewBox="0 0 420 260"
      role="img"
      aria-hidden={compact || undefined}
      aria-label={
        label ||
        'A robot observes a corner, moves with an uncertain estimate, and recognises the corner to correct its position and map'
      }
    >
      <title>One room, a moving robot, and the map it is building</title>
      <rect width="420" height="260" rx="14" fill="var(--canvas)" />
      <text x="25" y="20" className="diagram-section-label">
        THE ROOM
      </text>
      <text x="263" y="20" className="diagram-section-label">
        ITS GROWING MAP
      </text>
      <rect
        x="25"
        y="34"
        width="205"
        height="184"
        rx="12"
        fill="var(--surface)"
        stroke="var(--line)"
        strokeWidth="2"
      />
      <path
        d="M45 35v10h48V35M158 35v10h48V35M26 191h12v-28H26"
        fill="var(--soft)"
        stroke="var(--slate)"
        strokeWidth="2"
      />
      <rect
        x="251"
        y="34"
        width="145"
        height="184"
        rx="12"
        fill="var(--soft)"
        stroke="var(--line)"
      />
      {[70, 100, 130, 160, 190].map((y) => (
        <path key={y} d={`M262 ${y}H385`} stroke="var(--line)" strokeDasharray="2 5" />
      ))}
      {landmarks.map(([x, y], index) => (
        <g key={index}>
          <path
            d={`M${x - 7} ${y + 7}V${y - 7}H${x + 7}`}
            fill="none"
            stroke="var(--slate)"
            strokeWidth="3"
          />
          {index === 0 && (
            <text x="160" y="77">
              Corner A
            </text>
          )}
        </g>
      ))}
      {step > 0 && (
        <>
          <path
            d={`M70 125L${actual.join(' ')}`}
            fill="none"
            stroke="var(--slate)"
            strokeWidth="3"
            strokeDasharray="5 4"
          />
          <path
            d={`M70 125L${estimate.join(' ')}`}
            fill="none"
            stroke="var(--teal)"
            strokeWidth="3"
          />
          <circle cx={actual[0]} cy={actual[1]} r="12" fill="var(--slate)" opacity=".28" />
        </>
      )}
      {step === 1 && (
        <>
          <path
            d={`M${actual.join(' ')}L${estimate.join(' ')}`}
            stroke="var(--orange)"
            strokeWidth="2"
            strokeDasharray="4 4"
          />
          <text x="91" y="143">
            Actual
          </text>
          <text x="166" y="123">
            Estimate
          </text>
        </>
      )}
      {step === 2 && (
        <>
          <circle cx="165" cy="97" r="12" fill="none" stroke="var(--slate)" strokeDasharray="4 4" />
          <path d="M164 108Q160 126 145 119" fill="none" stroke="var(--teal)" strokeWidth="2.5" />
          <path d="M145 119l9 -2 -3 8" fill="none" stroke="var(--teal)" strokeWidth="2.5" />
        </>
      )}
      <path
        d={`M${actual.join(' ')}L200 55`}
        stroke="var(--orange)"
        strokeWidth={step === 2 ? 3 : 2}
        strokeDasharray="5 4"
      />
      {step > 0 && (
        <path
          d={`M${actual.join(' ')}L195 180M${actual.join(' ')}L65 180`}
          fill="none"
          stroke="var(--orange)"
          strokeWidth="1.5"
          opacity=".55"
        />
      )}
      <g
        className="mission-robot"
        style={{ transform: `translate(${estimate[0]}px, ${estimate[1]}px)` }}
      >
        <circle r="17" fill="var(--soft)" stroke="var(--teal)" strokeWidth="2" />
        <path d="M13 -4L-10 -11 -6 1 -5 10Z" fill="var(--teal)" />
      </g>
      {landmarks.map((_, index) => {
        if (step === 0 && index > 0) return null;
        const [x, y] = mapped(index);
        return (
          <g key={index}>
            <circle
              className="map-landmark"
              cx={x}
              cy={y}
              r={index === 0 ? 6 : 4}
              fill="var(--teal)"
            />
            {index === 0 && (
              <text x={x - 25} y={y + 21}>
                Corner A
              </text>
            )}
          </g>
        );
      })}
      <path
        d={`M${mapStart.join(' ')}L${mapRobot.join(' ')}`}
        fill="none"
        stroke="var(--teal)"
        strokeWidth="2"
      />
      <circle cx={mapRobot[0]} cy={mapRobot[1]} r="4" fill="var(--teal)" />
      <text x="27" y="245">
        {step === 0
          ? 'A familiar detail starts the map'
          : step === 1
            ? 'Movement adds uncertainty'
            : 'Recognise → correct both'}
      </text>
    </svg>
  );
}
