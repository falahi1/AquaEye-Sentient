# Source: ME5660-EE5098 Group Report — AquaSound (2024-25)
# Author: Victory Anyalewechi (1945112)
# Extracted from: Appendix / code listings in the AquaSound group and individual reports
# Preserved as-is. No modifications.

import os
import pyaudio
import wave
import soundfile as sf
import threading
import serial
import requests
import pickle
from datetime import datetime
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
import tkinter.messagebox as messagebox

# ---- Configuration ----
WAV_FOLDER = "/home/aqua-sense/Python/wav_files"
FLAC_FOLDER = "/home/aqua-sense/Python/flac_files"
UPLOADED_FOLDER = os.path.join(FLAC_FOLDER, "uploaded")
sensor_readings = "/home/aqua-sense/Python/arduino_readings.txt"
minutes = 5
wait_minutes = 1
GOOGLE_DRIVE_FOLDER_ID = "11QAYDOyePI-2t7yBnwD4fmWrq0ojsDI7"
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('drive', 'v3', credentials=creds)
    return service


def is_connected():
    try:
        requests.get('https://www.google.com', timeout=5)
        return True
    except requests.ConnectionError:
        return False


def upload_file(service, file_path):
    file_name = os.path.basename(file_path)
    file_metadata = {
        'name': file_name,
        'parents': [GOOGLE_DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='audio/flac', resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {file_name} with ID: {file.get('id')}")


def upload_pending_files(service):
    os.makedirs(UPLOADED_FOLDER, exist_ok=True)
    for filename in os.listdir(FLAC_FOLDER):
        if filename.endswith('.flac'):
            file_path = os.path.join(FLAC_FOLDER, filename)
            upload_file(service, file_path)
            os.rename(file_path, os.path.join(UPLOADED_FOLDER, filename))


def record_audio(wav_path, minutes):
    chunk = 1024
    sample_format = pyaudio.paInt16
    channels = 1
    fs = 48000
    p = pyaudio.PyAudio()
    stream = p.open(format=sample_format, channels=channels, rate=fs,
                    frames_per_buffer=chunk, input=True)
    print("Recording...")
    frames = []
    for _ in range(0, int(fs / chunk * 60 * minutes)):
        data = stream.read(chunk)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    p.terminate()
    os.makedirs(WAV_FOLDER, exist_ok=True)
    wf = wave.open(wav_path, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(fs)
    wf.writeframes(b''.join(frames))
    wf.close()


def convert_wav_to_flac(wav_path, flac_path):
    data, samplerate = sf.read(wav_path)
    sf.write(flac_path, data, samplerate, format='FLAC')
    os.makedirs(FLAC_FOLDER, exist_ok=True)


def read_serial():
    ser = serial.Serial('/dev/ttyACM0', 9600)
    while True:
        line = ser.readline().decode('utf-8').strip()
        with open(sensor_readings, 'a') as f:
            f.write(line + '\n')


def save():
    save_file = messagebox.askyesno('Results', 'Save results?')
    if save_file:
        Species_pred.to_csv('Species predictions.csv', mode='a', index=False)


def main():
    serial_thread = threading.Thread(target=read_serial, daemon=True)
    serial_thread.start()

    while True:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = os.path.join(WAV_FOLDER, f"recording_{timestamp}.wav")
        flac_path = os.path.join(FLAC_FOLDER, f"recording_{timestamp}.flac")

        record_audio(wav_path, minutes)
        convert_wav_to_flac(wav_path, flac_path)

        if is_connected():
            service = authenticate()
            upload_pending_files(service)

        time.sleep(wait_minutes * 60)


if __name__ == "__main__":
    main()
