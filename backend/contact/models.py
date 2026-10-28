from django.db import models
from django.utils.translation import gettext_lazy as _


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Contact Message")
        verbose_name_plural = _("Contact Messages")

    def __str__(self) -> str:
        return f"[{self.created_at:%Y-%m-%d}] {self.subject} — {self.email}"
