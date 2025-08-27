
import sounddevice as sd
import pandas as pd
import numpy as np
import sys
import termios
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
#from pynput.keyboard import Key, Controller
from scipy.signal import savgol_filter 
from enum import Enum

from websocket.socketudp import (send_wf_point, send_message, send_ls_array)

# TODO FINISH THE REST OF COMMS
try:
    COLUMNS, _ = shutil.get_terminal_size()
except AttributeError:
    COLUMNS = 80

# Configuration
INACTIVITY_TIMEOUT = 120  # seconds
WAITFORINFOVIDEOPLAY = 12 # seconds wating for the video
WAITFORINTROVIDEOPLAY = 13

RECORD_SECONDS = 10 # Duration of recording in seconds
SAMPLE_RATE = 44100 # Sample rate in Hz check with microphone
CHANNELS = 1 # Number of audio channels (1 for mono, 2 for stereo)
BLOCKSIZE = 1024 #4096 # Block size for audio processing, smaller uses more cpu but gives faster response
BITSPERSAMPLE = 24 # 24 bits per sample, better wavs
THRESHOLD_DB = -30

GAIN = 4000
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

############################################
#######    Messages to Unreal Engine   #####
RESET = "restart"
PLAYINTRO = "playintro"
READYTORECORD = "ready_to_record"
RECORDING = "start_waveform"
STOPRECORDING = "end_waveform"
CONVERTING = "converting"
READYTOPLAY = "ready_to_play"
PLAY = "play"


############################################
#######       Global APP STATES        ##### 
class POSSIBLESTATES(Enum):
    IDLE = "IDLE"
    INTRO = "INTRO"
    RECREADY = "RECREADY"
    RECORDING = "RECORDING"
    RECDONE = "RECDONE"
    CONVERTING = "CONVERTING"
    PLAYREADY = "PLAYREADY"
    PLAYING = "PLAYING"
    PLAYEND = "PLAYEND"
    INTROFINISHED = "INTROFINISHED"

# Global control flags
APPSTATE = POSSIBLESTATES.IDLE.value
cancelFLAG = False
playback_gain = 1.25
last_file_created = None
current_pitch = 0
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

def wait_for_converted_file(converted_filename):
    global APPSTATE, POSSIBLESTATES, last_file_created, cancelFLAG
    on_activity()    
    APPSTATE = POSSIBLESTATES.CONVERTING.value # TODO check
    print(f"[*] Waiting for {converted_filename} to appear... ")
    while not os.path.exists(converted_filename):
        time.sleep(0.05)        
        # if wait_cancel_event.is_set(): # ESTO SIRVE SI HAY THREADS
        #     send_message(RESET) ## Tell Unreal Engine we canceled the conversion
        #     waiting_for_file = False
        #     return
    initime = time.time()
    latent_data = pd.read_csv(str(converted_filename)[:-4]+"_feats_3d.csv", index_col=0)
    send_ls_array(latent_data.values)
    print(f"[✓] Converted file detected: {converted_filename}")
    curtime = time.time()
    print(f"[ ] Waiting for video to play")

    while curtime-initime < WAITFORINFOVIDEOPLAY: # and not cancelFLAG: # we need to wait for the video to play
        # this could be cancellable
        time.sleep(0.25)
        curtime = time.time()

    if cancelFLAG:
        cancelFLAG = False
    APPSTATE = POSSIBLESTATES.PLAYREADY.value
    send_message(READYTOPLAY) ## Tell Unreal Engine we are ready to play
    print(f"[✓] Video finished")
    last_file_created = converted_filename

def play_wav(filename):
    global APPSTATE, POSSIBLESTATES, playback_gain
    data, samplerate = sf.read(filename, dtype='float32')
    blocksize = 1024  # Small block for responsive stop

    def callback(outdata, frames, time, status):
        global APPSTATE, POSSIBLESTATES, playback_gain
        on_activity()
        # if play_cancel_event.is_set():
        #     send_message(RESET)  # Notify Unreal Engine we are stopping playback
        #     raise sd.CallbackStop()
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
            APPSTATE = POSSIBLESTATES.PLAYEND.value
            raise sd.CallbackStop()

    callback.pos = 0
    try:
        APPSTATE = POSSIBLESTATES.PLAYING.value
        with sd.OutputStream(samplerate=samplerate, channels=data.shape[1] if data.ndim > 1 else 1,
                             callback=callback, blocksize=blocksize):
            while callback.pos < len(data):
                time.sleep(0.1)
        APPSTATE = POSSIBLESTATES.PLAYEND.value   
        print("[*] Playback finished, state set to PLAYEND")     
    except sd.CallbackStop:
        APPSTATE = POSSIBLESTATES.PLAYEND.value
        print("[*] Playback cancelled, state set to PLAYEND")
        pass

