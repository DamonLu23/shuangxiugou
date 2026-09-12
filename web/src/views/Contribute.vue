<script setup>
import { ref } from 'vue'
import { reportJob } from '../api'

const title = ref('')
const company = ref('')
const city = ref('')
const salary = ref('')
const url = ref('')
const msg = ref('')

async function submit() {
  const { ok, data } = await reportJob({
    title: title.value,
    company_name: company.value,
    city: city.value,
    salary: salary.value,
    url: url.value,
  })
  msg.value = ok ? data.message : (data.detail || '提交失败')
}
</script>

<template>
  <h1 class="title" style="font-size:24px;">怎么办</h1>
  <p class="slogan">这是求职者与开发者共建的社区。三种方式参与：</p>

  <div class="card" style="margin-bottom:16px;">
    <h3 style="margin-bottom:8px;">1. 提交你见过的双休岗位</h3>
    <p class="muted" style="margin-bottom:10px;">审核通过且企业为白名单后展示</p>
    <input v-model="title" placeholder="岗位名称（必填）" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-bottom:8px;">
    <input v-model="company" placeholder="公司全名（必填）" style="width:100%;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;margin-bottom:8px;">
    <div style="display:flex;gap:10px;">
      <input v-model="city" placeholder="城市" style="flex:1;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;">
      <input v-model="salary" placeholder="薪资（如 15-25K）" style="flex:1;border:1px solid #e5e5df;border-radius:10px;padding:9px 12px;">
    </div>
    <button class="btn-green" style="margin-top:12px;" @click="submit" :disabled="!title.trim() || !company.trim()">提交岗位</button>
    <p v-if="msg" class="muted" style="margin-top:8px;">{{ msg }}</p>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h3 style="margin-bottom:8px;">2. 维护好物目录</h3>
    <p class="muted">在 GitHub 仓库 PR 修改 <code>data/goods.csv</code>（只收录白名单企业商品）。<br>详见仓库 <code>CONTRIBUTING.md</code>。</p>
  </div>

  <div class="card">
    <h3 style="margin-bottom:8px;">3. 补充企业证据 / 提出申诉</h3>
    <p class="muted">证据（offer/合同/公开报道链接）可提高企业档案置信度；企业方申诉请提交该企业档案页的「申诉」表单。</p>
  </div>
</template>