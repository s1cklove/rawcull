import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built straight into the Python package so `pip install` / PyInstaller pick it up.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../src/rawcull/web",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
});
