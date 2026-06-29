/** @type {import('tailwindcss').Config} */
// ExcelGPT design system — coral / near-black conversational theme.
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces
        base: '#0F0F0F', // near-black app background
        card: '#1A1A1A', // card background
        input: '#242424', // input background
        hover: '#2A2A2A', // hover state

        // Accents
        coral: '#FF6B6B', // primary accent — coral red
        'coral-dark': '#E8545A', // coral hover
        'coral-light': '#FF8E8E', // coral glow
        teal: '#4ECDC4', // success / positive
        amber: '#FFB347', // warning / neutral
        'red-alert': '#FF4757', // danger / negative
        gold: '#FFD700', // rank 1 / elite

        // Text
        'text-primary': '#F7F7F7',
        'text-secondary': '#A0A0A0',
        'text-muted': '#606060',

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
        'glow-coral': '0 0 20px rgba(255,107,107,0.3)',
        'glow-teal': '0 0 20px rgba(78,205,196,0.3)',
        glow: '0 0 20px rgba(255,107,107,0.3)', // legacy alias
        card: '0 1px 2px rgba(0,0,0,0.5), 0 8px 24px rgba(0,0,0,0.35)',
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
