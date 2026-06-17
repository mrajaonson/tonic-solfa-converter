# Solfadoc — VS Code Extension

Syntax highlighting and document formatting for `.solfa` files (tonic solfa notation).

## Features

- **Syntax highlighting** — voice labels, notes, barlines, beat separators, dynamics, navigation markers, lyrics, and section headers each get distinct colours
- **Document formatter** (Shift+Alt+F / "Format Document") — aligns all tonic solfa blocks like a table: voice labels, barlines, and beat separators line up across every block in the file; lyrics are indented to the first note column

## Installation

```shell
npm install
npm run package        # produces solfadoc-x.x.x.vsix
```

Then install the `.vsix` in VS Code: **Extensions → ⋯ → Install from VSIX…**

## Development

```shell
npm run compile        # one-shot TypeScript build
npm run watch          # rebuild on save
npm test               # compile and run formatter tests
```

Tests live in `src/test/formatter.test.ts` and use Node's built-in test runner (`node:test`) — no extra dependencies required.

## File format

Files use the `.solfa` extension and are automatically detected as `Solfadoc` language.
