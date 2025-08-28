from core import run_infer_script
from params_template import params
import sys

import numpy as np
import pandas as pd
import librosa

import logging

LOGS_PATH = 'log.out'
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_PATH),   # Logs to a file
        logging.StreamHandler()           # Prints to console
    ]
)
logging.info(f'------------- logs output to {LOGS_PATH}')


F_MARIA = 277
GATE_DB = 25

def relative_pitch(av):
    return int(12*np.log2(F_MARIA/av))

arguments = sys.argv[1:]

input_params = {
'input_path': arguments[0], 
'output_path': arguments[1], 
'pitch': int(arguments[2])}


####################### PITCH EXTRACTION #############################
# print('opening audio with librosa')
# audio_path = input_params['input_path']
# audio, sr = librosa.load(audio_path, sr=None)
# f0 = librosa.yin(audio, 
#                 fmin=librosa.note_to_hz('C2'), 
#                 fmax=librosa.note_to_hz('C7'), 
#                 sr=sr)

# avg_f0 = np.nanmedian(f0)

def find_relative_frequency(audio_path, gate_db = -25):
    # --- 1) Load audio at native SR ---
    y, sr = librosa.load(audio_path, sr=None)

    # --- 2) Choose analysis params (match across features!) ---
    frame_length = 2048
    hop_length   = 512
    center       = True   # yin and rms both default to center=True

    # --- 3) Pitch (YIN) on the chosen frame grid ---
    f0 = librosa.yin(
        y=y,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C7'),
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
        center=center,
    ) 

    # --- 4) Loudness proxy on the SAME frame grid (RMS -> dB) ---
    rms = librosa.feature.rms(
        y=y,
        frame_length=frame_length,
        hop_length=hop_length,
        center=center,
        pad_mode="reflect",
    ).squeeze()  # shape: (n_frames,)

    rms_db = librosa.amplitude_to_db(rms, ref=np.max)

    #gate_db = -25.0
    mask = rms_db >= gate_db

    # Option B (often better): adaptive gate relative to median energy
    # gate_db = (np.median(rms_db) - 10)   # tweak the -10 to be stricter/looser
    # mask = rms_db >= gate_db

    # --- 6) Apply mask to f0 (NaN = ignore/unvoiced/too quiet) ---
    f0_masked = f0.copy()
    f0_masked[~mask] = np.nan

    f0_median = np.nanmedian(f0)
    f0_median_mask = np.nanmedian(f0_masked)

    return f0_median_mask, f0_median

audio_path = input_params['input_path']
f0_rel_filter, f0_wrong = find_relative_frequency(audio_path, gate_db = GATE_DB)

pitch_shift = relative_pitch(f0_rel_filter)
pitch_shift_wrong =relative_pitch(f0_wrong)

logging.info(f'Fundamental frequency detected {f0_rel_filter}, pitch shift: {pitch_shift}')
logging.info(f'Without the filter we get frequency {f0_wrong}, pitch shift: {pitch_shift_wrong}')

######################################################################

if f0_rel_filter is not None:
    print(f'Updating pitch to {pitch_shift}')
    input_params.update({'pitch': pitch_shift})

params.update(input_params)

print(params)

run_infer_script(**params)