from rest_framework.permissions import BasePermission


class IsStaffMember(BasePermission):
    """Accès au back-office custom : Admin **ou** Commercial."""

    message = "Accès réservé au personnel."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_staff_member() or user.is_superuser


class IsStoreAdmin(BasePermission):
    """Niveau 2 : réservé au groupe « Admin » (et superusers).

    Utilisé pour tout ce qui touche aux comptes / au Django Admin.
    Les « Commercial » n'y ont jamais accès.
    """

    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or user.is_store_admin()
