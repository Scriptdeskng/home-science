from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from django.shortcuts import render, redirect

from django.views.decorators.csrf import csrf_exempt

from django.db.models import Sum


from datetime import datetime

from .models import *
from .subscriptionManager import HML
import json
from . import choices, tasks

from django.utils.crypto import get_random_string


import requests


# def subscribe(request):
#     N = 7

#     # using random.choices()
#     # generating random strings
#     res = "".join(random.choices(string.ascii_lowercase + string.digits, k=N))

#     redirect_url = f"http://ng-app.com/CloudIntegrated/MagicBox-168-No-23410220000022702-web?trxId={res}"

#     return redirect(redirect_url)


def subscribe(request):
    try:

        # fetch msisdn
        # if mtn, use secureD redirect

        if "Msisdn" in request.headers:
            msisdn = request.headers["Msisdn"]
            # get user msisdn

            print(f"redirecting {msisdn} to secureD DUI")

        # send to secureD for redirection
        # N = 7
        # res = "".join(random.choices(string.ascii_lowercase + string.digits, k=N))
        res = get_random_string(length=48)
        traffic_source = "Organic Search"
        # redirect_url = f"http://ng-app.com/CloudIntegrated/MagicBox-168-No-23410220000022702-web?trfsrc={traffic_source}&trxId={res}"
        redirect_url = f"http://ng-app.com/CloudIntegrated/magicbox-daily-en-doi-web?origin_banner=1&trfsrc={traffic_source}&trxId={res}"
        return redirect(redirect_url)
    except Exception as ex:
        print(ex)
        return redirect("core:home")


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
            return redirect("core:home")
        else:
            print("Subscribtion UnSuccessfull")
            return redirect("core:home")
    else:
        return redirect("users:onboarding")


def after_signup(request):
    # get user msisdn
    # msisdn = request.user.profile.phone
    # sub = mtnSubscribe(msisdn)
    # print(sub)
    # check subscription status
    ###########

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
        return redirect("core:home")
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


