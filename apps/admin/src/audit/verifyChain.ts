import type { AuditEntry } from '@lsc/api-client';

const GENESIS = '0'.repeat(64);

// Canonical JSON matching the backend's compute_hash: object keys sorted,
// compact separators (",",":"), UTF-8. This must byte-match the Python
// json.dumps(..., sort_keys=True, separators=(",",":"), ensure_ascii=False).
function canonical(value: unknown): string {
  if (value === null) return 'null';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const parts = keys.map((k) => `${JSON.stringify(k)}:${canonical(obj[k])}`);
    return `{${parts.join(',')}}`;
  }
  return 'null';
}

async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// Recompute each entry's hash and confirm it chains correctly from GENESIS.
// Entries are expected in insertion order (the backend lists ordered by `at`).
export async function verifyChain(entries: AuditEntry[]): Promise<boolean> {
  let prev = GENESIS;
  for (const e of entries) {
    if (e.prev_hash !== prev) return false;
    const payload = {
      entry_id: e.entry_id,
      actor: e.actor,
      action: e.action,
      target: e.target,
      metadata: e.metadata,
      at: e.at,
      prev_hash: e.prev_hash,
    };
    const computed = await sha256Hex(canonical(payload));
    if (computed !== e.entry_hash) return false;
    prev = e.entry_hash;
  }
  return true;
}
