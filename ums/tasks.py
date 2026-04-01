from .subscriptionManager import HML

from celery import shared_task

import os
import traceback

from datetime import datetime, date, timedelta
from django.utils import timezone
import calendar
from django.db.models import Sum
from dateutil.relativedelta import relativedelta

import pandas as pd
import requests


from content.mail import send_email

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# from celery import shared_task

from .models import (
    DataSync,
    UserSubscribtion,
    WebhookBackup,
    CampaignNotificationBackup,
    CampaignTracker,
    CampaignDuplicate,
    UserProfile,
)
from . import choices


def reconcile_subscription(msisdn, telco):
    try:
        client = HML()
        checkSub = client.checkPhoneStatus(msisdn, telco)
        if checkSub != False:
            if checkSub["data"]["active_subscription"] > 0:
                return True
            return False

        return False

    except Exception as ex:
        logger.error(f"{ex}")
        raise


@shared_task
def fetch_report():

    try:

        month_first_day = date.today().replace(day=1)
        # last_day = date.today().replace(
        #     day=calendar.monthrange(date.today().year, date.today().month)[1]
        # )
        yesterday = date.today() - timedelta(days=1)

        date_list = []

        while month_first_day <= yesterday:
            date_list.append(month_first_day)
            month_first_day += timedelta(days=1)
        else:
            last_month_last_day = yesterday.replace(
                day=calendar.monthrange(date.today().year, date.today().month)[1]
            )
            last_month_first_day = yesterday.replace(day=1)
            while last_month_first_day <= last_month_last_day:
                date_list.append(last_month_first_day)
                last_month_first_day += timedelta(days=1)

        curr_path = os.path.dirname(os.path.realpath(__file__))

        report_path = os.path.join(curr_path, "reports/")

        filename = f'{report_path}Daily_Report_{yesterday.strftime("%d/%m/%Y").replace("/", "")}.xlsx'

        ####
        # do your workings here

        data_cols = [
            "Date",
            "Total revenue",
            "Active user",
            "New users",
            "Deactivation",
        ]

        data = {}

        for dt in data_cols:
            data[dt] = []

        logger.info(date_list)

        for dte in date_list:
            ### Fetch data cols and data

            data["Date"].append(dte.strftime("%d/%m/%Y"))

            datasync_qs = DataSync.objects.filter(created_at__date=dte)

            subscriptions = datasync_qs.filter(type="SYNC_NOTIFICATION")
            sub_revenue = (
                subscriptions.aggregate(total=Sum("amount"))["total"]
                if subscriptions.exists()
                else 0
            )

            unsubs = datasync_qs.filter(type="UNSUBSCRIPTION_NOTIFICATION")

            renewals = datasync_qs.filter(type="RENEWAL_NOTIFICATION")
            renewals_revenue = (
                renewals.aggregate(total=Sum("amount"))["total"]
                if renewals.exists()
                else 0
            )

            total_revenue = sub_revenue + renewals_revenue
            data["Total revenue"].append(total_revenue)
            data["New users"].append(subscriptions.count())
            data["Deactivation"].append(unsubs.count())

            # all active users
            active_subs = UserSubscribtion.objects.filter(
                sub_active=True, created_at__date__lte=dte
            ).count()
            data["Active user"].append(active_subs)

            # subscribtion count

        new_df = pd.DataFrame(
            {key: pd.Series(value, dtype=object) for key, value in data.items()},
            columns=data_cols,
        )
        new_df.to_excel(filename, index=False, header=True)

        logger.info(report_path, os.path.exists(report_path), filename)

        ### send email

        EMAIL_SUBJECT = (
            f'Home Recipe Report for Today, {yesterday.strftime("%d/%m/%Y")}'
        )
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached report for today.
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "oladipupo.owoturo@cloudintegratedinc.com",
                "support@cloudintegratedinc.com",
                "adeola.olalekan@cloudintegratedinc.com",
                "adeleke@cloudintegratedinc.com",
                "anisere.desola@cloudintegratedinc.com",
                "favour.onyeloni@cloudintegratedinc.com",
                ###
                "tawa.ojutiku@forthsoft.net",
                "deborah.ajayi@forthsoft.net",
                "samuel.bukolarebecca@forthsoft.net",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/csv",
            quiet=False,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)


