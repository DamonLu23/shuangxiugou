<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const mode = ref('jobs')
const q = ref('')
const city = ref('')

function go() {
  if (!q.value.trim()) return
  if (mode.value === 'jobs') {
    router.push({ path: '/jobs', query: { q: q.value, city: city.value } })
  } else {
    router.push({ path: '/goods', query: { q: q.value } })
  }
}
</script>

<template>
  <h1 class="title">双休购</h1>
  <p class="slogan">找工作，只搜双休企业；买东西，只荐双休企业</p>

  <div class="tabs" style="margin-bottom:18px;">
    <button class="tab" :class="{ active: mode === 'jobs' }" @click="mode = 'jobs'">💼 找工作</button>
    <button class="tab" :class="{ active: mode === 'goods' }" @click="mode = 'goods'">🛒 买好物</button>
  </div>

  <form class="search-box" @submit.prevent="go">
    <input v-model="q" :placeholder="mode === 'jobs' ? '搜索岗位，如 前端/运营/会计' : '搜索品类，如 咖啡/键盘/寄件'" />
    <input v-if="mode === 'jobs'" v-model="city" placeholder="城市（可选）" style="flex:0 0 110px;" />
    <button type="submit">搜索</button>
  </form>

  <div style="margin-top:40px;display:flex;gap:14px;flex-wrap:wrap;">
    <RouterLink to="/jobs" class="btn-green" style="text-decoration:none;">去双休岗位库</RouterLink>
    <RouterLink to="/companies" class="btn-ghost btn-green" style="text-decoration:none;">双休企业榜</RouterLink>
  </div>

  <p class="disclaimer">本网站为白名单项目：严格双休（L1）与双休（L2）企业在此推荐；不收录、不评价、不展示任何企业的负面评级。</p>
</template>