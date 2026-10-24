# -*- coding: utf-8 -*-
"""GUI 与 CLI 功能同步的回归测试.

覆盖三处曾经缺失的能力:
1. 自动签到(auto_sign)在刷课前执行;
2. 刷课完成后按 target_count 增加章节学习次数;
3. 题库高级参数(多题库回退/JSON 模式/LIKE 开关等)正确映射给后端.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import webview  # noqa: F401  # gui_main 在模块级导入 pywebview
except ImportError:  # pragma: no cover - 无 pywebview 的环境跳过 GUI 用例
    webview = None

if webview is None:  # pragma: no cover
    raise unittest.SkipTest("未安装 pywebview, 跳过 GUI 相关测试")

import gui_main  # noqa: E402


class BuildMappedTikuConfigTestCase(unittest.TestCase):
    """界面配置 -> 后端 ini 风格字典的映射."""

    def test_advanced_options_are_mapped(self):
        conf = gui_main.build_mapped_tiku_config(
            {
                "provider": "TikuGo,TikuYanxi",
                "submit": True,
                "cover_rate": 0.8,
                "tokens": "t1,t2",
                "delay": 2.5,
                "go_authorization": "auth",
                "go_min_interval": 0.5,
                "min_interval_seconds": 0,
                "json_mode": True,
                "extra_body": '{"enable_thinking": false}',
                "likeapi_model": "glm-4.5",
                "manual_mode_default": "single",
                "url": "http://127.0.0.1:3000",
            },
            answer_enabled=True,
            check_llm=False,
        )

        self.assertEqual(conf["provider"], "TikuGo,TikuYanxi")
        self.assertEqual(conf["submit"], "true")
        self.assertEqual(conf["cover_rate"], "0.8")
        self.assertEqual(conf["delay"], "2.5")
        self.assertEqual(conf["go_authorization"], "auth")
        self.assertEqual(conf["go_min_interval"], "0.5")
        self.assertEqual(conf["min_interval_seconds"], "0")
        self.assertEqual(conf["json_mode"], "true")
        self.assertEqual(conf["extra_body"], '{"enable_thinking": false}')
        self.assertEqual(conf["likeapi_model"], "glm-4.5")
        self.assertEqual(conf["manual_mode_default"], "single")
        self.assertEqual(conf["url"], "http://127.0.0.1:3000")

    def test_answer_disabled_clears_provider(self):
        conf = gui_main.build_mapped_tiku_config(
            {"provider": "TikuYanxi"}, answer_enabled=False, check_llm=False
        )
        self.assertEqual(conf["provider"], "")

    def test_likeapi_flags_are_real_booleans(self):
        # 后端用真值判断, 传字符串 "false" 会被当成开启
        conf = gui_main.build_mapped_tiku_config(
            {"provider": "TikuLike", "likeapi_search": False, "likeapi_vision": True,
             "likeapi_retry": False},
            answer_enabled=True,
            check_llm=False,
        )
        self.assertIs(conf["likeapi_search"], False)
        self.assertIs(conf["likeapi_vision"], True)
        self.assertIs(conf["likeapi_retry"], False)


class FakeChaoxing:
    """只提供任务流程需要的接口, 不发网络请求."""

    def __init__(self, courses=None):
        """初始化测试替身, 默认返回一门可用课程."""
        self.courses = courses if courses is not None else [
            {"courseId": "100", "clazzId": "200", "cpi": "300", "title": "课程A"}
        ]

    def get_course_list(self):
        return list(self.courses)

    def get_course_point(self, course_id, clazz_id, cpi):
        return {"points": [{"title": "章节1", "has_finished": True}]}


class RunTasksFlowTestCase(unittest.TestCase):
    """验证 Api._run_tasks_thread 的调用顺序与信号联动."""

    def setUp(self):
        gui_main.logger.remove()
        self.api = gui_main.Api()
        self.api._chaoxing = FakeChaoxing()
        self.api._stop_event.clear()
        self.calls = []
        self._originals = {
            name: getattr(gui_main, name)
            for name in ("sign_in_course", "increase_learning_count_for_course", "JobProcessor")
        }
        self._install_fakes()

    def tearDown(self):
        for name, value in self._originals.items():
            setattr(gui_main, name, value)

    def _install_fakes(self, stop_on_run=False):
        """用记录调用顺序的假实现替换外部依赖."""
        calls = self.calls
        api = self.api

        gui_main.sign_in_course = lambda chaoxing, course: calls.append(
            ("sign", course["courseId"])
        )
        gui_main.increase_learning_count_for_course = lambda chaoxing, course, config: calls.append(
            ("count", course["courseId"], config["target_count"])
        )

        class FakeProcessor:
            def __init__(self, chaoxing, tasks, config, stop_event=None):
                calls.append(("processor", config["target_count"], stop_event is not None))

            def run(self):
                calls.append(("run",))
                if stop_on_run:
                    api._stop_event.set()

        gui_main.JobProcessor = FakeProcessor

    def _run(self, course_ids=("100",), stop_on_run=False, **common):
        """执行一次任务流程, 返回记录下来的调用序列."""
        self._install_fakes(stop_on_run=stop_on_run)
        self.api._config["common"].update(common)
        self.api._run_tasks_thread(list(course_ids))
        return self.calls

    def test_auto_sign_runs_before_chapters(self):
        calls = self._run(auto_sign=True)
        self.assertIn(("sign", "100"), calls)
        self.assertLess(calls.index(("sign", "100")), calls.index(("processor", 100, True)))

    def test_auto_sign_disabled_by_default(self):
        calls = self._run()
        self.assertNotIn("sign", [call[0] for call in calls])

    def test_learning_count_runs_after_completion(self):
        calls = self._run(add_learning_count=True, target_count=7)
        self.assertIn(("count", "100", 7), calls)
        self.assertLess(calls.index(("run",)), calls.index(("count", "100", 7)))

    def test_learning_count_skipped_when_disabled(self):
        calls = self._run()
        self.assertNotIn("count", [call[0] for call in calls])

    def test_stop_event_passed_to_processor(self):
        calls = self._run()
        self.assertEqual(calls[0], ("processor", 100, True))

    def test_stopped_run_skips_learning_count(self):
        calls = self._run(stop_on_run=True, add_learning_count=True, target_count=7)
        self.assertIn(("run",), calls)
        self.assertNotIn("count", [call[0] for call in calls])

    def test_unknown_course_id_does_not_start_processor(self):
        # 与 CLI 一致: 课程ID一个都没命中时报错, 不能静默跑空
        calls = self._run(course_ids=("999",))
        self.assertNotIn("processor", [call[0] for call in calls])


class ConfigDefaultsTestCase(unittest.TestCase):
    """GUI 默认配置必须包含 CLI 的全部可调项."""

    def test_common_defaults_cover_cli_options(self):
        common = gui_main.Api()._config["common"]
        for key in (
            "speed",
            "jobs",
            "notopen_action",
            "retry_interval",
            "auto_sign",
            "work_redo_enabled",
            "work_max_retries",
            "add_learning_count",
            "target_count",
            "use_cookies",
            "verbose",
        ):
            self.assertIn(key, common, f"GUI 配置缺少 {key}")

    def test_notification_has_telegram_chat_id(self):
        notification = gui_main.Api()._config["notification"]
        self.assertIn("tg_chat_id", notification)


if __name__ == "__main__":
    unittest.main()
