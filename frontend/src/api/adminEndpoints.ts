const ADMIN = '/api/admin'

export const adminEndpoints = {
  // Portfolios
  portfolios: `${ADMIN}/portfolios`,
  portfolio: (name: string) => `${ADMIN}/portfolios/${name}`,

  // Risk
  risk: `${ADMIN}/risk`,

  // Strategies
  strategies: `${ADMIN}/strategies`,
  strategy: (name: string) => `${ADMIN}/strategies/${name}`,

  // Workflow
  workflow: `${ADMIN}/workflow`,

  // Capital plan
  capitalPlan: `${ADMIN}/capital-plan`,

  // Reload
  reload: `${ADMIN}/reload`,
} as const
