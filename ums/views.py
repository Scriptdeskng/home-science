from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from django.shortcuts import render, get_object_or_404, HttpResponse, redirect, HttpResponseRedirect

from django.views.decorators.csrf import csrf_exempt

from django.db.models import Sum
from dateutil.relativedelta import relativedelta


from datetime import datetime

from .models import *
from .subscriptionManager import HML
import json
from . import choices, tasks

from django.utils.crypto import get_random_string


import requests

import logging


logger = logging.getLogger(__name__)


def subscribe(request):
    try:
        res = get_random_string(length=48)
        traffic_source = "Organic Search"
        redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={res}&trfsrc={traffic_source}"
        return redirect(redirect_url)
    except Exception as ex:
        print(ex)
        return redirect("content:home")


######### Unsubscribe ###########


def cancelSubscribtion(request):
    if "Msisdn" in request.headers:
        msisdn = request.headers["Msisdn"]
        # get user msisdn
        client = HML()

        checkNetwork = client.checkNetwork(msisdn)
        if checkNetwork == "AIRTEL":
            unSub = client.unSubscribe(msisdn, choices.Telco.AIRTEL.value)
        # elif checkNetwork == "MTN":
        else:
            unSub = client.unSubscribe(msisdn, choices.Telco.MTN.value)

        if unSub != False:
            print("Un-Subscribtion Successfull")
            return redirect("content:home")
        else:
            print("Subscribtion UnSuccessfull")
            return redirect("content:home")
    else:
        return redirect("users:onboarding")


def after_signup(request):
   

    return redirect("users:awaiting_response")


def awaiting_response(request):
    template = "users/awaiting_response.html"
    return render(request, template)


@login_required
def after_login(request):
    msisdn = request.user.username
    # check sub status
    sub_qs = Subscribtion.objects.filter(user=request.user.profile, sub_active=True)
    if sub_qs.exists():
        return redirect("content:home")
    else:
        return redirect("users:inactive_account")


def onboarding(request):

    template = "users/subscribe_page.html"

    context = {}

    return render(request, template, context)


def inactive_account(request):

    template = "users/inactive_account.html"

    context = {}
    return render(request, template, context)


# CampaignNotificationBackup
@require_POST
@csrf_exempt
def campaign_notification(request):
    CampaignNotificationBackup.objects.create(
        req_body=f"{request.body}"
    )
    return HttpResponse(200)





def generate_report(request):
    tasks.fetch_report.delay()
    tasks.subscribtion_source_report.delay()

    return HttpResponse(200)


