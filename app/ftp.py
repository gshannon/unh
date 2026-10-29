import logging
import os
from ftplib import FTP
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def send_files(*args) -> None:

    target_ip = os.environ.get("TARGET_IP", None)
    target_user = os.environ.get("TARGET_USER", None)
    target_password = os.environ.get("TARGET_PASSWORD", None)

    with FTP(target_ip) as ftp:
        ftp.login(target_user, target_password)

        for path in args:
            logger.debug(f"Sending {path}...")
            with open(path, "rb") as local_file:
                filename = Path(path).name
                ftp.storbinary(f"STOR {filename}", local_file)
