from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from .audio import decode_trial, MAX_UPLOAD_BYTES
from .client import AsrUnavailable
from .models import AsrTrial
from .tests import AsrDemoTests


class DecodeTrialTests(TestCase):
    def upload(self):
        return SimpleUploadedFile('voice.mp3', b'x'*1200, content_type='audio/mpeg')

    @patch('asr_demo.audio.shutil.which',return_value='ffmpeg')
    @patch('asr_demo.audio.subprocess.run')
    def test_ten_second_upload_and_five_second_recording(self,run,which):
        paths=[]
        def decode(args,**kw):
            paths.append(Path(args[args.index('-i')+1]))
            return SimpleNamespace(stdout=b'\0'*(16000*2*10))
        run.side_effect=decode
        pcm,duration=decode_trial(self.upload())
        self.assertEqual(duration,10)
        self.assertFalse(paths[0].exists())
        with self.assertRaises(ValueError):decode_trial(self.upload(),recording=True)
        self.assertFalse(paths[1].exists())
        run.return_value=SimpleNamespace(stdout=b'\0'*(16000*2*5));run.side_effect=None
        self.assertEqual(decode_trial(self.upload(),recording=True)[1],5)
        run.return_value=SimpleNamespace(stdout=b'\0'*(16000*2*10+2))
        with self.assertRaises(ValueError):decode_trial(self.upload())

    @patch('asr_demo.audio.subprocess.run')
    def test_oversize_rejected_before_decoder(self,run):
        fake=SimpleNamespace(size=MAX_UPLOAD_BYTES+1)
        with self.assertRaises(ValueError):decode_trial(fake)
        run.assert_not_called()


class DemoPrivacyTests(AsrDemoTests):
    def test_cleanup_removes_recent_audio_and_orphan_but_keeps_quota(self):
        from django.core.management import call_command
        trial=AsrTrial(user=self.user)
        trial.audio.save('old.webm',SimpleUploadedFile('old.webm',b'old'),save=True)
        orphan=Path(self.temp)/'asr_trials'/'orphan.audio'
        orphan.parent.mkdir(parents=True,exist_ok=True);orphan.write_bytes(b'orphan')
        call_command('purge_asr_trials')
        trial.refresh_from_db()
        self.assertFalse(trial.audio)
        self.assertFalse(orphan.exists())
        self.assertEqual(AsrTrial.objects.filter(user=self.user).count(),1)

    @patch('asr_demo.views.recognize',side_effect=AsrUnavailable('Недоступно'))
    @patch('asr_demo.views.decode_trial',return_value=(b'\0'*6400,.2))
    def test_no_audio_saved_on_failure(self,decode,recognize):
        self.client.force_login(self.user)
        response=self.client.post(reverse('asr-demo'),{'audio':SimpleUploadedFile('v.mp3',b'fake')})
        self.assertEqual(response.status_code,503)
        self.assertFalse(AsrTrial.objects.get().audio)
        self.assertEqual(list(Path(self.temp).rglob('*')),[])
