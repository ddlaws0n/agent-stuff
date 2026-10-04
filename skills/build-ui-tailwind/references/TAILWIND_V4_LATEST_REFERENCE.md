# Tailwind CSS v4.3+ Agent Reference

API and syntax facts for Tailwind v4.1-v4.3. Use it to check which release added a feature and the exact class or directive syntax. For when to use each feature and worked examples, read `references/PATTERN_LIBRARY.md`; copy-ready files are in `assets/`.

## Baseline

- Baseline: Tailwind CSS v4.3.0, released 2026-05-08; the latest patch at the time of writing is v4.3.3.
- In practice, use the latest v4 patch available in the project or package registry. If network access is available and the user asks for the current latest, verify before installing.
- Browser floor: Chrome 111, Safari 16.4, Firefox 128.
- v4.1-v4.3 is where most post-v4.0 agent-relevant feature work landed.

## Release map for agent decisions

<!-- prettier-ignore -->
| Release | Agent-relevant additions |
|-|-|
| v4.1 | `text-shadow-*`, `mask-*`, colored and opacity-aware shadows, `wrap-*`, pointer and `any-pointer-*` variants, `user-valid`/`user-invalid`, `noscript`, `inverted-colors`, `details-content`, safe alignment, last-baseline alignment (`items-baseline-last`, `self-baseline-last`), `@source inline()`, `@source not`, `@source not inline()` |
| v4.2 | mauve/olive/mist/taupe palettes, `@tailwindcss/webpack`, logical block/inline spacing/sizing/inset utilities, `font-features-*`, deprecation of `start-*`/`end-*` in favor of `inset-s-*`/`inset-e-*` |
| v4.3 | scrollbar utilities, `@container-size`, `zoom-*`, `tab-*`, compound (comma) and stacked (colon) CSS-side `@variant`, `--default()` for functional `@utility` definitions; 4.3.1: `@apply` works with CSS mixins, CLI `--silent`, a later `@source` can re-include paths excluded by `@source not`; 4.3.3: CLI `--watch --poll`, Preflight `font-sans` uses explicit platform fonts instead of `system-ui` |

## CSS-first configuration

The CSS entry starts with `@import "tailwindcss";`. Starter file: `assets/tailwind-v4-entry.css`.

<!-- prettier-ignore -->
| Directive | Purpose |
|-|-|
| `@theme { --color-*: ...; --font-*: ...; }` | Design tokens; each variable generates matching utilities |
| `@utility name { ... }` | Static custom utility that works with variants |
| `@utility name-* { prop: --value(integer); }` | Functional custom utility; `--value(...)` resolves the class suffix and is required in functional utilities since v4.3 |
| `--value(integer, --default(4))` | v4.3+: value used for the bare class (`name` alone); also works in `--modifier(integer, --default(1))` |
| `@custom-variant name (selector-or-at-rule);` | Custom variant |
| `@variant hover { ... }` | Apply a variant inside custom CSS |
| `@variant hover, focus { ... }` / `@variant dark:hover { ... }` | v4.3+: comma form applies the styles to each variant (compound); colon form stacks variants |
| `@source`, `@source not`, `@source inline(...)` | Source scanning control (below) |
| `@reference "../app.css";` | Theme and utility access (`@apply`, `theme()`) in Vue/Svelte `<style>` blocks and CSS modules without duplicating CSS output |
| `@plugin "@tailwindcss/typography";` | Load a JavaScript plugin |
| `@config "../tailwind.config.js";` | Load a retained JavaScript config; v4 never auto-detects it |
| `--spacing(n)` | Theme spacing function; compiles to `calc(var(--spacing) * n)` |

Do not redefine built-in utilities (for example `tab-*`) with `@utility`; give custom utilities their own names. Worked examples: `assets/component-styles.css`.

## Source scanning

