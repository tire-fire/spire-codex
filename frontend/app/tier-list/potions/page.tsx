import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL, SITE_NAME, DEFAULT_OG_IMAGE, buildLanguageAlternates } from "@/lib/seo";
import JsonLd from "@/app/components/JsonLd";
import { buildBreadcrumbJsonLd, buildCollectionPageJsonLd } from "@/lib/jsonld";
import TierList, { type TierEntity } from "@/app/components/TierList";
import BracketFilter from "@/app/components/BracketFilter";
import { bracketParam, normalizeBracket } from "@/lib/content-brackets";

const API_INTERNAL = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const revalidate = 300;

interface ApiPotion {
  id: string;
  name: string;
  image_url: string | null;
  pool?: string | null;
}

interface ScoresMap {
  [id: string]: { score: number | null };
}

export const metadata: Metadata = {
  title: `Potion Tier List - All 63 Potions Ranked - Slay the Spire 2 (sts2) | ${SITE_NAME}`,
  description:
    "Every Slay the Spire 2 (sts2) potion ranked S through F by community win rate. Codex Score with Bayesian shrinkage. Updated every 30 minutes.",
  alternates: { canonical: `${SITE_URL}/tier-list/potions` },
  openGraph: {
    title: `Potion Tier List - Slay the Spire 2 (sts2) | ${SITE_NAME}`,
    description: "Every Slay the Spire 2 potion ranked S through F by community win-rate data.",
    url: `${SITE_URL}/tier-list/potions`,
    siteName: SITE_NAME,
    type: "website",
    images: [{ url: DEFAULT_OG_IMAGE }],
  },
  twitter: {
    card: "summary_large_image",
    title: `Potion Tier List - Slay the Spire 2 (sts2) | ${SITE_NAME}`,
    description: "Every Slay the Spire 2 potion ranked S through F by community win-rate data.",
  },
};

interface PageProps {
  searchParams: Promise<{ bracket?: string }>;
}

async function fetchData(
  param?: string | null,
): Promise<{ potions: ApiPotion[]; scores: ScoresMap }> {
  try {
    const scoresUrl = `${API_INTERNAL}/api/runs/scores/potions${param ? `?bracket=${param}` : ""}`;
    const [potionsRes, scoresRes] = await Promise.all([
      fetch(`${API_INTERNAL}/api/potions`, { next: { revalidate: 1800 } }),
      fetch(scoresUrl, { next: { revalidate: 300 } }),
    ]);
    const potions = potionsRes.ok ? ((await potionsRes.json()) as ApiPotion[]) : [];
    const scores = scoresRes.ok ? ((await scoresRes.json()) as ScoresMap) : {};
    return { potions, scores };
  } catch {
    return { potions: [], scores: {} };
  }
}

export default async function PotionsTierListPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const bracket = normalizeBracket(sp.bracket);
  const param = bracketParam(bracket);
  const { potions, scores } = await fetchData(param);

  const entities: TierEntity[] = potions.map((p) => ({
    id: p.id,
    name: p.name,
    image_url: p.image_url,
    score: scores[p.id.toUpperCase()]?.score ?? null,
  }));

  // Top-30 by score for ItemList JSON-LD, gives Google a structured
  // ranked list it can render as carousel-style rich results.
  const rankedItems = [...entities]
    .filter((e) => e.score != null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 30)
    .map((e) => ({
      name: e.name,
      path: `/potions/${e.id.toLowerCase()}`,
    }));

  const jsonLd = [
    buildBreadcrumbJsonLd([
      { name: "Home", href: "/" },
      { name: "Tier List", href: "/tier-list" },
      { name: "Potion Tier List", href: "/tier-list/potions" },
    ]),
    buildCollectionPageJsonLd({
      name: "Potion Tier List",
      description: "Every Slay the Spire 2 (sts2) potion ranked by Codex Score from community-submitted run win rates.",
      path: "/tier-list/potions",
      items: rankedItems,
    }),
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <JsonLd data={jsonLd} />

      <div className="flex items-baseline gap-3 mb-2 flex-wrap">
        <h1 className="text-3xl font-bold">
          <span className="text-[var(--accent-gold)]">Potion Tier List</span>
        </h1>
        <span className="text-sm text-[var(--text-muted)]">{entities.length.toLocaleString()} potions</span>
      </div>
      <p className="text-sm text-[var(--text-muted)] mb-6">
        Ranked by <Link href="/leaderboards/scoring" className="text-[var(--accent-gold)] hover:underline">Codex Score</Link>,
        community win-rate data with Bayesian shrinkage. Click any potion for full stats.
      </p>

      {/* Content bracket: grade against all runs, A10, or win-rate skill tiers. */}
      <BracketFilter basePath="/tier-list/potions" current={bracket} composite />

      <TierList route="potions" entities={entities} />
    </div>
  );
}
