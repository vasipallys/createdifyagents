// Tiny API client for the DSL editor backend.
// In dev, Vite proxies /dsl and /api to the FastAPI server (see vite.config.js).

const BASE = '' // same origin in prod; proxied in dev

export async function listDslFiles() {
  const r = await fetch(`${BASE}/dsl/list`)
  if (!r.ok) throw new Error(`list failed: ${r.status}`)
  return r.json()
}

export async function getDslFile(name) {
  const r = await fetch(`${BASE}/dsl/file?name=${encodeURIComponent(name)}`)
  if (!r.ok) throw new Error(`load ${name} failed: ${r.status}`)
  return r.json() // { name, dsl, meta }
}

export async function saveDslFile(name, dsl, revision = null) {
  const writeKey = sessionStorage.getItem('story-pointer-dsl-key') || ''
  const r = await fetch(`${BASE}/dsl/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(writeKey ? { 'X-DSL-API-Key': writeKey } : {}),
    },
    body: JSON.stringify({ name, dsl, revision }),
  })
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error(body.detail || `save failed: ${r.status}`)
  }
  return r.json()
}

export async function validateDsl(dsl) {
  const r = await fetch(`${BASE}/dsl/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dsl }),
  })
  return r.json() // { loadable, dependencies, error }
}

export async function getConfig() {
  const r = await fetch(`${BASE}/api/config`)
  return r.json()
}
