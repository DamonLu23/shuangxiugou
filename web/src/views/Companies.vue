<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { companies, LEVEL_NAMES } from '../api'

const router = useRouter()
const list = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    list.value = await companies()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <h1 class="title" style="font-size:24px;">双休企业榜</h1>
  <p class="slogan">只收录有公开证据支撑的双休企业（白名单）</p>

  <div v-if="loading" class="loader">加载中…</div>
  <div v-else-if="error" class="loader">{{ error }}</div>
  <div v-else-if="!list.length" class="empty">暂未收录企业</div>

  <div v-else class="card">
    <div v-for="c in list" :key="c.name" class="row" style="cursor:pointer;"
         @click="router.push(`/companies/${c.id}`)">
      <span class="badge" :class="c.level === 1 ? 'badge--solid l1' : 'badge--outline l1'">
        {{ c.level === 1 ? 'L1 ' + c.level_name : 'L2 ' + c.level_name }}
      </span>
      <div class="name">
        <h3>{{ c.name }}</h3>
        <p>置信度 {{ Math.round(c.confidence * 100) }}%</p>
      </div>
    </div>
  </div>
</template>