def save_to_wav(filename, audio_np):
    on_activity()
    if BITSPERSAMPLE == 24:
        # difficult to save 24-bit directly, use a library
        sf.write(filename, audio_np, SAMPLE_RATE, subtype='PCM_24')
    elif BITSPERSAMPLE == 16:
        audio_np = (audio_np * 32767).astype(np.int16)  # Convert to 16-bit
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
    if BITSPERSAMPLE == 32:
        # Convert float32 [-1, 1] to int32
        audio_int32 = np.clip(audio_np * 2147483647, -2147483648, 2147483647).astype(np.int32)
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(4)  # 32 bits = 4 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int32.tobytes())            

def record_audio():
    global APPSTATE, POSSIBLESTATES, current_pitch, volume_queue
    timestamp = f"{int(time.time())}"
    filename = INPUTFOLDER / f"recording_{timestamp}.wav"
    converted_filename = OUTPUTFOLDER / f"recording_{timestamp}_converted.wav"
    audio_data = []
    audio_queue = []
    volume_queue = []
    stop_event = threading.Event()
    APPSTATE = POSSIBLESTATES.RECORDING.value
    send_message(RECORDING)

    print(f"[*] Recording started. ")  

    udp_thread = threading.Thread(target=send_volume_levels, args=(audio_queue, stop_event))
    udp_thread.start()

    def callback(indata, frames, time_info, status):
        on_activity()
        audio_data.append(indata.copy())
        audio_queue.append(indata.copy())

    try:        
        with sd.InputStream(callback=callback, 
                            channels=CHANNELS, 
                            samplerate=SAMPLE_RATE,
                            blocksize=BLOCKSIZE):
            start_time = time.time()
            while (time.time() - start_time) < RECORD_SECONDS:
                time.sleep(0.1)  # Check every 50ms for cancellation
    except sd.CallbackStop:
        print(f"[!] Recording canceled.")  
    finally:
        stop_event.set()
        udp_thread.join()

    try:            
        APPSTATE = POSSIBLESTATES.RECDONE.value
        send_message(STOPRECORDING)
        print(f"[*] Saving recording")          
        audio_np = np.concatenate(audio_data, axis=0)

        save_to_wav(filename, audio_np)
        print(f"[✓] Saved to {filename}")          

        ### SEND TO CONVERSION
        APPSTATE = POSSIBLESTATES.CONVERTING.value
        send_message(CONVERTING)
        if os.path.exists('infer_script.py'):
            cmd = ["python", "infer_script.py", str(filename), str(converted_filename), str(current_pitch)]
        else:
            #for debugging
            time.sleep(3) # TODO delete in production and chango to Applio call
            cmd = ["cp", str(filename), str(converted_filename)]  # Replace with your actual command
            pd.DataFrame(np.random.random((100,3))).to_csv(str(converted_filename)[:-4]+"_feats_3d.csv")
        print(f"[*] Running conversion asynchronously: {' '.join(cmd)}") 
        try:
            proc = subprocess.Popen(cmd)
            # Do NOT wait for proc to finish here!
        except Exception as e:
            print(f"[x] Conversion failed to start: {e}")  

        # Wait for conversion
        wait_thread = threading.Thread(target=wait_for_converted_file, args=(converted_filename,))
        wait_thread.start()
        wait_thread.join()
        # while not os.path.exists(converted_filename):
        #     time.sleep(1)
        # print(f"[✓] Converted file detected: {converted_filename}")
        # After conversion and file is ready, wait until the video plays out
        while APPSTATE != POSSIBLESTATES.PLAYREADY.value:
            time.sleep(0.05)
        on_play()
    except Exception as e:
        print(e)


def on_record():
    global APPSTATE, POSSIBLESTATES
    on_activity()
    APPSTATE = POSSIBLESTATES.RECORDING.value
    threading.Thread(target=record_audio).start()


def on_play():
    global APPSTATE, POSSIBLESTATES, last_file_created
    on_activity()
    record_armed = False # Reset arming after playback
    if last_file_created is not None:
        APPSTATE = POSSIBLESTATES.PLAYING.value
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



