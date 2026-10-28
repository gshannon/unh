import os
from ftplib import FTP
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def send_files(*args) -> None:

    target_ip = os.environ.get("TARGET_IP", None)
    target_user = os.environ.get("TARGET_USER", None)
    target_password = os.environ.get("TARGET_PASSWORD", None)

    with FTP(target_ip) as ftp:
        ftp.login(target_user, target_password)
        # print("Before sending...")
        # files = ftp.nlst()  # Get list of filenames
        # print(files)

        for path in args:
            print(f"  Sending {path}...")
            with open(path, "rb") as local_file:
                filename = Path(path).name
                ftp.storbinary(f"STOR {filename}", local_file)

        # print("After sending...")
        # files = ftp.nlst()  # Get list of filenames
        # print(files)
