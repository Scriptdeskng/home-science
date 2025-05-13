from datetime import datetime
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from ums.models import Profile, UserProfile
import uuid
from PIL import Image


class ContentCategory(models.Model):
    slug = models.SlugField()
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name


class ContentGenre(models.Model):
    slug = models.SlugField()
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name


class Content(models.Model):
    slug = models.SlugField()
    title = models.CharField(max_length=120)
    category = models.ForeignKey(ContentCategory, on_delete=models.CASCADE)
    genre = models.ForeignKey(ContentGenre, on_delete=models.CASCADE)
    description = models.TextField()
    language = models.CharField(max_length=120, blank=True, null=True)
    img_banner = models.ImageField(
        upload_to="magicbox/content_images/banner/", blank=True
    )
    img_poster = models.ImageField(
        upload_to="magicbox/content_images/poster/", blank=True
    )
    img_detail_poster = models.ImageField(
        upload_to="magicbox/content_images/poster/", blank=True
    )
    img_detail_banner = models.ImageField(
        upload_to="magicbox/content_images/banner/", blank=True
    )
    img_trailer = models.ImageField(
        upload_to="magicbox/content_images/trailer/", blank=True
    )
    img_thumbnail = models.ImageField(
        upload_to="magicbox/content_images/thumbnai/", blank=True
    )
    trailer_mp4 = models.FileField(
        upload_to="magicbox/content_file/trailer/mp4/", blank=True
    )
    # trailer_webm = models.FileField(
    #     upload_to="magicbox/content_file/trailer/webm/", blank=True
    # )
    file_mp4 = models.FileField(upload_to="magicbox/content_file/mp4/", blank=True)
    # file_webm = models.FileField(upload_to="magicbox/content_file/webm/", blank=True)
    timedelta = models.DurationField(blank=True)
    watch_times = models.IntegerField(default=1)
    upload_date = models.DateField(blank=True)
    featured = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Episode(models.Model):
    slug = models.SlugField()
    title = models.CharField(max_length=120)
    parent = models.ForeignKey(
        Content,
        on_delete=models.DO_NOTHING,
        related_name="content_episodes",
        blank=True,
        null=True,
    )
    description = models.TextField(default="Lorem Ipsum")
    img_banner = models.ImageField(
        upload_to="magicbox/content_images/banner/", blank=True
    )
    img_poster = models.ImageField(
        upload_to="magicbox/content_images/poster/", blank=True
    )
    img_detail_poster = models.ImageField(
        upload_to="magicbox/content_images/poster/", blank=True
    )
    img_detail_banner = models.ImageField(
        upload_to="magicbox/content_images/banner/", blank=True
    )
    img_trailer = models.ImageField(
        upload_to="magicbox/content_images/trailer/", blank=True
    )
    img_thumbnail = models.ImageField(
        upload_to="magicbox/content_images/thumbnai/", blank=True
    )
    trailer_mp4 = models.FileField(
        upload_to="magicbox/content_file/trailer/mp4/", blank=True
    )
    # trailer_webm = models.FileField(
    #     upload_to="magicbox/content_file/trailer/webm/", blank=True
    # )
    file_mp4 = models.FileField(upload_to="magicbox/content_file/mp4/", blank=True)
    # file_webm = models.FileField(upload_to="magicbox/content_file/webm/", blank=True)
    upload_date = models.DateField(blank=True)
    timedelta = models.DurationField(null=True, blank=True)
    position = models.IntegerField()
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.title} - {self.position}"

    def get_next(self):
        next = Episode.objects.filter(id__gt=self.id).order_by("id").first()
        if next:
            return next
        elif next == Episode.objects.order_by("id").last():
            return reverse("")
        else:
            return Episode.objects.order_by("id").first()


class WatchedContent(models.Model):
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="profile_content",
        blank=True,
        null=True,
    )
    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name="watched_content",
        blank=True,
        null=True,
    )
    count = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.user} - {self.content.title} - {self.count}"
