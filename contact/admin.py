from django.contrib import admin
from .models import ContactSubmission


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'ip_address', 'location', 'submitted_at', 'auto_reply_sent', 'webhook_triggered')
    list_filter = ('auto_reply_sent', 'webhook_triggered', 'submitted_at')
    search_fields = ('name', 'email', 'ip_address', 'location')
    readonly_fields = ('ip_address', 'device_info', 'location', 'submitted_at', 'auto_reply_sent', 'webhook_triggered')
    ordering = ('-submitted_at',)

    fieldsets = (
        ('Submission', {'fields': ('name', 'email', 'message')}),
        ('Technical Details', {'fields': ('ip_address', 'location', 'device_info', 'submitted_at')}),
        ('Status', {'fields': ('auto_reply_sent', 'webhook_triggered')}),
    )
