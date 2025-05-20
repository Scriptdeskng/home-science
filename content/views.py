from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.views.defaults import page_not_found
from django.views.generic import View
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .models import *
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from ums.models import (
    Subscribtion,
    CampaignTracker,
    UserProfile,
    UserSubscribtion,
    CampaignDuplicate,
)
import json
from django.http import JsonResponse
from ums.decorators import allowed_users
from .context_processor import fetch_msisdn

from ums import choices as ums_choices
from ums.subscriptionManager import HML

from ums.tasks import handle_occurence, handle_remarketing

import string, random

from django.utils.crypto import get_random_string
from django.core.cache import cache

# from ratelimit.decorators import ratelimit


# Create your views here.


def error404(request, exception):
    return render(request, "errors/404.html", status=404)


def error500(request):
    return render(request, "errors/500.html")


class Homepage(View):
    def get(self, request):

        # featured = Content.objects.filter(featured=True, verified=True).first()
        # featured2 = Content.objects.filter(featured=True, verified=True).last()
        # featured_content = cache.get("featured_content")
        # if not featured_content:
        # Try to retrieve featured content from cache
        # featured_content = cache.get("featured_content")
        # featured_content_2 = cache.get("featured_content_2")

        featured_content_queryset = Content.objects.filter(
            featured=True, verified=True, trailer_mp4__isnull=False
        ).only("id", "title", "watch_times", "trailer_mp4")

        # Order by watch times descending for featured_content and ascending for featured_content_2
        featured_content = featured_content_queryset.order_by("?").first()

        # Cache the results for 1 hour
        # cache.set("featured_content", featured_content, timeout=60 * 60)  # 1 hour
        # cache.set(
        #     "featured_content_2", featured_content_2, timeout=60 * 60
        # )  # 1 hour

        # Trending today, using only verified contents
        # trending_today = cache.get("trending_today")
        # if not trending_today:
        trending_today = Content.objects.filter(verified=True).only(
            "id", "title", "watch_times", "slug"
        )[:10]
        # cache.set("trending_today", trending_today, timeout=60 * 1440)

        # Recent contents ordered by upload date
        # recent_contents = cache.get("recent_contents")
        # if not recent_contents:
        recent_contents = (
            Content.objects.filter(verified=True)
            .only("id", "title", "slug", "upload_date")
            .order_by("-upload_date")[:10]
        )
        # cache.set("recent_contents", recent_contents, timeout=60 * 1440)

        # Latest episodes ordered by upload date
        # latest_episodes = cache.get("latest_episodes")
        # if not latest_episodes:
        latest_episodes = Episode.objects.only(
            "id", "title", "upload_date", "slug"
        ).order_by("-upload_date")[:10]
        cache.set("latest_episodes", latest_episodes, timeout=60 * 1440)
        template = "content/index.html"

        context = {
            "featured_content": featured_content,
            # "contents": contents,
            "trending_today": trending_today,
            "recent_contents": recent_contents,
            "latest_episodes": latest_episodes,
        }

        return render(request, template, context)


class AllContentsView(View):

    def get(self, request):
        recent_contents = (
            Content.objects.filter(verified=True).all().order_by("upload_date")
        )

        paginator = Paginator(recent_contents, 20)
        page_number = self.request.GET.get("page")
        # contents = paginator.get_page(page)

        try:
            contents = paginator.get_page(
                page_number
            )  # returns the desired page object
        except PageNotAnInteger:
            # if page_number is not an integer then assign the first page
            contents = paginator.page(1)
        except EmptyPage:
            # if page is empty then return last page
            contents = paginator.page(paginator.num_pages)

        template = "content/view-all.html"

        context = {
            "contents": contents,
        }

        return render(request, template, context)


