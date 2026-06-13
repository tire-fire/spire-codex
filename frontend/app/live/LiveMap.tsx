"use client";

// Spectator act mini-map. Renders the mod's exported act graph (nodes +
// edges) as an SVG DAG, draws the route the player has taken, and marks
// their current position. Contract: markdown-docs/live-presence.md (v3).
//
// Coordinates are the game's own grid: row is act depth (0 = act start),
// col is horizontal lane. We render row 0 at the bottom so it reads like
// the in-game map (climb upward toward the boss).

import type { Coord, LiveMapData } from "./live-shared";

// Per-node-type styling. Types arrive lowercase; an unrecognized type falls
// back to the neutral "node" entry so a new map symbol never breaks rendering.
const NODE_STYLE: Record<string, { fill: string; ring: string; glyph: string }> = {
  monster: { fill: "#9aa0a6", ring: "#c5c9ce", glyph: "M" },
  elite: { fill: "#e0843a", ring: "#ffb37a", glyph: "E" },
  boss: { fill: "#d53b27", ring: "#ff7a6a", glyph: "B" },
  shop: { fill: "#e8b830", ring: "#ffe08a", glyph: "$" },
  treasure: { fill: "#d9c24a", ring: "#fff0a0", glyph: "T" },
  restsite: { fill: "#23935b", ring: "#6fdfa3", glyph: "R" },
  event: { fill: "#8a6bbf", ring: "#c3a8ee", glyph: "?" },
  unknown: { fill: "#8a6bbf", ring: "#c3a8ee", glyph: "?" },
  ancient: { fill: "#45cfd8", ring: "#a0f0f5", glyph: "A" },
  node: { fill: "#596068", ring: "#8b9099", glyph: "" },
};

function styleFor(type: string) {
  return NODE_STYLE[type] ?? NODE_STYLE.node;
}

const COL = 30; // horizontal spacing between lanes
const ROW = 30; // vertical spacing between depths
const PAD = 18;
const R = 8; // node radius

function key(col: number, row: number): string {
  return `${col},${row}`;
}

export default function LiveMap({
  map,
  path,
  pos,
}: {
  map?: LiveMapData | null;
  path?: Coord[];
  pos?: Coord | null;
}) {
  const nodes = map?.nodes ?? [];
  if (!nodes.length) return null;

  const maxCol = Math.max(...nodes.map((n) => n[0]), 0);
  const maxRow = Math.max(...nodes.map((n) => n[1]), 0);
  const width = maxCol * COL + PAD * 2;
  const height = maxRow * ROW + PAD * 2;

  // row 0 at the bottom: y grows downward in SVG, so flip.
  const x = (col: number) => PAD + col * COL;
  const y = (row: number) => height - PAD - row * ROW;

  const visited = new Set((path ?? []).map(([c, r]) => key(c, r)));
  const onPath = (c: number, r: number) => visited.has(key(c, r));
  const isPos = (c: number, r: number) => !!pos && pos[0] === c && pos[1] === r;

  const edges = map?.edges ?? [];

  return (
    <div className="overflow-auto">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="max-w-full"
        role="img"
        aria-label="Act map showing the player's route"
      >
        {edges.map(([c, r, cc, cr], i) => {
          const lit = onPath(c, r) && onPath(cc, cr);
          return (
            <line
              key={`e-${c}-${r}-${cc}-${cr}-${i}`}
              x1={x(c)}
              y1={y(r)}
              x2={x(cc)}
              y2={y(cr)}
              stroke={lit ? "var(--accent-gold)" : "var(--border-subtle)"}
              strokeWidth={lit ? 2 : 1}
              strokeOpacity={lit ? 0.9 : 0.5}
            />
          );
        })}
        {nodes.map(([c, r, type]) => {
          const s = styleFor(type);
          const here = isPos(c, r);
          const seen = onPath(c, r);
          return (
            <g key={`n-${c}-${r}`}>
              {here && (
                <circle cx={x(c)} cy={y(r)} r={R + 4} fill="none" stroke="var(--accent-gold)" strokeWidth={2}>
                  <animate attributeName="r" values={`${R + 2};${R + 6};${R + 2}`} dur="1.4s" repeatCount="indefinite" />
                  <animate attributeName="stroke-opacity" values="1;0.3;1" dur="1.4s" repeatCount="indefinite" />
                </circle>
              )}
              <circle
                cx={x(c)}
                cy={y(r)}
                r={R}
                fill={s.fill}
                stroke={seen ? "var(--accent-gold)" : s.ring}
                strokeWidth={seen ? 2 : 1}
                fillOpacity={seen || here ? 1 : 0.55}
              />
              {s.glyph && (
                <text
                  x={x(c)}
                  y={y(r) + 3}
                  textAnchor="middle"
                  fontSize="9"
                  fontWeight="bold"
                  fill="#1a1a1a"
                  pointerEvents="none"
                >
                  {s.glyph}
                </text>
              )}
              <title>{type}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