<!-- prettier-ignore -->
| Syntax | Effect |
|-|-|
| `@source "../path";` | Add a path to automatic detection |
| `@source not "../path";` | Exclude a path; since 4.3.1 a later `@source` can re-include paths inside it |
| `@import "tailwindcss" source(none);` | Disable automatic detection; only explicit `@source` paths are scanned |
| `@source inline("a b c");` | Safelist exact classes |
| `@source inline("{hover:,focus:,}bg-red-{50,{100..900..100},950}");` | Brace expansion: `{a,b}` alternatives, `{start..end..step}` ranges, `{x,}` optional prefix |

Dynamic class names (`` `bg-${color}-500` ``) are invisible to the scanner: map them to complete class strings or safelist them. Examples: `assets/source-scanning-examples.css`.

## Utility syntax

<!-- prettier-ignore -->
| Area | Syntax | Notes |
|-|-|-|
| Text shadow | `text-shadow-{2xs,xs,sm,md,lg}`, opacity modifier `text-shadow-md/40` | v4.1 |
| Masks | `mask-{t,b,l,r,x,y}-from-<n>%`, `mask-{side}-to-<n>%` | v4.1 |
| Colored shadows | `drop-shadow-lg/25 drop-shadow-sky-500`; `shadow-<color>`, `inset-shadow-<color>/<opacity>` | Size and color are separate classes |
| Wrapping | `wrap-anywhere`, `wrap-break-word` | Pair with `min-w-0` in flex/grid children |
| Logical spacing | `pbs-*`, `pbe-*`, `mbs-*`, `mbe-*`; scroll padding/margin `scroll-pbs-*`, `scroll-pbe-*`, `scroll-mbs-*`, `scroll-mbe-*` | v4.2; block-start/end |
| Logical sizing | `inline-*`, `min-inline-*`, `max-inline-*`, `block-*`, `min-block-*`, `max-block-*` | v4.2; `block-size-*` is not a utility |
| Logical inset | `inset-s-*`, `inset-e-*`, `inset-bs-*`, `inset-be-*` | v4.2; `inset-s-*`/`inset-e-*` replace deprecated `start-*`/`end-*` |
| Logical borders | `border-bs-<color>`, `border-be-<color>` | v4.2 |
| Containers | `@container` (inline-size), `@container-size` (inline and block size, v4.3), `@md:`/`@xl:` variants, `cqb`/`cqh` units | |
| Safe alignment | `items-center-safe`, `justify-center-safe` | v4.1 |
| Last baseline | `items-baseline-last`, `self-baseline-last` | v4.1 |
| Pointer variants | `pointer-fine:`, `pointer-coarse:`, `pointer-none:`, `any-pointer-*:` | v4.1; `any-pointer-*` matches if any input device qualifies |
| Form state | `user-valid:`, `user-invalid:` | Match only after user interaction |
| Environment | `noscript:`, `inverted-colors:`, `details-content:` | v4.1 |
| Numbers | `tabular-nums` | Built-in numeric variant |
| OpenType | `font-features-['ss01','cv02']` | v4.2; arbitrary feature list |
| Tab size | `tab-<n>` (for example `tab-4`) | v4.3; `tab-size` |
| Scrollbars | `scrollbar-auto`, `scrollbar-thin`, `scrollbar-none`, `scrollbar-gutter-auto`, `scrollbar-gutter-stable`, `scrollbar-gutter-both`, `scrollbar-thumb-<color>`, `scrollbar-track-<color>` | v4.3 |
| Zoom | `zoom-<n>` (for example `zoom-75`, `zoom-125`) | v4.3; CSS `zoom` affects layout, unlike `scale-*` |
| Neutral palettes | `mauve`, `olive`, `mist`, `taupe` (`50`-`950`) | v4.2 |

## Upgrade tool and CLI

- `npx @tailwindcss/upgrade` (requires Node.js 20+) migrates a v3 project: dependencies, config to CSS, and template class renames. Run it on a clean branch, then review the diff.
- CLI: `npx @tailwindcss/cli -i in.css -o out.css --watch --poll` polls for changes where file events are unreliable (4.3.3); `--silent` suppresses build output (4.3.1).
- `@tailwindcss/webpack` has no official docs page; usage comes from PR #19610. Its peers are webpack 5 or Rspack.
