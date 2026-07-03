export const formatTokenBalance = (value: string | number, fallback = '0.00') => {
  const numeric = typeof value === 'number' ? value : Number(value.replace(/,/g, ''))

  if (!Number.isFinite(numeric)) {
    return fallback
  }

  return numeric.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
