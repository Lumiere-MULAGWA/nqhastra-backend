# Backend NQA — API Django (catalogue, commandes, stock, paiements)

API du site New Quin Astra : gestion produits/prix, commandes à distance,
comptes clients, stock local et paiement Mobile Money.

## Démarrage rapide

```bash
cd backend
source venv/bin/activate        # ou : python -m venv venv && pip install -r requirements.txt
python manage.py runserver      # API : http://localhost:8000
```

Backoffice admin : http://localhost:8000/admin/ (démo : `admin@nqa.cd` / `admin12345`)

Import complet du catalogue (20 produits, 44 modèles, 102 SKU) :

```bash
python manage.py import_products                      # sans prix
python manage.py import_products --prices demo_prices.json   # prix indicatifs de démo
```

## API — /api/v1/

| Méthode | Route | Description |
|---|---|---|
| GET | `/categories/` | Catégories {label: {fr, en}} |
| GET | `/products/` | Catalogue (filtres `?q=&category=&stock=`) |
| GET | `/products/{id}/` | Détail produit (variantes + **prix** + quantité) |
| GET | `/orders/` | Mes commandes (JWT) / toutes (staff) |
| POST | `/orders/` | Créer une commande (invité ou connecté) |
| GET | `/orders/{reference}/` | Détail commande (staff/propriétaire) |
| POST | `/orders/track/` | Suivi public `{reference, email}` |
| POST | `/orders/{ref}/cancel/` | Annulation (staff/propriétaire) |
| POST | `/orders/{ref}/pay/` | Initier le paiement Mobile Money |
| POST | `/payments/{ref}/simulate/` | **Sandbox stub** : finaliser le test |
| POST | `/payments/webhook/` | Webhook du fournisseur |
| POST | `/auth/register/` | Créer un compte client |
| POST | `/auth/token/` | Connexion JWT |
| POST | `/auth/token/refresh/` | Rafraîchir l'access token |
| GET/PATCH | `/auth/me/` | Profil (client / commercial / admin) |

### Création de commande

```json
POST /api/v1/orders/
{
  "customer_name": "...", "customer_email": "...", "customer_company": "...",
  "customer_phone": "...", "delivery_city": "lubumbashi | dar | other",
  "items": [{"sku": "NQA-GR-P-3030", "quantity": 100}]
}
```

Référence générée `NQA-AAAAMMJJ-XXXX`, prix figés en base à la création,
totaux calculés côté serveur. SKUs inconnus → 400.

## Paiements (Mobile Money)

Fournisseur interchangeable via `PAYMENTS_PROVIDER` :

- `stub` (défaut, **sandbox**) : aucun appel réseau ; compléter via
  `POST /api/v1/payments/{provider_reference}/simulate/` (`succeeded` | `failed`).
- `flutterwave` : Airtel Money, Orange Money, M-Pesa, carte.
  Variables : `FLUTTERWAVE_SECRET_KEY`, `FLUTTERWAVE_SECRET_HASH`.

Un paiement réussi confirme la commande et décrémente le stock.

## Stock local

`ProductVariant.quantity` + `low_stock_threshold` éditables dans l'admin
(section Produits → Variantes). Décrément automatique à la confirmation.

## PostgreSQL (production)

`docker compose up` ou variables :
`DATABASE_URL=postgres DATABASE_NAME=… DATABASE_USER=… DATABASE_PASSWORD=… DATABASE_HOST=…`

## Rôles

- **Client** : commande, suivi, annulation
- **Commercial** (groupe Django `Commercial`) : accès lecture + gestion de toutes les commandes
- **Admin** (groupe `Admin` ou `is_superuser`) : tout (produits, prix, stock, utilisateurs)
