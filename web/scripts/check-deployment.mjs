import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const base = new URL(process.argv[2] ?? "http://127.0.0.1:3000");
assert(
  ["http:", "https:"].includes(base.protocol),
  "Supply an HTTP(S) deployment URL",
);
assert(
  !base.username && !base.password && !base.search,
  "Use a URL without credentials or query parameters",
);
const expected = JSON.parse(await readFile("public/snapshot.json", "utf8"));
const privateFields =
  /ride_[a-f0-9]{64}|"timestamp_utc"|"latitude"\s*:|"longitude"\s*:|"approved_ride_ids"/;

async function get(path) {
  return fetch(new URL(path, base), {
    redirect: "error",
    signal: AbortSignal.timeout(15000),
  });
}

const home = await get("/");
assert.equal(home.status, 200, "Home page must be publicly accessible");
assert.equal(home.headers.get("x-content-type-options"), "nosniff");
const html = await home.text();
assert(html.includes("Ride Replay"), "Home page title missing");
assert(!privateFields.test(html), "Private data found in HTML");

const response = await get("/snapshot.json");
assert.equal(response.status, 200, "Snapshot must be publicly accessible");
assert.deepEqual(
  await response.json(),
  expected,
  "Deployed snapshot differs from the approved local snapshot",
);

const pending = new Set();
const checked = new Set();
function discover(text, parent) {
  const references = [
    ...text.matchAll(/(?:src|href)=["']([^"']+)["']/g),
    ...text.matchAll(/url\(["']?([^)'"\s]+)["']?\)/g),
    ...text.matchAll(/["'](\/_next\/static\/[^"'\\]+)["']/g),
  ];
  for (const match of references) {
    if (match[1].includes("${")) continue;
    const url = new URL(match[1], parent);
    if (
      url.origin === base.origin &&
      /\.(js|css|woff2?|ttf|otf|svg|json)$/.test(url.pathname) &&
      (url.pathname.startsWith("/_next/static/") ||
        url.pathname === "/icon.svg") &&
      !checked.has(url.href)
    )
      pending.add(url.href);
  }
}
discover(html, base);
while (pending.size) {
  assert(checked.size + pending.size <= 150, "Unexpectedly large asset graph");
  const batch = [...pending];
  pending.clear();
  await Promise.all(
    batch.map(async (url) => {
      checked.add(url);
      const asset = await get(url);
      assert.equal(asset.status, 200, `Asset unavailable: ${url}`);
      const type = asset.headers.get("content-type") ?? "";
      if (/javascript|css|json|html|svg/.test(type)) {
        const text = await asset.text();
        assert(
          !privateFields.test(text),
          `Private data found in asset: ${url}`,
        );
        discover(text, url);
      } else {
        await asset.arrayBuffer();
      }
    }),
  );
}
assert(checked.size > 0, "No deployed frontend assets were discovered");
for (const path of [
  "/.env",
  "/.env.local",
  "/data/rides.sqlite",
  "/data/manifests",
  "/src/ride_replay/strava.py",
]) {
  const result = await get(path);
  assert.equal(
    result.status,
    404,
    `Private path is unexpectedly reachable: ${path}`,
  );
  await result.arrayBuffer();
}
console.log(
  `Deployment checks passed: public home, exact approved snapshot, ${checked.size} referenced assets, and private-path 404s.`,
);
