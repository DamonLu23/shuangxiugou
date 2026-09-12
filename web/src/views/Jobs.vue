<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { searchJobs, LEVEL_NAMES } from '../api'

const route = useRoute()
const q = ref(route.query.q || '')
const city = ref(route.query.city || '')
const jobs = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const submitted = ref('')

async function load() {
  if (!q.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    const d = await searchJobs(q.value.trim(), city.value.trim())
    jobs.value = d.jobs
    total.value = d.total
  } catch (e) {
    error.value = `加载失败：${e.message}`
  } finally {
    loading.value = false
  }
}

function submit() {
  submitted.value = q.value
  load()
}

onMounted(() => { if (q.value) load() })
</script>

<template>
  <h1 class="title" style="font-size:24px;">双休岗位库</h1>
  <p class="slogan">只展示严格双休（L1）与双休（L2）企业的在招岗位</p>

  <form class="search-box" @submit.prevent="submit">
    <input v-model="q" placeholder="岗位关键词，如 前端/运营/会计" />
    <input v-model="city" placeholder="城市（可选）" style="flex:0 0 110px;" />
    <button type="submit">搜索</button>
  </form>

  <div v-if="loading" class="loader">搜索中…</div>
  <div v-else-if="error" class="loader">{{ error }}</div>
  <div v-else-if="jobs.length">
    <p class="muted" style="margin:14px 0;">共 {{ total }} 个岗位（白名单企业）</p>
    <div v-for="j in jobs" :key="j.id" class="card" style="margin-bottom:12px;">
      <div class="row" style="padding:4px 0;">
        <div class="name">
          <h3>{{ j.title }}</h3>
          <p>{{ j.company_name }} · {{ j.city || '城市未知' }} · {{ j.salary || '薪资面议' }}</p>
          <p>
            <span v-for="t in j.tags.filter(Boolean)" :key="t" class="chip" style="pointer-events:none;margin:2px;">{{ t }}</span>
          </p>
        </div>
        <span class="badge badge--outline" :class="`l${j.company_level}`">{{ j.company_level_name }}</span>
        <a v-if="j.url && j.url.startsWith('http')" :href="j.url" target="_blank" rel="noopener" class="btn-ghost btn-green" style="text-decoration:none;padding:6px 14px;font-size:13px;">查看岗位</a>
      </div>
    </div>
  </div>
  <div v-else-if="submitted" class="empty">没有找到匹配的双休企业岗位，换个关键词试试</div>
</template>