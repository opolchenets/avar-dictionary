from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Alliance, District

User = get_user_model()


class SignUpTests(TestCase):
    def setUp(self):
        alliance = Alliance.objects.create(name="Горный союз")
        self.district = District.objects.create(
            name="Хунзахский",
            alliance=alliance,
        )

    def test_signup_creates_profile(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "translator",
                "district": self.district.pk,
                "password1": "Strong-pass123",
                "password2": "Strong-pass123",
            },
        )

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="translator")
        self.assertEqual(user.username, "translator")
        self.assertEqual(user.profile.district, self.district)
