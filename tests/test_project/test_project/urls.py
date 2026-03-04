from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, re_path


urlpatterns = [
    re_path(r"^polls/", include("test_project.polls.urls", namespace="polls")),
    re_path(r"^admin/", admin.site.urls),
    re_path(r"^accounts/login/$", auth_views.LoginView.as_view(), name="login"),
    re_path(r"^accounts/logout/$", auth_views.LogoutView.as_view(), name="logout"),
]