@shared_task
def delete_redundant_records(num_of_month: None):

    try:
        nos_of_month = 3
        if num_of_month:
            nos_of_month = int(num_of_month)
        # get 3 months ago
        past_months = datetime.now() - relativedelta(months=nos_of_month)
        # fetch webhooks backup
        WebhookBackup.objects.filter(created_at__lte=past_months).delete()
        # fetch campaign trackers
        CampaignNotificationBackup.objects.filter(created_at__lte=past_months).delete()

        # clear campaign notifications without msisdn
        camp_track = CampaignTracker.objects.filter(msisdn__isnull=True).all()
        for val in camp_track:
            logger.info(f"deleting {val.click_id}")
            val.delete()

    except Exception as ex:
        logger.error(traceback.format_exc())
        logger.error(ex)


@shared_task
def campaign_behaviour(start_date, end_date):

    from xhtml2pdf import pisa

    from io import BytesIO

    from django.template.loader import get_template

    logger.info(start_date, end_date)

    if not (start_date or end_date):
        logger.info("start or end date required")
        return

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    logger.info(f"pulling reports between {start_date} and {end_date}")
    if end_date <= start_date:
        logger.info("end date should be greater than start date")
        return
    if (end_date - start_date).days > 30:
        logger.info("max days allowed is 30")
        return

    # pull all datasync subscribtion for each provider
    neth_subscriptions = []
    mobplus_subscriptions = []

    neth_unsubs = []
    mobplus_unsubs = []

    notification_qs = DataSync.objects.filter(created_at__range=(start_date, end_date))

    campaign_tracker = CampaignTracker.objects.filter(
        created_at__range=(start_date, end_date)
    )

    sub_notifications = notification_qs.filter(
        type="SYNC_NOTIFICATION", campaign_tracker__isnull=False
    )
    for sub in sub_notifications:
        if sub.campaign_tracker.provider == choices.CampaignProvider.NETH.value:
            if sub.phone not in neth_subscriptions:
                neth_subscriptions.append(sub.phone)

        elif sub.campaign_tracker.provider == choices.CampaignProvider.MOBPLUS.value:
            if sub.phone not in mobplus_subscriptions:
                mobplus_subscriptions.append(sub.phone)

    unsub_notifications = notification_qs.filter(type="UNSUBSCRIPTION_NOTIFICATION")
    for unsub in unsub_notifications:
        if unsub.phone in neth_subscriptions:
            if unsub.phone not in neth_unsubs:
                neth_unsubs.append(unsub.phone)

        elif unsub.phone in mobplus_subscriptions:
            if unsub.phone not in mobplus_unsubs:
                mobplus_unsubs.append(unsub.phone)

    export_data = {
        "tc_clicks": campaign_tracker.filter(
            provider=choices.CampaignProvider.NETH.value
        ).count(),
        "tc_subs": len(neth_subscriptions),
        "tc_unsubs": len(neth_unsubs),
        "mobplus_clicks": campaign_tracker.filter(
            provider=choices.CampaignProvider.MOBPLUS.value
        ).count(),
        "mobplus_subs": len(mobplus_subscriptions),
        "mobplus_unsubs": len(mobplus_unsubs),
        "start_date": start_date,
        "end_date": end_date,
    }

    curr_path = os.path.dirname(os.path.realpath(__file__))
    report_path = os.path.join(curr_path, "reports/")

    filename = f'{report_path}campaign_behaviour{end_date.strftime("%Y-%m-%d").replace("-", "")}.pdf'

    template = get_template("users/campaign_report.html")

    html = template.render(export_data)

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if pdf.err:
        logger.error(f"Error generating PDF {pdf.err}")
        return

    with open(filename, "wb+") as output:
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), output)

    # return HttpResponse(result.getvalue(), content_type="application/pdf")

    # send email

    start_date_obj = start_date.date()
    end_date_obj = end_date.date()

    EMAIL_SUBJECT = f"Campaign Behaviour[{start_date_obj, end_date_obj}]"
    REPORTING_MSG = """
        Hello Admin,
        Please find the attached report for requested date range.
        Regards.
        """

    try:
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "adeleke@cloudintegratedinc.com",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="application/pdf",
            quiet=False,
        )
    except Exception as ex:
        logger.error(f"Error sending email: {ex}")


