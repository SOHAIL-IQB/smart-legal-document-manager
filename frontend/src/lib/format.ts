/** Fold and version numbers as two figures: 4 → "04". */
export const pad = (n: number) => String(n).padStart(2, '0')
