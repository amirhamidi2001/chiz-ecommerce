from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("posts/", views.PostListView.as_view(), name="post-list"),
    path("posts/<slug:slug>/", views.PostDetailView.as_view(), name="post-detail"),
    path(
        "posts/<slug:slug>/related/",
        views.RelatedPostsView.as_view(),
        name="post-related",
    ),
    path(
        "posts/<slug:slug>/comments/",
        views.CommentCreateView.as_view(),
        name="comment-create",
    ),
]
