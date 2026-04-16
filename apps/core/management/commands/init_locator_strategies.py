"""
Django管理命令：初始化定位策略
用法：python manage.py init_locator_strategies
"""
from django.core.management.base import BaseCommand
from apps.ui_automation.locator_strategy_defaults import (
    DEFAULT_LOCATOR_STRATEGIES,
    ensure_default_locator_strategies,
)
from apps.ui_automation.models import LocatorStrategy


class Command(BaseCommand):
    help = '初始化UI自动化的元素定位策略'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始初始化定位策略...'))
        existing_names = set(LocatorStrategy.objects.values_list('name', flat=True))
        existing_descriptions = {
            name: description
            for name, description in LocatorStrategy.objects.values_list('name', 'description')
        }

        result = ensure_default_locator_strategies()

        for strategy_data in DEFAULT_LOCATOR_STRATEGIES:
            strategy_name = strategy_data['name']
            if strategy_name not in existing_names:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建策略: {strategy_name}'))
                continue

            if existing_descriptions.get(strategy_name) != strategy_data['description']:
                self.stdout.write(self.style.WARNING(f'  ↻ 更新策略: {strategy_name}'))
            else:
                self.stdout.write(f'  - 策略已存在: {strategy_name}')

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'初始化完成！'))
        self.stdout.write(self.style.SUCCESS(f'新创建: {result["created_count"]} 个'))
        self.stdout.write(self.style.SUCCESS(f'更新: {result["updated_count"]} 个'))
        self.stdout.write(self.style.SUCCESS(f'总计: {result["total_count"]} 个定位策略'))
        self.stdout.write('='*60 + '\n')

        # 列出所有定位策略
        self.stdout.write('\n当前可用的定位策略：')
        for strategy in LocatorStrategy.objects.all().order_by('id'):
            playwright_tag = ' [Playwright专用]' if strategy.name in ['text', 'placeholder', 'role', 'label', 'title', 'test-id'] else ''
            self.stdout.write(f'  - {strategy.name}{playwright_tag}: {strategy.description}')
