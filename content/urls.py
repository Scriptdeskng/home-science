from django.urls import path
from .views import *


app_name = "content"

urlpatterns = [
    path("", Homepage.as_view(), name="home"),
    path("view-all/", AllContentsView.as_view(), name="all_contents"),
    path("all-episodes/", AllEpisodesContentsView.as_view(), name="all_episodes"),
    path("headers/", getRequestInfo, name="getRequestInfo"),
    path("echo/", echoView, name="echo"),
    path("watch/<slug>/", content_detail_view, name="content_detail_view"),
    path("faq/", faqPage, name="faq"),
    # path("watch/<slug>/", content_detail, name="content_detail"),
    # path("watch-show/<slug>/", show_detail, name="show_detail"),
    path("watch/<content_slug>/<episode_slug>/", episode_detail, name="episode_detail"),
    path("category/<category_slug>/", category, name="category"),
]
