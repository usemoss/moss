# Changelog

All notable changes to `vitepress-plugin-moss` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0-beta.2] - 2026-04-28

### Changed
- Swapped runtime browser SDK from `@inferedge/moss` to `@moss-dev/moss-web

---

## [1.0.0-beta.1] - 2026-03-05

### Added
- Initial beta release of the Moss semantic search plugin for VitePress
- `MossPlugin` VitePress plugin with automatic markdown indexing via `@moss-tools/md-indexer`
- `Search.vue` component — full search modal with keyboard navigation
- `SearchButton.vue` component — trigger button for the search modal
- TypeScript types exported via `./types`
- Support for both ESM and CJS consumers
- Configurable `apiKey`, `indexId`, `placeholder`, and `maxResults` options

---
