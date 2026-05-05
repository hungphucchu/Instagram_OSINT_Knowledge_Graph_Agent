type Row = Record<string, unknown>;

function asText(v: unknown): string {
  if (typeof v === "string") {
    return v;
  }
  if (typeof v === "number") {
    return String(v);
  }
  return "";
}

export function SimpleGraph({ rows }: { rows: Row[] }) {
  const links = rows
    .map((row) => ({
      from: asText(row.entity1 || row.from_name || row.a_name || row.from_id || row.a),
      to: asText(row.entity2 || row.to_name || row.b_name || row.to_id || row.b),
      weight: Number(row.coappearances || row.freq || 1)
    }))
    .filter((x) => x.from && x.to);

  const uniqueNodes = Array.from(new Set(links.flatMap((x) => [x.from, x.to]))).slice(0, 18);
  const nodeIndex = new Map(uniqueNodes.map((n, i) => [n, i]));

  if (uniqueNodes.length === 0) {
    return <p className="muted">No pair-like evidence rows to visualize yet.</p>;
  }

  return (
    <div className="graph-wrap">
      <svg viewBox="0 0 900 560" className="graph-svg" role="img" aria-label="graph overview">
        {links.slice(0, 40).map((link, i) => {
          const a = nodeIndex.get(link.from);
          const b = nodeIndex.get(link.to);
          if (a === undefined || b === undefined) return null;
          const ax = 120 + (a % 6) * 130;
          const ay = 100 + Math.floor(a / 6) * 150;
          const bx = 120 + (b % 6) * 130;
          const by = 100 + Math.floor(b / 6) * 150;
          return (
            <g key={`${link.from}-${link.to}-${i}`}>
              <line x1={ax} y1={ay} x2={bx} y2={by} stroke="#7c8cff" strokeOpacity="0.6" />
              <text x={(ax + bx) / 2} y={(ay + by) / 2} className="edge-label">
                {link.weight}
              </text>
            </g>
          );
        })}
        {uniqueNodes.map((node, i) => {
          const x = 120 + (i % 6) * 130;
          const y = 100 + Math.floor(i / 6) * 150;
          return (
            <g key={node}>
              <circle cx={x} cy={y} r={28} fill="#1f2937" stroke="#6ee7b7" />
              <text x={x} y={y + 4} textAnchor="middle" className="node-label">
                {node.slice(0, 10)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
