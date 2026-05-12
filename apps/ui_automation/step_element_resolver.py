def _strategy_name(locator_strategy):
    if hasattr(locator_strategy, 'name'):
        return locator_strategy.name
    return str(locator_strategy or '').strip()


def build_step_element_data(step):
    element = getattr(step, 'element', None)
    override_strategy = str(getattr(step, 'element_locator_strategy', '') or '').strip()
    override_value = str(getattr(step, 'element_locator_value', '') or '').strip()

    if element:
        locator_strategy = override_strategy or _strategy_name(getattr(element, 'locator_strategy', None)) or 'css'
        locator_value = override_value or str(getattr(element, 'locator_value', '') or '')
        if not locator_value:
            return None

        return {
            'locator_strategy': locator_strategy,
            'locator_value': locator_value,
            'name': getattr(element, 'name', '') or locator_value,
            'wait_timeout': getattr(element, 'wait_timeout', 5),
            'force_action': getattr(element, 'force_action', False),
        }

    if override_value:
        return {
            'locator_strategy': override_strategy or 'css',
            'locator_value': override_value,
            'name': str(getattr(step, 'description', '') or '').strip() or '自定义元素',
            'wait_timeout': 5,
            'force_action': False,
        }

    return None
