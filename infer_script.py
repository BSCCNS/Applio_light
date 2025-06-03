from core import run_infer_script
from params_template import params
import sys

import numpy as np
import librosa

F_MARIA = 277

arguments = sys.argv[1:]

input_params = {
'input_path': arguments[0], 
'output_path': arguments[1], 
'pitch': int(arguments[2])}

print('opening audio with librosa')
audio_path = input_params['input_path']
audio, sr = librosa.load(audio_path, sr=None)

 ### PITCH EXTRACTION
f0 = librosa.yin(audio, 
                fmin=librosa.note_to_hz('C2'), 
                fmax=librosa.note_to_hz('C7'), 
                sr=sr)

avg_f0 = np.nanmean(f0)
print(f'Fundamental frequency detected {avg_f0}, computing pitch shift')

pitch_shift = int(12*np.log2(F_MARIA/avg_f0))

if avg_f0 is not None:
    print(f'Updating pitch to {pitch_shift}')
    input_params.update({'pitch': pitch_shift})

params.update(input_params)

print(params)

run_infer_script(**params)