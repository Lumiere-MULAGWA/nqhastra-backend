from django.contrib.auth.models import AbstractUser
from django.db import models


class BusinessProfile(models.Model):
    """Informations d'entreprise associées à un compte client / employé."""
    CITY_CHOICES = [
        ('lubumbashi', 'Siège Lubumbashi'),
        ('dar', 'Dar es Salaam'),
        ('other', 'Autre site'),
    ]
    user = models.OneToOneField(
        'accounts.User',
        related_name='profile',
        on_delete=models.CASCADE,
    )
    company = models.CharField("Entreprise", max_length=255)
    phone = models.CharField("Téléphone", max_length=50)
    address = models.CharField("Adresse", max_length=255, blank=True)
    city = models.CharField("Ville", max_length=20, choices=CITY_CHOICES, default='lubumbashi')
    tax_id = models.CharField("Numéro d'impôt / TVA", max_length=50, blank=True)

    def __str__(self):
        return f"{self.company} ({self.user.email})"


class User(AbstractUser):
    email = models.EmailField("e-mail", unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def is_store_admin(self):
        return self.is_superuser or self.groups.filter(name='Admin').exists()

    def is_sales(self):
        return self.groups.filter(name='Commercial').exists()

    def is_staff_member(self):
        return self.is_store_admin() or self.is_sales()

    def __str__(self):
        return self.get_full_name() or self.username
