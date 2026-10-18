"""Importe le catalogue complet issu du frontend (catalog_data.json).

    python manage.py import_products [--prices prices.json]

Idempotent : ré-entrant sans dupliquer (update_or_create à chaque niveau).
Les prix non fournis sont laissés à 0.00 et à ajuster via l'admin Django.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from products.models import (
    Category,
    Product,
    ProductModel,
    ProductVariant,
    ProductAttribute,
    ProductApplication,
    ProductSpec,
)

DATA_FILE = Path(__file__).resolve().parent / 'catalog_data.json'


class Command(BaseCommand):
    help = 'Import initial du catalogue complet depuis les données du frontend'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prices',
            type=str,
            default='',
            help='Fichier JSON optionnel {SKU: prix} pour initialiser les tarifs',
        )
        parser.add_argument(
            '--purge',
            action='store_true',
            help='Supprime d\'abord tout le contenu du catalogue',
        )

    def handle(self, *args, **options):
        if options['purge']:
            ProductVariant.objects.all().delete()
            ProductAttribute.objects.all().delete()
            ProductModel.objects.all().delete()
            ProductApplication.objects.all().delete()
            ProductSpec.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING('Catalogue purgé.'))

        if not DATA_FILE.exists():
            raise CommandError(f"Fichier introuvable : {DATA_FILE}")

        data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
        prices = {}
        if options['prices']:
            prices = json.loads(Path(options['prices']).read_text(encoding='utf-8'))

        categories_imported = 0
        for cat in data['categories']:
            if cat['id'] == 'all':
                continue
            category, created = Category.objects.update_or_create(
                slug=cat['id'],
                defaults={
                    'name_fr': cat['label']['fr'],
                    'name_en': cat['label']['en'],
                },
            )
            categories_imported += 1

        products_imported = models_imported = variants_imported = 0
        for product_data in data['products']:
            product, _ = Product.objects.update_or_create(
                id=product_data['id'],
                defaults={
                    'category': Category.objects.get(slug=product_data['category']),
                    'name_fr': product_data['name']['fr'],
                    'name_en': product_data['name']['en'],
                    'description_fr': product_data['description']['fr'],
                    'description_en': product_data['description']['en'],
                    'details_fr': product_data['details']['fr'],
                    'details_en': product_data['details']['en'],
                },
            )
            products_imported += 1

            product.applications.all().delete()
            for item in product_data['applications']:
                ProductApplication.objects.create(
                    product=product,
                    text_fr=item['fr'],
                    text_en=item['en'],
                )

            product.specs.all().delete()
            for item in product_data['specs']:
                ProductSpec.objects.create(
                    product=product,
                    text_fr=item['fr'],
                    text_en=item['en'],
                )

            for model_data in product_data['models']:
                model, _ = ProductModel.objects.update_or_create(
                    id=model_data['id'],
                    defaults={
                        'product': product,
                        'name_fr': model_data['name']['fr'],
                        'name_en': model_data['name']['en'],
                        'description_fr': model_data['description']['fr'],
                        'description_en': model_data['description']['en'],
                    },
                )
                models_imported += 1

                for variant_data in model_data['variants']:
                    variant, created = ProductVariant.objects.update_or_create(
                        sku=variant_data['sku'],
                        defaults={
                            'model': model,
                            'name_fr': variant_data['name']['fr'],
                            'name_en': variant_data['name']['en'],
                            'stock_status': variant_data['stock'],
                            'price': prices.get(variant_data['sku'], 0),
                        },
                    )
                    variants_imported += 1

                    variant.attributes.all().delete()
                    for attribute in variant_data['attributes']:
                        ProductAttribute.objects.create(
                            variant=variant,
                            label_fr=attribute['label']['fr'],
                            label_en=attribute['label']['en'],
                            value_fr=attribute['value']['fr'],
                            value_en=attribute['value']['en'],
                        )

        self.stdout.write(self.style.SUCCESS(
            f'Import terminé : {categories_imported} catégories, '
            f'{products_imported} produits, {models_imported} modèles, '
            f'{variants_imported} variantes.'
        ))
