from django.db import models, transaction
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, pagination, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import TestCase, TestCaseFolder
from .serializers import (
    TestCaseCreateSerializer,
    TestCaseFolderSerializer,
    TestCaseListSerializer,
    TestCaseSerializer,
    TestCaseUpdateSerializer,
)


def get_accessible_projects(user):
    return Project.objects.filter(Q(owner=user) | Q(members=user)).distinct()


def create_default_project(user):
    return Project.objects.create(
        name="默认项目",
        owner=user,
        description="系统自动创建的默认项目",
    )


def resolve_project_for_request(user, project_id, allow_auto_create=True):
    accessible_projects = get_accessible_projects(user)

    if project_id not in (None, "", "null"):
        try:
            return accessible_projects.get(id=project_id)
        except (Project.DoesNotExist, ValueError, TypeError) as exc:
            raise ValidationError({"project_id": "项目不存在或您没有访问权限"}) from exc

    project = accessible_projects.first()
    if project:
        return project

    if allow_auto_create:
        return create_default_project(user)

    raise ValidationError({"project_id": "请选择所属项目"})


def resolve_folder_for_project(user, folder_id, project):
    if folder_id in (None, "", "null"):
        return None

    try:
        return TestCaseFolder.objects.get(
            id=folder_id,
            project=project,
            project__in=get_accessible_projects(user),
        )
    except (TestCaseFolder.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError({"folder_id": "文件夹不存在、无权限访问，或不属于当前项目"}) from exc


class TestCasePagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class TestCaseListCreateView(generics.ListCreateAPIView):
    queryset = TestCase.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TestCasePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["priority", "test_type", "project"]
    search_fields = ["title", "description", "folder__name"]
    ordering_fields = ["created_at", "updated_at", "priority"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestCaseCreateSerializer
        return TestCaseListSerializer

    def get_queryset(self):
        queryset = (
            TestCase.objects.filter(project__in=get_accessible_projects(self.request.user))
            .select_related("author", "assignee", "project", "folder")
            .prefetch_related("versions")
            .distinct()
        )

        folder_filter = self.request.query_params.get("folder_filter")
        if folder_filter == "ungrouped":
            queryset = queryset.filter(folder__isnull=True)
        elif folder_filter not in (None, "", "all"):
            if not str(folder_filter).isdigit():
                raise ValidationError({"folder_filter": "文件夹筛选参数无效"})
            queryset = queryset.filter(folder_id=int(folder_filter))

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        project = resolve_project_for_request(user, self.request.data.get("project_id"))
        folder = resolve_folder_for_project(user, self.request.data.get("folder_id"), project)
        serializer.save(author=user, project=project, folder=folder)


class TestCaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TestCase.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return TestCaseUpdateSerializer
        return TestCaseSerializer

    def get_queryset(self):
        return (
            TestCase.objects.filter(project__in=get_accessible_projects(self.request.user))
            .select_related("author", "assignee", "project", "folder")
            .prefetch_related("versions", "step_details", "attachments", "comments")
        )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if "project_id" in self.request.data:
            project = resolve_project_for_request(
                user,
                self.request.data.get("project_id"),
                allow_auto_create=False,
            )
        else:
            project = instance.project

        if "folder_id" in self.request.data:
            folder = resolve_folder_for_project(user, self.request.data.get("folder_id"), project)
        else:
            folder = instance.folder
            if folder and folder.project_id != project.id:
                folder = None

        serializer.save(project=project, folder=folder)


class TestCaseFolderListCreateView(generics.ListCreateAPIView):
    serializer_class = TestCaseFolderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        queryset = (
            TestCaseFolder.objects.filter(project__in=get_accessible_projects(self.request.user))
            .select_related("project", "created_by")
            .annotate(testcase_count=Count("testcases"))
            .order_by("name", "id")
        )

        project_id = self.request.query_params.get("project")
        if project_id not in (None, "", "all"):
            queryset = queryset.filter(project_id=project_id)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        project = resolve_project_for_request(
            user,
            self.request.data.get("project_id"),
            allow_auto_create=False,
        )
        folder_name = (self.request.data.get("name") or "").strip()
        if not folder_name:
            raise ValidationError({"name": "文件夹名称不能为空"})

        if TestCaseFolder.objects.filter(project=project, name=folder_name).exists():
            raise ValidationError({"name": "当前项目下已存在同名文件夹"})

        serializer.save(project=project, created_by=user, name=folder_name)


class TestCaseFolderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestCaseFolderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TestCaseFolder.objects.filter(
            project__in=get_accessible_projects(self.request.user)
        ).select_related("project", "created_by")

    def perform_update(self, serializer):
        folder = self.get_object()
        folder_name = (self.request.data.get("name") or "").strip()
        if not folder_name:
            raise ValidationError({"name": "文件夹名称不能为空"})

        if TestCaseFolder.objects.filter(project=folder.project, name=folder_name).exclude(id=folder.id).exists():
            raise ValidationError({"name": "当前项目下已存在同名文件夹"})

        serializer.save(name=folder_name)


class TestCaseMoveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        testcase_ids = request.data.get("testcase_ids") or []
        folder_id = request.data.get("folder_id")

        if not isinstance(testcase_ids, list) or not testcase_ids:
            raise ValidationError({"testcase_ids": "请至少选择一个测试用例"})

        accessible_projects = get_accessible_projects(request.user)
        testcases = list(
            TestCase.objects.filter(id__in=testcase_ids, project__in=accessible_projects)
            .select_related("project", "folder")
            .distinct()
        )

        if len(testcases) != len(set(testcase_ids)):
            raise ValidationError({"testcase_ids": "部分测试用例不存在或您没有访问权限"})

        folder = None
        if folder_id not in (None, "", "null"):
            try:
                folder = TestCaseFolder.objects.get(id=folder_id, project__in=accessible_projects)
            except (TestCaseFolder.DoesNotExist, ValueError, TypeError) as exc:
                raise ValidationError({"folder_id": "目标文件夹不存在或您没有访问权限"}) from exc

            invalid_testcases = [item.id for item in testcases if item.project_id != folder.project_id]
            if invalid_testcases:
                raise ValidationError(
                    {
                        "folder_id": (
                            "只能将同一项目下的测试用例移动到该文件夹，"
                            f"以下用例不匹配: {', '.join(map(str, invalid_testcases))}"
                        )
                    }
                )

        with transaction.atomic():
            TestCase.objects.filter(id__in=[item.id for item in testcases]).update(folder=folder)

        return Response(
            {
                "message": "移动成功",
                "moved_count": len(testcases),
                "folder_id": folder.id if folder else None,
            },
            status=status.HTTP_200_OK,
        )
