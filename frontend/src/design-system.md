# ExcelGPT — Frontend Design System

The ExcelGPT interface reads like an executive financial product: dark navy canvas, electric-blue accents, restrained color, generous whitespace, and crisp Inter typography. This document defines the tokens and rules the React shell and Tailwind config (`tailwind.config.js`, `index.css`) implement.

---

## 1. Color palette

| Token | Hex | Role |
|-------|-----|------|
| `navy` | `#0A0F1E` | Primary background (app canvas). |
| `navy-light` | `#111827` | Raised surfaces: cards, panels, modals. |
| `blue-electric` | `#2563EB` | Primary accent: CTAs, active states, links. |
| `blue-glow` | `#3B82F6` | Hover/focus glow and highlights. |
| `emerald` | `#10B981` | Success, positive KPI direction (`up`). |
| `amber` | `#F59E0B` | Warning, caution states. |
| `red-alert` | `#EF4444` | Danger, negative KPI direction (`down`), errors. |
| `gold` | `#D97706` | Premium / executive formatting tier accents. |
| `text-primary` | `#F9FAFB` | Primary text on dark surfaces. |
| `text-secondary` | `#9CA3AF` | Secondary/muted text, captions, labels. |

### Color usage rules
1. **Navy is the canvas; navy-light is everything raised.** Never put a card directly on the same shade as the background — always step up to `navy-light`.
2. **One accent at a time.** `blue-electric` is the only primary CTA color. Don't compete it with gold/emerald in the same action.
3. **Semantic colors are reserved.** `emerald`/`red-alert`/`amber` mean something (positive/negative/warning) — never decorative.
4. **Gold signals premium.** Use `gold` only for executive-tier flourishes (premium badges, executive report accents).
5. **Text contrast.** Body uses `text-primary`; demote supporting copy to `text-secondary`. Never go lower-contrast than `text-secondary` on navy.

---

## 2. Typography

**Family:** Inter (imported in `index.css`), falling back to `system-ui`.

| Scale | Size | Weight | Use |
|-------|------|--------|-----|
| Display | `2.25rem` (text-4xl) | 800 | Hero / page title |
| H1 | `1.875rem` (text-3xl) | 700 | Section title |
| H2 | `1.5rem` (text-2xl) | 700 | Subsection |
| H3 | `1.25rem` (text-xl) | 600 | Card title |
| Body-lg | `1.125rem` (text-lg) | 400 | Lead paragraph |
| Body | `1rem` (text-base) | 400 | Default text |
| Small | `0.875rem` (text-sm) | 500 | Labels, metadata |
| Caption | `0.75rem` (text-xs) | 500 | KPI captions, hints |

**Rules:** headings tight leading (1.2), body normal (1.5); KPI values use heavy weight (700–800); never more than three type sizes in one component.

---

## 3. Spacing system

4px base unit. Allowed steps: `4, 8, 12, 16, 24, 32, 48, 64` (px) → tokens `--space-1 … --space-16`.

- **Component padding:** cards `24px`, compact controls `12–16px`.
- **Section rhythm:** `48–64px` vertical gaps between major sections.
- **Stack spacing:** `8–16px` between related elements; `24px+` between groups.

---

## 4. Elevation, radius & motion

- **Radius:** controls `8px` (`--radius-md`), cards `14px` (`--radius-lg`), modals `20px` (`--radius-xl`).
- **Shadows:** `--shadow-card` for resting surfaces, `--shadow-glow` for active/hover CTAs.
- **Motion:** `framer-motion` for panel/modal transitions; 150ms ease for hover, 250–350ms for layout transitions. Keep motion subtle and purposeful.

---

## 5. Component patterns

### KPI card
`navy-light` surface, `text-secondary` label (caption), large `text-primary` value, delta tinted by `direction` (emerald/red-alert/secondary). Optional `lucide-react` trend icon.

### Upload zone
Dashed border in `blue-electric` at 40% opacity; on drag-active, solid `blue-glow` border + `--shadow-glow`. Built on `react-dropzone`.

### Buttons
Primary = `eg-btn-primary` (`blue-electric` → `blue-glow` on hover with glow). Secondary = transparent with `text-secondary` border. Destructive = `red-alert`.

### Charts (Recharts)
Dark theme: navy background, `text-secondary` axes/grid, series in `blue-electric` / `emerald` / `gold`. Keep one or two series visible at a time for executive clarity.

### Modal (download)
`navy-light` panel, `--radius-xl`, `--shadow-card`, framer-motion fade+scale, dimmed navy backdrop.

---

## 6. Layout rules

- **Max content width:** ~1200px, centered; comfortable gutters on wide screens.
- **Primary flow is vertical:** Upload → Data Preview → Instruction → Progress → Preview → Download, each a full-width section with `48–64px` rhythm.
- **Two-column on desktop** for Instruction (left) + live Preview (right) once data is loaded; stacks on mobile.
- **Consistency:** every raised block is an `eg-card`; every CTA is `eg-btn-primary`. Don't invent one-off styles — extend tokens instead.
