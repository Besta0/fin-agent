from __future__ import annotations

import unittest
from unittest.mock import patch

from financial_agent.tools.run_preflight import run_preflight_payload, run_preflight_rejection_payload


def _settings(api_key_configured: bool = True) -> dict:
    return {
        "provider": "deepseek",
        "provider_label": "DeepSeek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "api_key_configured": api_key_configured,
        "api_key_masked": "已配置 sk-****1234" if api_key_configured else "未配置",
        "api_key_source": "Dashboard" if api_key_configured else None,
        "temperature": 0.2,
    }


class RunPreflightTest(unittest.TestCase):
    @patch("financial_agent.tools.run_preflight.load_user_model_settings")
    def test_research_preflight_can_start_when_model_ready(self, load_settings) -> None:
        load_settings.return_value = _settings(api_key_configured=True)
        payload = run_preflight_payload("帮我分析一下 NVDA 未来一个月走势", user_id="test")
        self.assertTrue(payload["can_start"])
        self.assertEqual(payload["target"]["ticker"], "NVDA")
        self.assertEqual(payload["decision"]["status"], "ready")
        self.assertEqual(payload["estimated_agent_count"], 14)
        self.assertTrue(any(action["kind"] == "start" for action in payload["actions"]))

    @patch("financial_agent.tools.run_preflight.load_user_model_settings")
    def test_research_preflight_blocks_when_api_key_missing(self, load_settings) -> None:
        load_settings.return_value = _settings(api_key_configured=False)
        payload = run_preflight_payload("帮我分析一下 NVDA 未来一个月走势", user_id="test")
        self.assertFalse(payload["can_start"])
        self.assertEqual(payload["route"], "research")
        self.assertIn("missing_api_key", payload["decision"]["blocked_by"])
        self.assertTrue(payload["warnings"])
        self.assertTrue(any(action["kind"] == "settings" for action in payload["actions"]))

    @patch("financial_agent.tools.run_preflight.load_user_model_settings")
    def test_out_of_scope_preflight_never_starts(self, load_settings) -> None:
        load_settings.return_value = _settings(api_key_configured=True)
        payload = run_preflight_payload("帮我写一段 Python 爬虫代码", user_id="test")
        self.assertFalse(payload["can_start"])
        self.assertEqual(payload["route"], "out_of_scope")
        self.assertEqual(payload["decision"]["label"], "超出范围")
        self.assertEqual(payload["estimated_agent_count"], 0)

    @patch("financial_agent.tools.run_preflight.load_user_model_settings")
    def test_rejection_payload_preserves_actions_and_summary(self, load_settings) -> None:
        load_settings.return_value = _settings(api_key_configured=True)
        preflight = run_preflight_payload("你能做什么", user_id="test")
        rejection = run_preflight_rejection_payload(preflight)
        self.assertFalse(rejection["ok"])
        self.assertFalse(rejection["can_start"])
        self.assertEqual(rejection["route"], "product")
        self.assertEqual(rejection["summary"], preflight["summary"])
        self.assertTrue(rejection["actions"])


if __name__ == "__main__":
    unittest.main()