class AllEpisodesContentsView(View):

    def get(self, request):
        recent_episodes = Episode.objects.all().order_by("-upload_date")

        paginator = Paginator(recent_episodes, 20)
        page_number = self.request.GET.get("page")
        # contents = paginator.get_page(page)

        try:
            contents = paginator.get_page(
                page_number
            )  # returns the desired page object
        except PageNotAnInteger:
            # if page_number is not an integer then assign the first page
            contents = paginator.page(1)
        except EmptyPage:
            # if page is empty then return last page
            contents = paginator.page(paginator.num_pages)

        template = "content/view-all-episodes.html"

        context = {
            "contents": contents,
        }

        return render(request, template, context)


# @allowed_users
def content_detail_view(request, slug=None):
    the_content = get_object_or_404(Content, slug=slug)

    other_contents = Content.objects.filter(verified=True).exclude(
        slug=the_content.slug
    )

    try:
        the_content.watch_times += 1
        the_content.save()

        user_profile = fetch_msisdn(request)
        msisdn = user_profile.get("msisdn")

        if msisdn:
            fetch_profile = UserProfile.objects.get(phone=msisdn)
            new_watched, created = WatchedContent.objects.get_or_create(
                user=fetch_profile, content=the_content
            )
            new_watched.count += 1
            new_watched.save()

    except Exception as e:
        pass

    if the_content.category.slug == "series":
        template = "cotent/show_details.html"
    else:
        template = "content/content_detail.html"

    context = {
        "the_content": the_content,
        "other_contents": other_contents,
    }

    # if the_content.category.slug != "series":
    #     context["other_contents"] = other_contents

    return render(request, template, context)


@allowed_users
def episode_detail(request, content_slug=None, episode_slug=None):
    # the_content = Content.object.get(slug=slug)
    the_content = get_object_or_404(Content, slug=content_slug)
    the_episode = get_object_or_404(Episode, slug=episode_slug)
    other_episodes = (
        Episode.objects.filter(parent=the_content).exclude(slug=the_episode.slug).all()
    )
    print(other_episodes)

    template = "cotent/episode_detail.html"

    context = {
        "the_content": the_content,
        "the_episode": the_episode,
        "other_episodes": other_episodes,
    }

    return render(request, template, context)


# @allowed_users
def category(request, category_slug=None):
    print(category_slug)
    the_category = ContentCategory.objects.filter(slug=category_slug).first()
    print(the_category)
    the_contents = Content.objects.filter(category=the_category, verified=True).all()

    paginator = Paginator(the_contents, 20)
    page = request.GET.get("page")
    contents = paginator.get_page(page)

    template = "content/category_content.html"

    context = {
        "the_contents": contents,
        "the_category": the_category,
    }

    return render(request, template, context)


def faqPage(request):

    faq_data = [
        (
            "What is MagicBoxx?",
            "MagicBox service is a video-on-demand where users enjoy premium & quality videos.",
        ),
        (
            "How much does the MagicBox service cost?",
            "Daily Subscription - N75, Weekly Subscription - N100, Monthly subscription - N150",
        ),
        (
            "How do I subscribe for this service?",
            "Daily Subscription - send MBD to 61445, Weekly Subscription - send MBW  to 61445, Monthly subscription - send MBM to 61445",
        ),
        (
            "What happens after I send the subscription request?",
            "Customer received a double opt-in prompt to either accept subscription or decline subscription",
        ),
        ("Do I need to register for the service?", "YES"),
        (
            "What benefits will I enjoy when using the MagicBox service?",
            "Subscribers get to enjoy a collection of entertaining, informative, and educative video content on demand",
        ),
        ("Who can use the MagicBox service?", "Everyone"),
        ("What devices can access the application?", "IOS and Andriod"),
        ("Do I get notified after my MagicBox Plan has expired?", "Yes"),
        (
            "How do I unsubscribe from MagicBox service?",
            "'STOP KEYWORD'. E.g (STOP MBD) for daily",
        ),
    ]
    return render(request, "cotent/faq.html", {"faq_data": faq_data})


def getRequestInfo(request):

    theheaders = json.dumps(dict(request.headers))
    print(theheaders)
    print(type(theheaders))
    returnData = {"MSISDN": theheaders}
    # print(returnData)
    return JsonResponse(returnData)


def echoView(request):
    return HttpResponse("YES, MAGICBOXX IS LIVE !!")
