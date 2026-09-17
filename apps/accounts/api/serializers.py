from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers
from apps.accounts.models import UserProfile


class UserSerializer(serializers.ModelSerializer):
    storage_quota_mb = serializers.SerializerMethodField()
    storage_used_mb = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'storage_quota_mb', 'storage_used_mb')

    def get_storage_quota_mb(self, obj):
        return obj.profile.get_quota_mb()

    def get_storage_used_mb(self, obj):
        return obj.profile.get_used_storage_mb()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        data['user'] = user
        return data
