# CAPABILITY-ADVERSARIAL-v1 policy for OPA — a default-deny decision engine.
package capability

import rego.v1

default allow := false

# The operator may read customer/2 and search tool:x — nothing else.
allow if {
	input.principal == "agent:operator"
	input.action == "read"
	input.resource == "customer/2"
}

allow if {
	input.principal == "agent:operator"
	input.action == "search"
	input.resource == "tool:x"
}
