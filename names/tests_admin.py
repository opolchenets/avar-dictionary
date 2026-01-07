from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class NamesAdminTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        self.client.force_login(self.admin_user)

    def test_name_category_admin_changelist_loads(self):
        response = self.client.get(reverse("admin:names_namecategory_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_avar_name_admin_changelist_loads(self):
        response = self.client.get(reverse("admin:names_avarname_changelist"))
        self.assertEqual(response.status_code, 200)
