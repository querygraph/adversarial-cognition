// UCAN adapter — DID-rooted, delegable capability tokens.
//
// A UCAN is a capability token signed by the issuer's DID key, carrying explicit
// capabilities (`{ with: resource, can: ability }`) and an `exp`. @ucans/ucans's
// `validate()` natively enforces the signature and the lease, and each capability
// is cryptographically bound to one resource. This adapter claims the two
// properties the library fully drives here:
//
// - `resource-instance-binding` — a capability is bound to one `with.hierPart`;
//   a token for customer/2 authorizes no other instance;
// - `lease-expiry` — `validate()` rejects a token past its `exp`.
//
// UCAN's delegation narrowing is real too (capabilityCanBeDelegated rejects
// widening a permission), but the corpus's `attenuation-monotonic` also bundles
// a lease-narrowing dimension this adapter does not drive, so it is left
// unclaimed rather than half-claimed. Revocation, reveal/declassify, tool, audit,
// and wire have no UCAN analog here and are declared unsupported.

import { readFileSync } from "node:fs";
import * as ucans from "@ucans/ucans";

const ADAPTER_VERSION = "ucans-0.12";
const CLAIMED = ["resource-instance-binding", "lease-expiry"];

const cap = (res, seg) => ({
  with: { scheme: "cap", hierPart: res },
  can: { namespace: "op", segments: [seg] },
});

async function mint(resource, lifetimeInSeconds = 300) {
  const issuer = await ucans.EdKeypair.create();
  const audience = await ucans.EdKeypair.create();
  const u = await ucans.build({
    audience: audience.did(),
    issuer,
    capabilities: [cap(resource, "READ")],
    lifetimeInSeconds,
  });
  return ucans.encode(u);
}

// A token authorizes `resource` iff it validates (signature + not expired) and
// carries a capability bound to exactly that resource instance.
async function authorizes(token, resource) {
  try {
    await ucans.validate(token);
  } catch {
    return false;
  }
  const parsed = ucans.parse(token);
  return parsed.payload.att.some((c) => c.with.hierPart === resource);
}

async function runCase(id) {
  if (id === "resource-instance-bound") {
    return authorizes(await mint("customer/2"), "customer/2");
  }
  if (id === "cross-resource-rejected") {
    // Bound to customer/2: it authorizes no other instance.
    return !(await authorizes(await mint("customer/2"), "customer/1"));
  }
  if (id === "lease-expiry-enforced") {
    const fresh = await authorizes(await mint("customer/2", 300), "customer/2");
    const expired = await authorizes(await mint("customer/2", -10), "customer/2");
    return fresh && !expired;
  }
  return false;
}

const request = JSON.parse(readFileSync(0, "utf8"));
const claimed = new Set(CLAIMED);
const rows = [];
for (const c of request.cases) {
  const supported = claimed.has(c.capability);
  let correct = false;
  if (supported) {
    try {
      correct = Boolean(await runCase(c.case_id));
    } catch (e) {
      process.stderr.write(`${c.case_id}: ${e}\n`);
    }
  }
  rows.push({ case_id: c.case_id, supported, correct });
}
process.stdout.write(JSON.stringify({
  adapter_version: ADAPTER_VERSION,
  capabilities: [...claimed].sort(),
  cases: rows,
}));
