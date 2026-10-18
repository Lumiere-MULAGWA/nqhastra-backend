"""Fournisseur Flutterwave (sandbox ou production selon les clés).

Variables d'environnement :
- FLUTTERWAVE_SECRET_KEY : clé secrète marchande
- FLUTTERWAVE_ENV : "sandbox" ou "production" (défaut : sandbox)
- FLUTTERWAVE_SECRET_HASH : secret du webhook, vérifié sur l'en-tête verif-hash

Le client choisit son opérateur mobile money :
airtel_money, orange_money, mtn_momo, mpesa (ou carte via checkout web).
"""
from django.conf import settings
import requests

API_BASE = "https://api.flutterwave.com"
TIMEOUT = 20

OPERATOR_ROUTES = {
    'airtel': 'airtel_money',
    'orange': 'orange_money',
    'mtn': 'mtn_momo',
    'mpsa': 'mpesa',
}


def _headers():
    return {
        'Authorization': f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        'Content-Type': 'application/json',
    }


def initiate(payment, phone_number="", currency=None, redirect_url=""):
    payload = {
        'tx_ref': payment.provider_reference or str(payment.id),
        'amount': str(payment.amount),
        'currency': payment.currency or currency or 'USD',
        'redirect_url': redirect_url,
        'customer': {
            'email': payment.order.customer_email,
            'phone_number': phone_number or payment.order.customer_phone,
            'name': payment.order.customer_name,
        },
        'meta': {'order_reference': payment.order.reference},
    }
    provider_reference = payment.provider_reference or str(payment.id)
    route = OPERATOR_ROUTES.get(payment.operator, 'card')
    response = requests.post(
        f"{API_BASE}/v3/charges?type={route}",
        json=payload,
        headers=_headers(),
        timeout=TIMEOUT,
    )
    data = response.json()
    payment.metadata = data
    if data.get('status') == 'success' and data.get('data'):
        payment.provider_reference = data['data'].get('tx_ref', provider_reference)
        link = data['data'].get('link') or data['data'].get('hosted_link') or ''
        if link:
            payment.checkout_url = link
        if data['data'].get('status') == 'successful':
            payment.status = 'succeeded'
        else:
            payment.status = 'pending'
    else:
        payment.status = 'failed'
    payment.save(update_fields=['provider_reference', 'checkout_url', 'status', 'metadata'])
    return data


def handle_event(payload):
    expected_hash = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', '')
    received_hash = payload.get('_verif_hash', '')
    status_map = {
        'successful': 'succeeded',
        'failed': 'failed',
        'cancelled': 'cancelled',
    }
    return {
        'reference': payload.get('tx_ref', ''),
        'status': status_map.get(payload.get('status', ''), 'pending'),
        'metadata': {'flutterwave_transaction_id': payload.get('data', {}).get('id')},
        'signature_valid': (
            bool(expected_hash)
            and bool(received_hash)
            and received_hash == expected_hash
        ),
    }
