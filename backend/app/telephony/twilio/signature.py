import base64
import hmac
from hashlib import sha1
from typing import Dict
from app.config import config
from app.utils.logging import logger


def validate_twilio_request(url: str, params: Dict[str, str], signature: str) -> bool:
    """Validates X-Twilio-Signature HTTP header for incoming Twilio webhook HTTP requests.

    Args:
        url: Full request URL (e.g., https://skp54pvx-8000.inc1.devtunnels.ms/api/twilio/voice)
        params: Form data parameters dictionary
        signature: Value of 'X-Twilio-Signature' HTTP header
    """
    if not config.TWILIO_VALIDATE_SIGNATURE:
        return True  # Configured to skip validation during local dev/testing

    if not signature or not config.TWILIO_AUTH_TOKEN:
        logger.warning("[TWILIO-SECURITY] Signature validation failed: Missing signature header or TWILIO_AUTH_TOKEN")
        return False

    try:
        # Build concatenation string of URL and alphabetically sorted param keys and values
        s = url
        for k in sorted(params.keys()):
            s += k + str(params[k])

        mac = hmac.new(config.TWILIO_AUTH_TOKEN.encode("utf-8"), s.encode("utf-8"), sha1)
        computed = base64.b64encode(mac.digest()).decode("utf-8")

        is_valid = hmac.compare_digest(computed, signature)
        if not is_valid:
            logger.warning(f"[TWILIO-SECURITY] Invalid X-Twilio-Signature header for URL '{url}'")
        return is_valid
    except Exception as e:
        logger.error(f"[TWILIO-SECURITY][ERROR] Exception during signature validation: {e}")
        return False
