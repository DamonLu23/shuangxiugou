const BASE = '/api'

async function get(path) {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

export function searchJobs(q, city = '') {
  const params = new URLSearchParams({ q })
  if (city) params.set('city', city)
  return get(`/jobs/search?${params}`)
}

export function searchGoods(q) {
  return get(`/goods/search?${new URLSearchParams({ q })}`)
}

export function companies(level, limit = 100) {
  const params = new URLSearchParams({ limit })
  if (level) params.set('level', level)
  return get(`/companies?${params}`)
}

export function companyDetail(id) {
  return get(`/companies/${id}`)
}

export function submitAppeal(companyId, payload) {
  return fetch(`${BASE}/companies/${companyId}/appeal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(async (r) => ({ ok: r.ok, data: await r.json() }))
}

export function reportJob(payload) {
  return fetch(`${BASE}/jobs/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(async (r) => ({ ok: r.ok, data: await r.json() }))
}

export const LEVEL_NAMES = {
  1: '严格双休',
  2: '双休',
  3: '大小周',
  4: '单休',
  5: '996',
  6: '待验证',
}

export function levelBadgeClass(level) {
  if ([1, 2].includes(level)) return `l${level}`
  return 'unknown'
}