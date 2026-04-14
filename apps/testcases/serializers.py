from rest_framework import serializers

from apps.users.serializers import UserSerializer
from apps.versions.serializers import VersionSimpleSerializer

from .models import (
    TestCase,
    TestCaseAttachment,
    TestCaseComment,
    TestCaseFolder,
    TestCaseStep,
)


class TestCaseStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCaseStep
        fields = "__all__"


class TestCaseAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = TestCaseAttachment
        fields = "__all__"


class TestCaseCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = TestCaseComment
        fields = "__all__"


class ProjectSimpleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class TestCaseFolderSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCaseFolder
        fields = ["id", "name"]


class TestCaseFolderSerializer(serializers.ModelSerializer):
    project = ProjectSimpleSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    project_id = serializers.IntegerField(write_only=True, required=False)
    testcase_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TestCaseFolder
        fields = [
            "id",
            "name",
            "project",
            "project_id",
            "created_by",
            "testcase_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "project", "created_by", "testcase_count"]


class TestCaseSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    assignee = UserSerializer(read_only=True)
    project = ProjectSimpleSerializer(read_only=True)
    versions = VersionSimpleSerializer(many=True, read_only=True)
    step_details = TestCaseStepSerializer(many=True, read_only=True)
    attachments = TestCaseAttachmentSerializer(many=True, read_only=True)
    comments = TestCaseCommentSerializer(many=True, read_only=True)
    folder = TestCaseFolderSimpleSerializer(read_only=True)
    folder_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "title",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "status",
            "test_type",
            "tags",
            "author",
            "assignee",
            "project",
            "folder",
            "folder_id",
            "versions",
            "step_details",
            "attachments",
            "comments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TestCaseListSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()
    folder = TestCaseFolderSimpleSerializer(read_only=True)
    folder_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "title",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "test_type",
            "author",
            "assignee",
            "project",
            "folder",
            "folder_id",
            "versions",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_author(self, obj):
        return {"id": obj.author.id, "username": obj.author.username} if obj.author else None

    def get_assignee(self, obj):
        return {"id": obj.assignee.id, "username": obj.assignee.username} if obj.assignee else None

    def get_project(self, obj):
        return {"id": obj.project.id, "name": obj.project.name} if obj.project else None

    def get_versions(self, obj):
        return [
            {"id": version.id, "name": version.name, "is_baseline": version.is_baseline}
            for version in obj.versions.all()
        ]


class TestCaseCreateSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(required=False, allow_null=True)
    folder_id = serializers.IntegerField(required=False, allow_null=True)
    version_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = TestCase
        fields = [
            "title",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "test_type",
            "tags",
            "project_id",
            "folder_id",
            "version_ids",
        ]

    def create(self, validated_data):
        version_ids = validated_data.pop("version_ids", [])
        validated_data.pop("project_id", None)
        validated_data.pop("folder_id", None)

        testcase = super().create(validated_data)
        if version_ids:
            testcase.versions.set(version_ids)

        return testcase


class TestCaseUpdateSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(required=False, allow_null=True)
    folder_id = serializers.IntegerField(required=False, allow_null=True)
    version_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = TestCase
        fields = [
            "title",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "test_type",
            "tags",
            "project_id",
            "folder_id",
            "version_ids",
        ]

    def update(self, instance, validated_data):
        version_ids = validated_data.pop("version_ids", None)
        validated_data.pop("project_id", None)
        validated_data.pop("folder_id", None)

        instance = super().update(instance, validated_data)
        if version_ids is not None:
            instance.versions.set(version_ids)

        return instance
