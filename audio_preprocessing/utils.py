import numpy as np
import pandas as pd
import librosa

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