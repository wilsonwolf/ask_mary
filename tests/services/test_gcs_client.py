"""Tests for the GCS audio storage client."""

import uuid
from unittest.mock import MagicMock, patch

from src.services.gcs_client import (
    UploadResult,
    build_object_path,
    generate_signed_url,
    upload_audio,
)


class TestBuildObjectPath:
    """Object path construction."""

    def test_builds_correct_path(self) -> None:
        """Path follows {trial_id}/{participant_id}/{conversation_id}.wav."""
        participant_id = uuid.uuid4()
        conversation_id = uuid.uuid4()
        path = build_object_path("trial-1", participant_id, conversation_id)
        assert path == f"trial-1/{participant_id}/{conversation_id}.wav"


class TestUploadAudio:
    """Audio upload to GCS."""

    async def test_uploads_and_returns_result(self) -> None:
        """Upload returns UploadResult with path and bucket."""
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch("src.services.gcs_client.storage.Client", return_value=mock_client):
            result = await upload_audio(
                b"fake-audio-data",
                "ask-mary-audio",
                "trial-1/pid/cid.wav",
            )
        assert isinstance(result, UploadResult)
        assert result.gcs_path == "trial-1/pid/cid.wav"
        assert result.bucket_name == "ask-mary-audio"
        mock_blob.upload_from_string.assert_called_once_with(
            b"fake-audio-data",
            content_type="audio/wav",
        )


class TestGenerateSignedUrl:
    """Signed URL generation."""

    def test_generates_url(self) -> None:
        """Returns a signed URL string."""
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch("src.services.gcs_client.storage.Client", return_value=mock_client):
            url = generate_signed_url(
                "ask-mary-audio",
                "trial-1/pid/cid.wav",
                ttl_seconds=3600,
            )
        assert url == "https://signed-url.example.com"
