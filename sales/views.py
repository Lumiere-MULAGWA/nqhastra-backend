
from datetime import date

from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nqa_backend.permissions import IsStaffMember, IsStoreAdmin

from .models import CURRENCY_CHOICES, DailyRate, RegisterSession, Sale
from .serializers import SaleCreateSerializer, SaleSerializer, RegisterSessionSerializer


class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Personnel uniquement.
    POST /api/v1/sales/    : encaisser une vente POS
    GET  /api/v1/sales/    : ventes récentes (filtres ?status= &method=)
    GET  /api/v1/sales/{ref}/
    GET  /api/v1/sales/stats/: chiffres du jour (POS)
    """
    permission_classes = [IsStaffMember]
    lookup_field = 'reference'
    lookup_value_regex = '[\\w\\-]+'
    filterset_fields = None

    def get_queryset(self):
        queryset = Sale.objects.all()
        status = self.request.query_params.get('status')
        method = self.request.query_params.get('method')
        date_from = self.request.query_params.get('from')
        date_to = self.request.query_params.get('to')
        if status:
            queryset = queryset.filter(status=status)
        if method:
            queryset = queryset.filter(payment_method=method)
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return SaleCreateSerializer
        return SaleSerializer

    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        return Response(SaleSerializer(sale, context=self.get_serializer_context()).data, status=201)

    def list(self, request, *args, **kwargs):
        # Rapports : jusqu'à 1000 lignes quand une période est demandée.
        snapshot = self.get_queryset()[:1000 if 'from' in request.query_params else 100]
        return Response(SaleSerializer(snapshot, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Chiffres du jour + créances à recouvrer."""
        now = timezone.localtime()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = Sale.objects.filter(created_at__gte=midnight)
        revenue_day = [
            {
                'currency': currency,
                'amount': str(
                    today.filter(status='paid', currency=currency).aggregate(
                        Sum('total')
                    )['total__sum'] or 0
                ),
            }
            for currency, _ in CURRENCY_CHOICES
        ]
        by_method = {
            method: [
                # regroupe par devise : total USD / total FC
                {
                    'currency': currency,
                    'amount': str(
                        today.filter(payment_method=method, currency=currency).aggregate(
                            Sum('total')
                        )['total__sum'] or 0
                    ),
                }
                for currency, _ in CURRENCY_CHOICES
            ]
            for method, _ in Sale.PAYMENT_CHOICES
        }
        credit_outstanding = [
            {
                'currency': currency,
                'amount': str(
                    sum(
                        sale.balance_due
                        for sale in Sale.objects.filter(status='credit', currency=currency)
                    )
                ),
            }
            for currency, _ in CURRENCY_CHOICES
        ]
        return Response({
            'date': midnight.date().isoformat(),
            'sales_count': today.count(),
            'revenue_day': revenue_day,
            'by_method': by_method,
            'credit_outstanding': credit_outstanding,
        })


class DailyRateView(APIView):
    """
    GET /api/v1/staff/rate/  : taux du jour (le personnel le lit).
    PUT /api/v1/staff/rate/  : fixer le taux du jour (admin uniquement).
    """

    def get_permissions(self):
        if self.request.method == 'PUT':
            return [IsStoreAdmin()]
        return [IsStaffMember()]

    def get(self, request):
        today = date.today()
        rate = DailyRate.objects.filter(date=today).first()
        data = {'date': today.isoformat(), 'usd_to_cdf': None, 'defined': False}
        if rate:
            data.update(usd_to_cdf=rate.usd_to_cdf, defined=True)
        return Response(data)

    def put(self, request):
        raw = request.data.get('usd_to_cdf')
        try:
            value = Decimal(str(raw))
        except (TypeError, ValueError, InvalidOperation):
            value = Decimal('-1')
        if value <= 0:
            return Response(
                {'usd_to_cdf': ["Indique un taux positif, ex. 2850.00 (1 USD = 2850 FC)."]},
                status=400,
            )
        rate, _ = DailyRate.objects.update_or_create(
            date=date.today(),
            defaults={'usd_to_cdf': value, 'created_by': request.user if request.user.is_authenticated else None},
        )
        return Response({
            'date': rate.date.isoformat(),
            'usd_to_cdf': rate.usd_to_cdf,
            'defined': True,
        })