@shared_task
def campaign_behaviour_daily_report(start_date, end_date):

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    logger.info(f"pulling reports between {start_date} and {end_date}")
    if end_date <= start_date:
        logger.info("end date should be greater than start date")
        return
    if (end_date - start_date).days > 30:
        logger.info("max days allowed is 30")
        return

    curr_path = os.path.dirname(os.path.realpath(__file__))

    report_path = os.path.join(curr_path, "reports/")

    filename = f'{report_path}campaign_behaviour_daily{start_date.strftime("%d/%m/%Y").replace("/", "")}.xlsx'

    dte_list = [
        start_date + timedelta(days=x)
        for x in range(((end_date + timedelta(days=1)) - start_date).days)
    ]

    data_cols = [
        "Date",
        "Traffic Company - Clicks",
        "Traffic Company - Subscribtions",
        "Traffic Company - Deactivations",
        "MobPlus - Clicks",
        "MobPlus - Subscribtions",
        "MobPlus - Deactivations",
    ]

    data = {}

    for dcol in data_cols:
        data[dcol] = []

    for dt in dte_list:
        data["Date"].append(dt.strftime("%d/%m/%Y"))

        neth_subscriptions = []
        mobplus_subscriptions = []

        neth_unsubs = []
        mobplus_unsubs = []

        notification_qs = DataSync.objects.filter(created_at__date=dt)

        campaign_tracker = CampaignTracker.objects.filter(created_at__date=dt)

        sub_notifications = notification_qs.filter(
            type="SYNC_NOTIFICATION", campaign_tracker__isnull=False
        )

        for sub in sub_notifications:
            if sub.campaign_tracker.provider == choices.CampaignProvider.NETH.value:
                if sub.phone not in neth_subscriptions:
                    neth_subscriptions.append(sub.phone)

            elif (
                sub.campaign_tracker.provider == choices.CampaignProvider.MOBPLUS.value
            ):
                if sub.phone not in mobplus_subscriptions:
                    mobplus_subscriptions.append(sub.phone)
        unsub_notifications = notification_qs.filter(type="UNSUBSCRIPTION_NOTIFICATION")
        for unsub in unsub_notifications:
            if unsub.phone in neth_subscriptions:
                if unsub.phone not in neth_unsubs:
                    neth_unsubs.append(unsub.phone)

            elif unsub.phone in mobplus_subscriptions:
                if unsub.phone not in mobplus_unsubs:
                    mobplus_unsubs.append(unsub.phone)

        data["Traffic Company - Clicks"].append(
            campaign_tracker.filter(
                provider=choices.CampaignProvider.NETH.value
            ).count()
        )
        data["Traffic Company - Subscribtions"].append(len(neth_subscriptions))
        data["Traffic Company - Deactivations"].append(len(neth_unsubs))
        data["MobPlus - Clicks"].append(
            campaign_tracker.filter(
                provider=choices.CampaignProvider.MOBPLUS.value
            ).count()
        )
        data["MobPlus - Subscribtions"].append(len(mobplus_subscriptions))
        data["MobPlus - Deactivations"].append(len(mobplus_unsubs))

    new_df = pd.DataFrame(
        {key: pd.Series(value, dtype=object) for key, value in data.items()},
        columns=data_cols,
    )
    new_df.to_excel(filename, index=False, header=True)

    logger.info(report_path, os.path.exists(report_path), filename)

    try:
        EMAIL_SUBJECT = "Home Recipe Campaign Behaviour Daily stats"
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached stats report requested.
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "adeleke@cloudintegratedinc.com",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/csv",
            quiet=False,
        )
    except Exception as ex:
        logger.error(f"Error sending email: {ex}")


