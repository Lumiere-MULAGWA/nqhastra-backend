from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from products.models import Category, Product, ProductModel, ProductVariant


PASSWORD = 'Str0ng-P4ss!'


def make_catalog():
    category = Category.objects.create(
        slug='consumables', name_fr='Consommables', name_en='Consumables',
    )
    product = Product.objects.create(
        id='currency-test-prod', category=category,
        name_fr='Produit devise test', name_en='Currency test product',
        description_fr='', description_en='', details_fr='', details_en='',
    )
    model = ProductModel.objects.create(
        id='currency-test-model', product=product,
        name_fr='Modèle A', name_en='Model A', description_fr='', description_en='',
    )
    variant_usd = ProductVariant.objects.create(
        sku='NQA-T-USD-1', model=model, name_fr='Variante USD', name_en='USD variant',
        price=Decimal('10.00'), quantity=50,  # devise par défaut : USD
    )
    variant_cdf = ProductVariant.objects.create(
        sku='NQA-T-CDF-1', model=model, name_fr='Variante FC', name_en='CDF variant',
        currency='CDF', price=Decimal('2000.00'), quantity=50,
    )
    return variant_usd, variant_cdf


class CurrencySalesTests(APITestCase):
    """Ventes en USD ou FC avec taux journalier, conversion serveur unique."""

    @classmethod
    def setUpTestData(cls):
        cls.variant_usd, cls.variant_cdf = make_catalog()
        cls.admin = User.objects.create_user(
            email='chef@nqa.cd', username='chef', password=PASSWORD,
            is_staff=True, is_superuser=True,
        )
        cls.sales = User.objects.create_user(
            email='vente@nqa.cd', username='vente', password=PASSWORD,
        )
        cls.sales.groups.add(Group.objects.get(name='Commercial'))

    def auth(self, user):
        client = APIClient()
        response = self.client.post(
            '/api/v1/auth/token/',
            {'email': user.email, 'password': PASSWORD}, format='json',
        )
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        return client

    def test_admin_sets_rate_staff_reads(self):
        client = self.auth(self.admin)
        response = client.put('/api/v1/staff/rate/', {'usd_to_cdf': '2850.0'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['usd_to_cdf'], Decimal('2850.0'))

        staff = self.auth(self.sales)
        response = staff.get('/api/v1/staff/rate/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['defined'])

    def test_commercial_cannot_set_rate(self):
        staff = self.auth(self.sales)
        response = staff.put('/api/v1/staff/rate/', {'usd_to_cdf': '2850.0'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_sale_usd_product_in_cdf_converts(self):
        """Produit à 10 USD vendu en FC avec taux 2850 → total 28500 FC."""
        self.auth(self.admin).put('/api/v1/staff/rate/', {'usd_to_cdf': '2850.0'}, format='json')
        client = self.auth(self.sales)
        response = client.post('/api/v1/sales/', {
            'payment_method': 'cash', 'currency': 'CDF',
            'items': [{'sku': 'NQA-T-USD-1', 'quantity': 1}],
            'amount_paid': '30000.00',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()
        self.assertEqual(Decimal(data['total']), Decimal('28500.00'))
        self.assertEqual(Decimal(data['change_due']), Decimal('1500.00'))
        self.assertEqual(data['currency'], 'CDF')
        self.assertEqual(Decimal(data['rate']), Decimal('2850.0'))

    def test_sale_cdf_product_in_usd_converts(self):
        """Produit à 2000 FC vendu en USD avec taux 2500 → total 0.80 USD."""
        self.auth(self.admin).put('/api/v1/staff/rate/', {'usd_to_cdf': '2500.0'}, format='json')
        client = self.auth(self.sales)
        response = client.post('/api/v1/sales/', {
            'payment_method': 'cash', 'currency': 'USD',
            'items': [{'sku': 'NQA-T-CDF-1', 'quantity': 1}],
            'amount_paid': '1.00',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()
        self.assertEqual(Decimal(data['total']), Decimal('0.80'))
        self.assertEqual(Decimal(data['rate']), Decimal('2500.0'))

    def test_sale_mixed_without_rate_rejected(self):
        """Devise mélangée sans taux du jour → 400 explicite."""
        client = self.auth(self.sales)
        response = client.post('/api/v1/sales/', {
            'payment_method': 'cash', 'currency': 'CDF',
            'items': [{'sku': 'NQA-T-USD-1', 'quantity': 1}],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Taux', str(response.data))

    def test_same_currency_sale_without_rate_ok(self):
        client = self.auth(self.sales)
        response = client.post('/api/v1/sales/', {
            'payment_method': 'cash', 'currency': 'USD',
            'items': [{'sku': 'NQA-T-USD-1', 'quantity': 2}],
            'amount_paid': '50.00',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()
        self.assertEqual(Decimal(data['total']), Decimal('20.00'))
        self.assertIsNone(data['rate'])

    def test_variant_exposes_currency(self):
        response = self.client.get('/api/v1/products/currency-test-prod/')
        variants = response.json()['models'][0]['variants']
        by_sku = {variant['sku']: variant for variant in variants}
        self.assertEqual(by_sku['NQA-T-CDF-1']['currency'], 'CDF')
        self.assertEqual(by_sku['NQA-T-USD-1']['currency'], 'USD')


class RegisterSessionTests(APITestCase):
    """Admin ouvre la caisse pour un agent (fond de caisse) ; clôture comptée."""

    @classmethod
    def setUpTestData(cls):
        cls.variant_usd, _ = make_catalog()
        cls.admin = User.objects.create_user(
            email='chef@nqa.cd', username='chef', password=PASSWORD,
            is_staff=True, is_superuser=True,
        )
        cls.cashier = User.objects.create_user(
            email='caisse@nqa.cd', username='caisse', password=PASSWORD,
            first_name='Jean', last_name='Kabongo',
        )
        cls.cashier.groups.add(Group.objects.get(name='Commercial'))

    def auth(self, user):
        client = APIClient()
        response = self.client.post(
            '/api/v1/auth/token/',
            {'email': user.email, 'password': PASSWORD}, format='json',
        )
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        return client

    def test_admin_opens_and_cashier_sells_into_session(self):
        admin = self.auth(self.admin)
        open_response = admin.post('/api/v1/staff/register/', {
            'cashier_id': self.cashier.pk, 'currency': 'USD', 'opening_amount': '50.00',
        }, format='json')
        self.assertEqual(open_response.status_code, 201, open_response.data)
        session = open_response.json()
        self.assertEqual(session['cashier_name'], 'Jean Kabongo')

        # pharmacie commerciale vend 2 articles dans cette session
        cashier = self.auth(self.cashier)
        sale_response = cashier.post('/api/v1/sales/', {
            'payment_method': 'cash', 'currency': 'USD',
            'items': [{'sku': 'NQA-T-USD-1', 'quantity': 1}], 'amount_paid': '50.00',
        }, format='json')
        self.assertEqual(sale_response.status_code, 201, sale_response.data)

        detail = admin.get(f"/api/v1/staff/register/{session['id']}/").json()
        self.assertEqual(detail['summary']['sales_count'], 1)
        cash = [v for v in detail['summary']['totals_by_method']['cash'] if v['currency'] == 'USD'][0]
        self.assertEqual(cash['amount'], '10')

        # 403 pour qui n'est ni admin ni l'agent concerné
        stranger = User.objects.create_user(email='a@nqa.cd', username='a', password=PASSWORD)
        stranger.groups.add(Group.objects.get(name='Commercial'))
        self.assertEqual(
            self.auth(stranger).post(f"/api/v1/staff/register/{session['id']}/close/", {'closing_amount': '60'}, format='json').status_code,
            403,
        )

        # L'agent peut fermer SA caisse ; le tiroir attendu = fond 50 + ventes 10
        close_response = cashier.post(f"/api/v1/staff/register/{session['id']}/close/", {
            'closing_amount': '60.00', 'closing_note': 'Ok',
        }, format='json')
        self.assertEqual(close_response.status_code, 200, close_response.data)
        self.assertEqual(close_response.json()['status'], 'closed')

    def test_commercial_cannot_open(self):
        self.assertEqual(
            self.auth(self.cashier).post('/api/v1/staff/register/', {
                'currency': 'USD', 'opening_amount': '0',
            }, format='json').status_code,
            403,
        )

    def test_admin_lists_staff_users(self):
        response = self.auth(self.admin).get('/api/v1/staff/users/')
        self.assertEqual(response.status_code, 200)
        emails = [u['email'] for u in response.json()]
        self.assertIn('caisse@nqa.cd', emails)
