# Frontend Quality Tooling Changes

## Summary

Added code quality tooling to the frontend: Prettier for automatic formatting and ESLint for JavaScript linting, along with a development script to run both checks.

---

## New Files

### `frontend/package.json`
Defines the frontend as a Node package and exposes four npm scripts:
- `npm run format` — auto-format all files with Prettier (in-place)
- `npm run format:check` — check formatting without modifying files (CI-safe)
- `npm run lint` — lint `script.js` with ESLint
- `npm run quality` — run both `format:check` and `lint` in sequence

Dev dependencies: `prettier@^3.3.3`, `eslint@^8.57.0`.

### `frontend/.prettierrc`
Prettier configuration matching the existing code style:
- 4-space indentation
- Single quotes
- Semicolons
- Trailing commas where valid in ES5
- `lf` line endings

### `frontend/.eslintrc.json`
ESLint configuration for browser JavaScript:
- Extends `eslint:recommended`
- Browser + ES2021 globals
- `marked` declared as a read-only global (loaded via CDN)
- Rules: `no-unused-vars` (warn), `no-console` (warn), `eqeqeq` (error)

### `frontend/scripts/quality-check.sh`
Shell script wrapping the npm quality checks. Installs dependencies automatically if `node_modules` is missing.

Usage:
```bash
# Check formatting and lint (exits non-zero on failure)
./frontend/scripts/quality-check.sh

# Auto-fix formatting issues
./frontend/scripts/quality-check.sh --fix
```

---

## Modified Files

### `frontend/script.js`
Applied Prettier formatting fixes:
- Removed trailing whitespace on blank lines (lines 35–36, line 82)
- Consolidated double blank lines between function blocks into single blank lines (after `setupEventListeners`, before `// Chat Functions`)

### `frontend/index.html` / `frontend/style.css`
No formatting changes needed — both files already conformed to the Prettier configuration.

---

## How to Run Quality Checks

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Check format + lint
npm run quality

# Auto-format
npm run format

# Lint only
npm run lint
```

Or use the convenience script from the project root:
```bash
./frontend/scripts/quality-check.sh
```