#### Vendor Onboarding
def fetch_stats(request):
    today = datetime.now()

    # start_date_str = "2024-06-24 00:00:01"
    the_day = request.GET.get("day", None)
    if the_day:
        date_format = "%Y-%m-%d %H:%M:%S"
        date_obj = datetime.strptime(f"{the_day} 00:00:00", date_format)

        campaing_tracker_neth = CampaignTracker.objects.filter(
            created_at__date=date_obj.date(),
            provider=choices.CampaignProvider.NETH.value,
            converted=True,
        ).count()

        campaing_tracker_neth_month = CampaignTracker.objects.filter(
            created_at__month=date_obj.month,
            provider=choices.CampaignProvider.NETH.value,
            converted=True,
        ).count()

        campaing_tracker_mobedia = CampaignTracker.objects.filter(
            created_at__date=date_obj.date(),
            provider=choices.CampaignProvider.MOBIDEA.value,
            converted=True,
        ).count()

        campaing_tracker_mobedia_month = CampaignTracker.objects.filter(
            created_at__month=date_obj.month,
            provider=choices.CampaignProvider.MOBIDEA.value,
            converted=True,
        ).count()

        campaing_tracker_angel = CampaignTracker.objects.filter(
            created_at__date=date_obj.date(),
            provider=choices.CampaignProvider.ANGELMEDIA.value,
            converted=True,
        ).count()

        campaing_tracker_angel_month = CampaignTracker.objects.filter(
            created_at__month=date_obj.month,
            provider=choices.CampaignProvider.ANGELMEDIA.value,
            converted=True,
        ).count()

        campaing_tracker_mob = CampaignTracker.objects.filter(
            created_at__date=date_obj.date(),
            provider=choices.CampaignProvider.MOBPLUS.value,
            converted=True,
        ).count()

        campaing_tracker_mob_month = CampaignTracker.objects.filter(
            created_at__month=date_obj.month,
            provider=choices.CampaignProvider.MOBPLUS.value,
            converted=True,
        ).count()

        campaign_not = CampaignNotificationBackup.objects.filter(
            created_at__date=date_obj.date()
        ).count()

        user_prof = UserProfile.objects.filter(created_at__date=date_obj.date()).count()
        ## revenues
        datasync_qs = DataSync.objects.filter(created_at__date=date_obj.date())

        subscriptions = datasync_qs.filter(type="SYNC_NOTIFICATION")
        sub_revenue = (
            subscriptions.aggregate(total=Sum("amount"))["total"]
            if subscriptions.exists()
            else 0
        )

        unsubs = datasync_qs.filter(type="UNSUBSCRIPTION_NOTIFICATION")

        renewals = datasync_qs.filter(type="RENEWAL_NOTIFICATION")
        renewals_revenue = (
            renewals.aggregate(total=Sum("amount"))["total"] if renewals.exists() else 0
        )

        total_revenue = sub_revenue + renewals_revenue

    else:
        campaing_tracker_neth = CampaignTracker.objects.filter(
            created_at__month=today.month,
            converted=True,
            provider=choices.CampaignProvider.NETH.value,
        ).count()

        campaing_tracker_neth_month = campaing_tracker_neth

        campaing_tracker_mobedia = CampaignTracker.objects.filter(
            created_at__month=today.month,
            converted=True,
            provider=choices.CampaignProvider.MOBIDEA.value,
        ).count()

        campaing_tracker_mobedia_month = campaing_tracker_mobedia

        campaing_tracker_angel = CampaignTracker.objects.filter(
            created_at__month=today.month,
            provider=choices.CampaignProvider.ANGELMEDIA.value,
            converted=True,
        ).count()

        campaing_tracker_angel_month = campaing_tracker_angel

        campaing_tracker_mob = CampaignTracker.objects.filter(
            created_at__month=today.month,
            converted=True,
            provider=choices.CampaignProvider.MOBPLUS.value,
        ).count()

        campaing_tracker_mob_month = campaing_tracker_mob

        campaign_not = CampaignNotificationBackup.objects.filter(
            created_at__month=today.month
        ).count()

        user_prof = UserProfile.objects.filter(created_at__month=today.month).count()

        # revenue

        datasync_qs = DataSync.objects.filter(created_at__month=today.month)

        subscriptions = datasync_qs.filter(type="SYNC_NOTIFICATION")
        sub_revenue = (
            subscriptions.aggregate(total=Sum("amount"))["total"]
            if subscriptions.exists()
            else 0
        )

        unsubs = datasync_qs.filter(type="UNSUBSCRIPTION_NOTIFICATION")

        renewals = datasync_qs.filter(type="RENEWAL_NOTIFICATION")
        renewals_revenue = (
            renewals.aggregate(total=Sum("amount"))["total"] if renewals.exists() else 0
        )

        total_revenue = sub_revenue + renewals_revenue

    data = {
        "New Users Aquisition": user_prof,
        "Web Traffic Conversions[Daan]": campaing_tracker_neth,
        "Web Traffic Conversions[Daan][Month Count]": campaing_tracker_neth_month,
        "Web Traffic Conversions[MobPlus]": campaing_tracker_mob,
        "Web Traffic Conversions[MobPlus][Month Count]": campaing_tracker_mob_month,
        "Web Traffic [MOBEDIA][Today]": campaing_tracker_mobedia,
        "Web Traffic [MOBEDIA][Month Count]": campaing_tracker_mobedia_month,
        "Web Traffic [ANGEL MEDIA][Today]": campaing_tracker_angel,
        "Web Traffic [ANGEL MEDIA][Month Count]": campaing_tracker_angel_month,
        "campaign_notifications": campaign_not,
        "Revenue Data": {
            "New Subscribtion Count": subscriptions.count(),
            "New Subscribtion Revenue": sub_revenue,
            "Renewal Count": renewals.count(),
            "Renewal Revenue": renewals_revenue,
            "Unsubscription Count": unsubs.count(),
            "Total Revenue": total_revenue,
        },
    }
    return JsonResponse(data)


# Forthsoft


@require_POST
@csrf_exempt
def data_sync_v2(request):
    try:
        WebhookBackup.objects.create(
                req_body=f"{request.body.decode("utf-8")}"
            )
        the_data = json.loads(request.body.decode('utf-8'))
        datasync_task = tasks.process_datasync(the_data)
        if datasync_task["status"] == "Failed":
            return JsonResponse({"status": 400, "error": f"Unable to process request-{datasync_task["error"]}"}, status=400)
        return JsonResponse({"status": 200, "message": "ok, [homerecipe] data sync processed successfully"})
    except Exception as ex:
        print(ex)
        return JsonResponse({"status": 400, "error": "Unable to process request", "details": str(ex)}, status=400)


