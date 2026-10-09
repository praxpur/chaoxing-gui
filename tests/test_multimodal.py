# -*- coding: utf-8 -*-
"""多模态题目解析与 OpenAI 兼容请求回归测试。"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from api import answer  # noqa: E402
from api.decode import _extract_choices  # noqa: E402


class _ImageResponse:
    content = b"fake-png-content"
    headers = {"Content-Type": "image/png"}

    def raise_for_status(self):
        return None


class MultimodalContentTestCase(unittest.TestCase):
    @patch("api.answer.requests.get", return_value=_ImageResponse())
    def test_image_html_becomes_data_url_parts(self, _get):
        content, has_images = answer._multimodal_content(
            '题目：函数图像<img src="http://example.test/q.png">\n选项：A'
        )

        self.assertTrue(has_images)
        self.assertIsInstance(content, list)
        self.assertEqual(content[0], {"type": "text", "text": "题目：函数图像"})
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_plain_html_becomes_text(self):
        content, has_images = answer._multimodal_content("题目：x<sup>2</sup>+1")

        self.assertFalse(has_images)
        self.assertEqual(content, "题目：x2+1")

    def test_choice_parser_preserves_image(self):
        soup = BeautifulSoup('<li>A <img src="http://example.test/a.png"></li>', "lxml")

        choice = _extract_choices(soup.li)

        self.assertIn("A", choice)
        self.assertIn('<img src="http://example.test/a.png">', choice)


class AIRequestTestCase(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
