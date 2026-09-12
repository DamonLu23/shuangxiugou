<script setup>
import { ref } from 'vue'
import { companies, submitAppeal } from '../api'

const list = ref([])
const loading = ref(true)
const companyId = ref(null)
const appealText = ref('')
const appealContact = ref('')
const appealUrl = ref('')
const msg = ref('')

async function load() {
  try {
    list.value = await companies()
  } finally {
    loading.value = false
  }
}
load()

const selected = (id) => companyId.value === id
const select = (id) => { companyId.value = id; msg.value = '' }

async function submit() {
  if (!companyId.value || appealText.value.trim().length < 5) return
  const { ok, data } = await submitAppeal(companyId.value, {
    reason: appealText.value.trim(),
    contact: appealContact.value.trim(),
    evidence_url: appealUrl.value.trim(),
  })
  msg.value = ok ? data.message : (data.detail || '提交失败')
}
</script>

<template>
  <h1 class="title" style="font-size:24px;">企业申诉</h1>
  <p class="slogan">白名单收录有异议？更正 / 删除 / 补充证据，一般 48 小时内处理</p>

  <div v-if="loading" class="loader">加载中…</div>
  <div v-else class="card" style="margin-bottom:16px;">
    <p class="muted" style="margin-bottom:8px;">1. 选择企业</p>
    <label v-for="c in list" :key="c.id" style="display:block;padding:6px 0;cursor:pointer;">
      <input type="radio" :checked="selected(c.id)" @change="select(c.id)" />
      {{ c.name }}（{{ c.level_name }}）
    </label>
  </div>

  <div class="card">
    <p class="muted" style="margin-bottom:8px;">2. 填写申诉</p>
    <textarea v-model="appealText" rows="3" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:10px;font-size:14px;"
      placeholder="申诉事由（至少 5 字）；有官方制度/合同依据请附链接"></textarea>
    <div style="display:flex;gap:10px;margin-top:8px;">
      <input v-model="appealContact" placeholder="联系人/邮箱（可选）" style="flex:1;border:1px solid #e5e5df;border-radius:10px;padding:8px 10px;">
      <input v-model="appealUrl" placeholder="证据链接（可选）" style="flex:1.5;border:1px solid #e5e5df;border-radius:10px;padding:8px 10px;">
    </div>
    <button class="btn-green" style="margin-top:12px;" @click="submit"
      :disabled="!companyId || appealText.trim().length < 5">提交申诉</button>
    <p v-if="msg" class="muted" style="margin-top:8px;">{{ msg }}</p>
    <p class="disclaimer">处理流程与承诺详见仓库 APPEAL.md。</p>
  </div>
</template>