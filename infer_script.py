from core import run_infer_script
from params_template import params
import sys

import librosa

arguments = sys.argv[1:]

# import argparse

# parser = argparse.ArgumentParser(
#                     prog='AudioConvLS',
#                     description='Converts audio using RVC and LS from Contentvec',
#                     epilog='Ask me for help')

# # Define named arguments
# parser.add_argument('--input_path', type=str, required=True, help="Path to the input wav file")
# parser.add_argument('--output_path', type=str, required=True, help="Path to the output wav file")
# parser.add_argument('--pitch', type=int, required=True, help="Pitch shift")

# args = parser.parse_args()

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

print(f'Fundamental frequency detected {f0}')


params.update(input_params)

print(params)

run_infer_script(**params)