# @shared_task
def marketing_report_deprecated():
    try:
        month_first_day = date.today().replace(day=1)

        yesterday = date.today() - timedelta(days=1)

        date_list = []

        while month_first_day <= yesterday:
            date_list.append(month_first_day)
            month_first_day += timedelta(days=1)
        else:
            last_month_last_day = yesterday.replace(
                day=calendar.monthrange(date.today().year, date.today().month)[1]
            )
            last_month_first_day = yesterday.replace(day=1)
            while last_month_first_day <= last_month_last_day:
                date_list.append(last_month_first_day)
                last_month_first_day += timedelta(days=1)

        curr_path = os.path.dirname(os.path.realpath(__file__))

        report_path = os.path.join(curr_path, "reports/")

        filename = f'{report_path}Campaign_Report_{yesterday.strftime("%d/%m/%Y").replace("/", "")}.xlsx'

        data_cols = [
            "Date",
            "Traffic Company - Clicks",
            "Traffic Company - Conversions",
            "Traffic Company - Unsubscribtions",
            "MobPlus - Clicks",
            "MobPlus - Conversions",
            "MobPlus - Unsubscribtions",
        ]

        data = {}

        for dt in data_cols:
            data[dt] = []

        logger.info("date list is ", date_list)

        for dte in date_list:
            ### Fetch data cols and data

            data["Date"].append(dte.strftime("%d/%m/%Y"))

            campaign_qs = CampaignTracker.objects.filter(created_at__date=dte)

            tc_hits = campaign_qs.filter(
                provider=choices.CampaignProvider.NETH.value
            ).count()
            tc_converted = campaign_qs.filter(
                provider=choices.CampaignProvider.NETH.value, converted=True
            ).count()

            deactivated_tcs = []
            for entry in CampaignTracker.objects.filter(
                provider=choices.CampaignProvider.NETH.value, converted=True
            ):
                if DataSync.objects.filter(
                    type="UNSUBSCRIPTION_NOTIFICATION",
                    phone=entry.msisdn,
                    created_at__date=dte,
                ).exists():
                    deactivated_tcs.append(entry.msisdn)

            logger.info(deactivated_tcs)

            data["Traffic Company - Clicks"].append(tc_hits)
            data["Traffic Company - Conversions"].append(tc_converted)
            data["Traffic Company - Unsubscribtions"].append(len(deactivated_tcs))

            mp_hits = campaign_qs.filter(
                provider=choices.CampaignProvider.MOBPLUS.value
            ).count()
            mp_converted = campaign_qs.filter(
                provider=choices.CampaignProvider.MOBPLUS.value, converted=True
            ).count()

            deactivated_mps = []
            for entry in CampaignTracker.objects.filter(
                provider=choices.CampaignProvider.MOBPLUS.value, converted=True
            ):
                if DataSync.objects.filter(
                    type="UNSUBSCRIPTION_NOTIFICATION",
                    phone=entry.msisdn,
                    created_at__date=dte,
                ).exists():
                    deactivated_mps.append(entry.msisdn)

            logger.info(deactivated_mps)

            data["MobPlus - Clicks"].append(mp_hits)
            data["MobPlus - Conversions"].append(mp_converted)
            data["MobPlus - Unsubscribtions"].append(len(deactivated_tcs))

        new_df = pd.DataFrame(
            {key: pd.Series(value, dtype=object) for key, value in data.items()},
            columns=data_cols,
        )
        new_df.to_excel(filename, index=False, header=True)

        logger.info(report_path, os.path.exists(report_path), filename)

        ### send email

        EMAIL_SUBJECT = f'Campaign Report for, {yesterday.strftime("%d/%m/%Y")}'
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached report for today.
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                # "adeleke@cloudintegratedinc.com",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/csv",
            quiet=False,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)


@shared_task
def handle_occurence(promo_id):
    try:
        promo = CampaignTracker.objects.get(id=promo_id)
        if (
            CampaignTracker.objects.filter(msisdn=promo.msisdn)
            .exclude(id=promo.id)
            .exists()
        ):
            promo.occurence += 1
            promo.save()
            duplicate, created = CampaignDuplicate.objects.get_or_create(
                msisdn=promo.msisdn, provider=promo.provider
            )
            duplicate.occurence += 1
            duplicate.save()

    except Exception:
        logger.error(traceback.format_exc())


@shared_task
def handle_remarketing(msisdn, provider):
    try:
        user_prof = UserProfile.objects.filter(phone=msisdn).first()
        user_sub = UserSubscribtion.objects.filter(user=user_prof).first()

        duplicate, _ = CampaignDuplicate.objects.get_or_create(
            msisdn=msisdn,
            provider=provider,
        )
        duplicate.remarketed = True
        duplicate.last_subscribtion = user_sub.ends_date
        duplicate.save()

    except Exception:
        logger.error(traceback.format_exc())


@shared_task
def reconcile_subscribtion():
    try:
        # fetch all ended User Subscription

        today = date.today()
        subs = UserSubscribtion.objects.filter(ends_date__date__lt=today)
        for sub in subs:
            logger.info(f"{sub.user} ended at {sub.ends_date}")
            sub.sub_active = False
            sub.save()
            sub.user.sub_status = "inactive"
            sub.user.save()

        logger.info(f"done processing {subs.count()}")

    except Exception:
        logger.error(traceback.format_exc())


# process datasyncs


def handle_datasync_payload(payload):
    new_sync_data = DataSync.objects.create(
        type=payload["type"],
        product_id=payload["product"]["id"],
        product_name=payload["product"]["name"],
        product_not_type=payload["product"]["type"],
        product_sub_type=payload["product"]["subscription_type"],
        phone=payload["details"]["phone"],
        telco_ref=payload["details"]["telco_ref"],
    )
    new_sync_data.telco = (payload.get("telco"),)
    new_sync_data.amount = int(payload["details"].get("amount", 0))
    new_sync_data.channel = payload["details"].get("channel")
    new_sync_data.sub_date = payload["details"].get("date")
    new_sync_data.auto_renewal = payload["details"].get("auto_renewal")
    new_sync_data.sub_expiry = payload["details"].get("expiry")
    new_sync_data.bearer_id = payload["details"].get("bearerId")
    new_sync_data.save()

    return new_sync_data


