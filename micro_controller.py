

import sounddevice as sd
import pandas as pd
import numpy as np
# parece que wave es el emas rapido https://github.com/bastibe/python-soundfile/issues/376
import wave
import soundfile as sf
import threading
import time
import os
import sys
import subprocess
import shutil
from pathlib import Path
from pynput import keyboard
from scipy.signal import savgol_filter 
import termios, tty

from websocket.socketudp import (send_wf_point, send_message, send_ls_array)

# TODO FINISH THE REST OF COMMS
try:
    COLUMNS, _ = shutil.get_terminal_size()
except AttributeError:
    COLUMNS = 80

INACTIVITY_TIMEOUT = 20  # seconds

# Configuration
RECORD_SECONDS = 10 # Duration of recording in seconds
SAMPLE_RATE = 44100 # Sample rate in Hz check with microphone
CHANNELS = 1 # Number of audio channels (1 for mono, 2 for stereo)
BLOCKSIZE = 1024 #4096 # Block size for audio processing, smaller uses more cpu but gives faster response
SAMPLEWIDTH = 3 # 24 bits per sample, better wavs
THRESHOLD_DB = -30
GAIN = 100
ROOTFOLDER = Path.absolute(Path("./audio/"))
SMOOTHORDER = 3
SMOOTHWINDOW = 80 # 10s*44100/BLOCKSIZE is the total amount of points, we want this window to be at least 5% ?  

INPUTFOLDER = ROOTFOLDER / "input"
OUTPUTFOLDER = ROOTFOLDER / "output"
# Ensure input and output directories exist
INPUTFOLDER.mkdir(parents=True, exist_ok=True)
OUTPUTFOLDER.mkdir(parents=True, exist_ok=True)
MAXPITCH = 18
MINPITCH = -18


## Messages to Unreal Engine
RESET = "restart"
PLAYINTRO = "playintro"
READYTORECORD = "ready_to_record"
RECORDING = "start_waveform"
STOPRECORDING = "end_waveform"
CONVERTING = "converting"
READYTOPLAY = "ready_to_play"
PLAY = "play"

# Global control flags
playback_gain = 1.25
recording = False
cancel_requested = False
waiting_for_file = False
wait_cancel_event = threading.Event()
play_cancel_event = threading.Event()
last_file_created = None
current_pitch = 0
playing_file = False
record_armed = False
volume_queue = []

last_activity = time.time()
listener = None
lock = threading.Lock()

def on_activity():
    global last_activity
    with lock:
        last_activity = time.time()

# Create a nice output gradient using ANSI escape sequences.
# Stolen from https://gist.github.com/maurisvh/df919538bcef391bc89f
def send_volume_levels(audio_queue, stop_event):    
    while not stop_event.is_set():
        on_activity()
        if not audio_queue:
            time.sleep(0.05)
            continue
        chunk = audio_queue.pop(0)
        # rms = librosa.feature.rms(y=indata)
        # vol = np.mean(rms)
        volume = float(np.linalg.norm(chunk) / len(chunk))
        volume_queue.append(volume)
        if len(volume_queue)>SMOOTHWINDOW+1:
            smooth_volume_array = savgol_filter(volume_queue, SMOOTHWINDOW, SMOOTHORDER)
            smooth_volume = float(smooth_volume_array[-1])
        else:
            smooth_volume = volume
        #smooth_volume_queue.append(smooth_volume)        
        send_wf_point((smooth_volume))
        # message = str(volume).encode()
        # sock.sendto(message, (UDP_IP, UDP_PORT))
        col = int(GAIN * smooth_volume * (COLUMNS - 1))  # Scale volume to terminal width
        col = min(max(col, 0), COLUMNS - 1)  # Ensure col is within bounds
        line = '█' * col + ' ' * (COLUMNS - col)
        print(line, end='\r', flush=True)  # Only update the current line
        #screen_clear(line)

