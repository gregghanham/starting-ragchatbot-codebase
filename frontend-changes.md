# Frontend Changes

## Quality Tooling

Added code quality tooling to the frontend: Prettier for automatic formatting and ESLint for JavaScript linting, along with a development script to run both checks.

---

### New Files

#### `frontend/package.json`
Defines the frontend as a Node package and exposes four npm scripts:
- `npm run format` — auto-format all files with Prettier (in-place)
- `npm run format:check` — check formatting without modifying files (CI-safe)
- `npm run lint` — lint `script.js` with ESLint
- `npm run quality` — run both `format:check` and `lint` in sequence

Dev dependencies: `prettier@^3.3.3`, `eslint@^8.57.0`.

#### `frontend/.prettierrc`
Prettier configuration matching the existing code style:
- 4-space indentation
- Single quotes
- Semicolons
- Trailing commas where valid in ES5
- `lf` line endings

#### `frontend/.eslintrc.json`
ESLint configuration for browser JavaScript:
- Extends `eslint:recommended`
- Browser + ES2021 globals
- `marked` declared as a read-only global (loaded via CDN)
- Rules: `no-unused-vars` (warn), `no-console` (warn), `eqeqeq` (error)

#### `frontend/scripts/quality-check.sh`
Shell script wrapping the npm quality checks. Installs dependencies automatically if `node_modules` is missing.

Usage:
```bash
# Check formatting and lint (exits non-zero on failure)
./frontend/scripts/quality-check.sh

# Auto-fix formatting issues
./frontend/scripts/quality-check.sh --fix
```

---

### Modified Files

#### `frontend/script.js`
Applied Prettier formatting fixes:
- Removed trailing whitespace on blank lines (lines 35–36, line 82)
- Consolidated double blank lines between function blocks into single blank lines (after `setupEventListeners`, before `// Chat Functions`)

#### `frontend/index.html` / `frontend/style.css`
No formatting changes needed — both files already conformed to the Prettier configuration.

---

### How to Run Quality Checks

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

---

## Feature 1 — Dark/Light Mode Toggle Button

Added a toggle button in the top-right corner to switch between dark and light themes.

### Files Modified

#### `frontend/style.css`
- Added `:root[data-theme="light"]` with a light colour palette.
- Added smooth `background-color`/`color`/`border-color` transitions on key layout elements.
- Added `.theme-toggle` styles: fixed circular button (40×40px) top-right with sun/moon icon animation.
- Sun/moon icons fade and rotate in/out over 0.25–0.3s.
- Bumped CSS cache-buster to `v=10`.

#### `frontend/index.html`
- Added `<button class="theme-toggle" id="themeToggle">` with `aria-label` for screen readers and two stacked SVGs (sun/moon, both `aria-hidden`).
- Bumped cache-busters to `v=10`.

#### `frontend/script.js`
- `initTheme()` — reads `localStorage` on page load and sets `data-theme="light"` if saved.
- `toggleTheme()` — toggles `data-theme` on `<html>` and persists the choice.
- Wired to the toggle button in `setupEventListeners()`.

---

## Feature 2 — Complete Light Theme CSS Variables

Completed and hardened the light theme so every colour in the stylesheet adapts correctly.

### Files Modified

#### `frontend/style.css`

**CSS variable refactor in `:root` (dark theme):**
- Added `--code-bg: rgba(0, 0, 0, 0.25)` — replaces hardcoded `rgba(0,0,0,0.2)` on code/pre blocks.
- Added `--source-hover-bg: #475569` and `--source-hover-text: #e2e8f0` — replaces hardcoded hover colours on source-link chips.
- Grouped variables by category (brand, backgrounds, typography, borders, messages, etc.) with comments.

**Light theme overrides in `:root[data-theme="light"]`:**

| Variable | Light value | Rationale |
|---|---|---|
| `--primary-color` | `#1d4ed8` | Darker blue ≈ 5.5:1 contrast on white (WCAG AA) |
| `--primary-hover` | `#1e40af` | Consistent darker hover for light bg |
| `--focus-ring` | `rgba(29, 78, 216, 0.2)` | Matches new primary |
| `--background` | `#f8fafc` | Near-white page background |
| `--surface` | `#ffffff` | Pure white card/sidebar surfaces |
| `--surface-hover` | `#f1f5f9` | Subtle hover tint |
| `--text-primary` | `#1e293b` | Dark slate ≈ 16:1 on white |
| `--text-secondary` | `#475569` | Medium slate ≈ 5.9:1 on white (WCAG AA) |
| `--border-color` | `#e2e8f0` | Soft light-gray borders |
| `--shadow` | `rgba(0,0,0,0.08)` | Lighter shadow for light surfaces |
| `--user-message` | `#1d4ed8` | Matches darker primary |
| `--assistant-message` | `#f1f5f9` | Light tint for assistant bubbles |
| `--code-bg` | `rgba(15,23,42,0.06)` | Subtle tint for inline/block code |
| `--source-hover-bg` | `#cbd5e1` | Light gray chip hover |
| `--source-hover-text` | `#1e293b` | Dark text on light chip |
| `--welcome-bg` | `#eff6ff` | Light blue tint for welcome banner |
| `--welcome-border` | `#1d4ed8` | Matches lighter primary |

**Hardcoded colour replacements:**
- `.sources-content a:hover` — was `background: #475569; color: #e2e8f0`. Now uses `var(--source-hover-bg)` and `var(--source-hover-text)`.
- `.message-content code` and `.message-content pre` — was `rgba(0,0,0,0.2)`. Now uses `var(--code-bg)`.
