/**
 * Moss sidebar search webview script.
 * Loaded via webview.asWebviewUri — kept out of TS template literals so regex escapes are not mangled.
 */
(function () {
  const vscode = acquireVsCodeApi();
  const input = document.getElementById("query");
  const btn = document.getElementById("searchBtn");
  const meta = document.getElementById("meta");
  const indexPrep = document.getElementById("indexPrep");
  const errorBanner = document.getElementById("errorBanner");
  const emptyBlock = document.getElementById("emptyBlock");
  const emptyState = document.getElementById("emptyState");
  const resultList = document.getElementById("resultList");
  const mossSettingsLink = document.getElementById("mossSettingsLink");

  if (
    !input ||
    !btn ||
    !meta ||
    !errorBanner ||
    !emptyBlock ||
    !emptyState ||
    !resultList ||
    !mossSettingsLink
  ) {
    return;
  }

  const DEFAULT_EMPTY_HTML =
    "Run <strong>Moss: Index Workspace</strong> to index your files,<br/>then search here.";

  const prior = vscode.getState();
  if (prior && typeof prior.query === "string") {
    input.value = prior.query;
  }

  let selectedHitIndex = -1;
  const SEARCH_DEBOUNCE_MS = 320;
  let searchDebounceId = null;

  function persistQuery() {
    vscode.setState({ query: input.value });
  }

  function openSettingsClick(e) {
    e.preventDefault();
    vscode.postMessage({ type: "openMossSettings" });
  }
  mossSettingsLink.addEventListener("click", openSettingsClick);
  mossSettingsLink.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") openSettingsClick(e);
  });

  function setLoading(loading) {
    // Do not disable the query input while loading: disabling removes focus in the
    // webview, so live search would force a click back into the field after each query.
    btn.disabled = loading;
    btn.textContent = loading ? "Searching…" : "Search";
  }

  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.classList.add("visible");
  }

  function clearError() {
    errorBanner.textContent = "";
    errorBanner.classList.remove("visible");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /** Split path into directory (with trailing slash) + basename for display. */
  function splitPath(p) {
    const norm = String(p).replace(/\\/g, "/");
    const i = norm.lastIndexOf("/");
    if (i <= 0) {
      return { dir: "", base: norm || "" };
    }
    return { dir: norm.slice(0, i + 1), base: norm.slice(i + 1) };
  }

  /**
   * Wrap query terms (length >= 2) in <mark>; split on regex so we never inject HTML from the snippet.
   */
  function highlightSnippet(text, query) {
    const raw = String(text);
    const q = typeof query === "string" ? query : "";
    const terms = [
      ...new Set(
        q
          .trim()
          .toLowerCase()
          .split(/\s+/)
          .filter((t) => t.length >= 2)
      ),
    ].sort((a, b) => b.length - a.length);
    if (terms.length === 0) {
      return escapeHtml(raw);
    }
    const pattern = terms.map((t) => escapeRegExp(t)).join("|");
    if (!pattern) {
      return escapeHtml(raw);
    }
    const re = new RegExp("(" + pattern + ")", "gi");
    const parts = raw.split(re);
    return parts
      .map((part, i) => {
        if (i % 2 === 1) {
          return '<mark class="query-hit">' + escapeHtml(part) + "</mark>";
        }
        return escapeHtml(part);
      })
      .join("");
  }

  function hitRowDomId(hitIndex) {
    return "moss-hit-" + hitIndex;
  }

  function getResultRows() {
    return [...resultList.querySelectorAll(".result-row")];
  }

  function clearResultSelection() {
    selectedHitIndex = -1;
    resultList.removeAttribute("aria-activedescendant");
    getResultRows().forEach((el) => {
      el.classList.remove("result-row--selected");
      el.setAttribute("aria-selected", "false");
      el.tabIndex = -1;
    });
  }

  function applyResultSelection(focusSelected) {
    const focus = focusSelected !== false;
    const rows = getResultRows();
    rows.forEach((el, i) => {
      const on = i === selectedHitIndex;
      el.classList.toggle("result-row--selected", on);
      el.setAttribute("aria-selected", on ? "true" : "false");
      el.tabIndex = on ? 0 : -1;
      if (on && focus) {
        el.focus();
        el.scrollIntoView({ block: "nearest" });
      }
    });
    if (selectedHitIndex >= 0 && rows[selectedHitIndex]) {
      const id = rows[selectedHitIndex].id;
      if (id) resultList.setAttribute("aria-activedescendant", id);
    } else {
      resultList.removeAttribute("aria-activedescendant");
    }
  }

  function openHitIndex(idx) {
    if (typeof idx !== "number" || !Number.isInteger(idx) || idx < 0) return;
    vscode.postMessage({ type: "openResult", hitIndex: idx });
  }

  function flushLiveQuery() {
    if (searchDebounceId !== null) {
      clearTimeout(searchDebounceId);
      searchDebounceId = null;
    }
    const text = input.value.trim();
    clearError();
    persistQuery();
    vscode.postMessage({ type: "query", text });
  }

  function scheduleLiveQuery() {
    if (searchDebounceId !== null) clearTimeout(searchDebounceId);
    searchDebounceId = setTimeout(() => {
      searchDebounceId = null;
      flushLiveQuery();
    }, SEARCH_DEBOUNCE_MS);
  }

  if (prior && typeof prior.query === "string" && prior.query.trim() !== "") {
    scheduleLiveQuery();
  }

  btn.addEventListener("click", () => flushLiveQuery());
  input.addEventListener("input", () => {
    clearResultSelection();
    persistQuery();
    scheduleLiveQuery();
  });
  input.addEventListener("focus", () => {
    clearResultSelection();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      flushLiveQuery();
      return;
    }
    if (e.key === "ArrowDown" && resultList.style.display !== "none") {
      const rows = getResultRows();
      if (rows.length === 0) return;
      e.preventDefault();
      selectedHitIndex = 0;
      applyResultSelection();
    }
  });

  resultList.addEventListener("keydown", (e) => {
    const rows = getResultRows();
    if (rows.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (selectedHitIndex < rows.length - 1) {
        selectedHitIndex += 1;
        applyResultSelection();
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (selectedHitIndex > 0) {
        selectedHitIndex -= 1;
        applyResultSelection();
      } else {
        clearResultSelection();
        input.focus();
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      const idx = parseInt(
        rows[selectedHitIndex]?.getAttribute("data-hit-index") || "",
        10
      );
      openHitIndex(idx);
    } else if (e.key === "Escape") {
      e.preventDefault();
      clearResultSelection();
      input.focus();
    }
  });

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || typeof msg.type !== "string") return;

    if (msg.type === "loading") {
      setLoading(!!msg.loading);
      if (msg.loading) {
        clearResultSelection();
        meta.textContent = "";
        if (indexPrep) {
          indexPrep.textContent = "";
          indexPrep.classList.remove("visible");
        }
        resultList.innerHTML = "";
        resultList.removeAttribute("aria-activedescendant");
        resultList.style.display = "none";
        emptyBlock.style.display = "none";
      }
      return;
    }

    if (msg.type === "localIndexLoading") {
      if (!indexPrep) return;
      const t = typeof msg.text === "string" ? msg.text : "";
      if (t) {
        indexPrep.textContent = t;
        indexPrep.classList.add("visible");
      } else {
        indexPrep.textContent = "";
        indexPrep.classList.remove("visible");
      }
      return;
    }

    if (msg.type === "clearError") {
      clearError();
      return;
    }

    if (msg.type === "clearResults") {
      clearResultSelection();
      clearError();
      meta.textContent = "";
      if (indexPrep) {
        indexPrep.textContent = "";
        indexPrep.classList.remove("visible");
      }
      resultList.innerHTML = "";
      resultList.removeAttribute("aria-activedescendant");
      resultList.style.display = "none";
      emptyBlock.style.display = "block";
      emptyState.innerHTML = DEFAULT_EMPTY_HTML;
      return;
    }

    if (msg.type === "error") {
      clearResultSelection();
      showError(msg.message || "Search failed.");
      resultList.style.display = "none";
      resultList.innerHTML = "";
      resultList.removeAttribute("aria-activedescendant");
      emptyBlock.style.display = "block";
      emptyState.innerHTML =
        "Could not complete this search. Fix the issue above, then try again.";
      return;
    }

    if (msg.type === "results") {
      clearResultSelection();
      const hits = Array.isArray(msg.hits) ? msg.hits : [];
      const queryText = typeof msg.query === "string" ? msg.query : "";
      if (hits.length === 0) {
        emptyBlock.style.display = "block";
        emptyState.innerHTML =
          "No results. Try different wording or run <strong>Moss: Index Workspace</strong>.";
        resultList.style.display = "none";
        resultList.innerHTML = "";
        resultList.removeAttribute("aria-activedescendant");
        const t = typeof msg.timeMs === "number" ? msg.timeMs + " ms" : "";
        meta.textContent = t ? "0 results · " + t : "0 results";
        return;
      }

      emptyBlock.style.display = "none";
      resultList.style.display = "flex";
      resultList.innerHTML = hits
        .map((h) => {
          const rawPath = h.path || "";
          const { dir, base } = splitPath(rawPath);
          const pathHtml =
            (dir
              ? '<span class="result-dir">' + escapeHtml(dir) + "</span>"
              : "") +
            '<span class="result-base">' +
            escapeHtml(base || rawPath) +
            "</span>";
          const line = escapeHtml(String(h.lineLabel ?? ""));
          const score =
            typeof h.score === "number" ? h.score.toFixed(3) : "";
          const snippet = highlightSnippet(h.snippet || "", queryText);
          const domId = hitRowDomId(h.index);
          return (
            '<li class="result-row" id="' +
            domId +
            '" role="option" tabindex="-1" aria-selected="false" data-hit-index="' +
            h.index +
            '">' +
            '<div class="result-path">' +
            pathHtml +
            "</div>" +
            '<div class="result-sub">Lines ' +
            line +
            (score ? " · score " + escapeHtml(score) : "") +
            "</div>" +
            '<div class="result-snippet">' +
            snippet +
            "</div>" +
            "</li>"
          );
        })
        .join("");

      resultList.querySelectorAll(".result-row").forEach((el) => {
        el.addEventListener("click", () => {
          const idx = parseInt(el.getAttribute("data-hit-index"), 10);
          const rows = getResultRows();
          selectedHitIndex = rows.indexOf(el);
          applyResultSelection(false);
          openHitIndex(idx);
        });
      });

      const t = typeof msg.timeMs === "number" ? msg.timeMs + " ms" : "";
      meta.textContent =
        hits.length +
        " result" +
        (hits.length === 1 ? "" : "s") +
        (t ? " · " + t : "");
      return;
    }
  });
})();
