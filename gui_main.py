import os
import sys

# ------------------------------------------------
# 全局网络安全补丁 (解决代理冲突与 SSL 握手断开问题)
# 强制 requests 和 httpx 忽略系统代理(如 Clash/V2ray)，防止 SSLEOFError
os.environ["NO_PROXY"] = "*"
# ------------------------------------------------

import json
import threading
import time
import webview
from loguru import logger
import traceback
import builtins
import tqdm

# 配置文件放在 exe（或脚本）所在目录，避免 cwd 不可写时静默失败
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_CONFIG_PATH = os.path.join(_APP_DIR, "gui_config.json")

# 全局共享的 devnull，避免每个 tqdm 实例各自 open 造成句柄泄漏
_DEVNULL = open(os.devnull, 'w')

# ---- UI State for Polling (Thread-Safe) ----
ui_lock = threading.Lock()
pending_logs = []
progress_state = {}

def push_log(msg):
    with ui_lock:
        pending_logs.append(msg)
        if len(pending_logs) > 1000:
            pending_logs.pop(0)

def push_progress(gui_id, desc, n, total):
    with ui_lock:
        progress_state[gui_id] = {
            "desc": desc,
            "n": n,
            "total": total
        }

# ---- TQDM Patch ----
import tqdm.std

class GuiTqdm(tqdm.std.tqdm):
    def __init__(self, *args, **kwargs):
        self._gui_id = str(id(self))
        kwargs['file'] = _DEVNULL
        super().__init__(*args, **kwargs)
        self._update_gui()

    def update(self, n=1):
        super().update(n)
        self._update_gui()

    def refresh(self, *args, **kwargs):
        super().refresh(*args, **kwargs)
        self._update_gui()

    def reset(self, total=None):
        super().reset(total=total)
        self._update_gui()

    def set_description(self, desc=None, refresh=True):
        super().set_description(desc, refresh)
        self._update_gui()

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        super().set_postfix(ordered_dict, refresh, **kwargs)
        self._update_gui()

    def close(self):
        super().close()
        self._update_gui()

    def _update_gui(self):
        if not hasattr(self, '_gui_id'):
            return
        desc_str = getattr(self, 'desc', "")
        if not desc_str:
            desc_str = ""
        postfix = getattr(self, 'postfix', None)
        if postfix:
            desc_str += f" | {postfix}"
        n = getattr(self, 'n', 0)
        total = getattr(self, 'total', 0)
        push_progress(self._gui_id, str(desc_str), n, total if total else 0)

# Monkey-patch tqdm globally before importing any project modules
tqdm.tqdm = GuiTqdm
tqdm.std.tqdm = GuiTqdm
try:
    import tqdm.auto
    tqdm.auto.tqdm = GuiTqdm
except ImportError:
    pass
# ------------------------------------------------

class PollingLogHandler:
    def write(self, message):
        if message != '\n' and message != '':
            push_log(message.rstrip('\n'))

class StdoutRedirector:
    def write(self, message):
        if message != '\n' and message != '':
            push_log(message.rstrip('\n'))
    def flush(self):
        pass