def _decimal(raw):
    try:
        return Decimal(str(raw))
    except (TypeError, ValueError, InvalidOperation):
        return None


@api_view(['GET', 'POST'])
def register_sessions(request):
    """
    GET  /api/v1/staff/register/  : sessions récentes (détail avec résumé)
    POST /api/v1/staff/register/  : OUVRIR la caisse (admin) pour un agent
    """
    if request.method == 'GET':
        sessions = RegisterSession.objects.all()[:50]
        return Response(RegisterSessionSerializer(sessions, many=True).data)

    # POST — ouverture réservée à l'admin
    if not (request.user.is_authenticated and
            (request.user.is_superuser or request.user.is_store_admin())):
        return Response({'detail': "Seul un administrateur ouvre la caisse."}, status=403)

    payload = request.data
    currency = payload.get('currency') or 'USD'
    opening = _decimal(payload.get('opening_amount') or '0')
    if opening is None or opening < 0:
        return Response({'opening_amount': ["Fond de caisse invalide (positif ou zéro)."]}, status=400)
    if currency not in dict(CURRENCY_CHOICES):
        return Response({'currency': ["Devise inconnue."]}, status=400)

    # PAS de cashier explicitement demandé → la caisse appartient à l'admin qui l'ouvre.
    cashier = None
    cashier_id = payload.get('cashier_id')
    if cashier_id:
        cashier = get_user_model().objects.filter(pk=cashier_id).first()
        if not cashier or not cashier.is_staff_member():
            return Response({'cashier_id': ["Agent introuvable ou non membre du personnel."]}, status=400)
        if RegisterSession.objects.filter(status='open', cashier=cashier).exists():
            return Response({'cashier_id': [f"{cashier.get_full_name() or cashier.username} a déjà une caisse ouverte."]}, status=400)

    session = RegisterSession.objects.create(
        cashier=cashier or request.user,
        opened_by=request.user,
        currency=currency,
        opening_amount=opening,
    )
    return Response(RegisterSessionSerializer(session).data, status=201)


def _staff_or_own_cashier(request, session):
    user = request.user
    if not (user and user.is_authenticated and user.is_staff_member()):
        return False
    return user.is_store_admin() or user.is_superuser or session.cashier_id == user.id


@api_view(['GET', 'POST'])
def register_close(request, pk):
    """POST /api/v1/staff/register/{id}/close/ : fermer avec le montant compté."""
    session = RegisterSession.objects.filter(pk=pk).first()
    if not session:
        return Response({'detail': 'Session introuvable.'}, status=404)
    if session.status != 'open':
        return Response({'detail': "Session déjà fermée."}, status=400)
    if not _staff_or_own_cashier(request, session):
        return Response({'detail': "Clôture réservée à l'admin ou à l'agent en caisse."}, status=403)

    closing = _decimal(request.data.get('closing_amount'))
    if closing is None or closing < 0:
        return Response({'closing_amount': ["Indique le total compté dans le tiroir."]}, status=400)
    session.closing_amount = closing
    session.closing_note = request.data.get('closing_note') or ''
    session.closed_at = timezone.now()
    session.closed_by = request.user
    session.status = 'closed'
    session.save()
    return Response(RegisterSessionSerializer(session).data)


@api_view(['GET'])
def register_detail(request, pk):
    """GET /api/v1/staff/register/{id}/ : détail + résumé de la session."""
    session = RegisterSession.objects.filter(pk=pk).first()
    if not session:
        return Response({'detail': 'Session introuvable.'}, status=404)
    if not (request.user and request.user.is_authenticated and request.user.is_staff_member()):
        return Response({'detail': "Accès réservé au personnel."}, status=403)
    return Response(RegisterSessionSerializer(session).data)