def handle_postback_delay(provider: str, tracker_id, new_sync_data_id, user_sub_id):
    print(f"processing {provider} and {tracker_id}")
    postback_processes = {
        choices.CampaignProvider.MOBPLUS.value: process_mobplus_postback,
        choices.CampaignProvider.NETH.value: process_neth_postback,
        choices.CampaignProvider.MOBIDEA.value: process_mobedia_postback,
        choices.CampaignProvider.ANGELMEDIA.value: process_angel_media_postback,
        choices.CampaignProvider.KMMOBI.value: process_kmmobi_postback,
        choices.CampaignProvider.MOBIKOK.value: process_mobikok_postback,
        choices.CampaignProvider.SHINE.value: process_shine_postback,
        choices.CampaignProvider.MOBIPIUM.value: process_mobipium_postback,
    }
    return postback_processes[provider].delay(tracker_id, new_sync_data_id, user_sub_id)


@shared_task
def share_datasync(request_body):
    try:
        resp = requests.post(
            "https://api.intellihq.net/api/v1/service/7/sync-notification/?api_key=0e351d54b2e3471fb896faa0ed77049c",
            data=request_body,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
    except Exception as req_ex:
        logger.error(f"Subscription processing error: {req_ex}")
    logger.info(f"Intelli sync request sent{resp}")


# @shared_task
def process_datasync(payload):
    try:
        new_sync_data = handle_datasync_payload(payload)
        today = timezone.now()
        not_type = payload["type"]  # UNSUBSCRIPTION_NOTIFICATION, SYNC_NOTIFICATION
        msisdn = payload["details"]["phone"]

        if msisdn.startswith("0") and len(msisdn) == 11:
            msisdn = msisdn.replace("0", "234", 1)

        # fetch user
        theUser, _ = UserProfile.objects.get_or_create(phone=msisdn)

        userSub, sub_created = UserSubscribtion.objects.get_or_create(
            user=theUser,
        )

        if not_type == "SYNC_NOTIFICATION":
            start_date = payload["details"]["date"]
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            end_date = payload["details"]["expiry"]
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")

            userSub.sub_active = end_datetime.astimezone() > today

            userSub.starts_date = start_datetime
            userSub.ends_date = end_datetime

            if not sub_created:
                userSub.first_sub = True
                if (
                    payload["details"].get("auto_renewal")
                    and payload["details"]["auto_renewal"]
                ):
                    userSub.auto_renewal = True

            theUser.sub_status = "active"
            # theUser.save()

            # find campaign tracker
            # tracker_qs = CampaignTracker.objects.filter(msisdn=msisdn)

            # if tracker_qs.exists():
            #     tracker = tracker_qs.last()
            #     try:
            #         handle_postback_delay(
            #             tracker.provider,
            #             tracker.id,
            #             new_sync_data.id,
            #             userSub.id,
            #         )
            #     except Exception as ex:
            #         logger.error(ex)
            #         print("error handling postback delays")
        elif not_type == "UNSUBSCRIPTION_NOTIFICATION":
            userSub.sub_active = False
            # userSub.save()

            theUser.sub_status = "inactive"

        elif not_type == "RENEWAL_NOTIFICATION":
            """
            b'{"type":"RENEWAL_NOTIFICATION","telco":"MTN","action":"NONE","shortcode":null,"product":{"id":70,"name":"Magic Box Daily","identity":"PD-16541987951000","type":"SUBSCRIPTION","subscription_type":"ONETIME_AND_RECURRING","status":"LIVE"},"details":{"phone":"2347047344879","amount":5000,"channel":"system-renewal","date":"2023-01-07 08:58","expiry":"2023-01-08 08:58","auto_renewal":true,"telco_status_code":"0","telco_ref":"upstream_paid_2617724eebdbc3e8"}}'
            """
            start_date = payload["details"]["date"]
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            end_date = payload["details"]["expiry"]
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")

            userSub.sub_active = end_datetime.astimezone() > today

            userSub.starts_date = start_datetime
            userSub.ends_date = end_datetime

            userSub.first_sub = False

            userSub.auto_renewal = bool(payload["details"].get("auto_renewal"))

            theUser.sub_status = (
                "active" if end_datetime.astimezone() > today else "inactive"
            )

        userSub.save()
        theUser.save()
        print(f"done processing datasync for  {new_sync_data.phone}")
        return {"status": "Success", "data": new_sync_data.id}
    except Exception as ex:
        logger.error(ex)
        return {"status": "Failed", "error": str(ex)}


# process neth postback


@shared_task
def process_neth_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.35"
        today = timezone.now()
        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):

            postbackUrl = f"https://postback.level23.nl/?currency=USD&handler=11556&hash=70fab57722baa9edfba229094ae78d26&tracker={find_promo_msisdn.click_id}"

            requests.get(postbackUrl)
            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.NETH.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.NETH.value
            user_sub.save()

    except Exception as ex:
        logger.error(ex)


