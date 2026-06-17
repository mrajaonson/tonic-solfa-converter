# Solfadoc — JetBrains Plugin

Syntax highlighting and code reformatting for `.solfa` files (tonic solfa notation) in JetBrains IDEs (IntelliJ IDEA, etc.).

## Features

- **Syntax highlighting** — voice labels, notes, barlines, beat separators, dynamics, navigation markers, lyrics, and section headers each get distinct colours; Dark and Light colour schemes included
- **Reformat Code** (Ctrl+Alt+L) — aligns all tonic solfa blocks like a table: voice labels, barlines, and beat separators line up across every block in the file; lyrics are indented to the first note column (lines in the `[notes]` section are left untouched)

## Build

This project uses Gradle. The plugin is a subproject under `jetbrains/`.

```shell
# Build the distributable zip
./gradlew :jetbrains:buildPlugin

# Output: jetbrains/build/distributions/jetbrains.zip
```

## Installation

1. Build the plugin (see above)
2. In your JetBrains IDE: **Settings → Plugins → ⚙ → Install Plugin from Disk…**
3. Select `jetbrains/build/distributions/jetbrains.zip`

## Development

```shell
./gradlew :jetbrains:compileKotlin   # compile only
./gradlew :jetbrains:test            # run formatter tests
./gradlew :jetbrains:runIde          # launch a sandboxed IDE instance with the plugin loaded
```

Tests live in `jetbrains/src/test/kotlin/org/solfadoc/format/SolfaFormatterTest.kt` and use JUnit 5.

## File format

Files use the `.solfa` extension and are automatically detected as `Solfadoc` language.
