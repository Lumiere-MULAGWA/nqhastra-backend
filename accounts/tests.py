from django.contrib.auth.models import Group
from rest_framework.test import APIClient, APITestCase
from django.test import Client

from accounts.models import User
from products.models import Category


STRONG_PASSWORD = 'Str0ng-P4ss!'


class RolePermissionsTests(APITestCase):
    """Admin = accès total (API staff + Django Admin). Commercial = API staff
    (création produits, commandes) mais JAMAIS le Django Admin."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email='chef@nqa.cd', username='chef', password=STRONG_PASSWORD,
            is_staff=True, is_superuser=True,
        )
        cls.sales = User.objects.create_user(
            email='vente@nqa.cd', username='vente', password=STRONG_PASSWORD,
            # PAS de is_staff : le commercial n'entre pas au Django Admin.
        )
        cls.sales.groups.add(Group.objects.get(name='Commercial'))
        Category.objects.create(slug='consumables', name_fr='Consommables', name_en='Consumables')

    def staff_token(self, user):
        response = self.client.post(
            '/api/v1/auth/token/',
            {'email': user.email, 'password': STRONG_PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['access']

    def staff_client(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.staff_token(user)}')
        return client

    def test_sales_can_use_staff_api(self):
        """Le commercial peut créer un produit / encaisser via l'API staff."""
        client = self.staff_client(self.sales)
        self.assertEqual(client.get('/api/v1/orders/').status_code, 200)
        payload = {
            'id': 'role-test-product',
            'category': 'consumables',
            'name': {'fr': 'Produit test', 'en': 'Test product'},
            'description': {'fr': '', 'en': ''},
            'details': {'fr': '', 'en': ''},
            'models': [],
        }
        response = client.post('/api/v1/staff/products/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_sales_blocked_from_django_admin(self):
        """Sans le flag is_staff, le Django Admin est fermé pour le commercial."""
        django_client = Client()
        django_client.force_login(self.sales)
        response = django_client.get('/admin/')
        self.assertRedirects(response, '/admin/login/?next=/admin/')

    def test_admin_reaches_django_admin(self):
        django_client = Client()
        django_client.force_login(self.admin)
        self.assertEqual(django_client.get('/admin/').status_code, 200)

    def test_anonymous_gets_no_orders(self):
        """Anonyme : la liste est filtrée → vide, sans crash."""
        response = self.client.get('/api/v1/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
