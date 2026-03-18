# Changelog

## [1.0.0-beta.2] - 2026-02-03

- Fixed ESM related conflicts

## [1.0.0-beta.1] - 2026-01-05

- function-based API for programmatic usage
  - Exported `sync()` function for building and uploading in one call
  - Exported `buildJsonDocs()` function for building search index programmatically
  - Exported `uploadDocuments()` function for uploading documents programmatically
  - Exported `createIndex()` function for uploading an existing index file
  - Functions can be imported and called directly in code
  - Support for passing credentials via function options or environment variables
  - Functions return structured data (e.g., `{ success: boolean, count: number }`)