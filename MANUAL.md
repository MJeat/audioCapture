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

