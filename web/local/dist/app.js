/* 双休购本地版渲染逻辑（vanilla JS，零依赖，file:// 可用）。 */
const GH_REPO = 'https://github.com/shuangxiugou/shuangxiugou'

const D = window.SXG_DATA || { companies: [], jobs: [], goods: [] }
const LEVEL_NAMES = { 1: '严格双休', 2: '双休' }
const resultsEl = document.getElementById('results')
const emptyEl = document.getElementById('empty')
const infoEl = document.getElementById('resultInfo')
const input = document.getElementById('searchInput')
let mode = 'jobs'

document.getElementById('updated').textContent = D.generated_at || '未知'
document.getElementById('generatedAt').textContent = D.generated_at || ''
const repo = document.getElementById('repoLink')
if (repo) repo.href = GH_REPO + '/issues'

// 企业 id → 名称映射
const nameById = Object.fromEntries(D.companies.map(c => [c.id, c.name]))

function badgeHtml(level, name) {
  return `<span class="badge ${level === 1 ? 'solid' : 'l1'}">${name}</span>`
}

function renderJobs(list) {
  if (!list.length) { showEmpty(); return }
  resultsEl.innerHTML = list.map(j => `
    <div class="card"><div class="row" style="padding:4px 0;">
      <div class="name">
        <h3>${esc(j.title)}</h3>
        <p class="sub">${esc(j.company_name)} · ${esc(j.city || '城市未知')} · ${esc(j.salary || '薪资面议')}</p>
        <p>${(j.tags || []).filter(Boolean).map(t => `<span class="chip">${esc(t)}</span>`).join('')}</p>
      </div>
      ${badgeHtml(j.company_level, j.company_level_name || '双休')}
      ${j.url && j.url.startsWith('http') ? `<a class="btn ghost" style="padding:6px 14px;font-size:13px;" href="${esc(j.url)}" target="_blank" rel="noopener">查看岗位</a>` : ''}
    </div></div>`).join('')
}

function renderGoods(list) {
  if (!list.length) { showEmpty(); return }
  resultsEl.innerHTML = list.map((g, i) => `
    <div class="card"><div class="row" style="padding:4px 0;">
      <div class="name">
        <h3>${esc(g.product)}</h3>
        <p class="sub">${esc(g.company_name)} · ${esc(g.category)}${g.note ? ' · ' + esc(g.note) : ''}</p>
      </div>
      ${badgeHtml(1, 'L1 严格双休')}
      ${g.official_link ? `<a class="btn ghost" style="padding:6px 14px;font-size:13px;" href="${esc(g.official_link)}" target="_blank" rel="noopener">官方店</a>` : ''}
    </div></div>`).join('')
}

function renderCompanies(list) {
  if (!list.length) { showEmpty(); return }
  resultsEl.innerHTML = list.map(c => `
    <div class="card">
      <div class="row" style="padding:4px 0;align-items:flex-start;">
        <div class="name">
          <h3>${esc(c.name)}</h3>
          <p class="sub">置信度 ${Math.round(c.confidence * 100)}% · ${c.evidence_count} 条公开证据</p>
          <p style="margin-top:6px;">
            ${(c.evidences || []).slice(0, 5).map(ev =>
              ev.url && ev.url.startsWith('http')
                ? `<span class="chip"><a href="${esc(ev.url)}" target="_blank" rel="noopener">${esc(kwText(ev))}</a></span>`
                : '').join('')}
            ${(c.evidences || []).length > 5 ? `<span class="chip">…</span>` : ''}
          </p>
        </div>
        ${badgeHtml(c.level, LEVEL_NAMES[c.level] || '双休')}
      </div>
      <button class="icon-btn" onclick="openIssue('appeal', ${c.id})">信息有误？申诉 / 更正 →</button>
    </div>`).join('')
}

function kwText(ev) { return (ev.keywords || []).join('、') || ev.source_type }

function search() {
  const q = input.value.trim().toLowerCase()
  infoEl.textContent = ''
  if (mode === 'jobs') {
    let list = D.jobs
    if (q) list = D.jobs.filter(j =>
      (j.title || '').toLowerCase().includes(q) ||
      (j.company_name || '').toLowerCase().includes(q) ||
      (j.city || '').toLowerCase().includes(q))
    infoEl.textContent = q ? `「${input.value.trim()}」匹配 ${list.length} 个双休岗位` : `共 ${list.length} 个双休岗位`
    renderJobs(list)
  } else if (mode === 'goods') {
    let list = D.goods
    if (q) list = D.goods.filter(g =>
      ((g.product || '') + (g.category || '') + (g.company_name || '')).toLowerCase().includes(q))
    infoEl.textContent = q ? `「${input.value.trim()}」匹配 ${list.length} 个双休好物` : `共 ${list.length} 个双休好物`
    renderGoods(list)
  } else {
    let list = D.companies
    if (q) list = D.companies.filter(c => (c.name || '').toLowerCase().includes(q))
    infoEl.textContent = q ? `「${input.value.trim()}」匹配 ${list.length} 家双休企业` : `共 ${list.length} 家白名单企业`
    renderCompanies(list)
  }
}

function showEmpty() {
  resultsEl.innerHTML = ''
  emptyEl.style.display = 'block'
  emptyEl.textContent = mode === 'jobs' ? '没有匹配的双休岗位，换个关键词；或到 GitHub 报岗位' :
    mode === 'goods' ? '该品类暂无双休企业好物，可到 GitHub 提交建议' : '未收录的企业不在白名单展示范围'
}

// GitHub Issue 预填跳转（面向社区：报岗位 / 纠错申诉）
window.openIssue = function (kind, companyId) {
  const c = D.companies.find(x => x.id === companyId) || {}
  let template = '', title = '', body = ''
  if (kind === 'appeal') {
    template = 'appeal.yml'
    title = `【申诉】${c.name || '企业'}`
    body = `企业：${c.name || ''}\n类型：\n事由：\n证据链接：\n`
  } else if (kind === 'report-job') {
    template = 'report_job.yml'
    title = '【报岗位】'
    body = `岗位：\n公司：\n城市：\n薪资：\n链接：\n`
  }
  const url = `${GH_REPO}/issues/new?template=${template}&title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`
  window.open(url, '_blank')
}

// 全局：企业榜里每个岗位也可报——简化：底部加一个全局报岗位按钮渲染在 info 区
function renderReportJobBtn() {
  const btn = document.createElement('button')
  btn.className = 'btn ghost'
  btn.style.cssText = 'padding:6px 14px;font-size:13px;margin-left:10px;'
  btn.textContent = '＋ 报岗位'
  btn.onclick = () => openIssue('report-job')
  infoEl.appendChild(btn)
}

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'))
  t.classList.add('on')
  mode = t.dataset.mode
  input.placeholder = mode === 'jobs' ? '搜索岗位，如 前端 / 运营 / 会计'
    : mode === 'goods' ? '搜索品类/商品，如 咖啡 / 键盘 / 寄件' : '搜索企业，如 顺丰 / 海尔'
  search()
}))

document.getElementById('searchForm').addEventListener('submit', e => { e.preventDefault(); search() })

search()
renderReportJobBtn()

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}