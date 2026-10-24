import { createApp } from 'vue'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'

// 启动时恢复上次主题（默认日间模式）
if (localStorage.getItem('theme') === 'dark') {
  document.documentElement.classList.add('dark')
}

// Element Plus 组件/样式由 unplugin 按需引入（见 vite.config.ts）
const app = createApp(App)
app.mount('#app')
