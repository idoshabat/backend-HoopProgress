import hashlib
import json
import logging
import time
from urllib import parse, request

from django.conf import settings


logger = logging.getLogger(__name__)


def _get_cloudinary_config():
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
    api_key = getattr(settings, "CLOUDINARY_API_KEY", "")
    api_secret = getattr(settings, "CLOUDINARY_API_SECRET", "")

    if not cloud_name or not api_key or not api_secret:
        return None

    return {
        "cloud_name": cloud_name,
        "api_key": api_key,
        "api_secret": api_secret,
    }


def delete_cloudinary_image(public_id: str | None) -> bool:
    if not public_id:
        return False

    config = _get_cloudinary_config()
    if config is None:
        logger.warning("Cloudinary delete skipped because backend Cloudinary credentials are not configured.")
        return False

    timestamp = int(time.time())
    signature_base = f"public_id={public_id}&timestamp={timestamp}{config['api_secret']}"
    signature = hashlib.sha1(signature_base.encode("utf-8")).hexdigest()
    payload = parse.urlencode(
        {
            "public_id": public_id,
            "timestamp": timestamp,
            "api_key": config["api_key"],
            "signature": signature,
        }
    ).encode("utf-8")

    try:
        response = request.urlopen(
            request.Request(
                url=f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/image/destroy",
                data=payload,
                method="POST",
            ),
            timeout=10,
        )
        data = json.loads(response.read().decode("utf-8"))
        return data.get("result") in {"ok", "not found"}
    except Exception:
        logger.exception("Failed to delete Cloudinary asset '%s'.", public_id)
        return False
