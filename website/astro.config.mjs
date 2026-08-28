import { defineConfig } from "astro/config";

const site = process.env.PUBLIC_SITE_URL ?? "https://xzx34.github.io";
const base = process.env.PUBLIC_BASE_PATH ?? "/AlgoWorlds";

export default defineConfig({
  site,
  base,
  output: "static",
  trailingSlash: "always",
  build: {
    format: "directory",
    inlineStylesheets: "auto",
  },
});
