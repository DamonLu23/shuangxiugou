// 本地版 bundle 完整性测试：构建产物与开源数据包一致、无负面评级数据。
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const ROOT = resolve(WEB, '..')

test('build-local 产物与数据包计数一致', () => {
  execSync('node scripts/build-local.mjs', { cwd: WEB })

  const raw = readFileSync(resolve(WEB, 'local/dist/data.js'), 'utf-8')
  const m = raw.match(/window\.SXG_DATA = (\{[\s\S]*\});/)
  assert.ok(m, 'data.js 应包含 window.SXG_DATA')
  const data = JSON.parse(m[1])

  const companies = JSON.parse(readFileSync(resolve(ROOT, 'data/companies.json'), 'utf-8'))
  const jobs = JSON.parse(readFileSync(resolve(ROOT, 'data/jobs.json'), 'utf-8'))

  assert.equal(data.companies.length, companies.count)
  assert.equal(data.jobs.length, jobs.count)
  assert.ok(data.goods.length > 0)
})

test('数据包仅含白名单等级（保守策略防线）', () => {
  const raw = readFileSync(resolve(WEB, 'local/dist/data.js'), 'utf-8')
  const data = JSON.parse(raw.match(/window\.SXG_DATA = (\{[\s\S]*\});/)[1])

  // 等级档案只允许 L1/L2（L3~L6 评级绝不进入公开数据）
  const levels = new Set(data.companies.map(c => c.level))
  assert.deepEqual([...levels].sort(), [1, 2], '只允许 L1/L2 进入公开数据')

  // 公开企业集合与 companies.json 完全一致（无多余档案夹带）
  const companies = JSON.parse(readFileSync(resolve(ROOT, 'data/companies.json'), 'utf-8'))
  const names = new Set(data.companies.map(c => c.name))
  assert.deepEqual([...names].sort(), companies.companies.map(c => c.name).sort())

  // 证据必须可溯源（http 链接或 UGC 标记），且不存正文
  for (const c of data.companies) {
    for (const ev of c.evidences) {
      assert.ok(ev.url.startsWith('http') || ev.url.startsWith('ugc://'),
        `证据需可溯源：${ev.url}`)
      assert.ok(Array.isArray(ev.keywords), '证据只存关键词列表')
    }
  }
})

test('岗位条目字段完整且来自白名单企业', () => {
  const raw = readFileSync(resolve(WEB, 'local/dist/data.js'), 'utf-8')
  const data = JSON.parse(raw.match(/window\.SXG_DATA = (\{[\s\S]*\});/)[1])
  const names = new Set(data.companies.map(c => c.name))

  for (const j of data.jobs) {
    assert.ok(j.title, '岗位需有标题')
    assert.ok(names.has(j.company_name), `岗位企业应为白名单：${j.company_name}`)
  }
})