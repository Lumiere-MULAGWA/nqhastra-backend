from django.db import models

class Category(models.Model):
    slug = models.SlugField(primary_key=True)
    name_fr = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)

    def __str__(self):
        return self.name_fr

    class Meta:
        verbose_name_plural = "Categories"

class Product(models.Model):
    id = models.SlugField(primary_key=True)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name_fr = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    description_fr = models.TextField()
    description_en = models.TextField()
    details_fr = models.TextField()
    details_en = models.TextField()
    image = models.ImageField(upload_to='products/', null=True, blank=True)

    def __str__(self):
        return self.name_fr

class ProductModel(models.Model):
    id = models.SlugField(max_length=100, primary_key=True)
    product = models.ForeignKey(Product, related_name='models', on_delete=models.CASCADE)
    name_fr = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    description_fr = models.TextField()
    description_en = models.TextField()

    def __str__(self):
        return f"{self.product.name_fr} - {self.name_fr}"

class ProductVariant(models.Model):
    STOCK_CHOICES = [
        ('in_stock', 'En stock'),
        ('limited', 'Stock limité'),
        ('on_request', 'Sur commande'),
    ]
    sku = models.CharField(max_length=100, unique=True)
    model = models.ForeignKey(ProductModel, related_name='variants', on_delete=models.CASCADE)
    name_fr = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    stock_status = models.CharField(max_length=20, choices=STOCK_CHOICES, default='in_stock')
    CURRENCY_CHOICES = [
        ('USD', 'Dollar américain ($)'),
        ('CDF', 'Franc congolais (FC)'),
    ]
    currency = models.CharField('Devise du prix', max_length=3, choices=CURRENCY_CHOICES, default='USD')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.sku} - {self.name_fr}"

class ProductAttribute(models.Model):
    variant = models.ForeignKey(ProductVariant, related_name='attributes', on_delete=models.CASCADE)
    label_fr = models.CharField(max_length=255)
    label_en = models.CharField(max_length=255)
    value_fr = models.CharField(max_length=255)
    value_en = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.label_fr}: {self.value_fr}"

class ProductApplication(models.Model):
    product = models.ForeignKey(Product, related_name='applications', on_delete=models.CASCADE)
    text_fr = models.CharField(max_length=255)
    text_en = models.CharField(max_length=255)

class ProductSpec(models.Model):
    product = models.ForeignKey(Product, related_name='specs', on_delete=models.CASCADE)
    text_fr = models.CharField(max_length=255)
    text_en = models.CharField(max_length=255)
