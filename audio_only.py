import pyaudio
import wave

# Open the audio file
filename = "Audio.wav"
wf = wave.open(filename, 'rb')

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open a stream
stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True)

# Read data in chunks
chunk = 1024
data = wf.readframes(chunk)

# Play the audio
while data:
    stream.write(data)
    data = wf.readframes(chunk)

# Close and terminate
stream.stop_stream()
stream.close()
p.terminate()