# process mobplus postback
@shared_task
def process_mobplus_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.45"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):

            postbackUrl = f"http://m.mobplus.net/c/p/fb83a001c07e407789097636bbf52f7c?txid={find_promo_msisdn.click_id}&pubid={find_promo_msisdn.pubid}&amt={sub_amount}&currency={find_promo_msisdn.currency}"

            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.MOBPLUS.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.MOBPLUS.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


@shared_task
def process_kmmobi_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.40"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):
            postbackUrl = f"http://kmmobi.fuse-ad.com/pb?tid={find_promo_msisdn.click_id}&affid={find_promo_msisdn.pubid}"

            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.KMMOBI.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.KMMOBI.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


# process mobedia postback
@shared_task
def process_mobedia_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.25"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            not CampaignDuplicate.objects.filter(msisdn=find_promo_msisdn).exists()
            and find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):

            postbackUrl = f"https://postback.mobidea.ai/postback?click_id={find_promo_msisdn.click_id}&security_token=259daaad-c527-488b-bbcb-f93cd6833d5d"
            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.MOBIDEA.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.MOBIDEA.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


# process angel media postback
@shared_task
def process_angel_media_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.40"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            not CampaignDuplicate.objects.filter(msisdn=find_promo_msisdn).exists()
            and find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):

            postbackUrl = f"http://postback.rustmobi.com/pb/425?click_id={find_promo_msisdn.click_id}&payout={sub_amount}"
            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.ANGELMEDIA.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.ANGELMEDIA.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


# process mobplus postback
@shared_task
def process_mobikok_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.35"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):
            postbackUrl = f"http://trace.sm4link.com/pb?tid={find_promo_msisdn.click_id}&pubId={find_promo_msisdn.pubid}"

            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.MOBIKOK.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.MOBIKOK.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


# process mobplus postback
@shared_task
def process_shine_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.35"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):
            postbackUrl = f"http://shinedigitalworld.offerstrack.net/advBack.php?click_id={find_promo_msisdn.click_id}"

            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.SHINE.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.SHINE.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


@shared_task
def process_mobipium_postback(tracker_id, sync_id, sub_id):
    try:
        data_sync = DataSync.objects.get(id=sync_id)
        user_sub = UserSubscribtion.objects.get(id=sub_id)
        theUser = user_sub.user
        sub_amount = "0.40"
        today = timezone.now()

        # check campaign tracker is msisdn is there
        find_promo_msisdn = CampaignTracker.objects.get(id=tracker_id)

        if (
            find_promo_msisdn.converted == False
            and find_promo_msisdn.is_convertable == True
        ):
            postbackUrl = f"https://smobipiumlink.com/conversion/index.php?jp={find_promo_msisdn.click_id}&source={find_promo_msisdn.pubid} "

            requests.get(postbackUrl)

            find_promo_msisdn.converted = True

            find_promo_msisdn.converted_at = today

            find_promo_msisdn.amt = sub_amount
            find_promo_msisdn.save()

            data_sync.campaign_tracker = find_promo_msisdn
            data_sync.save()

            theUser.traffic_source = choices.CampaignProvider.SHINE.value
            theUser.save()
            user_sub.traffic_source = choices.CampaignProvider.SHINE.value
            user_sub.save()
    except Exception as ex:
        logger.error(ex)


