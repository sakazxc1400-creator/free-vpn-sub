import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL("./site", import.meta.url)),
  base: "./",
  build: {
    outDir: "../docs",
    emptyOutDir: true,
    assetsDir: "build",
  },
});
