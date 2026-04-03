# Phase 1 spike — extension host notes

## Purpose

Confirm that **`@inferedge-rest/moss`** and **`@inferedge/moss`** both work inside the **VS Code extension host** (Node, ESM). The spike creates a throwaway index **`vscode-moss-phase1-spike`**, runs **`loadIndex` + `query`**, and records any failure.

## If `loadIndex` or local `query` fails

1. Read the full error in **Output → Moss Spike**.
2. Common causes: Node ABI / native addon constraints in the host, WASM path differences, or network/proxy blocking the download step.
3. The spike **automatically retries** with **`query` only** (cloud path), matching the idea of a **`queryMode: cloud`** fallback described in the implementation plan.
4. For product defaults: if local query is **unreliable** in the host after investigation, ship with **`moss.queryMode` default `cloud`** until fixed; keep the REST + SDK split so switching back to **`local`** is a small change.

## Index cleanup

The spike **deletes** index `vscode-moss-phase1-spike` before recreating it each run. You can also remove it from the Moss dashboard if needed.

## ESM

This extension uses **`"type": "module"`** because both Moss packages ship as ESM. The compiled **`out/extension.js`** is emitted as ESM (`NodeNext`).
