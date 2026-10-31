# ADR 0001 — PyYAML for reading config/*.yaml

- Status: accepted
- Date: 2026-10-30

## Context
`structure.md` places operational configuration in `config/` as YAML files
(`products.yaml`, `retention.yaml`, `consent_purposes.yaml`). The backend must
read these at startup (e.g. the consent purposes in W02). The pinned dependency
list in `tech.md` did not include a YAML parser, and the working agreement
forbids adding dependencies silently.

## Decision
Add `PyYAML==6.0.1` as a direct dependency of `apps/api`. Parsing uses
`yaml.safe_load` only (never `load`), consistent with the security baseline's
safe-deserialization rule.

## Consequences
- Exact pin, well-maintained, widely used, and already common in the Python
  ecosystem (low supply-chain risk).
- Config files remain human-editable YAML rather than being converted to JSON.
- `safe_load` prevents arbitrary object construction from config input.
