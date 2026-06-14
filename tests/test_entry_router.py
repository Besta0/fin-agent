from __future__ import annotations

import unittest

from financial_agent.entry_router import ENTRY_ROUTER_PROMPT, classify_entry_query


class EntryRouterTest(unittest.TestCase):
    def test_research_query_with_ticker_starts_research(self) -> None:
        route = classify_entry_query("帮我分析一下 NVDA 未来一个月走势")
        self.assertEqual(route.route, "research")
        self.assertTrue(route.should_start_research)

    def test_company_alias_can_start_research(self) -> None:
        route = classify_entry_query("看看苹果最近怎么样")
        self.assertEqual(route.route, "research")
        self.assertTrue(route.should_start_research)

    def test_missing_ticker_does_not_start_research(self) -> None:
        route = classify_entry_query("帮我分析一下未来一个月走势")
        self.assertEqual(route.route, "missing_ticker")
        self.assertFalse(route.should_start_research)
        self.assertIn("不会启动完整投研流程", route.response)

    def test_product_command_with_ticker_does_not_start_research(self) -> None:
        route = classify_entry_query("打开 NVDA 报告")
        self.assertEqual(route.route, "product")
        self.assertFalse(route.should_start_research)

    def test_research_with_preference_word_still_starts_research(self) -> None:
        route = classify_entry_query("我偏好短线，帮我分析 NVDA 的估值风险")
        self.assertEqual(route.route, "research")
        self.assertTrue(route.should_start_research)

    def test_out_of_scope_does_not_start_research(self) -> None:
        route = classify_entry_query("帮我写一段 Python 爬虫代码")
        self.assertEqual(route.route, "out_of_scope")
        self.assertFalse(route.should_start_research)
        self.assertIn("不属于 Fin Agent 的项目范围", route.response)

    def test_prompt_documents_entry_routes(self) -> None:
        self.assertIn("research | missing_ticker | product | out_of_scope", ENTRY_ROUTER_PROMPT)


if __name__ == "__main__":
    unittest.main()
