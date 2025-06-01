import sounddevice as sd
import numpy as np
import librosa
import socket
import subprocess
import threading
import time
from pynput import keyboard
from core import run_infer_script
from websocket.socketudp import send_wf_point
from params_template import params
from datetime import datetime
from scipy.io.wavfile import write

FS = 44100
DURATION = 10
CHUNKS = 100
CHUNK_SAMPLES = FS * DURATION // CHUNKS
HOST = "localhost"
PORT = 65432

AUDIO_FOLDER = '/Users/tomasandrade/Documents/BSC/ICHOIR/Applio_light/assets/audios'

user_pitch = input("Enter pitch shift: ")

def send_amplitudes(chunk):
    try:
        chunk_float = librosa.util.buf_to_float(chunk, n_bytes=2)
        amplitude = float(np.mean(np.abs(chunk_float)))
        send_wf_point(amplitude)
    except Exception as e:
        print(f"[send_amplitudes] Error: {e}")


def record_audio():
    try:
        print("Recording started...")
        full_recording = []

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[Audio Callback] {status}")
            full_recording.append(indata.copy())
            if len(indata) == CHUNK_SAMPLES:
                threading.Thread(target=send_amplitudes, args=(indata,)).start()

        with sd.InputStream(samplerate=FS, channels=1, dtype='int16',
                            blocksize=CHUNK_SAMPLES, callback=callback):
            sd.sleep(DURATION * 1000)

        recorded = np.concatenate(full_recording, axis=0)
        print("Recording finished.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        OUTPUT_FILE = f"{AUDIO_FOLDER}/output_{timestamp}.wav"

        write(OUTPUT_FILE, FS, recorded)
        print(f"Saved to {OUTPUT_FILE}")

        params['input_path'] = OUTPUT_FILE
        params['output_path'] = f"{AUDIO_FOLDER}/output_trained_{timestamp}.wav"

        print('--------------- params')
        print(params)
        run_infer_script(**params)

        # try:
        #     run_infer_script(**params)

        # except Exception as e:
        #     print(f"[run_infer_script] Error: {e}")

    except Exception as e:
        print(f"[record_audio] Error: {e}")


def on_press(key):
    try:
        if key.char == 'r':
            threading.Thread(target=record_audio).start()
        elif key.char == 's':
            print("ollaaa")
        # elif knob for pitch logic
        # elif reset? dont think its needed. 
    except AttributeError:
        pass
    except Exception as e:
        print(f"[on_press] Error: {e}")


if __name__ == "__main__":
    print("Press 'r' to start recording for 10 seconds...")
    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except Exception as e:
        print(f"[Main Listener] Error: {e}")
