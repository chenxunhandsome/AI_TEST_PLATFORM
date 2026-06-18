from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ui_automation.group_paths import normalize_group_path
from apps.ui_automation.models import Element, ElementGroup, LocatorStrategy, UiProject


User = get_user_model()


class ElementGroupTreeApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='element_group_tree_tester',
            email='element_group_tree_tester@example.com',
            password='password123',
        )
        self.client.force_authenticate(self.user)
        self.project = UiProject.objects.create(
            name='element-group-project',
            description='',
            status='IN_PROGRESS',
            base_url='https://example.com',
            owner=self.user,
        )
        self.locator_strategy = LocatorStrategy.objects.create(name='XPath', description='')
        self.tree_url = '/api/ui-automation/element-groups/tree/'

    def test_normalize_group_path_splits_path_like_segments(self):
        self.assertEqual(
            normalize_group_path(['数据结构设置/数据要素', '选择数据定义弹窗']),
            ['数据结构设置', '数据要素', '选择数据定义弹窗'],
        )
        self.assertEqual(
            normalize_group_path('系统管理模式 > 功能设计 > 业务流程'),
            ['系统管理模式', '功能设计', '业务流程'],
        )

    def test_tree_hides_placeholder_empty_groups_but_keeps_unique_empty_groups(self):
        root_group = ElementGroup.objects.create(project=self.project, name='管理模式首页', order=1)
        valid_group = ElementGroup.objects.create(
            project=self.project,
            name='数据结构设置',
            parent_group=root_group,
            order=1,
        )
        valid_child_group = ElementGroup.objects.create(
            project=self.project,
            name='数据要素',
            parent_group=valid_group,
            order=1,
        )
        target_group = ElementGroup.objects.create(
            project=self.project,
            name='选择数据定义弹窗',
            parent_group=valid_child_group,
            order=1,
        )

        Element.objects.create(
            project=self.project,
            group=target_group,
            name='确定按钮',
            description='',
            element_type='BUTTON',
            locator_strategy=self.locator_strategy,
            locator_value='//button[.="确定"]',
            page='选择数据定义弹窗',
            created_by=self.user,
        )

        ElementGroup.objects.create(project=self.project, name='数据结构设置')
        ElementGroup.objects.create(project=self.project, name='数据结构设置/数据要素')
        ElementGroup.objects.create(project=self.project, name='数据结构设置/数据要素/选择数据定义弹窗')
        ElementGroup.objects.create(project=self.project, name='数据要素')
        ElementGroup.objects.create(project=self.project, name='选择数据定义弹窗')
        unique_empty_group = ElementGroup.objects.create(project=self.project, name='后续补充页面', order=99)

        response = self.client.get(self.tree_url, {'project': self.project.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tree = response.data

        root_names = [node['name'] for node in tree]
        self.assertIn('管理模式首页', root_names)
        self.assertIn(unique_empty_group.name, root_names)
        self.assertNotIn('数据结构设置/数据要素', root_names)
        self.assertNotIn('数据结构设置/数据要素/选择数据定义弹窗', root_names)
        self.assertNotIn('数据结构设置', root_names)
        self.assertNotIn('数据要素', root_names)
        self.assertNotIn('选择数据定义弹窗', root_names)

        data_structure_node = tree[0]['children'][0]
        self.assertEqual(data_structure_node['name'], '数据结构设置')
        self.assertEqual(data_structure_node['children'][0]['name'], '数据要素')
        self.assertEqual(data_structure_node['children'][0]['children'][0]['name'], '选择数据定义弹窗')
