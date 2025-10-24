# CascadeFlow Assets

This directory contains brand assets and logos for CascadeFlow used across documentation and READMEs.

## Logo Files

### Main Logos

- **`CF_logo_bright.svg`** - CascadeFlow logo for light mode/bright backgrounds
- **`CF_logo_dark.svg`** - CascadeFlow logo for dark mode/dark backgrounds

### Platform Icons

- **`CF_python_color.svg`** - Python platform icon (color)
- **`CF_ts_color.svg`** - TypeScript platform icon (color)
- **`CF_n8n_color.svg`** - n8n integration icon (color)

## Usage

### Main Logo with Dark/Light Mode Support

```markdown
<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/assets/CF_logo_dark.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/assets/CF_logo_bright.svg">
  <img alt="CascadeFlow Logo" src=".github/assets/CF_logo_bright.svg" width="400">
</picture>
```

### Inline Platform Icons

```markdown
<img src=".github/assets/CF_python_color.svg" width="20" height="20" alt="Python"/>
<img src=".github/assets/CF_ts_color.svg" width="20" height="20" alt="TypeScript"/>
<img src=".github/assets/CF_n8n_color.svg" width="20" height="20" alt="n8n"/>
```

## Current Usage

These assets are used in:

- **Main README** (`/README.md`) - Logo header + navigation icons
- **TypeScript README** (`/packages/core/README.md`) - Logo header + TypeScript icon
- **n8n Integration README** (`/packages/integrations/n8n/README.md`) - Logo header + n8n icon

## Brand Guidelines

- **Logo Usage**: The main logo should be displayed at a width of 300-400px in README headers
- **Icon Usage**: Platform icons should be used at 20-24px for inline navigation
- **Colors**: All icons use official brand colors (Python blue/yellow, TypeScript blue, n8n pink/purple)
- **File Format**: All assets are SVG for scalability and quality at any size
