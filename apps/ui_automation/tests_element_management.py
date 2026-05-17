from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ui_automation.models import Element, ElementGroup, LocatorStrategy, TestCase as UiTestCase, TestCaseStep, UiProject
from apps.ui_automation.step_element_resolver import build_step_element_data


User = get_user_model()


class ElementManagementApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='element_management_tester',
            email='element_management_tester@example.com',
            password='password123',
        )
        self.client.force_authenticate(self.user)
        self.project = UiProject.objects.create(
            name='element-management-project',
            description='',
            status='IN_PROGRESS',
            base_url='https://example.com',
            owner=self.user,
        )
        self.locator_strategy = LocatorStrategy.objects.create(name='CSS', description='')
        self.list_url = '/api/ui-automation/elements/'
        self.group_list_url = '/api/ui-automation/element-groups/'

    def create_element(self, name, locator_value):
        return Element.objects.create(
            project=self.project,
            name=name,
            description='',
            locator_strategy=self.locator_strategy,
            locator_value=locator_value,
            page='管理页面',
            created_by=self.user,
        )

    def test_batch_delete_removes_multiple_elements(self):
        element_alpha = self.create_element('element-alpha', '#alpha')
        element_beta = self.create_element('element-beta', '#beta')

        response = self.client.post(f'{self.list_url}batch-delete/', {
            'ids': [element_alpha.id, element_beta.id]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertFalse(Element.objects.filter(id__in=[element_alpha.id, element_beta.id]).exists())

    def test_batch_delete_rejects_missing_ids(self):
        response = self.client.post(f'{self.list_url}batch-delete/', {
            'ids': []
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_element_locator_update_syncs_unoverridden_steps_and_preserves_manual_override(self):
        element = self.create_element('submit', '#old-submit')
        test_case = UiTestCase.objects.create(
            name='case-with-element',
            description='',
            project=self.project,
            status='draft',
            priority='medium',
            created_by=self.user,
        )
        inherited_step = TestCaseStep.objects.create(
            test_case=test_case,
            step_number=1,
            action_type='click',
            element=element,
            description='click inherited',
        )
        manual_step = TestCaseStep.objects.create(
            test_case=test_case,
            step_number=2,
            action_type='click',
            element=element,
            element_locator_strategy='xpath',
            element_locator_value="//button[@data-test='manual']",
            element_locator_override_enabled=True,
            description='click manual',
        )
        auto_copied_step = TestCaseStep.objects.create(
            test_case=test_case,
            step_number=3,
            action_type='click',
            element=element,
            element_locator_strategy='CSS',
            element_locator_value='#old-submit',
            element_locator_override_enabled=False,
            description='click copied',
        )

        response = self.client.patch(f'{self.list_url}{element.id}/', {
            'project_id': self.project.id,
            'locator_strategy_id': self.locator_strategy.id,
            'locator_value': '#new-submit',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        inherited_step.refresh_from_db()
        manual_step.refresh_from_db()
        auto_copied_step.refresh_from_db()
        self.assertEqual(build_step_element_data(inherited_step)['locator_value'], '#new-submit')
        self.assertEqual(build_step_element_data(manual_step)['locator_value'], "//button[@data-test='manual']")
        self.assertEqual(auto_copied_step.element_locator_value, '')
        self.assertEqual(build_step_element_data(auto_copied_step)['locator_value'], '#new-submit')

    def test_group_allows_same_name_under_different_parent(self):
        ElementGroup.objects.create(
            project=self.project,
            name='共享文件夹',
            description='root folder',
        )
        parent_group = ElementGroup.objects.create(
            project=self.project,
            name='父级文件夹',
            description='parent folder',
        )

        response = self.client.post(self.group_list_url, {
            'project': self.project.id,
            'parent_group': parent_group.id,
            'name': '共享文件夹',
            'description': 'nested folder',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ElementGroup.objects.filter(
            project=self.project,
            parent_group=parent_group,
            name='共享文件夹',
        ).exists())

        tree_response = self.client.get(f'{self.group_list_url}tree/', {'project': self.project.id})
        self.assertEqual(tree_response.status_code, status.HTTP_200_OK)
        root_names = [node['name'] for node in tree_response.data]
        self.assertIn('共享文件夹', root_names)
        parent_node = next(node for node in tree_response.data if node['name'] == '父级文件夹')
        child_names = [node['name'] for node in parent_node['children']]
        self.assertIn('共享文件夹', child_names)

    def test_group_rejects_same_name_under_same_parent(self):
        parent_group = ElementGroup.objects.create(
            project=self.project,
            name='父级文件夹',
            description='parent folder',
        )
        ElementGroup.objects.create(
            project=self.project,
            parent_group=parent_group,
            name='同级文件夹',
            description='existing folder',
        )

        response = self.client.post(self.group_list_url, {
            'project': self.project.id,
            'parent_group': parent_group.id,
            'name': '同级文件夹',
            'description': 'duplicate folder',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_group_rejects_path_separator_in_name(self):
        response = self.client.post(self.group_list_url, {
            'project': self.project.id,
            'name': 'abc/abc',
            'description': 'invalid folder name',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
        self.assertFalse(ElementGroup.objects.filter(project=self.project, name='abc/abc').exists())
