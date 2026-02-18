import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0a0f',
          secondary: '#12121a',
          tertiary: '#1a1a26',
          hover: '#22222e',
          active: '#2a2a38',
        },
        border: {
          primary: '#2a2a3a',
          secondary: '#1e1e2e',
        },
        text: {
          primary: '#e4e4ef',
          secondary: '#8888a0',
          muted: '#555568',
        },
        accent: {
          blue: '#4a9eff',
          green: '#22c55e',
          red: '#ef4444',
          yellow: '#eab308',
          orange: '#f97316',
          purple: '#a855f7',
          cyan: '#06b6d4',
        },
        pnl: {
          profit: '#22c55e',
          loss: '#ef4444',
          zero: '#555568',
        },
        status: {
          open: '#22c55e',
          closed: '#555568',
          whatif: '#4a9eff',
          manual: '#eab308',
          pending: '#f97316',
          executed: '#22c55e',
          rejected: '#ef4444',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      spacing: {
        '18': '4.5rem',
      },
    },
  },
  plugins: [],
}

export default config
