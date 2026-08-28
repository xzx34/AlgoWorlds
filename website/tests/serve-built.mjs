import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const argumentsList = process.argv.slice(2);
const portIndex = argumentsList.indexOf("--port");
const port = Number(portIndex >= 0 ? argumentsList[portIndex + 1] : 4321);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../dist");
const configuredBase = process.env.PUBLIC_BASE_PATH ?? "/AlgoWorlds";
const base = configuredBase === "/" ? "" : `/${configuredBase.replace(/^\/+|\/+$/g, "")}`;
/** @type {Record<string, string>} */
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

createServer((request, response) => {
  const requestPath = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
  if (base && requestPath === base) {
    response.writeHead(308, { Location: `${base}/` });
    response.end();
    return;
  }
  if (base && !requestPath.startsWith(`${base}/`)) {
    response.writeHead(404).end("Not found");
    return;
  }

  let relative = base ? requestPath.slice(base.length) : requestPath;
  if (relative.endsWith("/")) relative += "index.html";
  const target = resolve(root, `.${relative}`);
  if (target !== root && !target.startsWith(`${root}${sep}`)) {
    response.writeHead(400).end("Invalid path");
    return;
  }
  if (!existsSync(target) || !statSync(target).isFile()) {
    response.writeHead(404).end("Not found");
    return;
  }

  response.writeHead(200, {
    "Content-Type": contentTypes[extname(target)] ?? "application/octet-stream",
    "Cache-Control": "no-store",
  });
  createReadStream(target).pipe(response);
}).listen(port, "127.0.0.1", () => {
  process.stdout.write(`Serving ${root} at http://127.0.0.1:${port}${base}/\n`);
});
