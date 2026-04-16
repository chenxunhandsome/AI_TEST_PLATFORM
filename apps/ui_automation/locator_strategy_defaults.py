from apps.ui_automation.models import LocatorStrategy


DEFAULT_LOCATOR_STRATEGIES = [
    {
        'name': 'ID',
        'description': '通过元素的 id 属性定位，最快速可靠',
    },
    {
        'name': 'CSS',
        'description': '通过 CSS 选择器定位，灵活强大',
    },
    {
        'name': 'XPath',
        'description': '通过 XPath 表达式定位，功能最强大',
    },
    {
        'name': 'name',
        'description': '通过元素的 name 属性定位',
    },
    {
        'name': 'class',
        'description': '通过元素的 class 属性定位',
    },
    {
        'name': 'tag',
        'description': '通过 HTML 标签名定位',
    },
    {
        'name': 'text',
        'description': 'Playwright 专用：通过文本内容定位，推荐用于按钮、链接等',
    },
    {
        'name': 'placeholder',
        'description': 'Playwright 专用：通过 placeholder 属性定位输入框',
    },
    {
        'name': 'role',
        'description': 'Playwright 专用：通过 ARIA role 定位，推荐用于可访问性',
    },
    {
        'name': 'label',
        'description': 'Playwright 专用：通过关联的 label 文本定位表单元素',
    },
    {
        'name': 'title',
        'description': 'Playwright 专用：通过 title 属性定位',
    },
    {
        'name': 'test-id',
        'description': 'Playwright 专用：通过 data-testid 属性定位，推荐用于测试',
    },
]


def ensure_default_locator_strategies():
    created_count = 0
    updated_count = 0

    for strategy_data in DEFAULT_LOCATOR_STRATEGIES:
        strategy, created = LocatorStrategy.objects.get_or_create(
            name=strategy_data['name'],
            defaults={'description': strategy_data['description']},
        )

        if created:
            created_count += 1
            continue

        if strategy.description != strategy_data['description']:
            strategy.description = strategy_data['description']
            strategy.save(update_fields=['description'])
            updated_count += 1

    return {
        'created_count': created_count,
        'updated_count': updated_count,
        'total_count': LocatorStrategy.objects.count(),
    }