def wait_for_converted_file(converted_filename, wait_cancel_event):
    global waiting_for_file, last_file_created
    on_activity()    
    waiting_for_file = True
    screen_clear(f"[*] Waiting for {converted_filename} to appear... (press ctrl-X to cancel)")
    while not os.path.exists(converted_filename):
        if wait_cancel_event.is_set():
            send_message(RESET) ## Tell Unreal Engine we canceled the conversion
            screen_clear("[x] Waiting for converted file canceled by user.")
            waiting_for_file = False
            return
        time.sleep(0.05)        
    latent_data = pd.read_csv(str(converted_filename)[:-4]+"_feats_3d.csv", index_col=0)
    send_ls_array(latent_data.values)
    screen_clear(f"[✓] Converted file detected: {converted_filename}")
    send_message(READYTOPLAY) ## Tell Unreal Engine we are ready to play
    last_file_created = converted_filename
    waiting_for_file = False

def play_wav(filename):
    global playing_file, playback_gain
    play_cancel_event.clear()
    data, samplerate = sf.read(filename, dtype='float32')
    blocksize = 1024  # Small block for responsive stop

    def callback(outdata, frames, time, status):
        on_activity()
        if play_cancel_event.is_set():
            send_message(RESET)  # Notify Unreal Engine we are stopping playback
            raise sd.CallbackStop()
        start = callback.pos
        end = start + frames
        end = min(end, len(data))
        realframes = end-start
        if data.ndim == 1:
            outdata[:,0]=0
            outdata[:realframes,0]=data[start:end] * playback_gain
        else:
            outdata[:]=0
            outdata[:realframes]=data[start:end] * playback_gain

        callback.pos = end        
        if end >= len(data):
            playing_file = False
            raise sd.CallbackStop()
        
    callback.pos = 0
    try:
        playing_file = True
        with sd.OutputStream(samplerate=samplerate, channels=data.shape[1] if data.ndim > 1 else 1,
                             callback=callback, blocksize=blocksize):
            while callback.pos < len(data) and not play_cancel_event.is_set():
                time.sleep(0.05)
        playing_file = False        
    except sd.CallbackStop:
        playing_file = False
        pass
    
def save_to_wav(filename, audio_np):
    on_activity()
    if SAMPLEWIDTH == 3:
        # difficult to save 24-bit directly, use a library
        sf.write(filename, audio_np, SAMPLE_RATE, subtype='PCM_24')
    elif SAMPLEWIDTH == 2:
        audio_np = (audio_np * 32767).astype(np.int16)  # Convert to 16-bit
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
    if SAMPLEWIDTH == 4:
        # Convert float32 [-1, 1] to int32
        audio_int32 = np.clip(audio_np * 2147483647, -2147483648, 2147483647).astype(np.int32)
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(4)  # 32 bits = 4 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int32.tobytes())            

