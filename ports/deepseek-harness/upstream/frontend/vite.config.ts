import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { preparePdfViewer } from "./scripts/preparePdfViewer";
import { cpSync, mkdirSync } from "node:fs";
export default defineConfig({
  base: "/paper-research-coach/",
  plugins: [
    react(),
    {
      name: "pdf-support-assets",
      apply: "build",
      async closeBundle() {
        const dest = "../src/paper_research_coach/static/pdf-assets";
        mkdirSync(dest, { recursive: true });
        for (const part of ["cmaps", "standard_fonts", "wasm"])
          cpSync("node_modules/pdfjs-dist/" + part, dest + "/" + part, {
            recursive: true,
          });
        await preparePdfViewer("../src/paper_research_coach/static/pdf-viewer");
      },
    },
  ],
  build: {
    outDir: "../src/paper_research_coach/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: (id) => (id.includes("/node_modules/pdfjs-dist/") ? "pdf" : undefined),
      },
    },
  },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
