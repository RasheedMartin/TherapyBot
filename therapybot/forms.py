from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core import validators


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("email",)


THERAPY_TYPES = [
    ('teen_therapy', 'Teen Therapy'),
    ('couples_therapy', 'Couple Therapy'),
    ('family_therapy', 'Family Therapy'),
    ('general_therapy', 'general_therapy')

]


class FormName(forms.Form):
    therapy_type = forms.CharField(label="What type of therapy?",
                                   widget=forms.Select(choices=THERAPY_TYPES))
    question_field = forms.CharField(max_length=264)

    def clean(self):
        all_clean_data = super().clean()

