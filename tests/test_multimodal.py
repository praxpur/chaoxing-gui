# -*- coding: utf-8 -*-
"""多模态题目解析与 OpenAI 兼容请求回归测试。"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from api import answer  # noqa: E402
from api.base import Chaoxing, StudyResult  # noqa: E402
from api.decode import _extract_choices  # noqa: E402


class _ImageResponse:
    status_code = 200
    content = b"fake-png-content"
    headers = {"Content-Type": "image/png"}

    def raise_for_status(self):
        return None


class MultimodalContentTestCase(unittest.TestCase):
    @patch("api.answer.requests.get", return_value=_ImageResponse())
    def test_image_html_becomes_data_url_parts(self, _get):
        content, has_images, images_available = answer._multimodal_content(
            '题目：函数图像<img src="http://example.test/q.png">\n选项：A'
        )

        self.assertTrue(has_images)
        self.assertTrue(images_available)
        self.assertIsInstance(content, list)
        self.assertEqual(content[0], {"type": "text", "text": "题目：函数图像"})
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_plain_html_becomes_text(self):
        content, has_images, images_available = answer._multimodal_content("题目：x<sup>2</sup>+1")

        self.assertFalse(has_images)
        self.assertTrue(images_available)
        self.assertEqual(content, "题目：x2+1")

    def test_choice_parser_preserves_image(self):
        soup = BeautifulSoup('<li>A <img src="http://example.test/a.png"></li>', "lxml")

        choice = _extract_choices(soup.li)

        self.assertIn("A", choice)
        self.assertIn('<img src="http://example.test/a.png">', choice)

    @patch("api.answer.requests.get", return_value=_ImageResponse())
    def test_external_image_request_has_no_session_cookies(self, get):
        result = answer._image_data_url("https://example.test/q.png")

        self.assertTrue(result.startswith("data:image/png;base64,"))
        self.assertIsNone(get.call_args.kwargs["cookies"])
        self.assertNotIn("Referer", get.call_args.kwargs["headers"])

    @patch("api.cookies.use_cookies", return_value={"session": "secret"})
    @patch("api.answer.requests.get", return_value=_ImageResponse())
    def test_chaoxing_request_uses_scoped_cookie_jar(self, get, _cookies):
        result = answer._image_data_url("https://p.ananas.chaoxing.com/q.png")

        self.assertTrue(result.startswith("data:image/png;base64,"))
        jar = get.call_args.kwargs["cookies"]
        self.assertEqual(jar.get("session"), "secret")
        self.assertEqual(list(jar)[0].domain, ".chaoxing.com")
        for url, expected in [
            ("https://chaoxing.com/q.png", "session=secret"),
            ("https://p.ananas.chaoxing.com/q.png", "session=secret"),
            ("https://example.test/q.png", None),
            ("https://chaoxing.com.example.test/q.png", None),
        ]:
            with self.subTest(url=url):
                prepared = requests.Request("GET", url, cookies=jar).prepare()
                self.assertEqual(prepared.headers.get("Cookie"), expected)

    @patch("api.cookies.use_cookies", return_value={"session": "secret"})
    @patch("api.answer.requests.get")
    def test_redirect_to_external_host_drops_cookies(self, get, _cookies):
        """A redirect from Chaoxing to another host must not carry cookies."""
        get.side_effect = [
            SimpleNamespace(status_code=302, headers={"Location": "https://external.test/q.png"}),
            _ImageResponse(),
        ]

        self.assertTrue(answer._image_data_url("https://p.ananas.chaoxing.com/q.png").startswith("data:"))
        first, second = get.call_args_list
        self.assertIsInstance(first.kwargs["cookies"], requests.cookies.RequestsCookieJar)
        self.assertIsNone(second.kwargs["cookies"])
        self.assertNotIn("Referer", second.kwargs["headers"])
        self.assertFalse(first.kwargs["allow_redirects"])
        self.assertFalse(second.kwargs["allow_redirects"])

    @patch("api.cookies.use_cookies")
    @patch("api.answer.requests.get", return_value=_ImageResponse())
    def test_spoofed_chaoxing_hosts_never_load_cookies(self, get, cookies):
        """A hostname containing the domain is not sufficient for authentication."""
        for host in ("chaoxing.com.external.test", "fakechaoxing.com"):
            with self.subTest(host=host):
                answer._image_data_url(f"https://{host}/q.png")
                self.assertIsNone(get.call_args.kwargs["cookies"])
        cookies.assert_not_called()

    @patch("api.answer._MAX_IMAGE_BYTES", 4)
    @patch("api.answer.requests.get", return_value=_ImageResponse())
    def test_oversized_image_is_unavailable(self, _get):
        """Oversized downloads and inline images must never pass through as URLs."""
        self.assertIsNone(answer._image_data_url("https://example.test/q.png"))
        self.assertIsNone(answer._image_data_url("data:image/png;base64,YWJjZGU="))

    @patch("api.cookies.use_cookies", return_value={"session": "secret"})
    @patch("api.answer.requests.get", side_effect=requests.RequestException("403"))
    def test_unavailable_image_is_not_passed_to_model(self, _get, _cookies):
        content, has_images, images_available = answer._multimodal_content(
            '题目<img src="https://p.ananas.chaoxing.com/q.png">'
        )

        self.assertTrue(has_images)
        self.assertFalse(images_available)
        self.assertFalse(any(part["type"] == "image_url" for part in content))


class AIRequestTestCase(unittest.TestCase):
    def test_providers_skip_requests_when_one_image_is_unavailable(self):
        """Neither provider may guess from an incomplete set of images."""
        question = {
            "type": "single",
            "title": '<img src="https://example.test/q.png">',
            "options": 'A 0\nB <img src="https://example.test/b.png">',
        }
        ai = answer.AI()
        ai.endpoint = "https://example.test/v1"
        ai.key = "test-key"
        ai.http_proxy = ""
        siliconflow = answer.SiliconFlow()
        siliconflow.api_key = "test-key"
        with patch("api.answer.OpenAI") as client, patch("api.answer.requests.post") as post:
            for provider in (ai, siliconflow):
                with self.subTest(provider=provider.name):
                    with patch("api.answer._image_data_url", side_effect=["data:image/png;base64,YQ==", None]):
                        self.assertIsNone(provider._query_locked(question))
            client.return_value.chat.completions.create.assert_not_called()
            post.assert_not_called()

    @patch("api.answer.requests.get", return_value=_ImageResponse())
    @patch("api.answer.OpenAI")
    def test_ai_sends_multimodal_user_content(self, openai_cls, _get):
        captured = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"Answer":["正确"]}'))]
                )

        openai_cls.return_value.chat.completions = FakeCompletions()
        ai = answer.AI()
        ai.endpoint = "https://example.test/v1"
        ai.key = "test-key"
        ai.model = "vision-model"
        ai.http_proxy = ""
        ai.min_interval_seconds = 0

        result = ai._query_locked({
            "type": "judgement",
            "title": '<img src="http://example.test/q.png">',
            "options": "正确\n错误",
        })

        self.assertEqual(result, "正确")
        user_message = captured["messages"][-1]
        self.assertIsInstance(user_message["content"], list)
        self.assertTrue(any(part["type"] == "image_url" for part in user_message["content"]))

    @patch("api.answer.requests.get", return_value=_ImageResponse())
    @patch("api.answer.OpenAI")
    def test_image_choice_requests_and_returns_option_letter(self, openai_cls, _get):
        captured = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"Answer":["B"]}'))]
                )

        openai_cls.return_value.chat.completions = FakeCompletions()
        ai = answer.AI()
        ai.endpoint = "https://example.test/v1"
        ai.key = "test-key"
        ai.model = "vision-model"
        ai.http_proxy = ""
        ai.min_interval_seconds = 0

        result = ai._query_locked({
            "type": "single",
            "title": "请选择正确图形",
            "options": 'A <img src="http://example.test/a.png">\nB <img src="http://example.test/b.png">',
        })

        self.assertEqual(result, "B")
        system_message = captured["messages"][0]["content"]
        self.assertIn("只输出 JSON", system_message)
        user_message = captured["messages"][-1]
        self.assertTrue(any(part["type"] == "image_url" for part in user_message["content"]))

    def test_image_choice_rejects_formula_text(self):
        question = {
            "type": "single",
            "title": '<img src="question.png">',
            "options": 'A <img src="a.png">\nB <img src="b.png">',
        }
        self.assertEqual(answer._choice_letters("f(x)=1/x", question), "")
        self.assertEqual(answer._choice_letters("A", question), "A")

    def test_title_image_also_uses_letter_mode(self):
        question = {
            "type": "single",
            "title": '<img src="question.png">',
            "options": "A 1.\nB -1.\nC 0.\nD 不存在.",
        }
        self.assertTrue(answer._image_choice(question))
        self.assertEqual(answer._choice_letters("B", question), "B")


class ImageSubmissionTestCase(unittest.TestCase):
    def test_missing_image_answers_save_blank_without_random_fallback(self):
        """Choice and judgement images without answers must force save-only mode."""
        for question_type in ("single", "multiple", "judgement"):
            with self.subTest(question_type=question_type):
                client = Chaoxing.__new__(Chaoxing)
                client.kwargs = {}
                client.rollback_times = 1
                client.tiku = Mock(DISABLE=False, COVER_RATE=0, is_manual=False)
                client.tiku.query_all.return_value = [None]
                client.tiku.get_submit_params.return_value = ""  # Submit enabled.
                questions = {
                    "questions": [{
                        "id": "test-id",
                        "title": '<img src="https://example.test/q.png">',
                        "type": question_type,
                        "options": "A 1\nB 0",
                        "answerField": {"answertypetest-id": "0"},
                    }],
                }
                session = Mock()
                session.get.return_value = SimpleNamespace(status_code=200, text="test HTML")
                session.post.return_value.status_code = 200
                session.post.return_value.json.return_value = {"status": True, "msg": "saved"}
                with patch("api.base.SessionManager.get_session", return_value=session), \
                        patch("api.base.decode_questions_info", return_value=questions), \
                        patch("api.base.random_answer") as random_answer:
                    result = client.study_work(
                        {"courseId": "test-course", "clazzId": "test-class"},
                        {"jobid": "work-test", "enc": "test-enc"},
                        {"knowledgeid": "test-chapter", "ktoken": "test-token", "cpi": "test-cpi"},
                    )
                self.assertEqual(result, StudyResult.SUCCESS)
                random_answer.assert_not_called()
                data = session.post.call_args.kwargs["data"]
                self.assertEqual(data["pyFlag"], "1")
                self.assertEqual(data["answertest-id"], "")


if __name__ == "__main__":
    unittest.main()