def reconcile_subscribtions(request):
    from .tasks import reconcile_subscribtion

    reconcile_subscribtion.delay()

    return HttpResponse(200)


def fetch_campaign_behaviour(request):

    start = request.GET.get("start", None)
    end = request.GET.get("end", None)

    if not start:
        return JsonResponse({"status": 400, "error": "start date is required"})
    if not end:
        return JsonResponse({"status": 400, "error": "end date is required"})

    if not datetime.strptime(start, "%Y-%m-%d"):
        return JsonResponse({"status": 400, "error": "invalid start date"})
    if not datetime.strptime(end, "%Y-%m-%d"):
        return JsonResponse({"status": 400, "error": "invalid end date"})

    tasks.campaign_behaviour.delay(start, end)

    return JsonResponse({"status": 200, "message": "Processing report!"})


def fetch_campaign_behaviour_daily(request):
    start = request.GET.get("start", None)
    end = request.GET.get("end", None)

    if not start:
        return JsonResponse({"status": 400, "error": "start date is required"})
    if not end:
        return JsonResponse({"status": 400, "error": "end date is required"})

    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y-%m-%d")

    if (end_date - start_date).days > 30:
        return JsonResponse({"status": 400, "message": "Max date range is 30 days"})

    tasks.campaign_behaviour_daily_report.delay(start, end)

    return JsonResponse({"status": 200, "message": "Processing report!"})


def fetch_subscription_source_quick_report(request):

    dte = request.GET.get("date", None)
    tasks.subscribtion_source_quick_report.delay(dte)

    return JsonResponse({"status": 200, "message": "Processing report!"})


def pull_3rd_party_acquisition_report(request):

    tasks.pull_3rd_party_acquisition_count.delay()

    return JsonResponse({"status": 200, "message": "Processing report!"})


def cleanup_data(request):

    month_num = request.GET.get("month", None)

    tasks.delete_redundant_records.delay(month_num)

    return HttpResponse(200)


def cleanup_campaign_tracker(request):

    month_num = request.GET.get("month", None)

    tasks.cleanup_camp_tracker.delay(month_num)

    return JsonResponse({"status": 200, "message": "Processing report!"})


def cleanup_data_sync(request):

    month_num = request.GET.get("month", None)

    tasks.cleanup_data_sync.delay(month_num)

    return JsonResponse({"status": 200, "message": "Processing report!"})


def campaign_partner_user_behaviour_query(request):
    month_num = request.GET.get("month_num", None)

    tasks.campaign_partner_user_behaviour.delay(month_num)

    return JsonResponse({"status": 200, "message": "Processing report!"})


def get_cr_data(request):

    today = datetime.now()

    # start_date_str = "2024-06-24 00:00:01"
    the_day = request.GET.get("day", None)
    if the_day:
        date_format = "%Y-%m-%d %H:%M:%S"
        date_obj = datetime.strptime(f"{the_day} 00:00:00", date_format).date()
    else:
        date_obj = today.date()

    partner = request.GET.get("partner")
    if not partner:
        return JsonResponse({"status": 400, "message": "Partner required"})

    tracks_qs = CampaignTracker.objects.filter(
        created_at__date=date_obj, provider=partner
    )
    unique_tracks = tracks_qs.filter(occurence=0)
    converted = tracks_qs.filter(converted=True)

    traffic_hits = tracks_qs.count()
    unique_traffic = unique_tracks.count()
    converted_count = converted.count()

    cr = (converted_count / traffic_hits) * 100

    data = {
        "Traffic Hit": traffic_hits,
        "Unique Traffic Hits": unique_traffic,
        "Converted": converted_count,
        "CR": cr,
    }
    return JsonResponse(data)



