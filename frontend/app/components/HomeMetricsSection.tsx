import Link from "next/link";
import { t } from "@/lib/ui-translations";
import { colorTextClass } from "@/lib/character-colors";

const API =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const REVALIDATE = 60;

interface ApiMetricRow {
  id: string;
  upgraded?: boolean;
  elo: number | null;
  win_rate: number | null;
  pick_rate: number | null;
  picks: number;
}
interface ApiCard {
  id: string;
  name: string;
  color: string;
}

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { next: { revalidate: REVALIDATE } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function pct(v: number | null): string {
  return v === null || v === undefined ? "·" : `${v.toFixed(0)}%`;
}

/**
 * Home-page preview of the Card Metrics table, scoped to the A10 cohort
 * (ascension 10) and ranked by Codex Elo, the way /leaderboards/metrics
 * opens. Server-rendered; renders nothing when there's no A10 data yet so
 * the home page never shows an empty block.
 */
export default async function HomeMetricsSection({
  langPrefix = "",
  lang = "eng",
}: {
  langPrefix?: string;
  lang?: string;
}) {
  const [metrics, cards] = await Promise.all([
    fetchJson<{ rows: ApiMetricRow[] }>(`${API}/api/runs/metrics/cards?cohort=a10`),
    fetchJson<ApiCard[]>(`${API}/api/cards?lang=${lang}`),
  ]);
  if (!metrics?.rows || !cards) return null;

  const byId = new Map(cards.map((c) => [c.id.toUpperCase(), c]));
  const top = metrics.rows
    // Base cards only (upgraded rows have no Elo) with a real Elo + samples.
    .filter((r) => r.elo != null && r.picks > 0)
    .map((r) => ({ r, c: byId.get(r.id.toUpperCase()) }))
    .filter((x): x is { r: ApiMetricRow; c: ApiCard } => !!x.c)
    .sort((a, b) => (b.r.elo ?? 0) - (a.r.elo ?? 0))
    .slice(0, 8);
  if (top.length === 0) return null;

  const href = `${langPrefix}/leaderboards/metrics?cohort=a10`;

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
      <div className="flex items-baseline justify-between gap-3 mb-5">
        <h2 className="text-xl sm:text-2xl font-semibold text-[var(--text-primary)]">
          {t("Card Metrics", lang)}
          <span className="ml-2 text-xs font-bold px-2 py-0.5 rounded bg-[var(--accent-gold)]/15 text-[var(--accent-gold)] align-middle">
            A10
          </span>
        </h2>
        <Link
          href={href}
          className="shrink-0 inline-flex items-center gap-1 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--accent-gold)] transition-colors"
        >
          <span>{t("View Card metrics", lang)}</span>
          <span aria-hidden>→</span>
        </Link>
      </div>

      <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] overflow-x-auto">
        <table className="w-full min-w-[460px] text-sm">
          <thead className="text-[var(--text-secondary)]">
            <tr className="border-b border-[var(--border-subtle)]">
              <th className="px-3 py-2.5 text-right font-medium w-10">#</th>
              <th className="px-3 py-2.5 text-left font-medium">{t("Card", lang)}</th>
              <th className="px-3 py-2.5 text-right font-medium">{t("Codex Elo", lang)}</th>
              <th className="px-3 py-2.5 text-right font-medium">Win%</th>
              <th className="px-3 py-2.5 text-right font-medium">Pick%</th>
            </tr>
          </thead>
          <tbody>
            {top.map(({ r, c }, i) => (
              <tr
                key={c.id}
                className="border-b border-[var(--border-subtle)]/40 last:border-0 hover:bg-[var(--bg-card-hover)] transition-colors"
              >
                <td className="px-3 py-2 text-right tabular-nums text-[var(--text-muted)]">
                  {i + 1}
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`${langPrefix}/cards/${c.id.toLowerCase()}`}
                    className={`font-medium hover:underline ${colorTextClass(c.color)}`}
                  >
                    {c.name}
                  </Link>
                </td>
                <td className="px-3 py-2 text-right tabular-nums font-semibold text-[var(--accent-gold)]">
                  {r.elo === null ? "·" : Math.round(r.elo)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.win_rate)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-[var(--text-muted)]">
                  {pct(r.pick_rate)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
