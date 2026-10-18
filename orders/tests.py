from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import BusinessProfile, User
from orders.models import Order
from products.models import (
    Category, Product, ProductModel, ProductVariant,
)


class CatalogFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(slug='gratings', name_fr='Caillebotis', name_en='Gratings')
        cls.product = Product.objects.create(
            id='steel-gratings', category=cls.category,
            name_fr='Caillebotis', name_en='Gratings',
            description_fr='', description_en='', details_fr='', details_en='',
        )
        cls.model = ProductModel.objects.create(
            id='pressed', product=cls.product,
            name_fr='Pressé', name_en='Pressed',
            description_fr='', description_en='',
        )
        cls.variant = ProductVariant.objects.create(
            sku='NQA-TEST-1', model=cls.model,
            name_fr='Test', name_en='Test',
            stock_status='in_stock', price=50,
        )


class CatalogAPITests(CatalogFixtureMixin, APITestCase):
    def test_catalog_matches_frontend_shape(self):
        response = self.client.get('/api/v1/products/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[0]['category'], 'gratings')
        # La liste complète DOIT contenir les modèles/variantes (POS + site).
        first = data[0]
        self.assertIn('models', first)
        self.assertTrue(first['models'])
        self.assertIn('variants', first['models'][0])
        variant = first['models'][0]['variants'][0]
        self.assertIn('sku', variant)
        self.assertIn('stock', variant)
        self.assertIn('price', variant)
        detail = self.client.get('/api/v1/products/steel-gratings/').json()
        variant = detail['models'][0]['variants'][0]
        self.assertEqual(variant['stock'], 'in_stock')
        self.assertEqual(variant['price'], '50.00')

    def test_unknown_product_404(self):
        self.assertEqual(self.client.get('/api/v1/products/xyz/').status_code, 404)


class OrderAPITests(CatalogFixtureMixin, APITestCase):
    def test_guest_creates_order_with_snapshot_prices(self):
        payload = {
            'customer_name': 'Test', 'customer_email': 't@ex.cd',
            'customer_company': 'X', 'customer_phone': '000',
            'delivery_city': 'lubumbashi',
            'items': [{'sku': 'NQA-TEST-1', 'quantity': 3}],
        }
        response = self.client.post('/api/v1/orders/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        order = response.data
        reference = order['reference']
        self.assertRegex(reference, r'^NQA-\d{8}-\d{4,10}$')
        db_order = self.get_with_user(Order, reference, skip_user=True)
        self.assertEqual(db_order.total_amount, 150.00)
        self.assertEqual(db_order.items.exclude(price_at_order=db_order.items.first().price_at_order).count(), 0)
        item = db_order.items.first()
        self.assertEqual(item.price_at_order, 50)

    def get_with_user(self, model, reference, skip_user=True):
        if skip_user:
            return model.objects.get(reference=reference)
        return model.objects.get(reference=reference, user=self.user)

    def test_unknown_sku_returns_400(self):
        response = self.client.post('/api/v1/orders/', {
            'customer_name': 'T', 'customer_email': 't@ex.cd',
            'customer_company': 'X', 'customer_phone': '0',
            'delivery_city': 'dar',
            'items': [{'sku': 'GHOST-1', 'quantity': 1}],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('SKU inconnu', response.json()['items'][0])

    def test_track_public_endpoint(self):
        reference = self.create_order()
        response = self.client.post('/api/v1/orders/track/', {
            'reference': reference, 'email': 't@ex.cd',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'pending')

    def create_order(self):
        return self.client.post('/api/v1/orders/', {
            'customer_name': 'Test', 'customer_email': 't@ex.cd',
            'customer_company': 'X', 'customer_phone': '000',
            'delivery_city': 'lubumbashi',
            'items': [{'sku': 'NQA-TEST-1', 'quantity': 1}],
        }, format='json').data['reference']

    def test_wrong_email_cannot_track(self):
        reference = self.create_order()
        response = self.client.post('/api/v1/orders/track/', {
            'reference': reference, 'email': 'intruser@ex.cd',
        }, format='json')
        self.assertEqual(response.status_code, 404)


class PaymentTests(CatalogFixtureMixin, APITestCase):
    def _pay(self, reference, operator='airtel'):
        return self.client.post(f'/api/v1/orders/{reference}/pay/', {'operator': operator}, format='json')

    def test_pay_and_simulate_success_confirms_order_and_consumes_stock(self):
        self.variant.quantity = 100
        self.variant.save(update_fields=['quantity'])
        reference = Order.objects.create(
            customer_name='T', customer_email='t@ex.cd', customer_company='X',
            customer_phone='0', delivery_city='lubumbashi',
        ).reference
        from orders.models import OrderItem
        OrderItem.objects.create(order=Order.objects.get(reference=reference),
                                 variant=self.variant, quantity=4, price_at_order=50)
        order = Order.objects.get(reference=reference)
        order.recalculate_total()

        payment = self._pay(reference)
        self.assertEqual(payment.status_code, 201)
        provider_reference = payment.data['provider_reference']

        simulated = self.client.post(
            f'/api/v1/payments/{provider_reference}/simulate/',
            {'status': 'succeeded'}, format='json')
        self.assertEqual(simulated.status_code, 200)

        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual(self.variant.quantity, 96)

    def test_pay_rejects_unknown_operator(self):
        reference = Order.objects.create(
            customer_name='T', customer_email='t@ex.cd', customer_company='X',
            customer_phone='0', delivery_city='lubumbashi',
        ).reference
        response = self._pay(reference, operator='wave')
        self.assertEqual(response.status_code, 400)


class AccountTests(CatalogFixtureMixin, APITestCase):
    register_payload = {
        'email': 'cli@ex.cd', 'first_name': 'Cli', 'last_name': 'Ent',
        'password': 'Str0ng-P4ss!',
        'company': 'Co', 'phone': '000',
    }

    def test_register_login_and_me(self):
        response = self.client.post('/api/v1/auth/register/', self.register_payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email='cli@ex.cd').exists())
        self.assertTrue(BusinessProfile.objects.filter(company='Co').exists())

        token = self.client.post('/api/v1/auth/token/', {
            'email': 'cli@ex.cd', 'password': 'Str0ng-P4ss!',
        }, format='json').data
        self.assertIn('access', token)

        me = self.client.get('/api/v1/auth/me/', HTTP_AUTHORIZATION=f"Bearer {token['access']}")
        self.assertEqual(me.json()['role'], 'client')
        self.assertEqual(me.json()['profile']['company'], 'Co')

    def test_duplicate_email_rejected(self):
        User.objects.create_user(email='dbl@ex.cd', username='dbl', password='Str0ng-P4ss!')
        response = self.client.post('/api/v1/auth/register/', {
            'email': 'dbl@ex.cd', 'first_name': 'X', 'last_name': 'Y',
            'password': 'Str0ng-P4ss!', 'company': 'C', 'phone': '0',
        }, format='json')
        self.assertEqual(response.status_code, 400)
