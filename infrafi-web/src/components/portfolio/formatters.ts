export const formatDisplayAmount = (value: string) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '0.00'
  }
  return numeric.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export const formatUsdAmount = (value: string) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '$0.00'
  }
  return `$${numeric.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export const formatClaimableDate = (timestampSeconds: number | null) => {
  if (timestampSeconds === null) {
    return '-'
  }
  return new Date(timestampSeconds * 1000).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

export const getDaysUntil = (timestampSeconds: number, nowSeconds: number) => {
  return Math.max(0, Math.ceil((timestampSeconds - nowSeconds) / 86_400))
}
