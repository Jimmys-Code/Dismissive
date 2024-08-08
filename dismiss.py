from flask import Flask, render_template
from flask_socketio import SocketIO
import pyaudio
import numpy as np
import threading
import time
import base64
import sys

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

# PyAudio setup
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

def audio_stream():
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize to [-1, 1]
            amplitude = np.abs(audio_data).mean()
            sys.stdout.write(f"\rCurrent Amplitude: {amplitude:.4f}")
            sys.stdout.flush()
            socketio.emit('audio_data', {'data': audio_data.tolist()})
            time.sleep(0.01)  # Add a small delay to prevent overwhelming the socket
        except IOError as e:
            print(f"IOError occurred: {e}")
            time.sleep(0.1)  # Wait a bit before trying again
        except Exception as e:
            print(f"An error occurred: {e}")
            break

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    threading.Thread(target=audio_stream, daemon=True).start()

@socketio.on('request_audio_file')
def handle_audio_file_request():
    try:
        with open("audio.wav", "rb") as audio_file:
            audio_data = audio_file.read()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            socketio.emit('audio_file_data', {'data': audio_base64})
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    socketio.run(app, debug=True)
