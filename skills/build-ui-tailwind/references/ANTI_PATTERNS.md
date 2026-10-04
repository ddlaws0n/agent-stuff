# Tailwind v4.3 Anti-Patterns and Replacements

Use this during reviews and migrations.

<!-- prettier-ignore -->
| Anti-pattern | Why it is risky | Prefer |
|-|-|-|
| Creating `tailwind.config.js` by reflex in a new v4 app | v4 is CSS-first; config files add legacy assumptions | `@import "tailwindcss"`, `@theme`, `@utility`, `@custom-variant`, `@source` |
| `@tailwind base; @tailwind components; @tailwind utilities;` in a v4 CSS entry | v3-style directive structure | `@import "tailwindcss";` |
| `safelist` in a new config | v4 safelisting moved to CSS-side source controls | `@source inline(...)` |
| `content: [...]` as the primary scanning mechanism in new v4 code | v4 automatic detection plus CSS `@source` is the default | `@source`, `@source not`, `source(none)` |
| `start-*` and `end-*` positioning | Deprecated in favor of logical inset utilities | `inset-s-*`, `inset-e-*` |
| Dynamic template classes like `` `bg-${color}-500` `` | Source scanning cannot see all generated classes reliably | Map values to explicit class strings or safelist with `@source inline(...)` |
| Using `font-features-['tnum']` for routine numeric alignment | Too low-level for a common case | `tabular-nums` |
| Using `zoom-*` for hover animation | `zoom` affects layout | `scale-*` and transforms |
| Hiding primary scrollbars with `scrollbar-none` | Reduces affordance and discoverability | `scrollbar-thin`, visible track/thumb, or keep default scrollbar |
| Using masks to hide important content | Masks are visual and can impair access/understanding | Use masks only for decorative fades/reveals |
| Physical spacing for directional layout in global products | Does not adapt to RTL or vertical writing modes | Logical block/inline utilities |
| Forcing PostCSS in every project | v4 has dedicated Vite and webpack integrations | `@tailwindcss/vite` or `@tailwindcss/webpack` where appropriate |
| Treating v4.1 fallbacks as old-browser support | v4 requires Chrome 111, Safari 16.4, Firefox 128 | Check browser targets and avoid unsupported utilities when necessary |

## Migration checklist

- [ ] Confirm installed Tailwind version and integration package.
- [ ] Run `npx @tailwindcss/upgrade` (Node.js 20+) on a clean branch and review the diff.
- [ ] Replace v3 CSS directives with `@import "tailwindcss";` where appropriate.
- [ ] Move simple tokens from config to `@theme`.
- [ ] Move simple custom utilities to `@utility`.
- [ ] Replace `safelist` with `@source inline(...)`.
- [ ] Replace `content` path tuning with `@source`, `@source not`, or `source(none)` where needed.
- [ ] Replace `start-*`/`end-*` with `inset-s-*`/`inset-e-*`.
- [ ] Check dynamic classes in JSX/TSX/templating code.
- [ ] Prefer logical utilities in user-facing internationalized layouts.
- [ ] Validate with project build/lint and rerun the audit script.

## Dynamic class replacement pattern

Bad:

```tsx
<div className={`bg-${statusColor}-500 text-white`} />
```

Better:

```tsx
const statusClass = {
  success: "bg-green-500 text-white",
  warning: "bg-amber-500 text-white",
  danger: "bg-red-500 text-white",
} as const;

<div className={statusClass[status]} />
```

If the values truly come from a bounded external source, safelist the exact classes with `@source inline(...)` as in `assets/source-scanning-examples.css`.
