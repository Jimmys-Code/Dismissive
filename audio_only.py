import pyaudio
import wave
import os

def play_audio(filename):
    """Play an audio file using PyAudio."""
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return

    try:
        with wave.open(filename, 'rb') as wf:
            p = pyaudio.PyAudio()
            
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            
            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                stream.write(data)
                data = wf.readframes(chunk)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
    except Exception as e:
        print(f"Error playing audio: {e}")

def process_audio(input_file, output_file):
    """Process an audio file and save it as a new file."""
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return

    try:
        with wave.open(input_file, 'rb') as wf:
            p = pyaudio.PyAudio()
            
            # Read all frames at once
            frames = wf.readframes(wf.getnframes())
            framerates = wf.getframerate()
            print("the framerates is", framerates)
            # Create a new WAV file
            with wave.open(output_file, 'wb') as wf_out:
                wf_out.setnchannels(1)  # Set to mono
                wf_out.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf_out.setframerate(wf.getframerate())  # Set to 44.1 kHz
                wf_out.writeframes(frames)
            
            p.terminate()
        print(f"Processed audio saved as '{output_file}'")
    except Exception as e:
        print(f"Error processing audio: {e}")

if __name__ == "__main__":
    input_file = "Audio.wav"
    output_file = "processed_audio.wav"
    
    play_audio(input_file)
    process_audio(input_file, output_file)
    play_audio(output_file)