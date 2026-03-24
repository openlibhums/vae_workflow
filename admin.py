from django.contrib import admin

from plugins.vae_workflow import models


@admin.register(models.VAEPoolMember)
class VAEPoolMemberAdmin(admin.ModelAdmin):
    list_display = ('account', 'journal', 'added', 'added_by')
    list_filter = ('journal',)
    raw_id_fields = ('account', 'added_by')


@admin.register(models.EditorClaim)
class EditorClaimAdmin(admin.ModelAdmin):
    list_display = ('article', 'claimed_by', 'date_claimed', 'status', 'date_resolved', 'resolved_by')
    list_filter = ('status', 'article__journal')
    raw_id_fields = ('article', 'claimed_by', 'resolved_by')
    readonly_fields = ('date_claimed', 'date_resolved')
