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
from dismiss import EchoCanceller, apply_echo_cancellation, EchoCancellationServer

# Function to play reference audio out loud
def play_reference_audio(reference_queue, CHUNK):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    output=True)

    while True:
        if not reference_queue.empty():
            data = reference_queue.get()
            if isinstance(data, bytes):
                stream.write(data)
            elif isinstance(data, np.ndarray):
                stream.write(data.astype(np.int16).tobytes())
            else:
                print(f"Unexpected data type in reference queue: {type(data)}")

    stream.stop_stream()
    stream.close()
    p.terminate()

# Main function to run the Echo Cancellation Server
def main():
    server = EchoCancellationServer()
    
    # Start echo cancellation in the background
    echo_cancellation_thread = threading.Thread(
        target=apply_echo_cancellation,
        args=(server.mic_queue, server.reference_queue, server.output_queue, server.CHUNK),
        daemon=True
    )
    
    # Start playing reference audio out loud
    playback_thread = threading.Thread(
        target=play_reference_audio,
        args=(server.reference_queue, server.CHUNK),
        daemon=True
    )
    
    echo_cancellation_thread.start()
    playback_thread.start()

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

"""
How the input and output audio streams work:

1. Input Stream (Microphone):
   - The input stream captures audio from the default microphone using PyAudio.
   - Audio is captured in chunks (default size: 1024 samples) and added to the mic_queue.
   - This raw microphone data is used as the input for echo cancellation.

2. Output Stream (Speakers/Headphones):
   - The output stream plays audio through the default output device using PyAudio.
   - When an audio file is requested to be played, it's sent through this output stream.
   - The played audio also serves as the reference signal for echo cancellation.

3. Echo Cancellation Process:
   - The apply_echo_cancellation function runs in a separate thread.
   - It takes data from both mic_queue (input) and reference_queue (output/playback).
   - Processed audio (with echo cancelled) is put into the output_queue.

4. Websocket Communication:
   - Processed audio data is sent to the client (web browser) via websockets for visualization.

Integration with other applications:

1. As a standalone server:
   - Run this script, and it will start a Flask server.
   - Connect to http://localhost:5000 from a web browser to interact with the echo cancellation system.

2. As a module in another Python application:
   - Import the EchoCancellationServer class from this module.
   - Create an instance of EchoCancellationServer and call its start() method.
   - Use the mic_queue, reference_queue, and output_queue to interact with the audio streams:
     * Put microphone data into mic_queue
     * Put reference audio (e.g., speaker output) into reference_queue
     * Get processed audio from output_queue

3. Integrating with non-Python applications:
   - Run this server as a separate process.
   - Implement websocket communication in your application to send/receive audio data.
   - Send raw audio data to the server and receive processed audio data back.

Note: Ensure that the audio file format matches the PyAudio stream configuration 
(channels, sample rate, etc.) for proper playback and processing.
"""
