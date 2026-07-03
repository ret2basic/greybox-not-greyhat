// Placeholder shown when a value is unknown (matches the em-dash used by
// pending rows in data.ts). We never fabricate a base APY, since a made-up
// percentage would be misleading.
const UNKNOWN = '—'

/** Parses a percent label like "5.2%" into 5.2; returns null for "—"/non-numeric. */
export function parsePct(label: string): number | null {
  const value = Number.parseFloat(label.replace('%', '').trim())
  return Number.isFinite(value) ? value : null
}

/** Formats a percent number as "X.XX%". */
export function formatPct(value: number): string {
  return `${value.toFixed(2)}%`
}

/**
 * Composes a strategy's NET APY and breakdown by adding the live sUSD.tel base
 * yield to its own component rate (lend rate / trading fees). Routing every
 * strategy through this keeps them all on one base figure, so the page stays
 * internally consistent.
 */
export function composeNetApy({
  verb,
  componentLabel,
  componentPct,
  baseApyPct,
}: {
  verb: string // "lend" | "fees"
  componentLabel: string // pre-formatted component rate, e.g. "5.2%"
  componentPct: number // same rate as a number, e.g. 5.2
  baseApyPct: number | null // null when the nav feed is unavailable
}): { netApy: string; breakdown: string } {
  // Without a live base we can't form a real total — show "—" rather than a
  // misleading number, while still surfacing the known component rate.
  if (baseApyPct === null) {
    return { netApy: UNKNOWN, breakdown: `${verb} ${componentLabel} + ${UNKNOWN} base` }
  }

  return {
    netApy: formatPct(componentPct + baseApyPct),
    breakdown: `${verb} ${componentLabel} + ${formatPct(baseApyPct)} base`,
  }
}
