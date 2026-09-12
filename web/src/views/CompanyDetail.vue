<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { companyDetail, submitAppeal, levelBadgeClass } from '../api'

const route = useRoute()
const c = ref(null)
const loading = ref(true)
const error = ref('')
const appealText = ref('')
const appealContact = ref('')
const appealUrl = ref('')
const submittedMsg = ref('')

onMounted(async () => {
  try {
    c.value = await companyDetail(Number(route.params.id))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function submitAppealForm() {
  if (appealText.value.trim().length < 5) return
  const { ok, data } = await submitAppeal(c.value.id, {
    reason: appealText.value.trim(),
    contact: appealContact.value.trim(),
    evidence_url: appealUrl.value.trim(),
  })
  submittedMsg.value = ok ? data.message : (data.detail || '提交失败')
}
</script>

<template>
  <div v-if="loading" class="loader">加载中…</div>
  <div v-else-if="error" class="loader">{{ error }}</div>
  <template v-else-if="c">
    <h1 class="title" style="font-size:24px;">{{ c.name }}</h1>
    <p class="slogan">
      <span class="badge badge--solid l1">{{ c.level_name }}</span>
      &nbsp;置信度 {{ Math.round(c.confidence * 100) }}% · {{ c.evidence_count }} 条证据
    </p>

    <div class="card" style="margin-bottom:16px;">
      <h3 style="margin-bottom:10px;">证据来源（公开渠道，可点击复核）</h3>
      <div v-for="(ev, i) in c.evidences" :key="i" style="padding:8px 0;border-bottom:1px solid #f0f0ea;">
        <p class="muted">{{ ev.source_type }} · {{ ev.keywords.join('、') }} · {{ ev.collected_at }}</p>
        <a v-if="ev.url && ev.url.startsWith('http')" :href="ev.url" target="_blank" rel="noopener" style="font-size:13px;word-break:break-all;">{{ ev.url }}</a>
        <p v-else class="muted">（UGC 审核证据，不公开原文）</p>
      </div>
      <p v-if="!c.evidences.length" class="muted">暂无公开证据</p>
    </div>

    <div class="card">
      <h3 style="margin-bottom:10px;">信息有误？企业申诉/更正</h3>
      <textarea v-model="appealText" rows="3" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:10px;font-size:14px;"
        placeholder="说明申诉事由（至少 5 字），附官方制度/合同等依据链接更佳"></textarea>
      <div style="display:flex;gap:10px;margin-top:8px;">
        <input v-model="appealContact" placeholder="联系人/邮箱（可选）" style="flex:1;border:1px solid #e5e5df;border-radius:10px;padding:8px 10px;">
        <input v-model="appealUrl" placeholder="证据链接（可选）" style="flex:1.5;border:1px solid #e5e5df;border-radius:10px;padding:8px 10px;">
      </div>
      <button class="btn-green" style="margin-top:12px;" @click="submitAppealForm"
        :disabled="appealText.trim().length < 5">提交申诉</button>
      <p v-if="submittedMsg" class="muted" style="margin-top:8px;">{{ submittedMsg }}</p>
    </div>

    <p class="disclaimer">双休等级由公开渠道信息交叉验证生成，仅供参考。本页面仅展示白名单（L1/L2）企业。</p>
  </template>
</template>