from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ui_automation.models import TestCase, TestCaseStep, UiProject


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

    def test_copy_case_uses_next_available_suffix(self):
        source_case = self.create_case('case-alpha')
        self.create_case('case-alpha_copy')

        response = self.client.post(f'{self.list_url}{source_case.id}/copy_case/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'case-alpha_copy_2')
