# Tailwind v4.3+ Integration Playbook

Use this when installing or wiring Tailwind in a project. Always prefer the project's existing package manager and conventions. The config files referenced below live in `assets/`; copy them rather than retyping.

## Detect the build tool

Inspect, in order:

1. `package.json` scripts and dependencies, including workspace packages.
2. `vite.config.*` for Vite.
3. `webpack.config.*`, custom Next webpack config, or framework-specific webpack hooks.
4. `postcss.config.*` when CSS already flows through PostCSS.
5. Static or minimal sites that may only need the CLI.

Pick one integration path. Avoid stacking integrations unless the project already does so and you have a concrete reason.

## Vite

Use `@tailwindcss/vite` for Vite projects.

```bash
npm install tailwindcss @tailwindcss/vite
```

Add the plugin as in `assets/vite.config.ts` (merge into the existing config; keep other plugins). Use `assets/tailwind-v4-entry.css` as the CSS entry.

## Webpack

Use `@tailwindcss/webpack` when the project has a webpack 5 or Rspack pipeline you control. It has no official docs page yet; its usage comes from PR #19610.

```bash
npm install tailwindcss @tailwindcss/webpack css-loader mini-css-extract-plugin
```

Add the CSS rule from `assets/webpack.config.js`: list `@tailwindcss/webpack` last in the `use` array so it processes CSS before `css-loader` (webpack applies loaders right to left).

## PostCSS

Use PostCSS only when the framework or build pipeline requires it.

```bash
npm install tailwindcss @tailwindcss/postcss postcss
```

Use `assets/postcss.config.mjs`. Remove `postcss-import` and `autoprefixer`; v4 handles imports and vendor prefixing.

## CLI/static builds

For static sites or simple build scripts, use the Tailwind CLI package if appropriate:

```bash
npm install tailwindcss @tailwindcss/cli
npx @tailwindcss/cli -i ./src/input.css -o ./dist/output.css --watch
```

## CSS entry and source scanning

- Start from `assets/tailwind-v4-entry.css`: `@import "tailwindcss";` plus `@theme` tokens.
- Use `assets/source-scanning-examples.css` for `source(none)` with explicit `@source` paths (monorepos, multiple entry files), `@source not` exclusions, and `@source inline(...)` safelists, including brace-expanded ranges.
- Replace a v3 `safelist: [...]` in `tailwind.config.js` with `@source inline("...")` in the CSS entry.

## Existing `tailwind.config.*` files

When a v4 project still has a JavaScript config file, remember that v4 does not auto-detect it. Load a retained config explicitly from the CSS entry file using a path relative to that stylesheet:

```css
@import "tailwindcss";
@config "../tailwind.config.js";
```

Before retaining it:

- Inspect whether plugins or theme extensions still need it; do not keep it merely because the old file exists.
- Move tokens into `@theme` and simple custom utilities into `@utility` where practical.
- Move safelists into `@source inline(...)`.
- Migrate unsupported legacy options such as `corePlugins`, `safelist`, and `separator`; `@config` does not restore support for them.
- Validate the generated CSS so a missed config does not silently drop plugins or theme extensions.

## Validation commands

Prefer the project's existing commands:

```bash
npm run build
npm run lint
npm test
```

If no script exists, use the narrowest reasonable check, such as a framework build or TypeScript check. Re-run `uv run scripts/audit-tailwind-v4.py <project-root>` for migrations.