@shared_task
def subscribtion_source_report():

    try:
        month_first_day = date.today().replace(day=1)
        yesterday = date.today() - timedelta(days=1)

        date_list = []

        while month_first_day <= yesterday:
            date_list.append(month_first_day)
            month_first_day += timedelta(days=1)
        else:
            last_month_last_day = yesterday.replace(
                day=calendar.monthrange(date.today().year, date.today().month)[1]
            )
            last_month_first_day = yesterday.replace(day=1)
            while last_month_first_day <= last_month_last_day:
                date_list.append(last_month_first_day)
                last_month_first_day += timedelta(days=1)

        curr_path = os.path.dirname(os.path.realpath(__file__))

        report_path = os.path.join(curr_path, "reports/")

        filename = f'{report_path}Subscription_Source_Report_{yesterday.strftime("%d/%m/%Y").replace("/", "")}.xlsx'

        ####
        # do your workings here

        data_cols = [
            "Date",
            "SMS",
            "SecureD",
            "API",
            "USSD",
            "MobPlus",
            "TrafficCompany",
            "Remarketing",
            "Others",
        ]

        data = {}

        for dt in data_cols:
            data[dt] = []

        logger.info(date_list)

        for dte in date_list:
            ### Fetch data cols and data

            data["Date"].append(dte.strftime("%d/%m/%Y"))

            datasync_qs = DataSync.objects.filter(
                created_at__date=dte, type="SYNC_NOTIFICATION"
            )

            sms = datasync_qs.filter(channel="SMS")
            ussd = datasync_qs.filter(channel="USSD")
            api = datasync_qs.filter(channel="API")
            secureD = datasync_qs.filter(channel="SecureD")
            others = datasync_qs.exclude(channel__in=["SMS", "USSD", "API", "SecureD"])

            data["SMS"].append(sms.count())
            data["SecureD"].append(secureD.count())
            data["API"].append(api.count())
            data["USSD"].append(ussd.count())
            data["Others"].append(others.count())

            # all active users
            mobplus = CampaignTracker.objects.filter(
                created_at__date=dte,
                provider=choices.CampaignProvider.MOBPLUS.value,
                converted=True,
            )

            tc = CampaignTracker.objects.filter(
                created_at__date=dte,
                provider=choices.CampaignProvider.NETH.value,
                converted=True,
            )
            web_sum = mobplus.count() + tc.count()
            remarketing = secureD.count() - web_sum if secureD.count() > web_sum else 0

            data["MobPlus"].append(mobplus.count())
            data["TrafficCompany"].append(tc.count())
            data["Remarketing"].append(remarketing)

            # subscribtion count

        new_df = pd.DataFrame(
            {key: pd.Series(value, dtype=object) for key, value in data.items()},
            columns=data_cols,
        )
        new_df.to_excel(filename, index=False, header=True)

        logger.info(report_path, os.path.exists(report_path), filename)

        ### send email

        EMAIL_SUBJECT = f'Home Recipe Subscription Source Report for {yesterday.strftime("%d/%m/%Y")}'
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached report for today.
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "oladipupo.owoturo@cloudintegratedinc.com",
                "support@cloudintegratedinc.com",
                "adeola.olalekan@cloudintegratedinc.com",
                "adeleke@cloudintegratedinc.com",
                "anisere.desola@cloudintegratedinc.com",
                "favour.onyeloni@cloudintegratedinc.com",
                ###
                "tawa.ojutiku@forthsoft.net",
                "deborah.ajayi@forthsoft.net",
                "samuel.bukolarebecca@forthsoft.net",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/csv",
            quiet=False,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)


@shared_task
def backup_campaign_tracker(month):

    curr_path = os.path.dirname(os.path.realpath(__file__))

    report_path = os.path.join(curr_path, "reports/")

    today = date.today()

    filename = f'{report_path}Campaign_Tracker_backup{today.strftime("%d/%m/%Y").replace("/", "")}.xlsx'

    data_cols = ["Msisdn", "Provider", "Converted"]

    data = {}

    for dt in data_cols:
        data[dt] = []

    campaign_trackers = (
        CampaignTracker.objects.filter(created_at__month=month, msisdn__isnull=False)
        .all()
        .distinct("msisdn")
    )

    for val in campaign_trackers:
        data["Msisdn"].append(val.msisdn)
        data["Provider"].append(val.provider)

        converted_value = "False"
        if val.converted:
            converted_value = "True"
        data["Converted"].append(converted_value)

    new_df = pd.DataFrame(
        {key: pd.Series(value, dtype=object) for key, value in data.items()},
        columns=data_cols,
    )
    new_df.to_excel(filename, index=False, header=True)

    logger.info(report_path, os.path.exists(report_path), filename)

    try:
        EMAIL_SUBJECT = f"Campaign Tracker Backup for {month}"
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached backup.
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "adeleke@cloudintegratedinc.com",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/csv",
            quiet=False,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)


@shared_task
def cleanup_camp_tracker(num_of_month):
    nos_of_month = 3
    if num_of_month:
        nos_of_month = int(num_of_month)
    # get 3 months ago
    past_months = datetime.now() - relativedelta(months=nos_of_month)
    camp_track = CampaignTracker.objects.filter(msisdn__isnull=True).all()
    for val in camp_track:
        logger.info(f"deleting {val.click_id}")
        val.delete()

    campaign_trackers = CampaignTracker.objects.filter(
        created_at__lte=past_months, msisdn__isnull=False
    ).all()
    for val in campaign_trackers:
        logger.info(f"deleting {val.msisdn}")
        val.delete()
    logger.info("done deleting")


