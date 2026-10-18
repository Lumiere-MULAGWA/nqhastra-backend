"""Fournisseur de développement : pas d'appel réseau.

- `initiate` crée une référence locale et un lien de simulation.
- Le paiement est complété via la vue DEBUG /payments/<ref>/simulate/
  ou par un POST sur le webhook avec {"reference": ..., "status": "succeeded"}.

Basculez PAYMENTS_PROVIDER=flutterwave pour brancher un vrai processeur.
"""
import uuid


def initiate(payment, operator=""):
    payment.provider_reference = f"STUB-{uuid.uuid4().hex[:12].upper()}"
    payment.checkout_url = f"/api/v1/payments/{payment.provider_reference}/simulate/"
    payment.operator = operator
    payment.save(update_fields=['provider_reference', 'checkout_url', 'operator'])
    return {
        'provider_reference': payment.provider_reference,
        'checkout_url': payment.checkout_url,
        'mode': 'sandbox',
    }


def handle_event(payload):
    return {
        'reference': payload.get('reference', ''),
        'status': payload.get('status', 'pending'),
        'metadata': payload.get('metadata', {}),
    }