def record_audio():
    global recording, cancel_requested, wait_cancel_event, waiting_for_file, current_pitch, volume_queue
    timestamp = f"{int(time.time())}"
    filename = INPUTFOLDER / f"recording_{timestamp}.wav"
    converted_filename = OUTPUTFOLDER / f"recording_{timestamp}_converted.wav"
    audio_data = []
    audio_queue = []
    volume_queue = []
    stop_event = threading.Event()
    cancel_requested = False
    recording = True
    wait_cancel_event.clear()
    waiting_for_file = False
    send_message(RECORDING)

    screen_clear(f"[*] Recording started. Press ctrl-X to cancel.")  

    udp_thread = threading.Thread(target=send_volume_levels, args=(audio_queue, stop_event))
    udp_thread.start()

    def callback(indata, frames, time_info, status):
        on_activity()
        if cancel_requested:
            raise sd.CallbackStop
        audio_data.append(indata.copy())
        audio_queue.append(indata.copy())

    try:        
        with sd.InputStream(callback=callback, 
                            channels=CHANNELS, 
                            samplerate=SAMPLE_RATE,
                            blocksize=BLOCKSIZE):
            start_time = time.time()
            while (time.time() - start_time) < RECORD_SECONDS:
                if cancel_requested:
                    send_message(RESET)
                    break
                time.sleep(0.1)  # Check every 50ms for cancellation
    except sd.CallbackStop:
        screen_clear(f"[!] Recording canceled.")  
    finally:
        stop_event.set()
        udp_thread.join()
        recording = False

    if not cancel_requested:
        try:
            send_message(STOPRECORDING)
            screen_clear(f"[*] Saving to {filename}...")          
            audio_np = np.concatenate(audio_data, axis=0)

            save_to_wav(filename, audio_np)
            screen_clear(f"[✓] Saved to {filename}")          

            ### SEND TO CONVERSION
            send_message(CONVERTING)
            if os.path.exists('infer_script.py'):
                cmd = ["python", "infer_script.py", str(filename), str(converted_filename), str(current_pitch)]
            else:
                #for debugging
                time.sleep(3) # TODO delete in production and chango to Applio call
                cmd = ["cp", str(filename), str(converted_filename)]  # Replace with your actual command
                pd.DataFrame(np.random.random((100,3))).to_csv(str(converted_filename)[:-4]+"_feats_3d.csv")
            screen_clear(f"[*] Running conversion asynchronously: {' '.join(cmd)}") 
            try:
                proc = subprocess.Popen(cmd)
                # Do NOT wait for proc to finish here!
            except Exception as e:
                screen_clear(f"[x] Conversion failed to start: {e}")  

            # Wait for conversion
            wait_thread = threading.Thread(target=wait_for_converted_file, args=(converted_filename, wait_cancel_event))
            wait_thread.start()
            wait_thread.join()
            # while not os.path.exists(converted_filename):
            #     time.sleep(1)
            # print(f"[✓] Converted file detected: {converted_filename}")
            # After conversion and file is ready, play automatically after 1 second
            time.sleep(1)
            on_play()
        except Exception as e:
            print(e)
    else:
        screen_clear(f"[x] Recording not saved.")  

def screen_clear(text=None):
    os.system("clear")
    print("Press Ctrl+R to record, Ctrl+X to cancel, Ctrl+P to play, Ctrl+C to exit.")
    if text is not None:
        print(text)

def on_record():
    on_activity()
    global recording, waiting_for_file, record_armed
    if not recording and not waiting_for_file and not playing_file:
        if not record_armed:
            record_armed = True
            send_message(READYTORECORD)
            print("[*] Press Ctrl+R again to start recording.")
        else:
            record_armed = False
            threading.Thread(target=record_audio).start()
    else:
        print("[x] Cannot record while playing or waiting for file.")


def on_cancel():
    on_activity()
    global cancel_requested, play_cancel_event
    global recording, waiting_for_file, playing_file
    # if recording:
    #     cancel_requested = True
    # if waiting_for_file:
    #     wait_cancel_event.set()
    # if playing_file:
    #     play_cancel_event.set()
    if not recording and not waiting_for_file and not playing_file:
        print("[x] Cancel requested.")
        reset_state()

def on_play():
    on_activity()
    global last_file_created, record_armed
    record_armed = False # Reset arming after playback
    if recording or playing_file:
        print("[x] Cannot play while recording or already playing.")
    # return
    elif last_file_created is not None:
        play_cancel_event.set()
        send_message(PLAY)                
        threading.Thread(target=play_wav, args=(str(last_file_created),)).start()
        print(f"[*] Playing {last_file_created}")
    else:
        print("[x] No file to play.")
           
def set_system_volume(percent):
    # percent: 0-100
    volume = int(percent)
    subprocess.run(["osascript", "-e", f"set volume output volume {volume}"])

def increase_system_volume():
    on_activity()
    step=10
    # Get current volume
    current = int(subprocess.check_output(
        ["osascript", "-e", "output volume of (get volume settings)"]
    ).strip())
    percent = (min(100, current + step))
    volume = int(percent)
    subprocess.run(["osascript", "-e", f"set volume output volume {volume}"])