@shared_task
def cleanup_data_sync(num_of_month):
    nos_of_month = 3
    if num_of_month:
        nos_of_month = int(num_of_month)
    # get 3 months ago
    past_months = datetime.now() - relativedelta(months=nos_of_month)

    data_syncs = DataSync.objects.filter(created_at__lte=past_months).all()
    for val in data_syncs:
        logger.info(f"deleting {val.phone}")
        val.delete()
    logger.info("done deleting")


@shared_task
def campaign_partner_user_behaviour():
    # fetch all campaign partner
    partners = [
        choices.CampaignProvider.ANGELMEDIA.value,
        # choices.CampaignProvider.MOBIDEA.value,
        # choices.CampaignProvider.MOBPLUS.value,
        choices.CampaignProvider.NETH.value,
    ]

    result_data = {}

    for partner in partners:
        # result_data.update({f"{partner}": ""})
        patner_campaign = CampaignTracker.objects.filter(
            converted=True, provider=partner
        ).distinct("msisdn")
        patner_msisdns = []
        for val in patner_campaign:
            patner_msisdns.append(val.msisdn)

        logger.info(f"all msisdn in {patner_msisdns}")

        # find their datasync
        total_partner_revenue = 0
        for msisdn in patner_msisdns:
            datasync_rev = DataSync.objects.filter(phone=msisdn).aggregate(
                total=Sum("amount")
            )["total"]
            total_partner_revenue += int(datasync_rev)

        all_partner_inactive = UserProfile.objects.filter(
            phone__in=patner_msisdns, sub_status="inactive"
        ).count()

        result_data.update(
            {
                f"{partner}": {
                    "total_partner_revenue": total_partner_revenue,
                    "all_partner_inactive": all_partner_inactive,
                    "total_msisdn_count": len(patner_msisdns),
                }
            }
        )
    logger.info(result_data)

    try:
        EMAIL_SUBJECT = "Campaign Partner user summary "
        REPORTING_MSG = f"""
            Hello Admin,
            Please find the attached query result.
            {result_data}
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "adeleke@cloudintegratedinc.com",
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            quiet=False,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)


@shared_task
def export_user_msisdn(month_num):
    try:
        # fetch all users

        today = date.today()
        user_profs = UserProfile.objects.filter(
            created_at__month=int(month_num),
        ).distinct("phone")
        curr_path = os.path.dirname(os.path.realpath(__file__))

        report_path = os.path.join(curr_path, "reports/")
        os.makedirs(report_path, exist_ok=True)

        filename = f"{report_path}MSISDN_Exports_{today.strftime('%d/%m/%Y').replace('/', '')}.xlsx"

        data_cols = ["MSISDN", "Date"]

        data = {}

        for dt in data_cols:
            data[dt] = []

        for val in user_profs.all():
            print(f"{val.phone} - {val.created_at}")
            data["Date"].append(val.created_at.strftime("%d/%m/%Y"))
            data["MSISDN"].append(val.phone)

        new_df = pd.DataFrame(
            {key: pd.Series(value, dtype=object) for key, value in data.items()},
            columns=data_cols,
        )
        new_df.to_excel(filename, index=False, header=True)

        logger.info(report_path, os.path.exists(report_path), filename)

        ### send email

        EMAIL_SUBJECT = "Home Recipe MSISDN report"
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached report .
            Regards.
            """

        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "olusoji200@gmail.com",
                "support@avanzar.com.ng",
                ###
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/plain",
            quiet=False,
        )

    except Exception:
        logger.error(traceback.format_exc())


@shared_task
def export_all_msisdns():
    try:
        # fetch all ended User Subscription

        curr_path = os.path.dirname(os.path.realpath(__file__))

        report_path = os.path.join(curr_path, "reports/")
        os.makedirs(report_path, exist_ok=True)

        filename = f"{report_path}msisdn_export.txt"

        all_profiles = UserProfile.objects.filter(phone__isnull=False).all()
        with open(filename, "w") as f:

            for profile in all_profiles:
                logger.info(f"{profile.phone}")
                f.writelines(profile.phone + "\n")
        f.close()
        logger.info(f"done processing {all_profiles.count()}")

        ### send email

        EMAIL_SUBJECT = "Home Recipe Subscribers report"
        REPORTING_MSG = """
            Hello Admin,
            Please find the attached all the msisdn export.
            Regards.
            """
        send_email(
            recipients=[
                "olushola@scriptdeskng.com",
                "olusoji200@gmail.com",
                "support@avanzar.com.ng",
                ###
            ],
            subject=EMAIL_SUBJECT,
            body_text=REPORTING_MSG,
            attachment=filename,
            attachment_mime_type="text/plain",
            quiet=False,
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(e)
