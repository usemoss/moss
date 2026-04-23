import { defineConfig } from "vite";

export default defineConfig({
  optimizeDeps: {
    exclude: ["@moss-dev/moss-web"],
  },
  build: {
    rollupOptions: {
      input: {
        main: new URL("./index.html", import.meta.url).pathname,
        "load-and-query": new URL(
          "./load_and_query_sample.html",
          import.meta.url
        ).pathname,
        comprehensive: new URL(
          "./comprehensive_sample.html",
          import.meta.url
        ).pathname,
        "metadata-filtering": new URL(
          "./metadata_filtering_sample.html",
          import.meta.url
        ).pathname,
      },
    },
  },
});
