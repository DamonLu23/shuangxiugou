// 本地模式构建：把开源数据包内嵌进 data.js，产物可双击 index.html 直接使用。
//
// 用法: npm run local   →  生成 web/local/dist/（data.js + index.html + app.js 精简版）
// 或:  node scripts/build-local.mjs
//
// 产物结构:
//   web/local/dist/index.html  （本地入口，双击即可，file:// 安全）
//   web/local/dist/data.js     （window.SXG_DATA = { companies, jobs, goods }）
//   web/local/dist/app.js      （渲染逻辑，vanilla JS 零依赖）
import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const DATA = resolve(ROOT, 'data')
const OUT = resolve(ROOT, 'web/local/dist')

// 从公开制品读取
const companies = JSON.parse(readFileSync(resolve(DATA, 'companies.json'), 'utf-8'))
const jobs = JSON.parse(readFileSync(resolve(DATA, 'jobs.json'), 'utf-8'))
const goodsRaw = readFileSync(resolve(DATA, 'goods.csv'), 'utf-8')
const goods = goodsRaw.trim().split('\n').slice(1)
  .map(line => line.split(',').map(s => s.trim()))
  .filter(r => r.length >= 2 && r[0])
  .map(([company_name, category, product, official_link, note]) =>
    ({ company_name, category, product, official_link, note: note || '' }))

mkdirSync(OUT, { recursive: true })
writeFileSync(resolve(OUT, 'data.js'),
`/* 自动生成：shuangxiugou 本地数据包（保守策略：仅白名单公开数据） */
window.SXG_DATA = ${JSON.stringify({
    generated_at: companies.generated_at,
    companies: companies.companies,
    jobs: jobs.jobs,
    goods,
  }, null, 2)};
`)

for (const f of ['index.html', 'app.js']) {
  copyFileSync(resolve(ROOT, 'web/local/src', f), resolve(OUT, f))
}

console.log(`[local] 已生成 ${OUT}`)
console.log(`  白名单企业 ${companies.count} 家 · 岗位 ${jobs.count} 个 · 好物 ${goods.length} 条`)
console.log('  用法：双击 web/local/dist/index.html（或 python3 -m http.server -d web/local/dist）')