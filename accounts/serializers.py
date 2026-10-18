from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import BusinessProfile, User


class BusinessProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessProfile
        fields = ['company', 'phone', 'address', 'city', 'tax_id']


class UserSerializer(serializers.ModelSerializer):
    profile = BusinessProfileSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    is_staff = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'role', 'is_staff', 'profile']

    def get_role(self, obj):
        if obj.is_store_admin():
            return 'admin'
        if obj.is_sales():
            return 'commercial'
        return 'client'

    def get_is_staff(self, obj):
        return obj.is_staff_member()


class ProfileSerializer(UserSerializer):
    profile = BusinessProfileSerializer()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        instance = super().update(instance, validated_data)
        if profile_data:
            profile = instance.profile
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    company = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=50)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    city = serializers.ChoiceField(choices=BusinessProfile.CITY_CHOICES, default='lubumbashi')
    tax_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet e-mail.")
        return value

    def create(self, validated_data):
        profile_data = {key: validated_data.pop(key) for key in
                        ('company', 'phone', 'address', 'city', 'tax_id') if key in validated_data}
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            email=email,
            username=email.split('@')[0] or email,
            password=password,
            **validated_data,
        )
        BusinessProfile.objects.create(user=user, **profile_data)
        return user
