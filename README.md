## Getting Started

### 1. Installation

(Tested on MacOS)

Clone this repository

Create empty environment with python 3.10

$ ./run-install.sh

This creates the folder .venv inside the repo folder. You can deactivate the original environment, and activate the applio venv by

$ source .venv/bin/activate

The first time only, run this script to download all pre-trained models

$ ./run-applio.sh

This will open the applio app in the web browser, you can close it since we will not use it

### 2. Installation

To run the expanded voices backend app, execute

$ export PYTORCH_ENABLE_MPS_FALLBACK=1
$ python micro_controller.py

### Communications with Unreal (maybe outdate?)

- **Waveform:** real time while user is recording audio:

```
{"type": "waveform",
"message": {"data": 1.0}
}
```

Send a series of these until full time is completed.

- **Latent space:** after audio conversion and feature extraction has been performed

```
{"type": "latent",
"message": 
	{"frame": 0,
	"data": [1.0, 1.0, 1.0]}
}
```

Send a series of these, and at the end a finish message in case the length is variable (it should be approximately the same but to avoid issues)

- **Finish message:**

```
{"type": "end_latent",
"message": 
	{"frame": -1,
	"data": [1.0, 1.0, 1.0]}
}
```