def wait_for_intro_to_finish():
    global APPSTATE, POSSIBLESTATES, cancelFLAG
    on_activity()    
    curtime = time.time()
    initime = curtime
    print(f"[*] Waiting for intro to play (press ctrl-X to cancel)")
    cancelFLAG = False
    cancel_event = threading.Event()
    def on_cancel():
        global cancelFLAG
        cancelFLAG = True
        cancel_event.set()
        print("[x] Intro cancelled by user.")

    def press_r():
        print('User pressed r, ignoring')

    temp_listener = keyboard.GlobalHotKeys({
        '<ctrl>+x': on_cancel,
        'r': on_cancel,
        'p': on_cancel
    })
    temp_listener.start()    

    while curtime-initime < WAITFORINTROVIDEOPLAY and not cancelFLAG: # we need to wait for the video to play
        # this could be cancellable
        time.sleep(0.25)
        curtime = time.time()

    temp_listener.stop()
    print(f'-------- Exited the while loop, leaving wait_for_intro_to_finish, cancel flag is {cancelFLAG}')

    if cancelFLAG:
        cancelFLAG = False

    APPSTATE = POSSIBLESTATES.INTROFINISHED.value
    print(f'-------- updated APPSTATE to {APPSTATE}')
    #send_message(READYTORECORD)
     ## Tell Unreal Engine we are ready to play


def play_intro():
    global APPSTATE, POSSIBLESTATES
    on_activity()
    print("[ ] Playing intro...")
    APPSTATE = POSSIBLESTATES.INTRO.value    
    # Wait for conversion
    wait_thread = threading.Thread(target=wait_for_intro_to_finish)
    wait_thread.start()
    wait_thread.join()
    # while APPSTATE != POSSIBLESTATES.RECREADY.value:
    #     time.sleep(0.15)
    #     print('Im only sleeping in play intro')    
    #APPSTATE = POSSIBLESTATES.RECREADY.value

def reset_state():
    global APPSTATE, POSSIBLESTATES, last_file_created, listener
    last_file_created = None
    APPSTATE = POSSIBLESTATES.IDLE.value
    send_message(RESET)    
    # Restart hotkeys
    # if listener:
    #     listener.stop()
    # start_hotkeys()


def raise_cancel_flag():
    global cancelFLAG
    cancelFLAG = True


def inactivity_watcher():
    global APPSTATE, POSSIBLESTATES, listener, last_activity
    while True:
        time.sleep(1)
        with lock:
            inactive = (time.time() - last_activity) > INACTIVITY_TIMEOUT
        if inactive and APPSTATE != POSSIBLESTATES.IDLE.value:
            print("[*] State reset due to inactivity.")
            reset_state()  # <--- Reset everything!


def start_hotkeys():
    global listener, APPSTATE, POSSIBLESTATES
    print("Press a key to skip the idle state")
    if listener:
        print("[*] Stopping previous hotkeys listener...")
        listener.stop()
        # Give time for the listener to stop
        time.sleep(0.1)  

    def dispatcher(order):
        def inner(): # time.sleep(1)
            global APPSTATE, POSSIBLESTATES, last_file_created
            print(f"-- [ ] Received command: {order}, current state: {APPSTATE}")
            on_activity()
            if APPSTATE == POSSIBLESTATES.IDLE.value:
                if (order != "record"):
                    send_message(PLAYINTRO)
                    APPSTATE = POSSIBLESTATES.INTRO.value
                    play_intro()  
                    #send_message(READYTORECORD)
                    #APPSTATE = POSSIBLESTATES.RECREADY.value

            elif APPSTATE == POSSIBLESTATES.INTROFINISHED.value:
                print('Intro finished, sending messages')
                send_message(READYTORECORD)
                APPSTATE = POSSIBLESTATES.RECREADY.value

            elif APPSTATE == POSSIBLESTATES.RECREADY.value:
                if (order=="record"):
                    on_record()

            elif APPSTATE == POSSIBLESTATES.PLAYREADY.value:
                if (order=="play"):
                    on_play()
                if (order=="cancel"):
                    raise_cancel_flag()
            elif APPSTATE == POSSIBLESTATES.PLAYEND.value:
                if (order=="play"):
                    on_play()
                elif (order=="record"):
                    send_message(READYTORECORD)
                    print("[ ] Ready to record again, press Ctrl+R")
                    APPSTATE = POSSIBLESTATES.RECREADY.value
                elif (order=="exit"):
                    APPSTATE = POSSIBLESTATES.IDLE.value
                    print("[X] Reset to idle")
                    last_file_created = None
                    send_message(RESET)
            else:
                print(f"[x] Command '{order}' not allowed in state {APPSTATE}.")
            print(f"-- [ ] Finished command, new state: {APPSTATE}")
            # print("  R: Record")
            # print("  P: Play last file")
            # print("  Ctrl+X: Cancel recording/playback")
            # print("  Ctrl+G: Decrease volume")
            # print("  Ctrl+H: Increase volume")    
            # print("  Ctrl+C: Exit")
        return inner

    listener = keyboard.GlobalHotKeys({
        'r': dispatcher('record'),
        'p': dispatcher('play'),
        '<ctrl>+x': dispatcher('exit'),
        '<ctrl>+g': decrease_system_volume,
        '<ctrl>+h': increase_system_volume,
    })
    listener.start()

def main():    
    start_hotkeys()
    threading.Thread(target=inactivity_watcher, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()