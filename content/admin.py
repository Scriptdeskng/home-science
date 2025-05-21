from django.contrib import admin
from .models import *

# Register your models here.

from import_export import resources

from import_export.admin import ImportExportModelAdmin, ExportActionMixin


class ContentResource(resources.ModelResource):

    class Meta:
        model = Content


@admin.register(Content)
class ContentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "watch_times",
        "featured",
        "verified",
        "created_at",
    ]
    list_editable = ["featured", "verified", "category"]
    list_filter = ["category", "verified", "featured"]
    search_fields = ["title"]
    resource_class = ContentResource


class EpisodeResource(resources.ModelResource):

    class Meta:
        model = Episode


@admin.register(Episode)
class EpisodeAdmin(ImportExportModelAdmin):
    list_display = ("title", "parent", "upload_date")
    search_fields = ["title", "parent"]

    resource_classes = [EpisodeResource]


class ContentGenreResource(resources.ModelResource):

    class Meta:
        model = ContentGenre


@admin.register(ContentGenre)
class ContentGenreAdmin(ImportExportModelAdmin):
    resource_classes = [ContentGenreResource]


class WatchedContentResource(resources.ModelResource):

    class Meta:
        model = WatchedContent


@admin.register(WatchedContent)
class WatchedContentAdmin(ImportExportModelAdmin):
    resource_classes = [WatchedContentResource]


class ContentCategoryResource(resources.ModelResource):

    class Meta:
        model = ContentCategory


@admin.register(ContentCategory)
class ContentCategoryAdmin(ImportExportModelAdmin):
    resource_classes = [ContentCategoryResource]
