import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";

const keys = (value, expected) =>
  assert.deepEqual(Object.keys(value).sort(), [...expected].sort());
const data = JSON.parse(await readFile("public/snapshot.json", "utf8"));
keys(data, ["schema_version", "data_kind", "segments"]);
assert.equal(data.schema_version, 1);
assert(["synthetic", "real"].includes(data.data_kind));
for (const segment of data.segments) {
  keys(segment, ["label", "efforts", "counts"]);
  keys(segment.counts, ["rides", "accepted", "rejected"]);
  assert.equal(segment.counts.accepted, segment.efforts.length);
  segment.efforts.forEach((effort, index) => {
    keys(effort, ["order", "duration_seconds"]);
    assert.equal(effort.order, index + 1);
    assert(
      Number.isInteger(effort.duration_seconds) && effort.duration_seconds > 0,
    );
  });
}
async function walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(file);
    else {
      assert(
        !/\.(gpx|sqlite|db|py|env)$/i.test(entry.name),
        `Private file in output: ${file}`,
      );
      if (/\.(json|js|html|txt|map)$/i.test(entry.name)) {
        const content = await readFile(file, "utf8");
        assert(
          !/ride_[a-f0-9]{64}|"timestamp_utc"|"latitude"\s*:|"longitude"\s*:|"approved_ride_ids"/.test(
            content,
          ),
          `Private field in asset: ${file}`,
        );
      }
    }
  }
}
await walk("out");
assert.deepEqual(JSON.parse(await readFile("out/snapshot.json", "utf8")), data);
console.log(
  "Public snapshot and built assets passed field and private-data checks.",
);
