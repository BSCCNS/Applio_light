from core import run_infer_script
from params_template import params

import argparse

parser = argparse.ArgumentParser(
                    prog='AudioConvLS',
                    description='Converts audio using RVC and LS from Contentvec',
                    epilog='Ask me for help')

# Define named arguments
parser.add_argument('--input_path', type=str, required=True, help="Path to the input wav file")
parser.add_argument('--output_path', type=str, required=True, help="Path to the output wav file")
parser.add_argument('--pitch', type=int, required=True, help="Pitch shift")

args = parser.parse_args()

input_params = {
'input_path': args.input_path, 
'output_path': args.output_path, 
'pitch': args.pitch}

params.update(input_params)

print(params)

run_infer_script(**params)