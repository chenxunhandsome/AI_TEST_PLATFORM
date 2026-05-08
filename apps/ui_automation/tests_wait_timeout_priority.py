from types import SimpleNamespace
from unittest import TestCase

from apps.ui_automation.playwright_engine import resolve_element_action_timeout_ms
from apps.ui_automation.selenium_engine import resolve_element_action_timeout_seconds


class ElementActionTimeoutPriorityTests(TestCase):
    def test_manual_step_wait_time_overrides_element_default_in_playwright(self):
        step = SimpleNamespace(wait_time=8000)

        timeout_ms = resolve_element_action_timeout_ms(step, {'wait_timeout': 5})

        self.assertEqual(timeout_ms, 8000)

    def test_default_step_wait_time_uses_element_timeout_in_playwright(self):
        step = SimpleNamespace(wait_time=1000)

        timeout_ms = resolve_element_action_timeout_ms(step, {'wait_timeout': 5})

        self.assertEqual(timeout_ms, 5000)

    def test_manual_step_wait_time_overrides_element_default_in_selenium(self):
        step = SimpleNamespace(wait_time=8000)

        timeout_seconds = resolve_element_action_timeout_seconds(step, {'wait_timeout': 5})

        self.assertEqual(timeout_seconds, 8)

    def test_default_step_wait_time_uses_element_timeout_in_selenium(self):
        step = SimpleNamespace(wait_time=1000)

        timeout_seconds = resolve_element_action_timeout_seconds(step, {'wait_timeout': 5})

        self.assertEqual(timeout_seconds, 5)
