import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import Jobs from './views/Jobs.vue'
import Goods from './views/Goods.vue'
import Companies from './views/Companies.vue'
import CompanyDetail from './views/CompanyDetail.vue'
import Appeal from './views/Appeal.vue'
import Contribute from './views/Contribute.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/jobs', component: Jobs },
    { path: '/goods', component: Goods },
    { path: '/companies', component: Companies },
    { path: '/companies/:id', component: CompanyDetail },
    { path: '/appeal', component: Appeal },
    { path: '/contribute', component: Contribute },
  ],
})

createApp(App).use(router).mount('#app')