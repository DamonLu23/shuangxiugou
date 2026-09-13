<script setup>
import { ref } from 'vue'
import { reportJob, submitCorrection } from '../api'

// 报岗位表单
const title = ref('')
const company = ref('')
const city = ref('')
const salary = ref('')
const url = ref('')
const jobMsg = ref('')
const jobIssue = ref('')

async function submitJob() {
  const { ok, data } = await reportJob({
    title: title.value,
    company_name: company.value,
    city: city.value,
    salary: salary.value,
    url: url.value,
  })
  if (ok) {
    jobMsg.value = data.message
    jobIssue.value = data.issue_url || ''
  } else {
    jobMsg.value = data.detail || '提交失败'
  }
}

// 纠错表单
const target = ref('企业档案')
const subject = ref('')
const detail = ref('')
const corrMsg = ref('')
const corrIssue = ref('')

async function submitCorr() {
  const { ok, data } = await submitCorrection({
    target: target.value,
    subject: subject.value,
    detail: detail.value,
  })
  if (ok) {
    corrMsg.value = data.message
    corrIssue.value = data.issue_url || ''
  } else {
    corrMsg.value = data.detail || '提交失败'
  }
}
</script>

<template>
  <h1 class="title" style="font-size:24px;">怎么办</h1>
  <p class="slogan">这是求职者与开发者共建的社区。提交后维护者会收到处理（无需 GitHub 账号）</p>

  <div class="card" style="margin-bottom:16px;">
    <h3 style="margin-bottom:8px;">1. 报岗位</h3>
    <p class="muted" style="margin-bottom:10px;">提交你见过的双休岗位；审核通过且企业为白名单后展示</p>
    <input v-model="title" placeholder="岗位名称（必填）" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-bottom:8px;">
    <input v-model="company" placeholder="公司全名（必填）" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-bottom:8px;">
    <div style="display:flex;gap:10px;">
      <input v-model="city" placeholder="城市" style="flex:1;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;">
      <input v-model="salary" placeholder="薪资（如 15-25K）" style="flex:1;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;">
    </div>
    <input v-model="url" placeholder="岗位链接（可选）" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-top:8px;">
    <button class="btn-green" style="margin-top:12px;" @click="submitJob" :disabled="!title.trim() || !company.trim()">提交岗位</button>
    <p v-if="jobMsg" class="muted" style="margin-top:8px;">
      {{ jobMsg }}
      <a v-if="jobIssue" :href="jobIssue" target="_blank" rel="noopener">（查看处理单）</a>
    </p>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h3 style="margin-bottom:8px;">2. 数据纠错</h3>
    <p class="muted" style="margin-bottom:10px;">档案/岗位/好物信息有误？提交后直接送到维护者处理台</p>
    <select v-model="target" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-bottom:8px;">
      <option>企业档案</option>
      <option>岗位数据</option>
      <option>好物目录</option>
      <option>其他</option>
    </select>
    <input v-model="subject" placeholder="涉及对象（必填，如企业/商品名）" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-bottom:8px;">
    <textarea v-model="detail" rows="3" placeholder="问题描述（必填，至少 5 字，可附依据链接）"
      style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:10px;font-size:14px;"></textarea>
    <button class="btn-green" style="margin-top:12px;" @click="submitCorr"
      :disabled="subject.trim().length < 2 || detail.trim().length < 5">提交纠错</button>
    <p v-if="corrMsg" class="muted" style="margin-top:8px;">
      {{ corrMsg }}
      <a v-if="corrIssue" :href="corrIssue" target="_blank" rel="noopener">（查看处理单）</a>
    </p>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h3 style="margin-bottom:8px;">3. 维护好物目录</h3>
    <p class="muted">在 GitHub 仓库 PR 修改 <code>data/goods.csv</code>（只收录白名单企业商品）。<br>详见仓库 <code>CONTRIBUTING.md</code>。</p>
  </div>

  <div class="card">
    <h3 style="margin-bottom:8px;">4. 企业申诉 / 补充证据</h3>
    <p class="muted">企业方申诉请到该企业档案页提交；证据（offer/合同/公开报道链接）可提高企业档案置信度。</p>
  </div>
</template>