import pyaudio


#record mic for 5 seconds then play it back
def record_audio():
    print()
    # Set the chunk size of 1024 samples
    chunk = 1024
    format = pyaudio.paInt16
    channels = 1
    rate = 44100
    seconds = 5

    # Initialize the PyAudio object
    p = pyaudio.PyAudio()

    # Open the microphone stream
    stream_in = p.open(format=format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk)

    # Open the output stream
    stream_out = p.open(format=format,
                        channels=channels,
                        rate=rate,
                        output=True)

    # Record audio for 5 seconds
    frames = []
    for i in range(0, int(rate / chunk * seconds)):
        data = stream_in.read(chunk)
        frames.append(data)

    # Playback the recorded audio
    for i in range(0, int(rate / chunk * seconds)):
        stream_out.write(frames[i])

    # Stop the streams
    stream_in.stop_stream()
    stream_in.close()
    stream_out.stop_stream()
    stream_out.close()

    # Terminate the PyAudio object
    p.terminate()
    
    
if __name__ == "__main__":
    record_audio()