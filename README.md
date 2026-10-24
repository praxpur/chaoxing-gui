# :computer: 超星学习通自动化完成任务点(命令行版)

<p align="center">
    <a href="https://github.com/Samueli924/chaoxing" target="_blank" style="margin-right: 20px; font-style: normal; text-decoration: none;">
        <img src="https://img.shields.io/github/stars/Samueli924/chaoxing" alt="Github Stars" />
    </a>
    <a href="https://github.com/Samueli924/chaoxing" target="_blank" style="margin-right: 20px; font-style: normal; text-decoration: none;">
        <img src="https://img.shields.io/github/forks/Samueli924/chaoxing" alt="Github Forks" />
    </a>
    <a href="https://github.com/Samueli924/chaoxing" target="_blank" style="margin-right: 20px; font-style: normal; text-decoration: none;">
        <img src="https://img.shields.io/github/languages/code-size/Samueli924/chaoxing" alt="Code-size" />
    </a>
    <a href="https://github.com/Samueli924/chaoxing" target="_blank" style="margin-right: 20px; font-style: normal; text-decoration: none;">
        <img src="https://img.shields.io/github/v/release/Samueli924/chaoxing?display_name=tag&sort=semver" alt="version" />
    </a>
</p>
:muscle: 本项目的最终目的是通过开源消灭所谓的付费刷课平台，希望有能力的朋友都可以为这个项目提交代码，支持本项目的良性发展

:star: 觉得有帮助的朋友可以给个Star

