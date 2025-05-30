## Getting Started

### 1. Installation

Run the installation script based on your operating system:

- **Windows:** Double-click `run-install.bat`.
- **Linux/macOS:** Execute `run-install.sh`.

This creates the venv and places a .venv/ folder inside the project folder. 

### 2. Running Applio

Checkout the `original-version` branch. Start Applio using:

- **Windows:** Double-click `run-applio.bat`.
- **Linux/macOS:** Run `run-applio.sh`.

This launches the Gradio interface in your default browser.

### 3. Script 

To convert an audio in wav format, produce the features file, and send features to unreal via UDP

```
$ source .venv/bin/activate
$ python infer_script.py
```

### 4. Communications with Unreal 

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