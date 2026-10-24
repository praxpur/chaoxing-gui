import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()]
    }),
    Components({
      resolvers: [ElementPlusResolver({ directives: true })]
    })
  ],
  base: './', // Use relative paths so it works in file:// protocol (pywebview)
  build: {
    outDir: '../gui_dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
            if (id.includes('vue')) return 'vue'
            return 'vendor'
          }
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src')
    }
  }
})
