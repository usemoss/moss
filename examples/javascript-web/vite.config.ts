import { defineConfig } from "vite";
import { resolve } from "path";
export default defineConfig({
  optimizeDeps: {
    exclude: ["@moss-dev/moss-web"],
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        "load-and-query": resolve(__dirname, "load_and_query_sample.html"),
        comprehensive: resolve(__dirname, "comprehensive_sample.html"),
        "metadata-filtering": resolve(
          __dirname,
          "metadata_filtering_sample.html"
        ),
      },
    },
  },
});
