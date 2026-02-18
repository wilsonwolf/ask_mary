"""GCS audio storage client — upload and signed URL generation.

Uses Application Default Credentials (ADC) for authentication.
Object path convention: {trial_id}/{participant_id}/{conversation_id}.wav
Bucket: ask-mary-audio
Service account: ask-mary-audio@ask-mary-486802.iam.gserviceaccount.com
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from google.cloud import storage

logger = logging.getLogger(__name__)

DEFAULT_SIGNED_URL_TTL_SECONDS = 3600


@dataclass
class UploadResult:
    """Result of an audio file upload.

    Attributes:
        gcs_path: Object path in the bucket.
        bucket_name: GCS bucket name.
    """

    gcs_path: str
    bucket_name: str


def build_object_path(
    trial_id: str,
    participant_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> str:
    """Build the GCS object path for an audio recording.

    Args:
        trial_id: Trial string identifier.
        participant_id: Participant UUID.
        conversation_id: Conversation UUID.

    Returns:
        Object path string: {trial_id}/{participant_id}/{conversation_id}.wav
    """
    return f"{trial_id}/{participant_id}/{conversation_id}.wav"


async def upload_audio(
    audio_data: bytes,
    bucket_name: str,
    object_path: str,
) -> UploadResult:
    """Upload audio data to GCS.

    Args:
        audio_data: Raw audio bytes.
        bucket_name: GCS bucket name.
        object_path: Object path within the bucket.

    Returns:
        UploadResult with bucket and path info.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    blob.upload_from_string(audio_data, content_type="audio/wav")
    logger.info(
        "audio_uploaded",
        extra={
            "bucket": bucket_name,
            "object_path": object_path,
        },
    )
    return UploadResult(gcs_path=object_path, bucket_name=bucket_name)


def generate_signed_url(
    bucket_name: str,
    object_path: str,
    ttl_seconds: int = DEFAULT_SIGNED_URL_TTL_SECONDS,
) -> str:
    """Generate a signed URL for audio playback.

    Args:
        bucket_name: GCS bucket name.
        object_path: Object path within the bucket.
        ttl_seconds: URL expiration in seconds (default: 3600).

    Returns:
        Signed URL string.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    url = blob.generate_signed_url(
        expiration=timedelta(seconds=ttl_seconds),
        method="GET",
    )
    return url
