__all__ = ()

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email",
            },
        ),
    )
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Имя пользователя",
            },
        ),
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Пароль",
            },
        ),
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Подтверждение пароля",
            },
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()

        return user


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Имя пользователя",
            },
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Пароль",
            },
        ),
    )


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Имя",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Введите имя",
            },
        ),
    )
    last_name = forms.CharField(
        label="Фамилия",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Введите фамилию",
            },
        ),
    )
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Введите email",
            },
        ),
    )
    username = forms.CharField(
        label="Имя пользователя",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "readonly": "readonly",
            },
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["readonly"] = True

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if (
            User.objects.filter(email=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                "Пользователь с таким email уже существует",
            )

        return email
