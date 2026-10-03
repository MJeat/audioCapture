# Audio Capture App Manual

## What the app does

This app captures audio produced by another Windows application, such as Chrome, and saves:

- A QuickTime `.mov` audio recording
- A `.txt` transcript generated locally with faster-whisper

The app captures application audio only. It does not play the captured recording through your speakers.

## Requirements

- Windows 10 or later
- Python 3.14 or a compatible Python version
- An application currently playing audio
- The dependencies in [requirements.txt](./requirements.txt)

Install the dependencies from the project folder:

```powershell
python -m pip install -r requirements.txt
```

If `python` is not the Python interpreter used by VS Code, use the full interpreter path:

```powershell
C:\Python314\python.exe -m pip install -r requirements.txt
```

## Option 1: Use the GUI

Start the GUI:

```powershell
python audio_capture_gui.py
```

You can also open [audio_capture_gui.py](./audio_capture_gui.py) in VS Code and click **Run Python File**.

### GUI fields

#### Target process

Enter the process name to capture. The default is:

```text
chrome
```

Other examples:

```text
msedge
zoom
discord
```

The app searches for matching processes and prioritizes the process most likely to own the application's audio service.

### Finding a target process name

The target field expects a Windows process name, not a website title or meeting name.

1. Open the application you want to capture and make sure it is running.
2. Press `Ctrl+Shift+Esc` to open **Task Manager**.
3. Select the **Details** tab. If it is hidden, choose **More details** first.
4. Find the application in the list and read the value in the **Name** column.
5. Enter the name without the `.exe` suffix, or enter the beginning of the name.

Examples:

| Application | Typical process name |
|---|---|
| Google Chrome | `chrome` |
| Microsoft Edge | `msedge` |
| Zoom | `zoom` |
| Discord | `discord` |
| Microsoft Teams | `ms-teams` or `teams` |

For browser-based services such as YouTube or Google Meet, use the browser process (`chrome` or `msedge`), not `youtube` or `meet`.

If the GUI reports that the target was not found:

1. Confirm the application is open.
2. Copy the process name from Task Manager.
3. Remove `.exe` if it is present.
4. Try the name again while the application is playing audio.

The command-line app can also list matching processes:

```powershell
python audio_capture_app.py --target chrome --list-processes
```

This is useful when a browser has many helper processes. Prefer the process whose command line contains `audio.mojom.AudioService`.

#### File name

Enter the base name for the output files. For example:

```text
youtube_interview
```

The app creates:

```text
audios\youtube_interview.mov
transcripts\youtube_interview.txt
```

Invalid Windows filename characters are replaced automatically.

#### Whisper model

Choose the speech-to-text model:

- `tiny`: fastest, lowest accuracy
- `base`: better accuracy, slower
- `small`: higher accuracy, slower and uses more resources

The selected model is downloaded the first time it is used and then cached locally.

### GUI controls

- **Record [1]**: Start recording
- **Pause [2]**: Pause writing incoming audio
- **Resume [2]**: Continue after a pause
- **Stop [3]**: Stop recording, finalize the `.mov`, and generate the transcript

The keyboard shortcuts work while the GUI window is active:

| Key | Action |
|---|---|
| `1` | Record |
| `2` | Pause or resume |
| `3` | Stop |

The timer shows elapsed recording time and excludes time spent paused.

## Option 2: Use the command-line app

Start an unlimited recording:

```powershell
python audio_capture_app.py --target chrome
```

Record for a fixed duration:

```powershell
python audio_capture_app.py --target chrome --duration 30
```

Use a specific process ID:

```powershell
python audio_capture_app.py --pid 10988 --duration 30
```

List matching process IDs:

```powershell
python audio_capture_app.py --target chrome --list-processes
```

Use a more accurate model:

```powershell
python audio_capture_app.py --target chrome --model base --duration 60
```

Capture without transcription:

```powershell
python audio_capture_app.py --target chrome --duration 30 --no-transcribe
```

Press `Ctrl+C` to stop an unlimited command-line recording.

## Output folders

The default folders are:

```text
audios\
transcripts\
```

They are created automatically if they do not exist.

## Troubleshooting

### The recording is silent

1. Start the source application and begin playing audio before recording.
2. Use the process list:

   ```powershell
   python audio_capture_app.py --target chrome --list-processes
   ```

3. Prefer the process containing Chrome's audio service, usually shown with:

   ```text
   audio.mojom.AudioService
   ```

4. Capture that exact PID:

   ```powershell
   python audio_capture_app.py --pid <PID> --duration 30
   ```

The app reports an error instead of keeping a silent recording.

### The transcript says `[No speech detected]`

Confirm that the recording contains spoken language rather than music or sound effects. If speech is present, try the `base` model:

```powershell
python audio_capture_app.py --target chrome --model base --duration 60
```

### The first transcription takes a long time

The Whisper model is being downloaded or initialized. Wait for the first run to finish. Later recordings reuse the cached model.

### The GUI does not appear

Run it from a visible PowerShell window:

```powershell
C:\Python314\python.exe A:\Projects\audioCapture\audio_capture_gui.py
```

### The app cannot find the process

Make sure the target application is open and use its process name, not the video title. For YouTube, use `chrome`, because YouTube runs inside Chrome.

Yes. The app uses an AI speech-recognition model for transcription.

## AI model used

The app uses:

```text
faster-whisper
```

`faster-whisper` is an optimized implementation of OpenAI’s Whisper speech-to-text model.

The available model choices in the GUI are:

- `tiny`
- `base`
- `small`

## How it works

### 1. Capture application audio

The app uses `proc-tap` to capture audio from a Windows process such as Chrome.

The captured format is:

```text
48,000 Hz
Stereo
32-bit float PCM
```

### 2. Save the audio

The audio is converted to signed 16-bit PCM and saved as a QuickTime `.mov` file using PyAV.

Example:

```text
audios\youtube_recording.mov
```

### 3. Prepare the audio for Whisper

Whisper expects approximately:

```text
16,000 Hz
Mono
Float audio
```

The app therefore:

1. Decodes the `.mov` file.
2. Converts 16-bit samples back to normalized float values.
3. Mixes stereo channels into mono.
4. Reduces the sample rate from 48 kHz to 16 kHz.

### 4. Run the AI model locally

The app loads the selected Whisper model:

```python
model = WhisperModel(
    model_name,
    device="cpu",
    compute_type="int8",
)
```

The model runs on your own computer. The audio is not sent to OpenAI or another transcription API by this code.

The first time you use a model, it downloads from Hugging Face. After that, it is stored in the local Hugging Face cache.

### 5. Generate the transcript

The model analyzes the speech and returns recognized text. The app writes it to:

```text
transcripts\youtube_recording.txt
```

Sentence formatting places sentences ending with a period on separate indented lines.

## Model comparison

| Model | Speed | Accuracy | Resource usage |
|---|---:|---:|---:|
| `tiny` | Fastest | Lowest | Lowest |
| `base` | Medium | Better | Medium |
| `small` | Slowest of the current choices | Higher | Higher |

For normal YouTube speech, start with:

```text
base
```

Use `tiny` for quick tests and `small` when accuracy matters more than speed.

## Is this cloud AI?

No. The transcription runs locally through `faster-whisper`.

The only network activity is normally the first model download from Hugging Face. After the model has been downloaded, future transcription can run from the local cache.

## Main AI-related code

The transcription logic is in:

`audio_capture_app.py`

The GUI calls the same function through:

`audio_capture_gui.py`

The dependency is declared in:

`requirements.txt`

```text
faster-whisper>=1.1
```
