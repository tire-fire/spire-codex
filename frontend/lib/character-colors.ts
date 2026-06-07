// Single source of truth for the Slay the Spire 2 character colors. Use these
// everywhere a character or card-color is tinted, instead of redefining the
// hexes per component.

/** Canonical character hex colors, keyed by lowercase character/color id. */
export const CHARACTER_HEX: Record<string, string> = {
  ironclad: "#d53b27",
  silent: "#23935b",
  defect: "#3873a9",
  necrobinder: "#bf5a85",
  regent: "#f07c1e",
};

/**
 * Tailwind text-color class for a card/character color key (any casing).
 * Covers the five characters plus the non-character card pools. The literal
 * `text-[#...]` strings are kept inline so Tailwind's scanner emits them.
 */
export function colorTextClass(color: string | null | undefined): string {
  switch ((color || "").toLowerCase()) {
    case "ironclad":
      return "text-[#d53b27]";
    case "silent":
      return "text-[#23935b]";
    case "defect":
      return "text-[#3873a9]";
    case "necrobinder":
      return "text-[#bf5a85]";
    case "regent":
      return "text-[#f07c1e]";
    case "colorless":
      return "text-[var(--text-secondary)]";
    case "curse":
      return "text-[#9b6bd6]";
    case "event":
      return "text-[var(--accent-gold)]";
    case "token":
    case "status":
      return "text-[var(--text-muted)]";
    default:
      return "text-[var(--text-primary)]";
  }
}

/** Raw hex for a character id (any casing), or "" if not a known character.
 * For inline `style={{ color }}` / `backgroundColor` use. */
export function characterHex(character: string | null | undefined): string {
  return CHARACTER_HEX[(character || "").toLowerCase()] ?? "";
}
