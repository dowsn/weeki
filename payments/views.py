from datetime import timezone
from django.shortcuts import render
import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.core.mail import send_mail
from app.models import Profile, User
import os

stripe.api_key = settings.STRIPE_SECRET_KEY


def payment_view(request):
  return render(request, 'payments/payment.html',
                {'stripe_public_key': settings.STRIPE_PUBLISHABLE_KEY})


def success_view(request):
  return render(request, 'payments/success.html')


def cancel_view(request):
  return render(request, 'payments/cancel.html')


@require_http_methods(["POST"])
def create_checkout_session(request):
  try:
    user_id = request.user.id or request.POST.get('user_id')
    # Get the user's email
    user_email = Profile.objects.get(user_id=request.user.id).email

    # Get the subscription type from the request
    subscription_type = request.POST.get('subscription_type')

    if subscription_type == 'yearly':
      price = stripe.Price.create(
          unit_amount=6000,
          currency='eur',
          recurring={"interval": "year"},
          product_data={'name': 'Yearly Subscription'},
      )
    elif subscription_type == 'monthly':
      price = stripe.Price.create(
          unit_amount=700,  # 7 euros in cents
          currency='eur',
          recurring={"interval": "month"},
          product_data={'name': 'Monthly Subscription'},
      )
    else:
      return JsonResponse({'error': 'Invalid subscription type'}, status=400)

    # Create the checkout session with the Price object
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[
            {
                'price': price.id,
                'quantity': 1,
            },
        ],
        mode='subscription',
        success_url=request.build_absolute_uri('/payments/success/'),
        cancel_url=request.build_absolute_uri('/payments/cancel/'),
        customer_email=user_email,
        metadata={'subscription_type':
                  subscription_type},  # Add metadata for use in webhook
    )

    return JsonResponse({'id': checkout_session.id})
  except Exception as e:
    return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def stripe_webhook(request):
  payload = request.body
  sig_header = request.META['HTTP_STRIPE_SIGNATURE']
  event = None

  try:
    event = stripe.Webhook.construct_event(payload, sig_header,
                                           settings.STRIPE_WEBHOOK_SECRET)
  except ValueError as e:
    return HttpResponse(status=400)
  except stripe.error.SignatureVerificationError as e:
    return HttpResponse(status=400)

  if event['type'] == 'checkout.session.completed':
    session = event['data']['object']
    customer_email = session['customer_details']['email']
    customer_id = session['customer']
    subscription_type = session['metadata']['subscription_type']

    # Retrieve the subscription
    subscription = stripe.Subscription.retrieve(session['subscription'])

    # Retrieve the invoice
    invoice = stripe.Invoice.retrieve(session['invoice'])

    # Get the User instance

    # Calculate end_date for yearly subscriptions
    start_date = timezone.now()
    end_date = start_date + timezone.timedelta(
        days=365) if subscription_type == 'yearly' else None

    # saving profile premium date
    profile = Profile.objects.get(email=customer_email)
    user = User.objects.get(id=profile.user_id)
    profile.premium_date = end_date
    profile.premium_start = start_date

    # Save invoice data
    invoice_data = InvoiceData.objects.create(
        user=user,
        stripe_customer_id=customer_id,
        stripe_invoice_id=invoice.id,
        stripe_subscription_id=subscription.id,
        amount_paid=invoice.amount_paid /
        100,  # Convert cents to dollars/euros
        currency=invoice.currency,
        subscription_type=subscription_type,
        start_date=start_date,
        end_date=end_date,
    )

    # Prepare email content
    subscription_details = (
        f"Subscription type: {subscription_type.capitalize()}\n"
        f"Start date: {start_date.strftime('%Y-%m-%d')}\n"
        f"End date: {end_date.strftime('%Y-%m-%d') if end_date else 'Ongoing'}\n"
        f"Amount paid: {invoice_data.amount_paid} {invoice_data.currency.upper()}"
    )

    email_body = (
        f"Thank you for your {subscription_type} subscription.\n\n"
        f"Invoice ID: {invoice.id}\n"
        f"{subscription_details}\n\n"
        f"You can view your invoice at: {invoice.hosted_invoice_url}")

    html_email = (
        f"<h1>Thank you for your {subscription_type} subscription</h1>"
        f"<p><strong>Invoice ID:</strong> {invoice.id}</p>"
        f"<p><strong>Subscription details:</strong><br>"
        f"{subscription_details.replace(chr(10), '<br>')}</p>"
        f"<p>You can view your invoice <a href='{invoice.hosted_invoice_url}'>here</a>.</p>"
    )

    # Retrieve the invoice

    # Send email with invoice
    send_mail('Your Subscription Invoice',
              f'Your subscription was successful',
              os.environ('OUR_MAIL_ADDRESS'), [customer_email],
              fail_silently=False,
              html_message=html_email)

    print(
        f"Payment succeeded and {subscription_type} subscription created for session {session['id']}"
    )

    return HttpResponse(status=200)


def cancel_subscription(request):
  try:
    user_id = request.user.id or request.POST.get('user_id')
    profile = Profile.objects.get(user_id=user_id)

    if profile.premium_date == None:
      start_date = profile.premium_start
      start_day = start_date.strftime('%d')
      next_month = timezone.now().strftime('%m')
      premium_date_str = f'{timezone.now().year}-{next_month}-{start_day}'
      profile.premium_date = premium_date_str

    # Retrieve the customer's subscription
    subscriptions = stripe.Subscription.list(
        customer=request.user.stripe_customer_id)

    if subscriptions.data:
      subscription = subscriptions.data[0]
      # Cancel the subscription at the end of the current period
      stripe.Subscription.modify(subscription.id, cancel_at_period_end=True)
      return JsonResponse({'status': 'Subscription cancelled'})
    else:
      return JsonResponse({'error': 'No active subscription found'},
                          status=400)
  except Exception as e:
    return JsonResponse({'error': str(e)}, status=400)
