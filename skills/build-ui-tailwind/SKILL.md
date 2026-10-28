---
name: build-ui-tailwind
description: >-
  Builds, migrates, reviews, and debugs Tailwind CSS v4 projects with the
  CSS-first model: @import "tailwindcss", @theme, @utility, @custom-variant,
  @source, and the Vite, webpack, or PostCSS packages. Use when setting up
  Tailwind v4, migrating from v3 (tailwind.config.js, safelist, content,
  @tailwind directives), fixing classes missing from generated CSS, choosing
  v4.1-v4.3 utilities like logical spacing, masks, or scrollbars, or auditing a
  repo for v3 leftovers. Do not use for vanilla CSS, Bootstrap, unrelated
  bundler work, or v3 maintenance without migration.
license: MIT
compatibility: >-
  Optional Python 3.9+ run via uv for the bundled audit script.
metadata:
  author: ddlaws0n
  version: "0.2.0"
---

# Build UI with Tailwind CSS v4

Produce, migrate, or review Tailwind CSS work that follows v4 CSS-first conventions instead of v3-era habits.

Baseline: Tailwind CSS v4.3.0 (released 2026-05-08); the latest patch at the time of writing is v4.3.3. When the user asks for the literal latest release and network access is available, verify it from npm or the official Tailwind GitHub releases. Otherwise use the version already installed in the project, or the latest v4.3 patch.

## Workflow

1. **Classify the request**: new setup, v3-to-v4 migration, UI implementation, review/debugging, or design-system extension.
2. **Inspect the project**: `package.json` (including workspace packages), lockfiles, CSS entry files, `vite.config.*`, `webpack.config.*`, `postcss.config.*`, and any `tailwind.config.*`.
3. **Audit** existing projects with `uv run scripts/audit-tailwind-v4.py <project-root>` (see [Scripts](#scripts)). Treat findings as heuristics, not proof. For migrations and reviews, read `references/ANTI_PATTERNS.md`.
4. **Plan**: state whether the project should be v4 CSS-first, legacy-maintained, or mixed during migration. Pick one build integration for the detected build tool; do not present Vite, webpack, PostCSS, and the CLI as an equal menu unless no build tool is detectable.
5. **Implement** the smallest safe change that aligns the project with v4:
   - For v3-to-v4 migrations, start with `npx @tailwindcss/upgrade` (requires Node.js 20+) on a clean branch, then review the diff and finish what it misses by hand.
   - Use `@import "tailwindcss";` in the CSS entry file, with `@theme`, `@utility`, `@custom-variant`, `@source`, and CSS custom properties for customization.
   - Use `@tailwindcss/vite` for Vite, `@tailwindcss/webpack` for webpack 5 or Rspack (no official docs page yet; see `references/INTEGRATION_PLAYBOOK.md`), and `@tailwindcss/postcss` only when the pipeline requires PostCSS.
   - Do not create `tailwind.config.js` for a new v4 project unless a plugin or tool requires it. A retained config must be loaded explicitly with `@config`.
   - Replace v3 `safelist` and `content` with `@source inline(...)`, `@source`, `@source not "..."`, and `source(none)`.
   - Prefer logical utilities (`pbs-*`, `pbe-*`, `mbs-*`, `mbe-*`, `inline-*`, `block-*`, `inset-s-*`, `inset-e-*`) for internationalized UI, and `inset-s-*`/`inset-e-*` over deprecated `start-*`/`end-*`.
   - Use v4.1-v4.3 utilities when they fit, such as `text-shadow-*`, `mask-*`, colored shadows, `wrap-anywhere`, pointer and `user-invalid` variants, safe alignment, scrollbar utilities, `@container-size`, `zoom-*`, `tab-*`, and `font-features-*`.
   - Prefer named utilities and theme variables over arbitrary values, and preserve arbitrary-value syntax exactly.
6. **Validate**: run the project's build, lint, and test commands. Re-run the audit script for migrations and reviews. Fix invalid class syntax, source-scanning misses, and legacy config leftovers before finishing.
7. **Report** changed files, the integration choice, v4-specific decisions, validation results, and any remaining browser-support or dynamic-class risks.

## Scripts

- `scripts/audit-tailwind-v4.py`: read-only heuristic scan for v4 readiness issues: v3 `@tailwind` directives, legacy `safelist`/`content` config, deprecated `start-*`/`end-*`, dynamic template classes, a v3 `tailwindcss` dependency, missing integration packages, and a missing `@import "tailwindcss"`. It checks every `package.json` in nested workspaces and skips dependencies, build output, docs, and lockfiles.

  ```bash
  uv run scripts/audit-tailwind-v4.py <project-root>
  uv run scripts/audit-tailwind-v4.py <project-root> --format json
  uv run scripts/audit-tailwind-v4.py <project-root> --include-docs  # also scan docs/
  ```

## References

- Read `references/ANTI_PATTERNS.md` for migrations and reviews: legacy patterns, replacements, and a migration checklist.
- Read `references/INTEGRATION_PLAYBOOK.md` when installing or wiring Tailwind into Vite, webpack, PostCSS, or the CLI, or when retaining a `tailwind.config.*`.
- Read `references/TAILWIND_V4_LATEST_REFERENCE.md` for exact directive and utility syntax, and which release added a feature.
- Read `references/PATTERN_LIBRARY.md` when composing UI: when to use each modern pattern, with code in `assets/component-snippets.html` and `assets/component-styles.css`.
- Copy from `assets/` when creating files: `tailwind-v4-entry.css` (CSS entry with tokens), `vite.config.ts`, `webpack.config.js`, `postcss.config.mjs`, `source-scanning-examples.css` (`@source` and safelist forms), `component-snippets.html` (markup patterns), and `component-styles.css` (CSS-side `@variant` and `@utility` patterns).

## Gotchas

- Browser floor: Tailwind v4 requires Chrome 111, Safari 16.4, and Firefox 128. For older targets, stay on v3 or confirm the user accepts the floor. Some utilities wrap newer CSS features with narrower support; check them against the project's targets.
- Upgrading to v4.3.3 changes the default `font-sans` stack: Preflight now uses explicit platform fonts instead of `system-ui`, so expect visual diffs in text rendering.
- v4 does not auto-detect `tailwind.config.js`. `@config` does not restore `corePlugins`, `safelist`, or `separator`.
- `@source inline()` is the v4 safelist mechanism. Dynamic class names must become explicit class strings or be safelisted.
- `@container` creates an inline-size container. Use `@container-size` only when block-size units such as `cqb`/`cqh` are needed.
- `zoom-*` affects layout. Use `scale-*` for animation and visual-only scaling.
- Use `tabular-nums` before `font-features-['tnum']`.
- Use masks for decorative reveals and fades, never to hide important content. Use `scrollbar-none` sparingly because hidden scrollbars reduce affordance.
- Tailwind v4 is the preprocessor in most setups; do not layer Sass, Less, or Stylus on top unless the project already requires it.
- Prefer the latest v4.3 patch over a pinned older one; patches fix source scanning, JSX/MDX extraction, and arbitrary values.
