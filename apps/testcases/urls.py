from django.urls import path

from . import views

urlpatterns = [
    path("folders/", views.TestCaseFolderListCreateView.as_view(), name="testcase-folder-list"),
    path("folders/<int:pk>/", views.TestCaseFolderDetailView.as_view(), name="testcase-folder-detail"),
    path("move/", views.TestCaseMoveView.as_view(), name="testcase-move"),
    path("", views.TestCaseListCreateView.as_view(), name="testcase-list"),
    path("<int:pk>/", views.TestCaseDetailView.as_view(), name="testcase-detail"),
]