## :point_up: 更新通知
20241021更新通知： 感谢[sz134055](https://github.com/sz134055)提交代码[PR #360](https://github.com/Samueli924/chaoxing/pull/360)，**添加了对题库答题的支持**  

## :file_folder: 项目结构

```text
.
├── main.py                    # 命令行入口
├── gui_main.py                # 桌面客户端入口（PyWebView + Python 桥接）
├── api/                       # 学习、答题、直播、登录等核心业务模块
├── frontend/                  # Vue 3 + TypeScript 桌面前端源码
├── gui_dist/                  # 前端构建产物（生成，不纳入版本控制）
├── resource/                  # 运行时资源（超星字体映射表）
├── tests/                     # pytest 测试
├── packaging/                 # 图标、版本信息、用户说明与图标生成脚本
│   └── assets/                # 图标源文件及构建用 ICO
├── config_template.ini        # 命令行配置文件模板
├── ChaoxingDesktop.spec       # PyInstaller 可复现打包配置
├── requirements.txt           # Python 运行依赖
├── pyproject.toml             # 项目元数据与依赖声明
├── Dockerfile                 # 命令行版容器构建
├── .dockerignore              # 缩小容器构建上下文
├── build/、dist/               # 本地打包中间产物与发布产物（生成，不纳入版本控制）
└── .github/workflows/         # CI 与 Windows 客户端构建流程
```

## :books: 使用方法

### 图形化桌面客户端 (GUI版本)
本项目除了传统的命令行交互外，还提供了一个现代化、全可视化的**独立桌面客户端 (GUI)** (基于 Vue3 + PyWebView 构建)。
**它支持可视化的参数配置、扫码/账密登录、实时进度条面板、运行日志监控，以及可记忆的日间/夜间模式切换。**

桌面端与命令行的能力已对齐，`config_template.ini` 里的可调项在界面上都能找到对应开关：

| 命令行 / ini 配置 | 界面位置 |
| --- | --- |
| `--auto-sign` / `auto_sign` | 基础设置 → 自动签到 |
| `--retry-interval` / `retry_interval` | 基础设置 → 失败重试间隔 |
| `--add-learning-count` / `add_learning_count`、`target_count` | 基础设置 → 自动增加学习次数、目标学习次数 |
| `work_redo_enabled` / `work_max_retries` | 基础设置 → 章节检测答错重做、最大重做次数 |
| `use_cookies` | 基础设置 → 使用 Cookie 登录 |
| `-v/--verbose` | 基础设置 → 详细日志(TRACE) |
| `provider` 多题库回退、`TikuAdapter`、`url` | 题库/AI设置 → 题库引擎提供商（可多选）、适配器地址 |
| `json_mode`、`extra_body`、`delay`、`likeapi_*`、`go_*`、`min_interval_seconds`、`manual_mode_*` | 题库/AI设置 → 高级参数 |
| `notification.url` / `tg_chat_id` | 通知推送 → 推送链接、Telegram chat_id |

> `notopen_action=ask`（遇到关闭章节时交互式询问）为命令行专用：桌面端只有「重试 / 跳过」两种选项。

1. 安装运行依赖与 GUI 附加依赖:
```bash
pip install -r requirements.txt
pip install pywebview
```

2. 启动桌面客户端:
```bash
python gui_main.py
```

> **如何打包为独立可执行文件 (.exe)**
> 先构建前端（`cd frontend && npm ci && npm run build`，产物输出到根目录 `gui_dist/`），然后在项目根目录执行：
> ```bash
> pip install -r requirements.txt pywebview pyinstaller
> pyinstaller --noconfirm --clean ChaoxingDesktop.spec
> ```
> 打包配置（onedir 无黑窗、应用图标、版本信息、资源与模块收集/排除）集中在已纳入版本管理的 `ChaoxingDesktop.spec` 中，保证可复现构建；需要调整时可先用带参数的 `pyinstaller ...` 命令重新生成 spec 再提交。应用图标为扁平化 Material Design 3 风格，运行 `python packaging/build_logo_ico.py` 可重新生成 `packaging/assets/logo.svg`、`logo.png` 与多尺寸 `app.ico`，版本信息见 `packaging/version_info.txt`，各资源用途见 `packaging/README.md`。
> *(使用 `--onedir` 而非 `--onefile`，可避免 cv2 等组件单文件解包失败的问题。)*


### 源码运行（Python 3.13+）

1. clone 项目至本地

```bash
git clone --depth=1 https://github.com/Samueli924/chaoxing 
cd chaoxing
```

2. 安装依赖

```bash
pip install -r requirements.txt
```
或使用 `pip install .`（通过 pyproject.toml 安装依赖）

3. (可选直接运行)

```bash
python main.py
```

4. (可选配置文件运行)

> 复制config_template.ini文件为config.ini文件，修改文件内的账号密码内容

```bash
python main.py -c config.ini
```

5. (可选命令行运行)

```bash
python main.py -u 手机号 -p 密码 -l 课程ID1,课程ID2,课程ID3...(可选) -a [retry|ask|continue](可选)
```

> Tips:  
> 如果已安装低版本 Python 推荐使用 `uv` 运行：

```bash
uv run --python 3.13 main.py
```

使用配置文件运行 ：
```bash
uv run --python 3.13 main.py -c config.ini
```

### 打包文件运行
1. 从最新[Releases](https://github.com/Samueli924/chaoxing/releases)中下载exe文件
2. (可选直接运行) 双击运行即可
3. (可选配置文件运行) 下载config_template.ini文件保存为config.ini文件，修改文件内的账号密码内容, 执行 `./chaoxing.exe -c config.ini`
4. (可选命令行运行)`./chaoxing.exe -u "手机号" -p "密码" -l 课程ID1,课程ID2,课程ID3...(可选) -a [retry|ask|continue](可选)`

### Docker运行
1. 构建Docker镜像
   ```bash
   docker build -t chaoxing .
   ```

2. 运行Docker容器
   ```bash
   # 直接运行（将使用默认配置模板）
   docker run -it chaoxing
   
   # 使用自定义配置文件运行
   docker run -it -v /本地路径/config.ini:/config/config.ini chaoxing
   ```

3. 配置说明
   - Docker版本默认使用挂载到 `/config/config.ini` 的配置文件
   - 首次运行时，会自动将 `config_template.ini` 复制到该位置作为模板
   - 可以将本地编辑好的配置文件挂载到容器中，按照上述示例命令操作

### 题库配置说明

在你的配置文件中找到`[tiku]`，按照注释填写想要使用的题库名（即`provider`，大小写要一致），并填写必要信息，如token，然后在启动时添加`-c [你的配置文件路径]`即可。

题库会默认使用根目录下的`config.ini`文件中的配置，所以你可以复制配置模板（参照前面的说明）命名为`config.ini`，并只配置题库项`[tiku]`，这样即使你不填写账号之类的信息，不使用`-c`参数指定配置文件，题库也会根据这个配置文件自动配置并启用。

对于那些有章节检测且任务点需要解锁的课程，必须配置题库。

**提交模式与答题**
不配置题库（既不提供配置文件，也没有放置默认配置文件`config.ini`或填写要使用的题库）视为不使用题库，对于章节检测等需要答题的任务会自动跳过。
题库覆盖率：搜到的题目占总题目的比例
提交模式`submit`值为

- `true`：会答完题，达到题库题目覆盖率提交，没达到只保存，**正确率不做保证**。
- `false`：会答题，但是不会提交，仅保存搜到答案的，随后你可以自行前往学习通查看、修改、提交。**任何填写不正确的`submit`值会被视为`false`**

> 题库名即`answer.py`模块中根据`Tiku`类实现的具体题库类，例如`TikuYanxi`（言溪题库），在填写时，请务必保持大小写一致。

### 已关闭任务点处理配置说明

在配置文件的 `[common]` 部分，可以通过 `notopen_action` 选项配置遇到已关闭任务点时的处理方式:

- `retry` (默认): 遇到关闭的任务点时尝试重新完成上一个任务点，如果连续重试 3 次仍然失败 (或未配置题库及自动提交) 则停止
- `ask`: 遇到关闭的任务点时询问用户是否继续。选择继续后会自动跳过连续的关闭任务点，直到遇到开放的任务点
- `continue`: 自动跳过所有关闭的任务点，继续检查和完成后续任务点

也可以通过命令行参数 `-a` 或 `--notopen-action` 指定处理方式，例如：

```bash
python main.py -a ask  # 使用询问模式
```

### 章节学习次数配置说明

在配置文件的 `[common]` 部分，可以通过下面两个选项控制章节学习次数功能：

- `add_learning_count = false`：是否在完成刷课任务后，继续对课程章节执行学习次数增加
- `target_count = 100`：章节学习次数的目标总次数，程序会轮询课程章节直到达到该次数

当前实现会先完成所选课程的任务点，再统一执行章节学习次数增加流程。如果开启了 `add_learning_count`，它会作为刷课完成后的追加步骤执行，而不是独立模式。

### 自动签到配置说明

`--auto-sign` 命令行参数，或在 `[common]` 中设置 `auto_sign = true`，会在刷课开始前遍历本次要学习的课程，完成其中**当前正在进行**的签到活动。

- 只处理活动列表中 `status` 为进行中的签到，已结束或未开始的签到不会误触发
- 程序只运行一次检查，不会在刷课过程中轮询；签到开始时间晚于程序启动的，需要重启程序
- 手势签到、位置签到无法代替完成，服务端返回的提示（如距离限制）会原样记录到日志

**外部通知配置说明**

这功能会在所有课程学习任务结束后，或是程序出现错误时，使用外部通知服务推送消息告知你（~~有用但不多~~）

与题库配置类似，不填写视为不使用，按照注释填写想要使用的外部通知服务（也是`provider`，大小写要一致），并填写必要的`url`

## :white_check_mark: 测试与构建检查

```bash
# Python 测试
pip install pytest
python -m pytest tests -q

# 前端构建检查
cd frontend
npm ci
npm run build
```

## :arrows_counterclockwise: 上游同步记录

本仓库已合入上游 [Samueli924/chaoxing](https://github.com/Samueli924/chaoxing) 的以下 PR（保留原作者提交信息）：

| PR | 内容 |
| --- | --- |
| #631 | 修复单选题答案含顿号被误判为多选而随机作答 |
| #633 | AI 题库新增 `json_mode` 与 `extra_body` 配置，移除 DeepSeek 硬编码 |
| #635 | 言溪题库查询失败时的健壮性处理 |
| #637 | 日志与通知中的认证信息脱敏 |
| #638 | wheel 安装包携带字体资源，`chaoxing` 命令可直接使用 |
| #640 | 支持图片型多模态题目 |
| #642 | 课程列表未命中时报错，不再静默学习全部课程 |
| #643 | AI 题库兼容正文为空、答案只在 `reasoning_content` 的响应 |
| #644 | 实现 `--auto-sign` 自动签到 |
| #646 | 视频播放结束后按官方播放器规则重置续播位置 |

未合入的 PR：

- **#630**（任务校验/并发降档/本机控制台）：属于另一套并行架构的重写，会删除本仓库已有的自动签到接口与作答详情解析，功能上属于倒退，故保留在独立分支供评估。
- **#634**（Flask 网页 GUI）：与现有 Vue3 + PyWebView 桌面客户端功能重复，且需重新引入 Flask 依赖，不合并。
- **#639**（任务中心与提交前复核）：仍为 Draft，约 1.6 万行改动，与现有流程冲突面过大，暂不合并。

## :heart: CONTRIBUTORS

![Alt](https://repobeats.axiom.co/api/embed/d3931e84b4b2f17cbe60cafedb38114bdf9931cb.svg "Repobeats analytics image")  

<a style="margin-top: 15px" href="https://github.com/Samueli924/chaoxing/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Samueli924/chaoxing" />
</a>

## :warning: 免责声明
- 本代码遵循 [GPL-3.0 License](https://github.com/Samueli924/chaoxing/blob/main/LICENSE) 协议，允许**开源/免费使用和引用/修改/衍生代码的开源/免费使用**，不允许**修改和衍生的代码作为闭源的商业软件发布和销售**，禁止**使用本代码盈利**，以此代码为基础的程序**必须**同样遵守 [GPL-3.0 License](https://github.com/Samueli924/chaoxing/blob/main/LICENSE) 协议
- 本代码仅用于**学习讨论**，禁止**用于盈利**
- 他人或组织使用本代码进行的任何**违法行为**与本人无关
