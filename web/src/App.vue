<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header>
    <nav class="container" style="display:flex;gap:24px;align-items:center;padding:20px 20px;">
      <RouterLink to="/" style="font-weight:800;font-size:20px;color:var(--green);">🌿 双休购</RouterLink>
      <RouterLink to="/jobs">找工作</RouterLink>
      <RouterLink to="/goods">买好物</RouterLink>
      <RouterLink to="/companies">企业榜</RouterLink>
      <RouterLink to="/appeal">企业申诉</RouterLink>
      <RouterLink to="/contribute">贡献</RouterLink>
    </nav>
  </header>
  <main class="container">
    <RouterView />
  </main>
  <footer>
    数据来自公开招聘信息与公开讨论，仅供参考 · 这是一个白名单项目：只推荐，不贬损
  </footer>
</template>