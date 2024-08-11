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
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.fftpack import fft

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
            output_signal[i] = cleaned_sample
        return output_signal

def apply_echo_cancellation(input_queue, reference_queue, output_queue, chunk_size=1024):
    echo_canceller = EchoCanceller(filter_length=chunk_size)
    while True:
        input_chunk = input_queue.get()
        reference_chunk = reference_queue.get()
        if input_chunk is None or reference_chunk is None:
            break
        input_array = np.frombuffer(input_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        reference_array = np.frombuffer(reference_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        processed_array = echo_canceller.process(input_array, reference_array)
        processed_chunk = (processed_array * 32768.0).astype(np.int16).tobytes()
        output_queue.put(processed_chunk)

class EchoCancellationServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.is_running = False
        self.thread = None

        # PyAudio setup
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=self.FORMAT,
                                  channels=self.CHANNELS,
                                  rate=self.RATE,
                                  input=True,
                                  frames_per_buffer=self.CHUNK)

        # Queues for echo cancellation
        self.mic_queue = Queue()
        self.reference_queue = Queue()
        self.output_queue = Queue()

        # Call visualizer setup
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 8))
        self.line1, = self.ax1.plot([], [], lw=2)
        self.line2, = self.ax2.plot([], [], lw=2)
        self.ax1.set_ylim(-1, 1)
        self.ax2.set_ylim(0, 1)
        self.ax1.set_title("Waveform")
        self.ax2.set_title("Frequency Spectrum")
        self.x_waveform = np.arange(self.CHUNK)
        self.x_spectrum = np.linspace(0, self.RATE // 2, self.CHUNK // 2)

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.socketio.on('connect')
        def handle_connect():
            print('Client connected')
            threading.Thread(target=self.audio_stream, daemon=True).start()

        @self.socketio.on('processed_audio')
        def handle_processed_audio(data):
            processed_audio = np.array(data['data'])
            self.display_amp(processed_audio)

        @self.socketio.on('request_audio_file')
        def handle_audio_file_request():
            try:
                audio_thread = threading.Thread(target=play_audio, args=("audio.wav",), daemon=True)
                audio_thread.start()
                with open("audio.wav", "rb") as audio_file:
                    audio_data = audio_file.read()
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    self.socketio.emit('audio_file_data', {'data': audio_base64})
            except Exception as e:
                print(f"Error: {e}")

    def audio_stream(self):
        while self.is_running:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                self.mic_queue.put(data)
                self.reference_queue.put(np.zeros(self.CHUNK, dtype=np.int16).tobytes())  # Dummy reference
                processed_chunk = self.output_queue.get()
                
                audio_data = np.frombuffer(processed_chunk, dtype=np.int16)
                audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize to [-1, 1]
                self.socketio.emit('audio_data', {'data': audio_data.tolist()})
                self.update_visualizer(audio_data)
                time.sleep(0.01)  # Add a small delay to prevent overwhelming the socket
            except IOError as e:
                print(f"IOError occurred: {e}")
                time.sleep(0.1)  # Wait a bit before trying again
            except Exception as e:
                print(f"An error occurred: {e}")
                break

    def display_amp(self, processed_audio):
        amplitude = np.abs(processed_audio).mean()
        bar_length = int(amplitude * 50)  # Scale the bar length
        bar = '█' * bar_length
        print(f"\rAmplitude: {bar.ljust(50)} {amplitude:.4f}", end='', flush=True)

    def update_visualizer(self, audio_data):
        # Update waveform
        self.line1.set_ydata(audio_data)
        
        # Update frequency spectrum
        spectrum = np.abs(fft(audio_data))[:self.CHUNK//2]
        self.line2.set_ydata(spectrum)

    def animate(self, i):
        return self.line1, self.line2

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_server)
            self.thread.start()
            ip = socket.gethostbyname(socket.gethostname())
            print(f"Echo cancellation server started successfully. Access it at http://localhost:5000")
            
            # Start the call visualizer
            self.line1.set_data(self.x_waveform, np.zeros_like(self.x_waveform))
            self.line2.set_data(self.x_spectrum, np.zeros_like(self.x_spectrum))
            ani = FuncAnimation(self.fig, self.animate, interval=50, blit=True)
            plt.show()

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()
            self.mic_queue.put(None)
            self.reference_queue.put(None)
            plt.close()

    def _run_server(self):
        # Disable Flask logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # Run the Flask-SocketIO app
        self.socketio.run(self.app, debug=False, use_reloader=False, host="0.0.0.0")

def main():
    server = EchoCancellationServer()
    
    # Start echo cancellation in the background
    echo_cancellation_thread = threading.Thread(
        target=apply_echo_cancellation,
        args=(server.mic_queue, server.reference_queue, server.output_queue, server.CHUNK),
        daemon=True
    )
    echo_cancellation_thread.start()
    
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
