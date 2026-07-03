const PLACEHOLDER_ENV_PATTERN = /^YOUR_[A-Z0-9_]+_HERE$/

export function isPlaceholderEnvValue(value: string): boolean {
  return PLACEHOLDER_ENV_PATTERN.test(value.trim().toUpperCase())
}

export function getConfiguredEnv(name: string): string | null {
  const value = process.env[name]?.trim()
  if (!value || isPlaceholderEnvValue(value)) {
    return null
  }

  return value
}

export function getM0OrchestrationApiKey(): string | null {
  return getConfiguredEnv('M0_ORCHESTRATION_API_KEY')
}
