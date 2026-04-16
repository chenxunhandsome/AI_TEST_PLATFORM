from unittest import TestCase

from apps.core.variable_resolver import clear_runtime_variables, resolve_variables, set_runtime_variable


class VariableResolverTests(TestCase):
    def tearDown(self):
        clear_runtime_variables()

    def test_runtime_variable_reference_resolves_to_stored_value(self):
        set_runtime_variable('abcd', 'qqq')

        self.assertEqual(resolve_variables('${abcd}'), 'qqq')

    def test_timestamp_function_resolves_without_leaving_placeholder(self):
        resolved = resolve_variables('prefix-${timestamp()}')

        self.assertTrue(resolved.startswith('prefix-'))
        self.assertNotIn('${timestamp()}', resolved)
        self.assertTrue(resolved.split('prefix-', 1)[1].isdigit())
