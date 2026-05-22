import type { Metadata } from "next";
import JsonLd from "@/app/components/JsonLd";
import { buildBreadcrumbJsonLd, buildCollectionPageJsonLd } from "@/lib/jsonld";
import EncounterStatsClient from "@/app/leaderboards/encounters/EncounterStatsClient";
import {
  isValidLang,
  LANG_GAME_NAME,
  LANG_NAMES,
  LANG_HREFLANG,
  SUPPORTED_LANGS,
  type LangCode,
} from "@/lib/languages";
import { DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL } from "@/lib/seo";
import { t } from "@/lib/ui-translations";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!isValidLang(lang)) return {};

  const langCode = lang as LangCode;
  const gameName = LANG_GAME_NAME[langCode];
  const nativeName = LANG_NAMES[langCode];
  const title = `${gameName} ${t("Encounter Stats", lang)} | Spire Codex (${nativeName})`;
  const description = t("encounter_stats_tagline", lang);

  const languages: Record<string, string> = {
    en: `${SITE_URL}/leaderboards/encounters`,
    "x-default": `${SITE_URL}/leaderboards/encounters`,
  };
  for (const code of SUPPORTED_LANGS) {
    languages[LANG_HREFLANG[code]] = `${SITE_URL}/${code}/leaderboards/encounters`;
  }

  return {
    title,
    description,
    openGraph: {
      type: "website",
      siteName: SITE_NAME,
      url: `${SITE_URL}/${lang}/leaderboards/encounters`,
      title,
      description,
      locale: LANG_HREFLANG[langCode],
      images: [{ url: DEFAULT_OG_IMAGE }],
    },
    twitter: { card: "summary_large_image", title, description },
    alternates: { canonical: `/${lang}/leaderboards/encounters`, languages },
  };
}

export default async function LangEncounterStatsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isValidLang(lang)) return null;
  const langCode = lang as LangCode;
  const gameName = LANG_GAME_NAME[langCode];
  const jsonLd = [
    buildBreadcrumbJsonLd([
      { name: t("Home", lang), href: `/${lang}` },
      { name: t("Leaderboards", lang), href: `/${lang}/leaderboards` },
      { name: t("Encounters", lang), href: `/${lang}/leaderboards/encounters` },
    ]),
    buildCollectionPageJsonLd({
      name: `${gameName} ${t("Encounter Stats", lang)}`,
      description: t("encounter_stats_tagline", lang),
      path: `/${lang}/leaderboards/encounters`,
      inLanguage: LANG_HREFLANG[langCode],
    }),
  ];
  return (
    <>
      <JsonLd data={jsonLd} />
      <EncounterStatsClient />
    </>
  );
}
