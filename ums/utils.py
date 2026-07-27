import logging

import requests
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme

from .models import UserProfile, UserSubscribtion

logger = logging.getLogger(__name__)

COOKIE_SALT = "ums"
COOKIE_MAX_AGE = 86400  # 1 day

INTELLI_SERVICE_ID = 7


def safe_next_url(request, next_url):
    """Reject off-site/absolute-scheme next= values to prevent open redirects."""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return ""


def normalize_msisdn(phone):
    """Converts 08012345678 -> 2348012345678. Leaves 234... unchanged."""
    phone = phone.strip()
    if phone.startswith("0") and len(phone) == 11:
        return "234" + phone[1:]
    return phone


def resolve_msisdn_from_request(request):
    """
    Resolve the caller's MSISDN by priority:
      1. Msisdn request header (telco gateway)
      2. 'sub_msisdn' signed cookie (phone-login users)
    """
    if "Msisdn" in request.headers:
        return normalize_msisdn(request.headers["Msisdn"])

    raw = request.get_signed_cookie("sub_msisdn", default=None, salt=COOKIE_SALT)
    if raw:
        return normalize_msisdn(raw)

    return None


def set_auth_cookies(response, msisdn, sub_active=False):
    """Set identity and subscription-status cookies on any response."""
    response.set_signed_cookie(
        "sub_msisdn",
        msisdn,
        salt=COOKIE_SALT,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    response.set_signed_cookie(
        "sub_active",
        "1" if sub_active else "0",
        salt=COOKIE_SALT,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    return response


def check_subscriber_status(msisdn):
    """GET /api/v1/service/{id}/subscription/status/?msisdn=..."""
    url = (
        f"https://api.intellihq.net/api/v1/service/"
        f"{INTELLI_SERVICE_ID}/subscription/status/"
    )
    response = requests.get(
        url,
        params={
            "msisdn": msisdn,
        },
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def extract_redirect_url(sub_data):
    """client_action is a nullable list (sometimes dict) of action objects."""
    client_actions = sub_data.get("client_action") or []
    if isinstance(client_actions, dict):
        return client_actions.get("redirection_url", "")
    for action in client_actions:
        if isinstance(action, dict) and action.get("action") == "redirect":
            return action.get("redirection_url", "")
    return ""


def sync_subscription_from_intellihq(msisdn, data):
    """Sync IntelliHQ subscription data into local UserSubscribtion."""
    has_active = data.get("has_active_subscription", False)
    active_sub = data.get("active_subscription") or {}

    profile, _ = UserProfile.objects.get_or_create(phone=msisdn)
    sub, _ = UserSubscribtion.objects.get_or_create(user=profile)

    sub.sub_active = has_active
    if active_sub:
        sub.auto_renewal = active_sub.get("auto_renewal", False)
        sub.starts_date = (
            parse_datetime(active_sub.get("starts_date") or "") or sub.starts_date
        )
        sub.ends_date = (
            parse_datetime(active_sub.get("ends_date") or "") or sub.ends_date
        )
    sub.save()

    profile.sub_status = "active" if has_active else "inactive"
    profile.save(update_fields=["sub_status"])
