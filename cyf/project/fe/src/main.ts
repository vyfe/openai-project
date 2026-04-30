import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/tailwind.css'  // 新增：Tailwind CSS
import App from './App.vue'
import router from './router'
import i18n from './i18n' // 引入国际化配置
import { installElementPlus } from './plugins/element-plus'

const app = createApp(App)

app.use(createPinia())
app.use(router)
installElementPlus(app)
app.use(i18n) // 添加国际化支持

app.mount('#app')
