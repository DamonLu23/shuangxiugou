<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { searchGoods } from '../api'

const route = useRoute()
const q = ref(route.query.q || '')
const items = ref([])
const loading = ref(false)
const error = ref('')
const submitted = ref(false)

async function load() {
  if (!q.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    const d = await searchGoods(q.value.trim())
    items.value = d.items
    submitted.value = true
  } catch (e) {
    error.value = `加载失败：${e.message}`
  } finally {
    loading.value = false
  }
}

function submit() { load() }
onMounted(() => { if (q.value) load() })
</script>

<template>
  <h1 class="title" style="font-size:24px;">双休好物</h1>
  <p class="slogan">由社区维护的好物目录：只有双休企业的商品</p>

  <form class="search-box" @submit.prevent="submit">
    <input v-model="q" placeholder="搜索品类/商品，如 咖啡/键盘/寄件" />
    <button type="submit">搜索</button>
  </form>

  <div v-if="loading" class="loader">搜索中…</div>
  <div v-else-if="error" class="loader">{{ error }}</div>
  <div v-else-if="items.length">
    <div v-for="(it, i) in items" :key="i" class="card" style="margin-bottom:12px;">
      <div class="row" style="padding:4px 0;">
        <div class="name">
          <h3>{{ it.product }}</h3>
          <p>{{ it.company_name }} · {{ it.category }} {{ it.note ? '· ' + it.note : '' }}</p>
        </div>
        <span class="badge badge--solid l1">L1 严格双休</span>
        <a v-if="it.official_link" :href="it.official_link" target="_blank" rel="noopener" class="btn-ghost btn-green" style="text-decoration:none;padding:6px 14px;font-size:13px;">官方店</a>
      </div>
    </div>
  </div>
  <div v-else-if="submitted" class="empty">该品类暂无双休企业好物，可<a href="/contribute">参与贡献</a>提交，或换关键词试试</div>
</template>