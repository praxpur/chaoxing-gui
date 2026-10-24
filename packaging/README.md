# 打包资源

本目录只存放 Windows 打包相关资源与脚本，运行时业务资源位于根目录 `resource/`。

| 文件 | 用途 |
|---|---|
| `assets/logo.svg` | 应用图标的矢量母版（扁平化 Material Design 3 风格） |
| `assets/logo.png` | 1024×1024 图标位图母版 |
| `assets/app.ico` | 写入 exe 的多尺寸图标（16/24/32/48/64/128/256） |
| `assets/logo_preview.png` | 各尺寸图标检查图，由脚本生成，不参与打包 |
| `build_logo_ico.py` | 从矢量定义重新生成上述图标资源 |
| `version_info.txt` | 写入 exe 的 Windows 版本信息 |
| `使用说明.txt` | 随发布包分发的用户说明模板 |

## 重新生成图标

在项目根目录执行：

```bash
python packaging/build_logo_ico.py
```

## 构建 Windows 客户端

先构建前端，再使用根目录的 PyInstaller 配置打包：

```bash
cd frontend
npm ci
npm run build
cd ..
pyinstaller --noconfirm --clean ChaoxingDesktop.spec
```

`ChaoxingDesktop.spec` 使用相对路径引用本目录的 `assets/app.ico` 和 `version_info.txt`，因此打包命令需在项目根目录执行。
