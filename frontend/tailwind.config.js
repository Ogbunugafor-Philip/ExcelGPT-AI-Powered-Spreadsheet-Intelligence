/** @type {import('tailwindcss').Config} */
// ExcelGPT design system — navy / electric-blue executive theme.
// Color usage rules are documented in src/design-system.md.
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0A0F1E', // primary background
        'navy-light': '#111827', // raised surfaces / cards
        'blue-electric': '#2563EB', // primary accent / CTAs
        'blue-glow': '#3B82F6', // hover / focus glow
        emerald: '#10B981', // success / positive direction
        amber: '#F59E0B', // warning
        'red-alert': '#EF4444', // danger / negative direction
        gold: '#D97706', // premium / executive tier
        'text-primary': '#F9FAFB', // primary text
        'text-secondary': '#9CA3AF', // secondary / muted text
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(59, 130, 246, 0.4), 0 8px 24px rgba(37, 99, 235, 0.25)',
        card: '0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 24px rgba(0, 0, 0, 0.25)',
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.25rem',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
