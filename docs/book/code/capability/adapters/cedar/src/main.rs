//! Cedar adapter — a policy engine, not a capability system.
//!
//! Cedar (AWS's authorization language, behind Amazon Verified Permissions)
//! decides `Allow`/`Deny` for a (principal, action, resource) request against a
//! policy set. That is real, fine-grained governance — but it mints no token
//! that travels, attenuates, or revokes. So this adapter claims only the
//! columns a decision engine genuinely covers:
//!
//! - `resource-instance-binding` — a permit names one resource instance; a
//!   different instance is denied by default;
//! - `deny-by-default-tool` — Cedar is default-deny, so an action with no
//!   matching permit is refused (no ambient authority);
//! - `confused-deputy-resistance` — permits are action-scoped, so authority for
//!   one action cannot drive another.
//!
//! The capability-token columns — mint (an unforgeable token), attenuation,
//! revocation, lease-expiry, reveal/declassify, audit, wire — have no Cedar
//! analog and are declared unsupported. That contrast is the point.

use std::io::Read;
use std::str::FromStr;

use cedar_policy::{Authorizer, Context, Decision, Entities, EntityUid, PolicySet, Request};

const ADAPTER_VERSION: &str = "cedar-policy-4";
const CLAIMED: &[&str] = &[
    "resource-instance-binding",
    "deny-by-default-tool",
    "confused-deputy-resistance",
];

const POLICY: &str = r#"
permit(principal == User::"agent:operator", action == Action::"read",   resource == Resource::"customer/2");
permit(principal == User::"agent:operator", action == Action::"search", resource == Resource::"tool:x");
"#;

fn allowed(action: &str, resource: &str, principal: &str) -> bool {
    let policies = PolicySet::from_str(POLICY).expect("parse policies");
    let p = EntityUid::from_str(&format!("User::\"{principal}\"")).unwrap();
    let a = EntityUid::from_str(&format!("Action::\"{action}\"")).unwrap();
    let r = EntityUid::from_str(&format!("Resource::\"{resource}\"")).unwrap();
    let request = Request::new(p, a, r, Context::empty(), None).expect("build request");
    let answer = Authorizer::new().is_authorized(&request, &policies, &Entities::empty());
    answer.decision() == Decision::Allow
}

fn run_case(id: &str) -> bool {
    match id {
        "resource-instance-bound" => allowed("read", "customer/2", "agent:operator"),
        "cross-resource-rejected" => !allowed("read", "customer/1", "agent:operator"),
        // No permit covers an execute by an unauthorized principal → default deny.
        "ambient-tool-call-denied" => !allowed("execute", "tool:x", "agent:analyst"),
        // The operator may `search` tool:x but not `delete` it — action-scoped.
        "confused-deputy-rejected" => {
            allowed("search", "tool:x", "agent:operator")
                && !allowed("delete", "tool:x", "agent:operator")
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