def build_mapped_tiku_config(tiku_config, answer_enabled, check_llm):
    """将 GUI 题库配置映射为后端 Tiku 所需的 ini 风格配置字典。

    test_api_connection 与 save_config_and_login 共用，避免两处维护不一致。
    高级项（延时/LIKE/GO/JSON 模式等）缺省时回落到与 config_template.ini 相同的默认值，
    所以旧版 gui_config.json 依旧可用。
    """
    use_runtime_values = check_llm  # 连接测试时使用用户填写的硅基流动参数

    def text(key, default=""):
        """取出文本类配置, None 视为未填写."""
        value = tiku_config.get(key, default)
        return default if value is None else str(value)

    def flag(key, default=False):
        """把界面上的布尔开关转换成 ini 中的 true/false."""
        value = tiku_config.get(key, default)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None or value == "":
            return "true" if default else "false"
        return "true" if str(value).strip().lower() in {"1", "true", "yes", "y", "on"} else "false"

    def boolean(key, default=False):
        """likeapi_* 由后端按真值判断, 必须传真正的布尔值, 传 "false" 会被当成开启."""
        value = tiku_config.get(key, default)
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    provider = text("provider") if answer_enabled else ""
    return {
        "provider": provider,
        "submit": flag("submit", False),
        "cover_rate": text("cover_rate", "0.9"),
        "tokens": text("tokens"),
        "endpoint": text("endpoint"),
        "key": text("key"),
        "model": text("model"),
        "true_list": "正确,对,√,是",
        "false_list": "错误,错,×,否,不对,不正确",
        "delay": text("delay", "1.0"),
        "check_llm_connection": "true" if check_llm else "false",
        "likeapi_search": boolean("likeapi_search", False),
        "likeapi_vision": boolean("likeapi_vision", True),
        "likeapi_model": text("likeapi_model", "glm-4.5-air"),
        "likeapi_retry": boolean("likeapi_retry", True),
        "likeapi_retry_times": text("likeapi_retry_times", "3"),
        "go_authorization": text("go_authorization"),
        "go_min_interval": text("go_min_interval", "1.0"),
        "go_retry_times": text("go_retry_times", "3"),
        "go_retry_backoff": text("go_retry_backoff", "1.2"),
        "min_interval_seconds": text("min_interval_seconds", "3"),
        "json_mode": flag("json_mode", False),
        "extra_body": text("extra_body", '{"thinking": {"type": "disabled"}}'),
        "http_proxy": text("http_proxy"),
        "siliconflow_key": text("key") if use_runtime_values else "",
        "siliconflow_model": text("model", "deepseek-ai/DeepSeek-R1") if use_runtime_values else "deepseek-ai/DeepSeek-R1",
        "siliconflow_endpoint": text("endpoint", "https://api.siliconflow.cn/v1/chat/completions") if use_runtime_values else "https://api.siliconflow.cn/v1/chat/completions",
        "manual_mode_default": text("manual_mode_default", "batch"),
        "manual_mode_separator": text("manual_mode_separator", ";"),
        "url": text("url")
    }

# Now import chaoxing internals
from api.base import Chaoxing
from api.answer import Tiku
from main import init_chaoxing, filter_courses, JobProcessor, ChapterTask
from api.notification import Notification
from api.process import increase_learning_count_for_course, sign_in_course

