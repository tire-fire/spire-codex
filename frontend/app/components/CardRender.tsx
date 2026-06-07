"use client";

import { useEffect, useLayoutEffect, useRef } from "react";
import { imageUrl } from "@/lib/image-url";
import { getCardDisplayModel } from "@/lib/card-display";
import RichDescription from "./RichDescription";
import type { Card } from "@/lib/api";

/**
 * 1:1 Slay the Spire 2 card render. Geometry, font sizes, and colors are pulled
 * directly from the game's card layout (extraction scenes/cards/card.tscn): the
 * card is 300x422 game units, nodes anchored at center with the exact offsets.
 * Frame/banner/border/orb textures are sliced from the game atlas and tinted
 * with the game's HSV shader (tools/extract_card_frames.py); font is Kreon.
 *
 * Ancient cards use the game's separate node branch: a full-bleed art, the
 * crystalline border (approximated by masking a blurred copy of the art to the
 * frame ring, replicating the game's screen-space refraction shader), the
 * ancient banner, and a translucent text panel.
 */

const FRAMES = "/static/images/card-frames";
const CARD_W = 300;

const useIsoLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

const RARITY_STROKE: Record<string, string> = {
  common: "#4d4b40",
  uncommon: "#005c75",
  rare: "#6b4b00",
  ancient: "#4d4c41",
  status: "#4f522f",
  curse: "#550b9e",
  event: "#1b6131",
  quest: "#7e3e15",
};
const COST_STROKE: Record<string, string> = {
  ironclad: "#802020",
  silent: "#1a6625",
  regent: "#803d0e",
  necrobinder: "#803367",
  defect: "#1a6625",
  colorless: "#5c5440",
};
const CREAM = "#fff6e2";

/**
 * Rounded text outline built from layered text-shadows (a disc dilation of the
 * glyph). The game's font outline is a dilation with round joins; CSS
 * `-webkit-text-stroke` uses miter joins, which spike out at the sharp serif
 * vertices of Kreon (most visibly the apex of a capital "A"). Dilating with
 * shadows on concentric rings reproduces the game's smooth outline. `drop` is
 * the soft offset shadow, painted behind the outline.
 */
function outlineShadow(radius: number, color: string, drop = true): string {
  const rings: Array<[number, number]> = [
    [radius, 16],
    [radius * 0.66, 12],
    [radius * 0.33, 8],
  ];
  const layers: string[] = [];
  for (const [r, n] of rings) {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 2 * Math.PI;
      layers.push(`${(Math.cos(a) * r).toFixed(2)}px ${(Math.sin(a) * r).toFixed(2)}px 0 ${color}`);
    }
  }
  if (drop) layers.push("2px 2px 1px rgba(0,0,0,0.22)");
  return layers.join(", ");
}

function frameType(type: string): "attack" | "skill" | "power" | "quest" {
  const t = type.toLowerCase();
  if (t === "attack") return "attack";
  if (t === "power") return "power";
  if (t === "quest") return "quest";
  return "skill";
}
function frameColor(color: string): string {
  const c = (color || "").toLowerCase();
  if (["ironclad", "silent", "defect", "necrobinder", "regent"].includes(c)) return c;
  if (c === "curse") return "curse";
  if (c === "quest") return "quest";
  return "colorless";
}
function energyColor(color: string): string {
  const c = (color || "").toLowerCase();
  if (["ironclad", "silent", "defect", "necrobinder", "regent"].includes(c)) return c;
  if (c === "quest") return "quest";
  return "colorless";
}
function bannerRarity(rarity: string): string {
  const r = (rarity || "").toLowerCase();
  if (["uncommon", "rare", "curse", "status", "event", "quest", "ancient"].includes(r)) return r;
  return "common";
}
function borderType(type: string): "attack" | "skill" | "power" {
  const t = frameType(type);
  return t === "quest" ? "skill" : t;
}

