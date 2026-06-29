/** @type {import('tailwindcss').Config} */
// ExcelGPT design system — coral / near-black conversational theme.
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces — refreshed near-black ladder with subtle depth.
        base: '#0C0C0E', // near-black app background
        surface: '#141416', // raised surface (KPI cards)
        card: '#1C1C1F', // card background
        'card-hover': '#222226', // card hover state
        sidebar: '#111113', // sidebar background
        input: '#1C1C1F', // input background
        hover: '#222226', // hover state

        // Accents
        coral: '#FF5C5C', // primary accent — coral red
        'coral-600': '#E04444', // coral hover
        'coral-dark': '#E04444', // legacy alias for hover
        'coral-light': '#FF8E8E', // coral glow

        // Semantic
        positive: '#34D399', // positive / up
        negative: '#F87171', // negative / down
        warning: '#FBBF24', // warning / at risk
        gold: '#F59E0B', // elite / rank 1
        teal: '#34D399', // success / positive (remapped to positive green)
        amber: '#FBBF24', // warning / neutral
        'red-alert': '#F87171', // danger / negative

        // Text
        'text-1': '#FFFFFF',
        'text-2': '#A1A1AA',
        'text-3': '#52525B',
        'text-primary': '#FFFFFF',
        'text-secondary': '#A1A1AA',
        'text-muted': '#52525B',

        // Borders as named colors (so `border-border` / `border-strong` work).
        border: 'rgba(255,255,255,0.06)',
        'border-strong': 'rgba(255,255,255,0.12)',

        // Legacy token names remapped to the new palette so any older class
        // still renders on-theme (no navy / electric-blue anywhere).
        navy: '#0F0F0F',
        'navy-light': '#1A1A1A',
        'navy-card': '#1A1A1A',
        'blue-electric': '#FF6B6B',
        'blue-glow': '#FF8E8E',
        emerald: '#4ECDC4',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-coral': '0 0 0 1px rgba(255,92,92,0.4), 0 0 24px rgba(255,92,92,0.18)',
        'glow-teal': '0 0 20px rgba(52,211,153,0.25)',
        glow: '0 0 24px rgba(255,92,92,0.18)', // legacy alias
        card: '0 1px 2px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.3)',
        elevated: '0 2px 4px rgba(0,0,0,0.5), 0 12px 32px rgba(0,0,0,0.4)',
        coral: '0 0 0 1px rgba(255,92,92,0.5), 0 0 20px rgba(255,92,92,0.15)',
      },
      borderColor: {
        DEFAULT: 'rgba(255,255,255,0.06)',
        strong: 'rgba(255,255,255,0.12)',
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.25rem',
      },
    },
  },
  // 'class' strategy: don't inject global form base styles (which hardcode a
  // blue focus ring/accent). Our inputs are styled explicitly with coral.
  plugins: [require('@tailwindcss/forms')({ strategy: 'class' })],
}
