from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(Profile)


# admin.site.register(WebhookBackup)
@admin.register(WebhookBackup)
class WebhookBackupAdmin(admin.ModelAdmin):
    list_display = [
        "req_body",
        "telco",
        "operator",
        "created_at",
    ]


admin.site.register(Subscribtion)
# admin.site.register(CampaignTracker)

# admin.site.register(UserProfile)
# admin.site.register(UserSubscribtion)
admin.site.register(CampaignNotificationBackup)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        "phone",
        "sub_status",
        "traffic_source",
        "created_at",
    ]
    search_fields = ["phone"]


@admin.register(UserSubscribtion)
class UserSubscribtionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "sub_active",
        "starts_date",
        "ends_date",
        "first_sub",
        "traffic_source",
        "renewal_sub",
        "auto_renewal",
    ]
    search_fields = ["user__phone"]


@admin.register(CampaignTracker)
class CampaignTrackerAdmin(admin.ModelAdmin):
    list_display = [
        "msisdn",
        "partner",
        "amt",
        "click_id",
        "telco",
        "occurence",
        "is_convertable",
        "converted",
        "provider",
        "created_at",
        "converted_at",
    ]
    search_fields = ["msisdn", "click_id", "provider"]


@admin.register(CampaignDuplicate)
class CampaignDuplicateAdmin(admin.ModelAdmin):
    list_display = [
        "msisdn",
        "provider",
        "occurence",
        "remarketed",
        "last_subscribtion",
        "created_at",
    ]
    search_fields = ["msisdn"]


@admin.register(DataSync)
class DataSyncAdmin(admin.ModelAdmin):
    list_display = [
        "type",
        "telco",
        "operator",
        "product_id",
        "product_name",
        "product_not_type",
        "product_sub_type",
        "amount",
        "channel",
        "auto_renewal",
        "sub_date",
        "sub_expiry",
        "phone",
        "telco_ref",
        "bearer_id",
        "webhook_backup",
        "campaign_tracker",
        "created_at",
    ]
    search_fields = ["phone", "type"]
