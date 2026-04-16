from django.test import TestCase

from apps.ui_automation.locator_strategy_defaults import (
    DEFAULT_LOCATOR_STRATEGIES,
    ensure_default_locator_strategies,
)
from apps.ui_automation.models import LocatorStrategy


class LocatorStrategyDefaultsTests(TestCase):
    def test_ensure_default_locator_strategies_populates_empty_table(self):
        self.assertEqual(LocatorStrategy.objects.count(), 0)

        result = ensure_default_locator_strategies()

        self.assertEqual(result['created_count'], len(DEFAULT_LOCATOR_STRATEGIES))
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['total_count'], len(DEFAULT_LOCATOR_STRATEGIES))
        self.assertEqual(
            list(LocatorStrategy.objects.order_by('id').values_list('name', flat=True)),
            [strategy['name'] for strategy in DEFAULT_LOCATOR_STRATEGIES],
        )

    def test_ensure_default_locator_strategies_is_idempotent(self):
        ensure_default_locator_strategies()

        result = ensure_default_locator_strategies()

        self.assertEqual(result['created_count'], 0)
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['total_count'], len(DEFAULT_LOCATOR_STRATEGIES))