class Api:
    def __init__(self):
        # Prefix all internal states with underscore '_' so pywebview won't serialize them!
        self._chaoxing = None
        self._config = {
            "common": {
                "username": "",
                "password": "",
                "speed": 1.0,
                "jobs": 4,
                "notopen_action": "retry",
                "retry_interval": 1.0,
                "auto_sign": False,
                "work_redo_enabled": False,
                "work_max_retries": 3,
                "add_learning_count": False,
                "target_count": 100,
                "use_cookies": False,
                "verbose": False
            },
            "tiku": {
                "enabled": False,
                "provider": "TikuYanxi",
                "submit": False,
                "cover_rate": 0.9,
                "tokens": "",
                "key": "",
                "endpoint": "",
                "model": "",
                "http_proxy": "",
                "delay": 1.0,
                "json_mode": False,
                "extra_body": '{"thinking": {"type": "disabled"}}',
                "likeapi_search": False,
                "likeapi_vision": True,
                "likeapi_model": "glm-4.5-air",
                "likeapi_retry": True,
                "likeapi_retry_times": 3,
                "go_authorization": "",
                "go_min_interval": 1.0,
                "go_retry_times": 3,
                "go_retry_backoff": 1.2,
                "min_interval_seconds": 3,
                "manual_mode_default": "batch",
                "manual_mode_separator": ";",
                "url": ""
            },
            "notification": {
                "provider": "",
                "url": "",
                "tg_chat_id": ""
            }
        }
        self._load_config()
        self._stop_event = threading.Event()
        self._running_thread = None

    def get_ui_updates(self):
        global pending_logs, progress_state
        with ui_lock:
            logs_copy = pending_logs[:]
            pending_logs.clear()
            progress_copy = progress_state.copy()
        return {"success": True, "logs": logs_copy, "progress": progress_copy}

    def _load_config(self):
        if os.path.exists(GUI_CONFIG_PATH):
            try:
                with open(GUI_CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved_config = json.load(f)
                    for key in self._config:
                        if key in saved_config:
                            self._config[key].update(saved_config[key])
            except Exception as e:
                print("Failed to load config:", e)

    def _save_config(self):
        try:
            with open(GUI_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config to {GUI_CONFIG_PATH}: {e}")

    def get_config(self):
        return {"success": True, "data": self._config}

    def test_api_connection(self, config_str):
        try:
            new_config = json.loads(config_str)
            tiku_config = new_config.get("tiku", self._config.get("tiku", {}))
            if tiku_config.get("enabled", False) is not True:
                return {"success": False, "msg": "答题功能未启用，请先开启“启用答题”开关。"}

            mapped_tiku_config = build_mapped_tiku_config(tiku_config, answer_enabled=True, check_llm=True)
            
            from api.answer import Tiku
            test_tiku = Tiku.get_tiku_from_config(mapped_tiku_config, config_path=None)
            test_tiku.init_tiku()
            
            if not test_tiku.check_llm_connection():
                return {"success": False, "msg": f"{test_tiku.name} 连接测试失败，请检查配置密钥或网络。"}
                
            return {"success": True, "msg": f"{test_tiku.name} 连接测试成功！"}
        except Exception as e:
            return {"success": False, "msg": f"测试异常: {e}"}

    def save_config_and_login(self, config_str):
        try:
            new_config = json.loads(config_str)
            for key in self._config:
                if key in new_config:
                    self._config[key].update(new_config[key])
            self._save_config()
            apply_log_level(bool(self._config["common"].get("verbose", False)))

            common_config = self._config["common"]
            tiku_config = self._config["tiku"]
            answer_enabled = tiku_config.get("enabled", False) is True

            # init_chaoxing 在缺少账号密码时会走 input() 交互, 桌面端会卡死, 这里先拦截
            if not common_config.get("use_cookies") and not (
                common_config.get("username") and common_config.get("password")
            ):
                return {
                    "success": False,
                    "msg": "请填写账号和密码，或开启 Cookie 登录（需要程序目录下的 cookies.txt）",
                }

            mapped_tiku_config = build_mapped_tiku_config(tiku_config, answer_enabled, check_llm=False)
            
            if not answer_enabled:
                logger.info("答题功能已关闭，将跳过章节检测答题")
            
            logger.info("Initializing Chaoxing API...")
            self._chaoxing = init_chaoxing(common_config, mapped_tiku_config, config_path=None)
            
            logger.info(f"Trying to login with account: {common_config['username']}")
            _login_state = self._chaoxing.login(login_with_cookies=common_config.get("use_cookies", False))
            
            if not _login_state["status"]:
                return {"success": False, "msg": _login_state["msg"]}
            
            return {"success": True, "msg": "登录成功"}
        except Exception as e:
            logger.error(f"登录时发生异常: {e}")
            return {"success": False, "msg": str(e)}

    def get_courses(self):
        if not self._chaoxing:
            return {"success": False, "msg": "尚未登录"}
        try:
            all_course = self._chaoxing.get_course_list()
            formatted_courses = []
            for c in all_course:
                formatted_courses.append({
                    "courseId": c.get("courseId", ""),
                    "classId": c.get("clazzId", ""),
                    "title": c.get("title", ""),
                    "class_name": c.get("className", ""),
                    "teacher": c.get("teacher", "")
                })
            return {"success": True, "data": formatted_courses}
        except Exception as e:
            logger.error(f"获取课程异常: {e}")
            return {"success": False, "msg": str(e)}

    def start_tasks(self, course_ids_str):
        if not self._chaoxing:
            return {"success": False, "msg": "未登录"}
        
        course_ids = json.loads(course_ids_str)
        if not course_ids:
            return {"success": False, "msg": "未选择课程"}
            
        if self._running_thread and self._running_thread.is_alive():
            return {"success": False, "msg": "当前已有任务正在运行，请先停止"}

        self._stop_event.clear()
        
        self._running_thread = threading.Thread(target=self._run_tasks_thread, args=(course_ids,))
        self._running_thread.start()
        
        return {"success": True, "msg": "任务已在后台启动"}

    def stop_tasks(self):
        if self._running_thread and self._running_thread.is_alive():
            self._stop_event.set()
            logger.info("已发送停止信号，未开始的任务会被取消，正在执行的章节跑完后停止...")
            return {"success": True, "msg": "已发送停止信号"}
        return {"success": False, "msg": "当前没有运行的任务"}

    def _notification_config(self):
        """把界面上的通知配置转成后端需要的字符串字典."""
        conf = self._config.get("notification", {}) or {}
        return {key: ("" if value is None else str(value)) for key, value in conf.items()}

    def _send_notification(self, message):
        """按当前通知配置推送消息，失败只记日志，不影响主流程."""
        conf = self._notification_config()
        if not conf.get("provider"):
            return
        try:
            notification = Notification()
            notification.config_set(conf)
            service = notification.get_notification_from_config()
            service.init_notification()
            service.send(message)
        except Exception as exc:
            logger.warning(f"发送通知失败: {exc}")

    def _run_tasks_thread(self, course_ids):
        try:
            logger.info(f"开始执行选定的 {len(course_ids)} 门课程...")
            common_config = dict(self._config["common"])
            try:
                common_config["speed"] = min(2.0, max(1.0, float(common_config.get("speed", 1.0) or 1.0)))
            except (TypeError, ValueError):
                common_config["speed"] = 1.0
            common_config["course_list"] = course_ids

            all_course = self._chaoxing.get_course_list()
            # 与命令行一致: 按 (courseId, clazzId) 去重, 课程ID一个都没命中时直接报错
            target_courses = filter_courses(all_course, course_ids)

            # 签到有时效性, 所以在刷课开始前先处理当前进行中的签到
            if common_config.get("auto_sign"):
                logger.info("已开启自动签到, 开始检查签到活动...")
                for course in target_courses:
                    if self._stop_event.is_set():
                        break
                    sign_in_course(self._chaoxing, course)

            tasks = []
            for course in target_courses:
                if self._stop_event.is_set():
                    break
                logger.info(f"正在读取课程章节: {course['title']}")
                point_list = self._chaoxing.get_course_point(
                    course["courseId"], course["clazzId"], course["cpi"]
                )
                for i, point in enumerate(point_list["points"]):
                    task = ChapterTask(point=point, index=i, course=course)
                    tasks.append(task)

            if tasks and not self._stop_event.is_set():
                processor = JobProcessor(
                    self._chaoxing, tasks, common_config, stop_event=self._stop_event
                )
                processor.run()

            if self._stop_event.is_set():
                logger.warning("任务已被手动停止！")
                self._send_notification("超星学习通桌面版: 任务已被手动停止")
                return

            logger.info("========== 所有选定的任务已完成 ==========")
            self._send_notification("超星学习通桌面版: 您选定的课程学习任务已完成")

            # 刷课完成后，如果开启了增加章节学习次数，则执行
            if common_config.get("add_learning_count"):
                logger.info("刷课完成，开始增加章节学习次数...")
                try:
                    common_config["target_count"] = int(common_config.get("target_count", 100) or 100)
                except (TypeError, ValueError):
                    logger.warning("目标次数配置无效, 使用默认值 100")
                    common_config["target_count"] = 100
                for course in target_courses:
                    if self._stop_event.is_set():
                        break
                    increase_learning_count_for_course(self._chaoxing, course, common_config)
                logger.info("所有课程章节学习次数增加完成")
                self._send_notification("超星学习通桌面版: 章节学习次数增加完成")

        except Exception as e:
            logger.error(f"执行任务发生异常: {e}")
            traceback.print_exc()
            self._send_notification(
                f"超星学习通桌面版: 出现错误 {type(e).__name__}: {e}"
            )


def apply_log_level(verbose: bool = False):
    """按配置切换控制台日志级别, 详细日志额外输出 TRACE."""
    logger.remove()
    logger.add(
        PollingLogHandler(),
        format="{message}",
        level="TRACE" if verbose else "DEBUG",
        diagnose=False,
    )


def setup_logger():
    # Intercept loguru logs
    apply_log_level(False)

    # Catch all raw prints and tracebacks safely (Polling mode doesn't crash PyWebView)
    sys.stdout = StdoutRedirector()
    sys.stderr = StdoutRedirector()

if __name__ == '__main__':
    setup_logger()

    # 打包后把工作目录固定到 exe 目录, 让 cookies.txt 等相对路径与配置文件保持一致
    if getattr(sys, 'frozen', False):
        os.chdir(_APP_DIR)

    api = Api()
    
    # 兼容 PyInstaller 打包路径
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    dist_path = os.path.join(base_dir, "gui_dist", "index.html")
    if not os.path.exists(dist_path):
        print(f"Frontend not found at {dist_path}. Please build the Vue project first.")
        sys.exit(1)

    window = webview.create_window('超星学习通 桌面客户端', url=dist_path, js_api=api, width=1024, height=768)
    webview.start(debug=False)
