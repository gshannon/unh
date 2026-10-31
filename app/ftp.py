import logging
import os
from ftplib import FTP
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

target_ip = os.environ.get("TARGET_IP", None)
target_user = os.environ.get("TARGET_USER", None)
target_password = os.environ.get("TARGET_PASSWORD", None)


def send_file(file_path) -> None:

    with FTP(target_ip) as ftp:
        ftp.login(target_user, target_password)

        logger.debug(f"Sending {file_path}...")
        with open(file_path, "rb") as local_file:
            filename = Path(file_path).name
            ftp.storbinary(f"STOR {filename}", local_file)


def clean_files(nfiles: int | None) -> int:
    with FTP(target_ip) as ftp:
        ftp.login(target_user, target_password)
        files = ftp.nlst()
        print("Before...")
        print(files)
        n = 0
        for f in files:
            print(f"Deleting {f}")
            ftp.delete(f)
            n = n + 1
            if n >= nfiles:
                break
        print("After...")
        files = ftp.nlst()
        print(files)
        return n
