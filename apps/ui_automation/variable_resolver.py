"""
UI鑷姩鍖栨祴璇曞彉閲忚В鏋愬櫒锛堝凡搴熷純锛岃浣跨敤 apps.core.variable_resolver锛夈€傛鏂囦欢淇濈暀鐢ㄤ簬鍚戝悗鍏煎銆?
"""
from apps.core.variable_resolver import (
    VariableResolver,
    resolve_variables,
    set_runtime_variable,
    set_runtime_variables,
    get_runtime_variable,
    get_runtime_variables,
    clear_runtime_variables,
)

__all__ = [
    'VariableResolver',
    'resolve_variables',
    'set_runtime_variable',
    'set_runtime_variables',
    'get_runtime_variable',
    'get_runtime_variables',
    'clear_runtime_variables',
]
