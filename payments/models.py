from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User


class InvoiceData(models.Model):
  user = models.ForeignKey(User, on_delete=models.CASCADE)
  stripe_customer_id = models.CharField(max_length=255)
  stripe_invoice_id = models.CharField(max_length=255)
  stripe_subscription_id = models.CharField(max_length=255)
  amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
  currency = models.CharField(max_length=3)
  subscription_type = models.CharField(max_length=10)  # 'monthly' or 'yearly'
  start_date = models.DateTimeField()
  end_date = models.DateTimeField(null=True,
                                  blank=True)  # null for monthly subscriptions
  is_active = models.BooleanField(default=True)

  def __str__(self):
    return f"Invoice {self.stripe_invoice_id} for {self.user.email}"