### Web Partners Promo URL
def mobplus_campaign_url(request):
    try:
        partner = request.GET.get("partner", None)
        click_id = request.GET.get("clickid", None)
        telco = request.GET.get("telco", None)
        pubid = request.GET.get("pubid", None)

        unique_sub_ref = get_random_string(length=48)
        msisdn = request.headers.get("Msisdn")
        if not msisdn:
            traffic_source = "OrganicSource"
            redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={unique_sub_ref}&trfsrc={traffic_source}"
            return HttpResponseRedirect(redirect_url)

        if msisdn.startswith("0") and len(msisdn) == 11:
            msisdn = msisdn.replace("0", "234", 1)

        new_promo_hit = CampaignTracker.objects.filter(
            click_id=click_id, provider=choices.CampaignProvider.MOBPLUS.value
        ).last()
        if not new_promo_hit:
            new_promo_hit = CampaignTracker.objects.create(
                click_id=click_id,
                msisdn=msisdn,
                provider=choices.CampaignProvider.MOBPLUS.value,
                currency="USD",
            )

        if any([partner, telco, pubid]):
            new_promo_hit.partner = partner or new_promo_hit.partner
            new_promo_hit.telco = telco or new_promo_hit.telco
            new_promo_hit.pubid = pubid or new_promo_hit.pubid
            # new_promo_hit.save() 
        

        user_prof = UserProfile.objects.filter(phone=msisdn).first()
        if user_prof:
            # check if user has active subscribtion
            now = timezone.now()
            one_month_ago = now - relativedelta(hours=24)
            # user deactivated active subscribtion
            user_sub = UserSubscribtion.objects.filter(user=user_prof).first()
            if user_sub.ends_date and user_sub.ends_date <= one_month_ago:
                tasks.handle_remarketing.apply_async(
                args=[msisdn, choices.CampaignProvider.MOBPLUS.value],
                countdown=120,
                )
                # redirect to secured D
                new_promo_hit.is_convertable = False
                ### redirect as organic source
                traffic_source = "OrganicSource"
                redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={unique_sub_ref}&trfsrc={traffic_source}"
                return HttpResponseRedirect(redirect_url)
            else:
                return redirect("content:home")

        new_promo_hit.save()
        tasks.handle_occurence.delay(new_promo_hit.id)
        traffic_source = "MobPlus"
        redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={unique_sub_ref}&trfsrc={traffic_source}"
        return HttpResponseRedirect(redirect_url)
    except Exception as ex:
        logger.error("exception occurred", exc_info=True)
        return redirect("content:home")
    


def kmmobi_campaign_url(request):
    try:
        partner = request.GET.get("partner", None)
        click_id = request.GET.get("clickid", None)
        telco = request.GET.get("telco", None)
        pubid = request.GET.get("pubid", None)

        unique_sub_ref = get_random_string(length=48)
        msisdn = request.headers.get("Msisdn")
        if not msisdn:
            traffic_source = "OrganicSource"
            redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={unique_sub_ref}&trfsrc={traffic_source}"
            return HttpResponseRedirect(redirect_url)

        if msisdn.startswith("0") and len(msisdn) == 11:
            msisdn = msisdn.replace("0", "234", 1)

        new_promo_hit = CampaignTracker.objects.filter(
            click_id=click_id, provider=choices.CampaignProvider.KMMOBI.value
        ).last()
        if not new_promo_hit:
            new_promo_hit = CampaignTracker.objects.create(
                click_id=click_id,
                msisdn=msisdn,
                provider=choices.CampaignProvider.KMMOBI.value,
                currency="USD",
            )

        if any([partner, telco, pubid]):
            new_promo_hit.partner = partner or new_promo_hit.partner
            new_promo_hit.telco = telco or new_promo_hit.telco
            new_promo_hit.pubid = pubid or new_promo_hit.pubid
            # new_promo_hit.save() 
        

        user_prof = UserProfile.objects.filter(phone=msisdn).first()
        if user_prof:
            # check if user has active subscribtion
            now = timezone.now()
            one_month_ago = now - relativedelta(hours=24)
            # user deactivated active subscribtion
            user_sub = UserSubscribtion.objects.filter(user=user_prof).first()
            if user_sub.ends_date and user_sub.ends_date <= one_month_ago:
                tasks.handle_remarketing.apply_async(
                args=[msisdn, choices.CampaignProvider.KMMOBI.value],
                countdown=120,
                )
                # redirect to secured D
                new_promo_hit.is_convertable = False
                ### redirect as organic source
                traffic_source = "OrganicSource"
                redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={unique_sub_ref}&trfsrc={traffic_source}"
                return HttpResponseRedirect(redirect_url)
            else:
                return redirect("content:home")

        new_promo_hit.save()
        tasks.handle_occurence.delay(new_promo_hit.id)
        traffic_source = "KM Mobi"
        redirect_url = f"http://ng-app.com/AVANZAR/homerecipe-landing-en-doi-web?origin_banner=1&trxId={unique_sub_ref}&trfsrc={traffic_source}"
        return HttpResponseRedirect(redirect_url)
    except Exception as ex:
        logger.error("exception occurred", exc_info=True)
        return redirect("content:home")