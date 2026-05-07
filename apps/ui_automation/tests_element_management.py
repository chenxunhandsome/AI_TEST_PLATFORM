from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ui_automation.models import Element, LocatorStrategy, UiProject


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
