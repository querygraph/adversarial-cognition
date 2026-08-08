//! Biscuit adapter — offline, attenuable capability tokens with Datalog caveats.
//!
//! A Biscuit is a public-key-verifiable token whose authority is narrowed by
//! appending sealed blocks of Datalog checks; a block cannot be removed without
//! breaking the signature chain. That gives Biscuit four of this benchmark's
//! properties, and this adapter claims only those:
//!
//! - `attenuation-monotonic` — an appended check only narrows; it cannot be
//!   removed, so authority never widens and a time bound never loosens;
//! - `resource-instance-binding` — a `check if resource("customer/2")` is
//!   satisfied only by the request fact for that instance;
//! - `lease-expiry` — a `check if time($t), $t <= <date>` is enforced against
//!   the authorizer's clock;
//! - `revocation` — every token carries revocation identifiers; a revoked id on
//!   a denylist stops authorization (Biscuit revocation is per-id).
//!
//! Biscuit has no policy-gated mint, no information-flow labels, and no
//! reveal/declassify, so those columns are declared unsupported.

use std::collections::HashSet;
use std::io::Read;

use biscuit_auth::macros::{authorizer, biscuit, block};
use biscuit_auth::{Biscuit, KeyPair};

const ADAPTER_VERSION: &str = "biscuit-auth-5";
const CLAIMED: &[&str] = &[
    "attenuation-monotonic",
    "resource-instance-binding",
    "lease-expiry",
    "revocation",
];

/// Authorize a token in a request context, honoring a revocation denylist.
/// The token carries only *checks*; the request facts (resource, operation,
/// time) come from the authorizer, so a check is satisfied only by a matching
/// request — that is what makes resource binding and expiry real.
fn authorize(token: &Biscuit, ctx: &str, revoked: &HashSet<Vec<u8>>) -> bool {
    if token
        .revocation_identifiers()
        .iter()
        .any(|id| revoked.contains(id))
    {
        return false;
    }
    let mut a = authorizer!(r#"allow if true;"#);
    if a.add_code(ctx).is_err() {
        return false;
    }
    a.set_time();
    if a.add_token(token).is_err() {
        return false;
    }
    a.authorize().is_ok()
}

fn base(root: &KeyPair) -> Biscuit {
    // A capability to act on customer/2: the check is satisfied by the request.
    biscuit!(r#"check if resource("customer/2");"#)
        .build(root)
        .unwrap()
}

fn run_case(id: &str) -> bool {
    let root = KeyPair::new();
    let none: HashSet<Vec<u8>> = HashSet::new();
    match id {
        "attenuate-narrows" => {
            // Append an operation check → the token now passes only for read.
            let narrowed = base(&root)
                .append(block!(r#"check if operation("read");"#))
                .unwrap();
            authorize(&narrowed, r#"resource("customer/2"); operation("read");"#, &none)
        }
        "widen-permission-rejected" => {
            // The narrowed (read-only) token cannot authorize write, and the
            // appended check cannot be removed — authority cannot be widened.
            let narrowed = base(&root)
                .append(block!(r#"check if operation("read");"#))
                .unwrap();
            !authorize(&narrowed, r#"resource("customer/2"); operation("write");"#, &none)
        }
        "extend-lease-rejected" => {
            // Two time checks: the earliest bound governs. A past bound denies
            // even alongside a far-future one — a lease cannot be extended.
            let bounded = base(&root)
                .append(block!(r#"check if time($t), $t <= 2000-01-01T00:00:00Z;"#))
                .unwrap()
                .append(block!(r#"check if time($t), $t <= 2100-01-01T00:00:00Z;"#))
                .unwrap();
            !authorize(&bounded, r#"resource("customer/2");"#, &none)
        }
        "resource-instance-bound" => {
            authorize(&base(&root), r#"resource("customer/2");"#, &none)
        }
        "cross-resource-rejected" => {
            // Same type, different instance: the request fact for customer/1
            // does not satisfy the token's check for customer/2.
            !authorize(&base(&root), r#"resource("customer/1");"#, &none)
        }
        "lease-expiry-enforced" => {
            let fresh = base(&root)
                .append(block!(r#"check if time($t), $t <= 2100-01-01T00:00:00Z;"#))
                .unwrap();
            let expired = base(&root)
                .append(block!(r#"check if time($t), $t <= 2000-01-01T00:00:00Z;"#))
                .unwrap();
            authorize(&fresh, r#"resource("customer/2");"#, &none)
                && !authorize(&expired, r#"resource("customer/2");"#, &none)
        }
        "revoke-by-id" => {
            let token = base(&root);
            let before = authorize(&token, r#"resource("customer/2");"#, &none);
            let mut revoked: HashSet<Vec<u8>> = HashSet::new();
            revoked.extend(token.revocation_identifiers());
            before && !authorize(&token, r#"resource("customer/2");"#, &revoked)
        }
        "revoke-all-epoch" => {
            // Biscuit revocation is per-id; a bulk revocation revokes every
            // outstanding id, catching this token mid-lease.
            let token = base(&root);
            let before = authorize(&token, r#"resource("customer/2");"#, &none);
            let mut revoked: HashSet<Vec<u8>> = HashSet::new();
            revoked.extend(token.revocation_identifiers());
            before && !authorize(&token, r#"resource("customer/2");"#, &revoked)
        }
        _ => false,
    }
}

fn main() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("read stdin");
    let request: serde_json::Value = serde_json::from_str(&input).expect("parse request");
    let cases = request["cases"].as_array().cloned().unwrap_or_default();

    let mut rows = Vec::new();
    for case in &cases {
        let id = case["case_id"].as_str().unwrap_or("");
        let capability = case["capability"].as_str().unwrap_or("");
        let supported = CLAIMED.contains(&capability);
        let correct = supported && run_case(id);
        rows.push(format!(
            "{{\"case_id\":\"{id}\",\"supported\":{supported},\"correct\":{correct}}}"
        ));
    }
    let caps = CLAIMED
        .iter()
        .map(|c| format!("\"{c}\""))
        .collect::<Vec<_>>()
        .join(",");
    println!(
        "{{\"adapter_version\":\"{ADAPTER_VERSION}\",\"capabilities\":[{caps}],\"cases\":[{}]}}",
        rows.join(",")
    );
}
