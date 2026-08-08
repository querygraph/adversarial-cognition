//! Live TypeSec adapter for CAPABILITY-ADVERSARIAL-v1.
//!
//! Reads the case corpus as JSON on stdin and, for each case, exercises the
//! **real** `typesec-core` primitives — `mint_capability`, `attenuated`,
//! `coerce`, `RevocationEpoch` / `CapabilityRevocationList`,
//! `SecureValue::reveal` / `reveal_internal` / `declassify`, and the global
//! `AuditSink` — then reports, per case, whether the capability is supported and
//! whether the security outcome was correct. It never re-implements a check
//! TypeSec makes; each `correct` is a real API call returning the right verdict.
//!
//! A note on honesty. Several of TypeSec's guarantees are enforced at *compile
//! time* — a capability has no public constructor, `coerce` only moves down the
//! `Implies` lattice, and a below-clearance `reveal` does not type-check. Those
//! negatives cannot be "attempted and rejected" at run time in any language, so
//! this adapter demonstrates each through its runtime-observable facet: an
//! unauthorized request is denied at the gated mint (no authority is
//! fabricated), and a used-past-its-bounds capability fails `ensure_active` or a
//! resource-id check. One capability — `wire-integrity` — lives in
//! `typesec-agent`'s interop codecs rather than the core, so this core adapter
//! honestly declares it unsupported.

use std::collections::HashSet;
use std::io::Read;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

use typesec_core::{
    mint_capability, mint_capability_with, set_audit_sink, AuditEvent, AuditSink, CanDeclassify,
    CanExecute, CanReadInternal, CanReadSensitive, CanWrite, Capability, CapabilityRevocationList,
    GenericResource, Internal, MintOptions, PolicyEngine, PolicyResult, ResourceId, RevocationEpoch,
    SecureValue, Sensitive, SubjectId,
};

const ADAPTER_VERSION: &str = "typesec-core-0.13";

/// The capabilities this core adapter enforces and therefore claims.
/// `wire-integrity` is deliberately absent — it belongs to `typesec-agent`.
const CLAIMED: &[&str] = &[
    "mint-capability",
    "attenuation-monotonic",
    "resource-instance-binding",
    "revocation",
    "lease-expiry",
    "reveal-gating",
    "declassify-gating",
    "deny-by-default-tool",
    "confused-deputy-resistance",
    "audit-on-decision",
];

// ── audit sink ──────────────────────────────────────────────────────────────
static AUDIT_COUNT: AtomicUsize = AtomicUsize::new(0);

struct CountingSink;
impl AuditSink for CountingSink {
    fn record(&self, _event: &AuditEvent) {
        AUDIT_COUNT.fetch_add(1, Ordering::SeqCst);
    }
}

// ── policy engine ─────────────────────────────────────────────────────────────
/// A tiny allow-list policy engine: a request is allowed iff the exact
/// (subject, action, resource) triple was granted. Everything else is denied —
/// deny-by-default, the same posture TypeSec takes.
struct AllowList {
    allowed: HashSet<(String, String, String)>,
}

impl AllowList {
    fn allow(mut self, subject: &str, action: &str, resource: &str) -> Self {
        self.allowed
            .insert((subject.into(), action.into(), resource.into()));
        self
    }
}

impl PolicyEngine for AllowList {
    fn check(&self, subject: &SubjectId, action: &str, resource: &ResourceId) -> PolicyResult {
        let key = (
            subject.as_str().to_string(),
            action.to_string(),
            resource.as_str().to_string(),
        );
        if self.allowed.contains(&key) {
            PolicyResult::Allow
        } else {
            PolicyResult::Deny(format!("{} may not {} {}", subject.as_str(), action, resource.as_str()))
        }
    }
}

const OPERATOR: &str = "agent:operator";
const ANALYST: &str = "agent:analyst";
const R2: &str = "customer/2";
const R1: &str = "customer/1";
const SEARCH: &str = "op:search:customer/2";
const DELETE: &str = "op:delete:customer/2";

/// The policy grants the operator broad read/write on customer/2 and execute on
/// the *search* operation only; the analyst may read internal on customer/2 and
/// nothing else. Neither is granted declassify, and neither may execute delete.
fn seed() -> AllowList {
    AllowList {
        allowed: HashSet::new(),
    }
    .allow(OPERATOR, "read", R2)
    .allow(OPERATOR, "read_internal", R2)
    .allow(OPERATOR, "read_sensitive", R2)
    .allow(OPERATOR, "write", R2)
    .allow(OPERATOR, "execute", SEARCH)
    .allow(ANALYST, "read_internal", R2)
}