export default function CardRender({
  card,
  width = 320,
  className = "",
  upgraded = false,
}: {
  card: Card;
  width?: number;
  className?: string;
  upgraded?: boolean;
}) {
  const ft = frameType(card.type);
  const fc = frameColor(card.color);
  const rarity = bannerRarity(card.rarity);
  const energy = energyColor(card.color);
  const isAncient = (card.rarity || "").toLowerCase() === "ancient";

  // Apply the upgrade (name +, cost/value changes, green-highlighted deltas in
  // the body) via the shared display model, so the render matches the card
  // page's upgrade toggle exactly.
  const display = getCardDisplayModel(card, upgraded);
  const isUpgraded = display.isUpgraded;
  const displayName = `${card.name}${isUpgraded ? "+" : ""}`;
  // The game shows the keyword line (Exhaust, Unplayable, Ethereal, ...) under
  // the description. For curses with no other text that line is the whole body.
  const bodyText = [display.descriptionText, display.keywordText]
    .filter(Boolean)
    .join("\n");

  // Cost / playability. Unplayable cards (cost < 0: curses, most statuses) keep
  // the orb but swap the number for the barred unplayable icon. Upgraded costs
  // render green (the game's EnergyLabel upgrade color).
  const isXCost = !!(card.is_x_cost || card.is_x_star_cost);
  const isUnplayable = !isXCost && display.cost != null && display.cost < 0;
  const costUpgraded = isUpgraded && display.upgrade?.cost != null;
  const cost = isXCost ? "X" : (display.cost ?? 0).toString();

  const gp = (v: number) => `${(v * width) / CARD_W}px`;
  const gpn = (v: number) => (v * width) / CARD_W;
  const frame = (name: string) => imageUrl(`${FRAMES}/${name}.webp`);
  const art = card.image_url ? imageUrl(card.image_url) : "";

  // Auto-shrink the description to fit, like the game's MegaRichTextLabel.
  const boxRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  useIsoLayoutEffect(() => {
    const box = boxRef.current;
    const text = textRef.current;
    if (!box || !text) return;
    const fit = () => {
      const base = (21 * width) / CARD_W;
      const min = (10 * width) / CARD_W;
      let size = base;
      text.style.fontSize = `${size}px`;
      let guard = 0;
      while (
        (text.scrollHeight > box.clientHeight + 0.5 ||
          text.scrollWidth > box.clientWidth + 0.5) &&
        size > min &&
        guard < 60
      ) {
        size -= base * 0.04;
        text.style.fontSize = `${size}px`;
        guard++;
      }
    };
    fit();
    let cancelled = false;
    if (typeof document !== "undefined" && document.fonts?.ready) {
      document.fonts.ready.then(() => {
        if (!cancelled) fit();
      });
    }
    return () => {
      cancelled = true;
    };
  }, [bodyText, width, isAncient]);

  // Description box rect differs between layouts (regular desc box vs the
  // ancient text panel).
  const descBox = isAncient
    ? { left: "9%", top: "63%", width: "82%", height: "25%" }
    : { left: "9.33%", top: "58.77%", width: "81.33%", height: "32.23%" };

  return (
    <div
      className={`relative select-none ${className}`}
      style={{
        width,
        aspectRatio: "300 / 422",
        fontFamily: "Kreon, Georgia, serif",
      }}
    >
      {isAncient ? (
        <>
          {/* Full-bleed art + crystalline refraction, clipped to the card's
              rounded corners. (Kept in its own clip so the energy orb, which
              overflows the top-left, isn't cut off.) */}
          <div
            className="absolute overflow-hidden"
            style={{ inset: 0, borderRadius: "5%" }}
          >
            {art && (
              <img
                src={art}
                alt={card.name}
                crossOrigin="anonymous"
                className="absolute object-cover"
                style={{ left: 0, top: 0, width: "100%", height: "100%" }}
              />
            )}
            {/* Crystalline refractive border: a blurred copy of the art masked
                to the ancient frame ring (replicates the screen-space shader). */}
            {art && (
              <div
                className="absolute overflow-hidden"
                style={{
                  inset: 0,
                  WebkitMaskImage: `url(${frame("ancient_glass")})`,
                  maskImage: `url(${frame("ancient_glass")})`,
                  WebkitMaskSize: "100% 100%",
                  maskSize: "100% 100%",
                  WebkitMaskRepeat: "no-repeat",
                  maskRepeat: "no-repeat",
                }}
              >
                <img
                  src={art}
                  alt=""
                  crossOrigin="anonymous"
                  className="absolute object-cover"
                  style={{
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    filter: `blur(${gp(6)}) brightness(1.45) saturate(1.3)`,
                  }}
                />
              </div>
            )}
          </div>
          {/* Additive border glow. */}
          <img
            src={frame("ancient_border")}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: 0, top: 0, width: "100%", height: "100%", mixBlendMode: "screen", opacity: 0.9 }}
          />
          {/* Translucent text panel. */}
          <img
            src={frame(`ancient_textbg_${borderType(card.type)}`)}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: "5.7%", top: "44.8%", width: "88%", height: "48%" }}
          />
          {/* Ancient banner. */}
          <img
            src={frame("banner_ancient_raw")}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: "-4.3%", top: "0.95%", width: "109%" }}
          />
          {/* Animated flame (Fire AnimatedSprite2D, 10-frame loop @10fps).
              card.tscn: Fire is centered at card (151, -6) = (50.33%, -1.42%);
              texture 49x76 at scale 0.6 -> 9.8% x 10.8%. */}
          <img
            src={frame("ancient_flame")}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: "45.43%", top: "-6.82%", width: "9.8%", height: "10.8%" }}
          />
        </>
      ) : (
        <>
          {/* Art (Portrait): -125,-168 .. 125,22 */}
          {art && (
            <img
              src={art}
              alt={card.name}
              crossOrigin="anonymous"
              className="absolute object-cover"
              style={{ left: "8.33%", top: "10.19%", width: "83.33%", height: "45.02%" }}
            />
          )}
          {/* Type frame, tinted by character. */}
          <img
            src={frame(`frame_${ft}_${fc}`)}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: 0, top: 0, width: "100%", height: "100%" }}
          />
          {/* Portrait border, tinted by rarity. */}
          <img
            src={frame(`border_${borderType(card.type)}_${rarity}`)}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: "4.17%", top: "11.14%", width: "91.67%", height: "49.76%" }}
          />
          {/* Title banner. Node rect -163..164 / -207..-124 (327x83) with the
              game's KEEP_ASPECT_COVERED, so the full-logical-size banner texture
              is mapped with object-fit:cover (not stretched). */}
          <img
            src={frame(`banner_${rarity}`)}
            alt=""
            crossOrigin="anonymous"
            className="absolute"
            style={{ left: "-4.33%", top: "0.95%", width: "109%", height: "19.67%", objectFit: "cover" }}
          />
        </>
      )}

      {/* Type plaque + label (shared — the game shows it on ancients too):
          -30.5,1 .. 30.5,38, font 16, black 75%. */}
      <img
        src={frame(`plaque_${rarity}`)}
        alt=""
        crossOrigin="anonymous"
        className="absolute"
        style={{ left: "39.83%", top: "50.24%", width: "20.33%", height: "8.77%" }}
      />
      <div
        className="absolute flex items-center justify-center text-center font-bold"
        style={{
          left: "33%",
          top: "50.24%",
          width: "34%",
          height: "8.77%",
          color: "rgba(0,0,0,0.75)",
          fontSize: gp(16),
        }}
      >
        {card.type}
      </div>

      {/* Card name (TitleLabel): font 26, cream, per-rarity outline. Nudged
          up ~2% vs the exact rect to match Kreon metrics. */}
      <div
        className="absolute flex items-center justify-center text-center font-bold"
        style={{
          left: "15%",
          // The ancient banner texture is taller, so its name area sits lower.
          top: isAncient ? "2%" : "-0.4%",
          width: "70%",
          height: "12.8%",
          lineHeight: 1,
          color: CREAM,
          fontSize: gp(26),
          textShadow: outlineShadow(gpn(3), RARITY_STROKE[rarity] ?? "#4d4b40"),
        }}
      >
        {displayName}
      </div>

      {/* Energy orb + cost (font 32, outline 16). */}
      <img
        src={frame(`energy_${energy}`)}
        alt=""
        crossOrigin="anonymous"
        className="absolute"
        style={{ left: "-5.33%", top: "-3.79%", width: "21.33%", height: "15.17%" }}
      />
      {isUnplayable ? (
        // Barred unplayable icon overlaid on the orb (EnergyIcon child at 8,8
        // size 48 within the 64px orb), with no cost number.
        <img
          src={frame("unplayable_icon")}
          alt=""
          crossOrigin="anonymous"
          className="absolute"
          style={{ left: "-2.67%", top: "-1.9%", width: "16%", height: "11.37%" }}
        />
      ) : (
        <div
          className="absolute flex items-center justify-center font-bold"
          style={{
            left: "-5.33%",
            top: "-3.79%",
            width: "21.33%",
            height: "15.17%",
            // Upgraded cost renders green (game EnergyLabel upgrade color).
            color: costUpgraded ? "#00ff00" : CREAM,
            fontSize: gp(32),
            textShadow: outlineShadow(
              gpn(4),
              costUpgraded ? "#1f5923" : COST_STROKE[energy] ?? "#4c4943"
            ),
          }}
        >
          {cost}
        </div>
      )}

      {/* Description (auto-shrinks to fit). */}
      <div
        ref={boxRef}
        className="absolute flex items-center justify-center overflow-hidden"
        style={{ ...descBox }}
      >
        <div
          ref={textRef}
          className="text-center"
          style={{
            color: CREAM,
            fontSize: gp(21),
            lineHeight: 1.1,
            textShadow: "2px 2px rgba(0,0,0,0.25)",
          }}
        >
          <RichDescription text={bodyText} />
        </div>
      </div>
    </div>
  );
}
