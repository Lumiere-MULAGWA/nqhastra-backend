"""Interface commune pour tous les fournisseurs de paiement.

Chaque fournisseur est un module dans payments/providers/ se terminant par :
- initiate(payments.models.Payment) -> dict : prépare le paiement, renseigne
  provider_reference / checkout_url, et retourne la réponse de l'API
- handle_event(payload, headers) -> dict : interprète un webhook
  {"reference": <provider_reference>, "status": <uuid.Payment.STATUS_CHOICES>}
"""
