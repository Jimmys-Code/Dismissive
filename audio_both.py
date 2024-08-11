import pyaudio  # Library for audio input/output
import wave  # Library for reading and writing WAV files
import numpy as np  # Library for numerical operations
import matplotlib.pyplot as plt  # Library for plotting
from matplotlib.animation import FuncAnimation  # For creating animated plots
import os  # For file and directory operations
import time  # For timestamps and sleep
from threading import Thread, Event  # For running multiple tasks concurrently
from audio_only import play_audio  # Importing the play_audio function from audio_only.py

# Audio settings
CHUNK = 1024  # Number of audio frames per buffer
FORMAT = pyaudio.paInt16  # Audio format (16-bit int)
CHANNELS = 1  # Mono audio
RATE = 44100  # Sample rate (Hz)

# Create a PyAudio object
p = pyaudio.PyAudio()

# Create an event for signaling threads to stop
stop_event = Event()

# Open the microphone stream
stream_in = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK)

# Create a figure and axis for the plot
fig, ax = plt.subplots()
x = np.arange(0, CHUNK)  # X-axis values (sample indices)
line, = ax.plot(x, np.random.rand(CHUNK))  # Initial random data for the plot

# Set up the plot
ax.set_ylim(-32768, 32767)  # Y-axis limits (16-bit audio range)
ax.set_xlim(0, CHUNK)  # X-axis limits
ax.set_title('Real-time Audio Waveform')
ax.set_xlabel('Sample')
ax.set_ylabel('Amplitude')

# Function to update the plot
def update_plot(frame):
    try:
        if stop_event.is_set():
            return line,
        data = stream_in.read(CHUNK, exception_on_overflow=False)  # Read audio data
        waveform = np.frombuffer(data, dtype=np.int16)  # Convert to numpy array
        line.set_ydata(waveform)  # Update the plot with new data
    except OSError:
        pass  # Handle potential errors when reading from the stream
    return line,

# Function to record audio
def record_audio():
    if not os.path.exists('recordings'):
        os.makedirs('recordings')  # Create a directory for recordings if it doesn't exist

    while not stop_event.is_set():
        frames = []
        for _ in range(0, int(RATE / CHUNK * 5)):  # Record for 5 seconds
            if stop_event.is_set():
                break
            try:
                data = stream_in.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except OSError:
                break

        if frames:
            timestamp = int(time.time())
            filename = f"recordings/recording_{timestamp}.wav"

            # Save the recorded audio as a WAV file
            wf = wave.open(filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

        time.sleep(5)  # Wait for 5 seconds before starting the next recording

# Function to play audio in a loop
def play_audio_loop():
    # Open the wave file
    wf = wave.open('audio.wav', 'rb')

    # Open stream
    stream_out = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)

    try:
        while not stop_event.is_set():
            # Reset the file pointer to the beginning of the file
            wf.rewind()

            # Read data
            data = wf.readframes(CHUNK)

            # Play stream
            while len(data) > 0 and not stop_event.is_set():
                stream_out.write(data)
                data = wf.readframes(CHUNK)

    finally:
        # Stop stream
        stream_out.stop_stream()
        stream_out.close()

# Start the recording thread
record_thread = Thread(target=record_audio)
record_thread.daemon = True
record_thread.start()

# Start the playback thread
playback_thread = Thread(target=play_audio_loop)
playback_thread.daemon = True
playback_thread.start()

# Create the animation
ani = FuncAnimation(fig, update_plot, blit=True, interval=30)

# Show the plot
plt.show()

# Clean up
stop_event.set()
record_thread.join()
playback_thread.join()
stream_in.stop_stream()
stream_in.close()
p.terminate()

# How to use this script:
# 1. Make sure you have the required libraries installed (pyaudio, numpy, matplotlib)
# 2. Place an audio file named "audio.wav" in the same directory as this script
# 3. Run the script
#
# This script does three things simultaneously:
# 1. Records audio in 5-second chunks and saves them as WAV files
# 2. Plays an audio file (audio.wav) in a loop
# 3. Displays a real-time waveform of the input audio
#
# You can extend this script by:
# - Adding a GUI for controlling recording and playback
# - Implementing audio processing effects
# - Adding error handling and user input validation
# - Optimizing performance for longer recordings or higher sample rates
