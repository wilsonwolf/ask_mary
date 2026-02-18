"""Integration tests for GCS audio storage."""

from unittest.mock import MagicMock, patch

from src.services.gcs_client import generate_signed_url, upload_audio


class TestGcsAudioStorage:
    """GCS audio upload and signed URL generation."""

    async def test_upload_returns_upload_result(self) -> None:
        """Upload returns an UploadResult with gcs_path and bucket_name."""
        with patch("src.services.gcs_client.storage") as mock_storage:
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_storage.Client.return_value.bucket.return_value = mock_bucket

            result = await upload_audio(
                b"audio-bytes",
                "ask-mary-audio",
                "trial-1/p-id/conv-id.wav",
            )

        assert result.gcs_path == "trial-1/p-id/conv-id.wav"
        assert result.bucket_name == "ask-mary-audio"

    def test_signed_url_generation(self) -> None:
        """Signed URL is generated for audio path."""
        with patch("src.services.gcs_client.storage") as mock_storage:
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed"
            mock_bucket.blob.return_value = mock_blob
            mock_storage.Client.return_value.bucket.return_value = mock_bucket

            url = generate_signed_url(
                "ask-mary-audio",
                "audio/conv-123.wav",
            )

        assert url.startswith("https://")
