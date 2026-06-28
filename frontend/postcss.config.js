// Enables Tailwind (and autoprefixer) so the @tailwind directives in index.css
// expand into utility classes. Without this, none of the bg-navy / flex / text-*
// utilities exist and the UI renders unstyled.
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
