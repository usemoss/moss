# Moss Go SDK

This directory contains the in-progress Go SDK for Moss.

The first implementation track is intentionally:

- pure Go
- cloud-first
- compatible with the public repository

Current scope:

- typed client construction
- cloud index metadata reads
- cloud document reads
- cloud query

Deferred follow-up work:

- mutation flows (`CreateIndex`, `AddDocs`, `DeleteDocs`, `GetJobStatus`)
- examples
- integration tests
- local runtime loading/query parity
