# 超星学习通桌面客户端 - 前端

基于 Vue 3 + TypeScript + Vite + Element Plus 构建的 GUI 前端，通过 PyWebView 与 Python 后端 (`gui_main.py`) 交互。

## 开发

```bash
npm install
npm run dev
```

## 构建

```bash
npm run build
```

构建产物输出到项目根目录的 `gui_dist/`（见 `vite.config.ts` 中 `build.outDir`），
`gui_main.py` 启动时会加载 `gui_dist/index.html`。使用相对路径 (`base: './'`) 以兼容
pywebview 的 `file://` 协议加载。

## 目录说明

- `src/App.vue`：主界面（账号配置、课程列表、运行控制面板）
- `src/main.ts`：入口，注册 Vue 与 Element Plus
- `public/`：不参与打包处理的静态资源（favicon、图标）

## 打包 exe

前端构建完成后，回到项目根目录执行 PyInstaller 打包，详见根目录 `README.md` 的打包说明。
