from django.db import models


class ContactSubmission(models.Model):
    """Stores every form submission for audit/log purposes."""
    name = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()

    # Meta fields collected automatically
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.TextField(blank=True)   # User-Agent string
    location = models.CharField(max_length=300, blank=True)  # GeoIP city/country
    submitted_at = models.DateTimeField(auto_now_add=True)

    # Status flags
    auto_reply_sent = models.BooleanField(default=False)
    webhook_triggered = models.BooleanField(default=False)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Contact Submission'
        verbose_name_plural = 'Contact Submissions'

    def __str__(self):
        return f"{self.name} <{self.email}> @ {self.submitted_at:%Y-%m-%d %H:%M}"
