from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SignUpTests(TestCase):
    def test_signup_creates_profile(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "translator",
                "password1": "Strong-pass123",
                "password2": "Strong-pass123",
            },
        )

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="translator")
        self.assertEqual(user.username, "translator")
