from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from dotenv import load_dotenv
from testingAI import therapy_chat
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import redirect
from django.conf import settings
load_dotenv()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    print(user)
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'email': user.email,
    })


@api_view(['POST'])
def register_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')

    if not username or not password:
        return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(password)
    except ValidationError as e:
        return Response({'error': e.messages}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password, email=email)
    print(user)
    return Response({'message': 'User created successfully'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_started(request):
    therapy_type = request.data.get('therapy_type')
    question = request.data.get('question')
    result = therapy_chat(question, therapy_type)
    return Response({'result': str(result)})

@api_view(['POST'])
def forgot_password(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Do not reveal if email exists (security best practice)
        return Response({'message': 'If an account with that email exists, a reset link has been sent.'}, status=status.HTTP_200_OK)

    # Generate reset token
    token = default_token_generator.make_token(user)
    reset_url = request.build_absolute_uri(
        reverse('reset-password') + f'?uid={user.pk}&token={token}'
    )

    # Send email (you can customize this)
    send_mail(
        subject='Password Reset Request',
        message=f'Hi {user.username},\n\nClick the link below to reset your password:\n{reset_url}',
        from_email='no-reply@therapybot.com',
        recipient_list=[user.email],
        fail_silently=True,
    )

    return Response({'message': 'If an account with that email exists, a reset link has been sent.'}, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
def reset_password(request):
    if request.method == 'GET':
        uid = request.query_params.get('uid')
        token = request.query_params.get('token')

        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response({'error': 'Invalid user'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        frontend_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        return redirect(frontend_url)

    # Handle POST request for actually resetting password
    uid = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    print(request.data)

    if not all([uid, token, new_password]):
        return Response({'error': 'uid, token, and new_password are required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        return Response({'error': 'Invalid user'}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password reset successful'}, status=status.HTTP_200_OK)