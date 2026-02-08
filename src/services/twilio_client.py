"""Twilio service client for SMS, voice, and DNC checks."""

import logging

from twilio.rest import Client as TwilioRestClient

logger = logging.getLogger(__name__)


class TwilioClient:
    """Stateless Twilio client for outbound communications.

    Attributes:
        account_sid: Twilio account SID.
        from_number: Twilio phone number for outbound.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        messaging_service_sid: str = "",
    ) -> None:
        """Initialize TwilioClient.

        Args:
            account_sid: Twilio account SID.
            auth_token: Twilio auth token.
            from_number: Twilio outbound phone number.
            messaging_service_sid: Messaging Service SID for opt-out.
        """
        self.account_sid = account_sid
        self.from_number = from_number
        self.messaging_service_sid = messaging_service_sid
        self._client = TwilioRestClient(account_sid, auth_token)

    def check_dnc_status(self, phone: str) -> bool:
        """Check if a phone number is opted out via Twilio.

        Args:
            phone: Phone number to check.

        Returns:
            True if the number is opted out.
        """
        return self._check_opt_out(phone)

    def _check_opt_out(self, phone: str) -> bool:
        """Internal opt-out check via Twilio Messaging Service.

        Args:
            phone: Phone number to check.

        Returns:
            True if opted out.
        """
        if not self.messaging_service_sid:
            return False
        try:
            self._client.messaging.v1.services(
                self.messaging_service_sid,
            ).phone_numbers(phone).fetch()
            return True
        except Exception:
            return False

    async def send_sms(self, *, to: str, body: str) -> str:
        """Send an SMS message.

        Args:
            to: Recipient phone number.
            body: Message text.

        Returns:
            Message SID.
        """
        message = self._client.messages.create(
            to=to,
            from_=self.from_number,
            body=body,
        )
        logger.info("sms_sent", extra={"to": to, "sid": message.sid})
        return message.sid

    async def initiate_warm_transfer(
        self,
        *,
        participant_call_sid: str,
        coordinator_phone: str,
    ) -> str:
        """Initiate a warm transfer to a coordinator.

        Args:
            participant_call_sid: Active call SID to transfer.
            coordinator_phone: Coordinator phone number.

        Returns:
            New call SID for the coordinator leg.
        """
        call = self._client.calls.create(
            to=coordinator_phone,
            from_=self.from_number,
            twiml=f"<Response><Dial><Conference>{participant_call_sid}</Conference></Dial></Response>",
        )
        logger.info(
            "warm_transfer_initiated",
            extra={"coordinator": coordinator_phone, "sid": call.sid},
        )
        return call.sid
