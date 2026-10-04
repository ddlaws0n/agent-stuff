# Tailwind v4.3 Pattern Library

When to use each modern Tailwind pattern. The code lives in `assets/component-snippets.html` (markup) and `assets/component-styles.css` (CSS-side patterns); each heading below matches a comment heading in those files. Syntax details are in `references/TAILWIND_V4_LATEST_REFERENCE.md`. Adapt tokens, colors, and layout to the project rather than pasting snippets unchanged.

## Hero over image: masks + text shadow + logical spacing

- Use text shadows for text over images, video, or busy backgrounds. Prefer small sizes (`text-shadow-2xs` to `text-shadow-sm`) in product UI; avoid large, muddy effects.
- Use masks for decorative fades and reveals only. Never mask content the user needs. Test complex artwork in Safari, Chromium, and Firefox.

## Colored glow shadow

Use colored and opacity-aware shadows for glows, active states, brand treatments, and illustrations. A glow must never be the only visible focus indicator.

## Logical positioning (RTL-safe)

Prefer logical spacing, sizing, and inset utilities for internationalized UI. Use physical utilities only when the physical screen direction is intentional. Replace legacy `start-*`/`end-*` with `inset-s-*`/`inset-e-*`.

## Responsive cards: container queries + wrap-anywhere

- Use `@container` for most responsive components.
- Use `wrap-anywhere` (with `min-w-0` on flex/grid children) for constrained cards, tables, filenames, email addresses, URLs, and chat output.

## Size container only when block-size units matter

Use `@container-size` only when block-size or height-derived container units (`cqb`, `cqh`) are required. Do not use it for ordinary width-based card layouts.

## Safe alignment in a constrained, scrollable container

Use `*-center-safe` alignment where centered content can overflow, so it stays reachable instead of being clipped at the start edge.

## Last-baseline alignment for wrapping heading/metadata rows

Use `items-baseline-last` when wrapped headings sit beside metadata that should align to the last line.

## Pointer-aware controls

Use pointer variants to enlarge hit targets and spacing on coarse pointers. Do not use them to hide critical functionality.

## Form validation after user interaction

Use `user-invalid`/`user-valid` instead of `invalid`/`valid` so errors appear only after the user interacts. Use `noscript`, `inverted-colors`, and `details-content` for progressive enhancement and accessibility-sensitive states.

## Numbers and OpenType features

Use `tabular-nums` for routine numeric alignment. Reserve `font-features-*` for uncommon or font-specific features such as stylistic sets.

## Stable scrolling panel

- Use scrollbar utilities for panels, modals, logs, sidebars, and other controlled scroll regions.
- Use `scrollbar-gutter-stable` to prevent layout shift when a scrollbar appears.
- Use `scrollbar-none` sparingly; hidden scrollbars reduce affordance.

## Code/log panel with tab size

Use `tab-*` for `<pre>`, code blocks, logs, terminals, and editor-like surfaces that render real tab characters.

## Layout-affecting zoom for previews and minimaps

Use `zoom-*` when scaled content should affect layout, such as preview canvases, minimaps, or dense dashboards. Use `scale-*` for animation and visual-only scaling.

## Neutral palette usage

Use `mauve`, `olive`, `mist`, and `taupe` as neutral systems, not random accents. Pick one neutral family per system or surface unless deliberately building multiple themes.

## CSS-side reusable button with compound variant

Use CSS-side `@variant` when a reusable class is justified (the comma form needs v4.3+; on older versions write one `@variant` block per variant): shared components, styling third-party markup, or small internal abstractions. Prefer utility classes in markup for one-off components.

## Custom functional utility with its own name

Add functional utilities with `@utility name-*` only for repeated needs the built-ins do not cover; they must use `--value()` (required since v4.3). Add a default (v4.3+) only when it is obvious: `--value(integer, --default(4))` makes the bare class (`indent-step`) use 4, and `--modifier(integer, --default(1))` works the same way for modifiers.
