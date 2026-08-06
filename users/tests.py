from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def test_user_str_uses_full_name_or_username(self):
        user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123',
            first_name='Alex',
            last_name='Morgan',
        )

        self.assertEqual(str(user), 'Alex Morgan')