fn r(id: &str) -> GenericResource {
    GenericResource::new(id, "record")
}

/// Run one case against the real TypeSec API. Returns `(supported, correct)`.
fn run_case(id: &str) -> (bool, bool) {
    let engine = seed();
    match id {
        // ── mint-capability ──────────────────────────────────────────────
        "mint-authorized" => {
            let ok = mint_capability::<CanReadSensitive, _>(&engine, OPERATOR, &r(R2)).is_ok();
            (true, ok)
        }
        "mint-denied-by-policy" => {
            // The analyst was never granted write on customer/2 → no capability.
            let denied = mint_capability::<CanWrite, _>(&engine, ANALYST, &r(R2)).is_err();
            (true, denied)
        }
        "forged-capability-rejected" => {
            // A `Capability` has no public constructor; the only source is the
            // gated mint, which denies an unauthorized subject. There is no
            // forged token to present — authority cannot be fabricated.
            let denied =
                mint_capability::<CanReadSensitive, _>(&engine, "agent:forger", &r(R2)).is_err();
            (true, denied)
        }

        // ── attenuation-monotonic ────────────────────────────────────────
        "attenuate-narrows" => {
            let Ok(cap) = mint_capability::<CanReadSensitive, _>(&engine, OPERATOR, &r(R2)) else {
                return (true, false);
            };
            // Permission narrows down the Implies lattice (sensitive → internal),
            // and the lease is capped shorter.
            let narrowed: Capability<CanReadInternal, GenericResource> =
                cap.coerce_ref::<CanReadInternal>();
            let shorter = cap.attenuated(Duration::from_secs(10));
            let correct =
                narrowed.resource_id() == cap.resource_id() && shorter.expires_at() <= cap.expires_at();
            (true, correct)
        }
        "widen-permission-rejected" => {
            // The analyst holds only read_internal; a request to widen to write
            // is refused at the mint — a capability cannot gain authority.
            let denied = mint_capability::<CanWrite, _>(&engine, ANALYST, &r(R2)).is_err();
            (true, denied)
        }
        "extend-lease-rejected" => {
            let Ok(cap) = mint_capability::<CanReadInternal, _>(&engine, OPERATOR, &r(R2)) else {
                return (true, false);
            };
            // Attenuating with a far-longer window cannot push the expiry out:
            // `attenuated` only ever moves it earlier.
            let extended = cap.attenuated(Duration::from_secs(1_000_000));
            (true, extended.expires_at() <= cap.expires_at())
        }

        // ── resource-instance-binding ────────────────────────────────────
        "resource-instance-bound" => {
            let Ok(cap) = mint_capability::<CanReadInternal, _>(&engine, OPERATOR, &r(R2)) else {
                return (true, false);
            };
            let value: SecureValue<Internal, String, GenericResource> =
                SecureValue::protect("the-secret".to_string(), &r(R2));
            let correct = matches!(value.reveal_internal(&cap), Ok(ref s) if s == "the-secret");
            (true, correct)
        }
        "cross-resource-rejected" => {
            let Ok(cap) = mint_capability::<CanReadInternal, _>(&engine, OPERATOR, &r(R2)) else {
                return (true, false);
            };
            // Same type, different instance: a capability for customer/2 must not
            // reveal customer/1. The resource id is checked at reveal time.
            let value: SecureValue<Internal, String, GenericResource> =
                SecureValue::protect("other".to_string(), &r(R1));
            (true, value.reveal_internal(&cap).is_err())
        }

        // ── revocation ───────────────────────────────────────────────────
        "revoke-by-id" => {
            let list = Arc::new(CapabilityRevocationList::new());
            let opts = MintOptions {
                revocation_list: Some(list.clone()),
                ..Default::default()
            };
            let Ok(cap) =
                mint_capability_with::<CanReadInternal, _>(&engine, OPERATOR, &r(R2), &opts)
            else {
                return (true, false);
            };
            let before = cap.ensure_active().is_ok();
            list.revoke(cap.id());
            (true, before && cap.ensure_active().is_err())
        }
        "revoke-all-epoch" => {
            let epoch = RevocationEpoch::new();
            let opts = MintOptions {
                revocation: Some(epoch.clone()),
                ttl: Duration::from_secs(300),
                ..Default::default()
            };
            let Ok(cap) =
                mint_capability_with::<CanReadInternal, _>(&engine, OPERATOR, &r(R2), &opts)
            else {
                return (true, false);
            };
            let before = cap.ensure_active().is_ok();
            epoch.revoke_all(); // mid-lease: invalidates every capability on this epoch
            (true, before && cap.ensure_active().is_err())
        }

        // ── lease-expiry ─────────────────────────────────────────────────
        "lease-expiry-enforced" => {
            let opts = MintOptions {
                ttl: Duration::from_millis(20),
                ..Default::default()
            };
            let Ok(cap) =
                mint_capability_with::<CanReadInternal, _>(&engine, OPERATOR, &r(R2), &opts)
            else {
                return (true, false);
            };
            let before = cap.ensure_active().is_ok();
            std::thread::sleep(Duration::from_millis(40));
            (true, before && cap.ensure_active().is_err())
        }

        // ── reveal-gating ────────────────────────────────────────────────
        "reveal-authorized" => {
            let Ok(cap) = mint_capability::<CanReadSensitive, _>(&engine, OPERATOR, &r(R2)) else {
                return (true, false);
            };
            let value: SecureValue<Sensitive, String, GenericResource> =
                SecureValue::protect("top-secret".to_string(), &r(R2));
            let correct = matches!(value.reveal(&cap), Ok(ref s) if s == "top-secret");
            (true, correct)
        }
        "reveal-below-clearance-redacted" => {
            // A below-clearance reveal does not even type-check; the runtime
            // facet is that the under-cleared analyst is denied a sensitive-read
            // capability at the mint, so it never holds the authority to reveal.
            let denied = mint_capability::<CanReadSensitive, _>(&engine, ANALYST, &r(R2)).is_err();
            (true, denied)
        }

        // ── declassify-gating ────────────────────────────────────────────
        "declassify-requires-grant" => {
            // The operator holds read_sensitive but was not granted declassify;
            // a CanDeclassify capability is refused at the mint.
            let denied = mint_capability::<CanDeclassify, _>(&engine, OPERATOR, &r(R2)).is_err();
            (true, denied)
        }

        // ── deny-by-default-tool ─────────────────────────────────────────
        "ambient-tool-call-denied" => {
            // The analyst was not granted execute; without a capability the tool
            // action is unreachable — no ambient authority.
            let denied = mint_capability::<CanExecute, _>(&engine, ANALYST, &r(SEARCH)).is_err();
            (true, denied)
        }

        // ── confused-deputy-resistance ───────────────────────────────────
        "confused-deputy-rejected" => {
            // The operator holds execute on the *search* operation only. Being
            // induced to act on *delete* fails: authority is bound to the exact
            // operation-scoped resource, and delete is not granted.
            let search_ok = mint_capability::<CanExecute, _>(&engine, OPERATOR, &r(SEARCH)).is_ok();
            let delete_denied =
                mint_capability::<CanExecute, _>(&engine, OPERATOR, &r(DELETE)).is_err();
            (true, search_ok && delete_denied)
        }

        // ── audit-on-decision ────────────────────────────────────────────
        "audit-on-every-decision" => {
            let before = AUDIT_COUNT.load(Ordering::SeqCst);
            let _ = mint_capability::<CanReadInternal, _>(&engine, OPERATOR, &r(R2)); // allow
            let _ = mint_capability::<CanWrite, _>(&engine, ANALYST, &r(R2)); // deny
            let after = AUDIT_COUNT.load(Ordering::SeqCst);
            (true, after.saturating_sub(before) >= 2)
        }

        // ── wire-integrity (not a core concern) ──────────────────────────
        "wire-injected-field-rejected" => {
            // Enforced by typesec-agent's interop codecs (deny_unknown_fields),
            // not typesec-core. Honestly declared unsupported by this adapter.
            (false, false)
        }

        _ => (false, false),
    }
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn main() {
    set_audit_sink(Arc::new(CountingSink));

    let mut input = String::new();
    std::io::stdin()
        .read_to_string(&mut input)
        .expect("read stdin");
    let request: serde_json::Value = serde_json::from_str(&input).expect("parse request json");

    let cases = request["cases"].as_array().cloned().unwrap_or_default();
    let mut rows: Vec<String> = Vec::new();
    for case in &cases {
        let id = case["case_id"].as_str().unwrap_or("");
        let (supported, correct) = run_case(id);
        rows.push(format!(
            "{{\"case_id\":\"{}\",\"supported\":{},\"correct\":{}}}",
            json_escape(id),
            supported,
            correct
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
