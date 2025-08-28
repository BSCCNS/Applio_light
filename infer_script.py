from core import run_infer_script
from params_template import params
import sys

from audio_preprocessing import utils as u

# import numpy as np
# import pandas as pd
# import librosa

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
GATE_DB = -25

def relative_pitch(av):
    if av is None:
        return None
    else:
        return int(12*np.log2(F_MARIA/av))

arguments = sys.argv[1:]

input_params = {
'input_path': arguments[0], 
'output_path': arguments[1], 
'pitch': int(arguments[2])}

f0_rel_filter, _ = u.find_relative_frequency(input_params['input_path'], 
                                            gate_db = GATE_DB)

pitch_shift = relative_pitch(f0_rel_filter)
logging.info(f'Fundamental frequency detected {f0_rel_filter}, pitch shift: {pitch_shift}')

if f0_rel_filter is not None:
    print(f'Updating pitch to {pitch_shift}')
    input_params.update({'pitch': pitch_shift})

params.update(input_params)

print(params)

run_infer_script(**params)