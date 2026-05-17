from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ui_automation.models import Element, LocatorStrategy, TestCase, TestCaseFolder, TestCaseStep, UiProject


User = get_user_model()


class TestCaseManagementApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ui_case_tester',
            email='ui_case_tester@example.com',
            password='password123'
        )
        self.client.force_authenticate(self.user)
        self.project = UiProject.objects.create(
            name='ui-project',
            description='',
            status='IN_PROGRESS',
            base_url='https://example.com',
            owner=self.user
        )
        self.list_url = '/api/ui-automation/test-cases/'

    def create_case(self, name):
        return TestCase.objects.create(
            name=name,
            description='',
            project=self.project,
            status='draft',
            priority='medium',
            created_by=self.user
        )

    def create_step(self, test_case, step_number=1, description='step-1'):
        return TestCaseStep.objects.create(
            test_case=test_case,
            step_number=step_number,
            action_type='click',
            description=description,
            wait_time=1000
        )

    def create_element(self):
        locator_strategy = LocatorStrategy.objects.create(name='css')
        return Element.objects.create(
            project=self.project,
            name='submit',
            description='',
            element_type='BUTTON',
            page='',
            component_name='',
            locator_strategy=locator_strategy,
            locator_value='.old-submit',
            wait_timeout=5,
            created_by=self.user,
        )

    def create_folder(self, name='folder-alpha'):
        return TestCaseFolder.objects.create(
            project=self.project,
            name=name,
            created_by=self.user
        )

    def test_create_rejects_duplicate_name_within_same_project(self):
        self.create_case('case-alpha')

        response = self.client.post(self.list_url, {
            'name': 'case-alpha',
            'description': 'duplicate',
            'project': self.project.id,
            'priority': 'medium',
            'steps': []
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_update_rejects_duplicate_name_within_same_project(self):
        self.create_case('case-alpha')
        target_case = self.create_case('case-beta')

        response = self.client.patch(f'{self.list_url}{target_case.id}/', {
            'name': 'case-alpha'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_patch_without_steps_keeps_existing_steps(self):
        test_case = self.create_case('case-with-step')
        self.create_step(test_case)

        response = self.client.patch(f'{self.list_url}{test_case.id}/', {
            'description': 'updated-description'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        test_case.refresh_from_db()
        self.assertEqual(test_case.description, 'updated-description')
        self.assertEqual(test_case.steps.count(), 1)

    def test_update_steps_preserves_step_locator_override(self):
        test_case = self.create_case('case-with-override')
        element = self.create_element()

        response = self.client.patch(f'{self.list_url}{test_case.id}/', {
            'name': test_case.name,
            'steps': [{
                'step_number': 1,
                'action_type': 'click',
                'element_id': element.id,
                'element_locator_strategy': 'xpath',
                'element_locator_value': "//button[@data-test='submit']",
                'element_locator_override_enabled': True,
                'description': 'click submit',
                'wait_time': 1000,
            }]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        step = test_case.steps.get()
        self.assertEqual(step.element, element)
        self.assertEqual(step.element_locator_strategy, 'xpath')
        self.assertEqual(step.element_locator_value, "//button[@data-test='submit']")
        self.assertTrue(step.element_locator_override_enabled)

    def test_copy_case_uses_next_available_suffix(self):
        source_case = self.create_case('case-alpha')
        self.create_case('case-alpha_copy')

        response = self.client.post(f'{self.list_url}{source_case.id}/copy_case/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'case-alpha_copy_2')

    def test_batch_delete_removes_multiple_cases(self):
        case_alpha = self.create_case('case-alpha')
        case_beta = self.create_case('case-beta')

        response = self.client.post(f'{self.list_url}batch-delete/', {
            'ids': [case_alpha.id, case_beta.id]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertFalse(TestCase.objects.filter(id__in=[case_alpha.id, case_beta.id]).exists())

    def test_delete_folder_keeps_cases_and_moves_them_to_ungrouped(self):
        folder = self.create_folder()
        test_case = self.create_case('case-with-folder')
        test_case.folder = folder
        test_case.save(update_fields=['folder'])

        response = self.client.delete(f'/api/ui-automation/test-case-folders/{folder.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['affected_test_case_count'], 1)
        test_case.refresh_from_db()
        self.assertIsNone(test_case.folder)
        self.assertFalse(TestCaseFolder.objects.filter(id=folder.id).exists())