def decrease_system_volume():
    on_activity()
    step=10
    current = int(subprocess.check_output(
        ["osascript", "-e", "output volume of (get volume settings)"]
    ).strip())
    percent = (max(0, current - step))
    volume = int(percent)
    subprocess.run(["osascript", "-e", f"set volume output volume {volume}"])

def wait_or_skip_video_with_hotkeys(timeout=15):
    global record_armed
    """
    Waits for Ctrl+R, Ctrl+P, or Ctrl+X or timeout (in seconds), whichever comes first.
    If a key is pressed, sends a SKIP_VIDEO message.
    """
    print("[*] Reproducing video from intro.")
    result = wait_for_ctrl_hotkey()
    if result:
        send_message(READYTORECORD)
        record_armed = True
        print("[*] Video skipped by user.")
    else:
        print("[*] Video finished.")


def reset_state():
    global recording, playing_file, waiting_for_file, cancel_requested
    global play_cancel_event, wait_cancel_event, last_file_created, record_armed
    # Stop playback and recording
    if playing_file:
        play_cancel_event.set()
    if recording:
        cancel_requested = True
    if waiting_for_file:
        wait_cancel_event.set()
    # Reset flags
    recording = False
    playing_file = False
    waiting_for_file = False
    cancel_requested = False
    last_file_created = None
    record_armed = False
    send_message(RESET)
    
    # Optionally clear queues, etc.
    print("[*] State reset due to inactivity.")

def inactivity_watcher():
    global listener, last_activity
    while True:
        time.sleep(1)
        with lock:
            inactive = (time.time() - last_activity) > INACTIVITY_TIMEOUT
        if inactive:
            reset_state()  # <--- Reset everything!
            if listener:
                listener.stop()
            wait_for_ctrl_hotkey()
            with lock:
                last_activity = time.time()
            wait_or_skip_video_with_hotkeys(timeout=15)
            # Restart hotkeys
            start_hotkeys()

def wait_for_ctrl_hotkey():
    """
    Waits for Ctrl+R, Ctrl+P, or Ctrl+X to be pressed.
    Returns the key pressed as a string: 'r', 'p', or 'x'.
    """
    event = threading.Event()
    result = {'key': None}

    def on_activate_any(keyname):
        def inner():
            result['key'] = keyname
            event.set()
            on_activity()
        return inner

    print("\n[Idle] Press Ctrl+R to record, Ctrl+P to play, or Ctrl+X to cancel...")
    with keyboard.GlobalHotKeys({
        '<ctrl>+r': on_activate_any('r'),
        '<ctrl>+p': on_activate_any('p'),
        '<ctrl>+x': on_activate_any('x'),
    }) as listener:
        event.wait()
        listener.stop()
    return result['key']

def start_hotkeys():
    global listener, record_armed
    print("Global Hotkey")
    print("  Ctrl+R: Record")
    print("  Ctrl+P: Play last file")
    print("  Ctrl+X: Cancel recording/playback")
    print("  Ctrl+G: Decrease volume")
    print("  Ctrl+H: Increase volume")    
    print("  Ctrl+C: Exit")
    send_message(READYTORECORD)
    record_armed = True
    listener = keyboard.GlobalHotKeys({
        '<ctrl>+r': on_record,
        '<ctrl>+p': on_play,
        '<ctrl>+x': on_cancel,
        '<ctrl>+g': decrease_system_volume,
        '<ctrl>+h': increase_system_volume,
    })
    listener.start()

def main():
    while True:
        key = wait_for_ctrl_hotkey()
        send_message(PLAYINTRO)
        # Optionally, you can act on the key here (e.g., start record/play/cancel immediately)
        wait_or_skip_video_with_hotkeys(timeout=15)
        start_hotkeys()
        threading.Thread(target=inactivity_watcher, daemon=True).start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
            break

if __name__ == "__main__":
    main()
