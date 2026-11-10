from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from accounts.models import Alliance, District
from clips.models import Batch, Clip, ClipEdit

class LeaderboardTests(TestCase):
    def test_ranks_accepted_clip_work_and_groups(self):
        alliance = Alliance.objects.create(name="Alliance")
        district = District.objects.create(name="District", alliance=alliance)
        user = get_user_model().objects.create_user(username="worker")
        user.profile.district = district
        user.profile.save()
        clip = Clip.objects.create(batch=Batch.objects.create(name="Batch"), audio="dummy.wav")
        ClipEdit.objects.create(clip=clip, user=user, text="text", verdict="accepted")
        response = self.client.get(reverse("leaderboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user_rows"][0]["edits"], 1)
        self.assertEqual(response.context["district_rows"][0]["obj"], district)
        self.assertEqual(response.context["alliance_rows"][0]["obj"], alliance)
