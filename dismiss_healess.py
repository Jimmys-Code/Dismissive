from flask import Flask, render_template
from flask_socketio import SocketIO
import pyaudio
import numpy as np
import threading
import time
import base64
import logging
import socket
from queue import Queue
from audio_only import play_audio
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import wave
from datetime import datetime
import subprocess

class EchoCanceller:
    def __init__(self, filter_length=1024, learning_rate=0.1):
        self.filter_length = filter_length
        self.learning_rate = learning_rate
        self.filter_coeffs = np.zeros(filter_length)
        self.buffer = np.zeros(filter_length)

    def process(self, input_signal, reference_signal):
        output_signal = np.zeros_like(input_signal)
        for i in range(len(input_signal)):
            self.buffer = np.roll(self.buffer, -1)
            self.buffer[-1] = reference_signal[i]
            echo_estimate = np.dot(self.filter_coeffs, self.buffer)
            cleaned_sample = input_signal[i] - echo_estimate
            self.filter_coeffs += self.learning_rate * cleaned_sample * self.buffer
            output_signal[i] = np.clip(cleaned_sample, -1, 1)
        return output_signal

class EchoCancellationServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.is_running = False
        self.thread = None

        # PyAudio setup
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 44100

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=self.FORMAT,
                                  channels=self.CHANNELS,
                                  rate=self.RATE,
                                  input=True,
                                  frames_per_buffer=self.CHUNK)

        # Echo canceller setup
        self.echo_canceller = EchoCanceller(filter_length=self.CHUNK)

        # Selenium WebDriver setup
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        self.chrome_options.add_argument("--use-fake-device-for-media-stream")
        self.chrome_options.add_argument("--use-fake-ui-for-media-stream")
        self.chrome_options.add_argument("--alsa-output-device=BlackHole_2ch")
        self.driver = None

        # Recording setup
        self.recording_buffer = []
        self.samples_per_recording = self.RATE * 5  # 5 seconds of audio
        self.sample_count = 0

        # Reference audio setup
        self.reference_audio = np.zeros(self.CHUNK, dtype=np.float32)

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.socketio.on('connect')
        def handle_connect():
            print('Client connected')
            threading.Thread(target=self.audio_stream, daemon=True).start()
            self.play_server_audio()

        @self.socketio.on('processed_audio')
        def handle_processed_audio(data):
            processed_audio = np.array(data['data'])
            self.display_amp(processed_audio)

        @self.socketio.on('request_audio_file')
        def handle_audio_file_request():
            self.play_server_audio()

    def play_server_audio(self):
        try:
            audio_thread = threading.Thread(target=play_audio, args=("audio.wav",), daemon=True)
            audio_thread.start()
            with open("audio.wav", "rb") as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                self.socketio.emit('audio_file_data', {'data': audio_base64})
        except Exception as e:
            print(f"Error playing server audio: {e}")

    def audio_stream(self):
        while self.is_running:
            try:
                input_data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                input_array = np.frombuffer(input_data, dtype=np.float32)

                # Apply echo cancellation
                processed_array = self.echo_canceller.process(input_array, self.reference_audio)

                # Update reference audio
                self.reference_audio = input_array

                # Handle NaN and Inf values
                processed_array = np.nan_to_num(processed_array, nan=0.0, posinf=1.0, neginf=-1.0)

                # Clip values to ensure they're in the valid range
                processed_array = np.clip(processed_array, -1, 1)

                self.socketio.emit('audio_data', {'data': processed_array.tolist()})
                self.display_amp(processed_array)
                self.record_audio(processed_array)
            except IOError as e:
                print(f"IOError occurred: {e}")
            except Exception as e:
                print(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()
                break

    def display_amp(self, processed_audio):
        amplitude = np.abs(processed_audio).mean()
        bar_length = int(amplitude * 50)  # Scale the bar length
        bar = '█' * bar_length
        print(f"\rAmplitude: {bar.ljust(50)} {amplitude:.4f}", end='', flush=True)

    def record_audio(self, audio_data):
        self.recording_buffer.extend(audio_data)
        self.sample_count += len(audio_data)
        
        if self.sample_count >= self.samples_per_recording:
            self.save_recording()
            self.recording_buffer = self.recording_buffer[self.samples_per_recording:]
            self.sample_count -= self.samples_per_recording

    def save_recording(self):
        if not os.path.exists("recordings"):
            os.makedirs("recordings")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recordings/recording_{timestamp}.wav"
        
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.RATE)
        audio_data = np.array(self.recording_buffer[:self.samples_per_recording])
        audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=1.0, neginf=-1.0)
        audio_data = np.clip(audio_data, -1, 1)
        wf.writeframes((audio_data * 32767.0).astype(np.int16).tobytes())
        wf.close()
        
        print(f"\nSaved recording: {filename}")

    def kill_chrome_instances(self):
        try:
            if os.name == 'nt':  # Windows
                os.system("taskkill /f /im chrome.exe")
            else:  # macOS and Linux
                os.system("pkill -f chrome")
        except Exception as e:
            print(f"Error killing Chrome instances: {e}")

    def start(self):
        if not self.is_running:
            self.kill_chrome_instances()
            self.is_running = True
            self.thread = threading.Thread(target=self._run_server)
            self.thread.start()
            ip = socket.gethostbyname(socket.gethostname())
            print(f"Echo cancellation server started successfully. Access it at http://localhost:5002")

            # Open the browser in the background
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.get("http://localhost:5002")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Enable audio output
            self.driver.execute_script("const audio = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA'); audio.loop = true; audio.play();")

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()
            if self.driver:
                self.driver.quit()
            self.kill_chrome_instances()

    def _run_server(self):
        # Disable Flask logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # Run the Flask-SocketIO app
        self.socketio.run(self.app, debug=False, use_reloader=False, port=5002)

def main():
    server = EchoCancellationServer()
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()

if __name__ == '__main__':
    main()
    print("Server stopped.")
