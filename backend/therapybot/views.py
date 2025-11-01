from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from dotenv import load_dotenv
from testingAI import therapy
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
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
    result = therapy(question, therapy_type)
    return Response({'result': str(result)})
