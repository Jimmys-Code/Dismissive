import pyaudio
import wave
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import os
import time
from threading import Thread, Event

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

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
x = np.arange(0, CHUNK)
line, = ax.plot(x, np.random.rand(CHUNK))

# Set up the plot
ax.set_ylim(-32768, 32767)
ax.set_xlim(0, CHUNK)
ax.set_title('Real-time Audio Waveform')
ax.set_xlabel('Sample')
ax.set_ylabel('Amplitude')

# Function to update the plot
def update_plot(frame):
    try:
        if stop_event.is_set():
            return line,
        data = stream_in.read(CHUNK, exception_on_overflow=False)
        waveform = np.frombuffer(data, dtype=np.int16)
        line.set_ydata(waveform)
    except OSError:
        pass
    return line,

# Function to record audio
def record_audio():
    if not os.path.exists('recordings'):
        os.makedirs('recordings')

    while not stop_event.is_set():
        frames = []
        for _ in range(0, int(RATE / CHUNK * 5)):
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

            wf = wave.open(filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

        time.sleep(5)

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