# DATA SYNC
@require_POST
@csrf_exempt
def data_sync(request):
    print("Receiving from HML datasync")

    the_data = json.loads(request.body)
    print(the_data)

    try:
        new_sync = WebhookBackup.objects.create(
            req_body=f"{request.body}", operator="HML"
        )
    except:
        pass

    try:
        new_sync_data = DataSync.objects.create(
            type=the_data["type"],
            telco=the_data["telco"],
            product_id=the_data["product"]["id"],
            product_name=the_data["product"]["name"],
            product_not_type=the_data["product"]["type"],
            product_sub_type=the_data["product"]["subscription_type"],
            phone=the_data["details"]["phone"],
            telco_ref=the_data["details"]["telco_ref"],
            operator="HML",
        )
        if the_data["details"]["amount"]:
            new_sync_data.amount = int(the_data["details"]["amount"]) / 100
        if the_data["details"]["channel"]:
            new_sync_data.channel = the_data["details"]["channel"]
        if the_data["details"]["date"]:
            new_sync_data.sub_date = the_data["details"]["date"]
        if the_data["details"]["auto_renewal"]:
            new_sync_data.auto_renewal = the_data["details"]["auto_renewal"]
        if the_data["details"]["expiry"]:
            new_sync_data.sub_expiry = the_data["details"]["expiry"]
        if the_data["details"]["bearerId"]:
            new_sync_data.bearer_id = the_data["details"]["bearerId"]
        if new_sync:
            new_sync_data.webhook_backup = new_sync

        new_sync_data.save()
    except Exception as ex:
        print("saving datasync error", ex)
        pass

    if the_data["telco"] == "MTN":
        not_type = the_data["type"]  # UNSUBSCRIPTION_NOTIFICATION, SYNC_NOTIFICATION
        msisdn = the_data["details"]["phone"]
        # "%Y-%m-%dT%H:%M:%S.%fZ",

        prod_type = the_data["product"]["type"]
        # sub_type = the_data["product"]["subscription_type"]
        print("prod_type", prod_type)

        if msisdn.startswith("0") and len(msisdn) == 11:
            msisdn = msisdn.replace("0", "234", 1)

        # fetch user
        theUser, user_created = UserProfile.objects.get_or_create(phone=msisdn)
        userSub, sub_created = UserSubscribtion.objects.get_or_create(user=theUser)
        if not_type == "SYNC_NOTIFICATION":

            """
            b'{"type":"SYNC_NOTIFICATION","telco":"MTN","action":"NONE","shortcode":null,"product":{"id":70,"name":"Magic Box Daily","identity":"PD-16541987951000","type":"SUBSCRIPTION","subscription_type":"ONETIME_AND_RECURRING","status":"LIVE"},"details":{"phone":"2348130801443","amount":5000,"channel":"SecureD","date":"2023-01-07 08:57","expiry":"2023-01-08 08:57","auto_renewal":true,"telco_status_code":"0","telco_ref":"upstream_paid_f562330523f48921"}}'
            """

            start_date = the_data["details"]["date"]
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
            end_date = the_data["details"]["expiry"]
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d %H:%M")

            sub_amount = "0.35"

            userSub.sub_active = True
            userSub.starts_date = start_datetime
            userSub.ends_date = end_datetime

            try:
                if not sub_created:
                    userSub.first_sub = True
                    if the_data["details"]["auto_renewal"] == True:
                        userSub.auto_renewal = True
            except:
                pass
            userSub.save()

            theUser.sub_status = "active"
            theUser.save()

            # try mobplus
            try:
                find_mobplus_promo_msisdn_qs = CampaignTracker.objects.filter(
                    msisdn=msisdn, provider=choices.CampaignProvider.MOBPLUS.value
                )
                if find_mobplus_promo_msisdn_qs.exists():
                    find_promo_msisdn = find_mobplus_promo_msisdn_qs.last()
                    postbackUrl = f"http://m.mobplus.net/c/p/5085e36b2e1e4d909b1a732a9841c965?txid={find_promo_msisdn.click_id}&pubid={find_promo_msisdn.pubid}&amt={sub_amount}&currency={find_promo_msisdn.currency}"
                    send_postback = requests.get(postbackUrl)
                    find_promo_msisdn.converted = True
                    find_promo_msisdn.amt = sub_amount
                    find_promo_msisdn.save()
                    new_sync_data.campaign_tracker = find_promo_msisdn
                    new_sync_data.save()
                    print(send_postback)
            except Exception as ex:
                print("mobplus exception", ex)
                pass

            try:
                # check campaign tracker is msisdn is there
                find_neth_promo_msisdn_qs = CampaignTracker.objects.filter(
                    msisdn=msisdn, provider=choices.CampaignProvider.NETH.value
                )
                if find_neth_promo_msisdn_qs.exists():
                    find_promo_msisdn = find_neth_promo_msisdn_qs.last()

                    postbackUrl = f"https://postback.level23.nl/?currency=USD&handler=11349&hash=63857b26c564dd6b79e5a2fb1bb209e8&tracker={find_promo_msisdn.click_id}"

                    send_postback = requests.get(postbackUrl)
                    find_promo_msisdn.converted = True
                    find_promo_msisdn.amt = sub_amount
                    find_promo_msisdn.save()
                    new_sync_data.campaign_tracker = find_promo_msisdn
                    new_sync_data.save()
                    print(send_postback)
            except Exception as ex:
                print("neth exception is ", ex)
                pass

            return JsonResponse({"status": 200, "message": "ok"})

        elif not_type == "UNSUBSCRIPTION_NOTIFICATION":
            print("this is a unsubscribtion request")
            userSub.sub_active = False
            userSub.save()

            theUser.sub_status = "inactive"
            theUser.save()

            print("done with unsubscribtion")
            return JsonResponse({"status": 200, "message": "ok"})
        elif not_type == "RENEWAL_NOTIFICATION":

            """
            b'{"type":"RENEWAL_NOTIFICATION","telco":"MTN","action":"NONE","shortcode":null,"product":{"id":70,"name":"Magic Box Daily","identity":"PD-16541987951000","type":"SUBSCRIPTION","subscription_type":"ONETIME_AND_RECURRING","status":"LIVE"},"details":{"phone":"2347047344879","amount":5000,"channel":"system-renewal","date":"2023-01-07 08:58","expiry":"2023-01-08 08:58","auto_renewal":true,"telco_status_code":"0","telco_ref":"upstream_paid_2617724eebdbc3e8"}}'
            """
            start_date = the_data["details"]["date"]
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
            end_date = the_data["details"]["expiry"]
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d %H:%M")

            userSub.sub_active = True

            userSub.starts_date = start_datetime
            userSub.ends_date = end_datetime

            try:
                userSub.first_sub = False
                userSub.renewal_sub = True
                if the_data["details"]["auto_renewal"] == True:
                    userSub.auto_renewal = True
            except:
                pass
            userSub.save()

            theUser.sub_status = "active"
            theUser.save()

            return JsonResponse({"status": 200, "message": "ok"})

        else:
            return JsonResponse({"status": 200, "message": "ok"})
    else:
        return JsonResponse({"status": 200, "message": "ok"})


# CampaignNotificationBackup
@require_POST
@csrf_exempt
def campaign_notification(request):
    try:
        the_data = json.loads(request.body)
        print(the_data)

        try:
            new_sync = CampaignNotificationBackup.objects.create(
                req_body=f"{request.body}"
            )
        except:
            pass
    except Exception as e:
        print("error", e)
        pass

    return HttpResponse(200)


def pullData(request):
    try:
        allSub = UserSubscribtion.objects.all()
        allSubCount = allSub.count()
        print("allsub count", allSubCount)

        allActiveSubCount = allSub.filter(sub_active=True).count()
        print("allActiveSub count", allActiveSubCount)

        allRenewalSub = allSub.filter(renewal_sub=True, first_sub=False).count()
        print("all renewal sub", allRenewalSub)

    except Exception as e:
        pass

    return HttpResponse(200)


def generate_report(request):
    from .tasks import fetch_report, subscribtion_source_report

    fetch_report.delay()
    subscribtion_source_report.delay()

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


# DATA SYNC
@require_POST
@csrf_exempt
def data_sync_v2(request):

    from .tasks import process_datasync

    print("Receiving from Forthsoft  datasync")

    the_data = json.loads(request.body)
    # process_datasync.delay(the_data)
    process_datasync.apply_async(args=[the_data], countdown=45)

    return JsonResponse({"status": 200, "message": "ok"})


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
