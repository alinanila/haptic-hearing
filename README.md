# Haptic Hearing

Technical documentation for the haptic actuator backend used in the Access Technology for Performer Tracking and Communication in the Theatre MEng Final Year Project at Imperial College London (Alina Roche, 2026).

This repository is a fork of `samchin/haptic-hearing-website`. The inherited Python WebSocket/audio backend that converts per-actuator amplitude commands into multi-channel sine-wave audio has been adapted for the use-case; the Create React App frontend for manual haptic control and psychophysics experiments and unchanged from the base repository. The base repository is designed for use with one PCB driving 8 LRAs. This repository implements changes to drive two PCBs with a total of 16 LRAs.

## Role In The Overall System

`haptic-hearing` is the haptic output layer. It receives amplitude frames over WebSocket and drives the haptic PCB/audio hardware.

In the current full system, HaptiStage in the `stage-support` repository is the component that fetches UWB pose and wearable sensor data, maps those values into the stage model, generates safety/navigation cues, and sends haptic patterns to this backend.

| Repository | Role |
|---|---|
| `uwb_app` | UWB anchors, measurement hub, 2-D localizer, dashboard/API, wearable sensor bridge. |
| `uwb_wearable_pi` | BNO085 IMU publisher for performer heading. |
| `stage-support` | HaptiStage operator app, cue engine, UWB bridge, haptic cue translation, and haptic backend client. |
| `haptic-hearing` | WebSocket-to-audio haptic backend and inherited React experiment/manual-control frontend. |

## Current Implementation Status

| Area | Status |
|---|---|
| Python haptic backend | Implemented in `server.py`. Receives WebSocket JSON and drives `sounddevice.OutputStream`. |
| Dual-PCB deployment | Implemented with `haptic-pcb1` and `haptic-pcb2` systemd services, `.env.pcb1`, `.env.pcb2`, and an ALSA card-naming udev rule. |
| Flask data endpoint | Implemented as `GET /data`; returns recent received command frames. |
| React frontend | Implemented as a Create React App with manual control and psychophysics routes. It is not the HaptiStage runtime UI. |
| HaptiStage integration | Implemented from the `stage-support` side. This repo provides the WebSocket backend that HaptiStage targets. |
| Dual-PCB frontend support | Implemented for current use. Backend supports `8000` and `8001` and generates distinct haptic outputs on both PCBs, but many older React components hard-code `ws://localhost:8000` or `ws://127.0.0.1:8000`. |
| Offline vibration analysis | Present in `PhaseBasedMotion.py`, but experimental and not connected to runtime. It contains hard-coded macOS paths. |
| Tests | Minimal and outdated. `src/App.test.js` is still the default Create React App placeholder. |

## System Architecture And Data Flow

Runtime backend flow:

```text
HaptiStage or another WebSocket client
  -> JSON amplitude frame
  -> server.py WebSocket handler
  -> in-memory amplitude queue
  -> sounddevice audio callback
  -> multi-channel sine wave at REACT_APP_FREQ
  -> USB audio interface / haptic PCB
  -> vibrotactile actuators
```

Diagnostic/frontend flow:

```text
server.py
  -> pandas command log
  -> Flask GET /data
  -> React chart/manual-control pages
```

Dual-PCB deployment:

| Service | Env file | Intended role | WebSocket | Flask | ALSA card |
|---|---|---|---:|---:|---|
| `haptic-pcb1` | `.env.pcb1` | PCB1 output | `8000` | `5000` | `HapticPCB1` |
| `haptic-pcb2` | `.env.pcb2` | PCB2 output | `8001` | `5001` | `HapticPCB2` |

## Hardware Requirements

| Component | Quantity | Role |
|---|---:|---|
| Raspberry Pi or Linux host | 1 | Runs two `server.py` instances. |
| 8-channel USB audio interface - HapticHearing PCB | 2 | Receives generated audio channels. |
| Vibrotactile actuators | Up to 8 per backend instance | Driven from audio output channels through the haptic PCB. |
| Powered multi-TT USB hub | Recommended for two PCBs | Needed for reliable simultaneous dual 8-channel USB audio on Raspberry Pi. |
| Browser host | Optional | Runs the React frontend or HaptiStage UI. |

The provided udev rule names USB sound cards by physical USB port because the cards do not expose unique serial numbers.

## Software Requirements

| Area | Requirement |
|---|---|
| Python backend | Python 3.13 was used in `environment.yml`; `requirements.txt` lists `asyncio`, `websockets`, `sounddevice`, `numpy`, `pandas`, `flask`, `flask_cors`, and `python-dotenv`. |
| Audio output | ALSA/PortAudio-compatible audio device visible to `sounddevice`. |
| React frontend | Node.js/npm with `react-scripts`. |
| systemd deployment | Linux with systemd, udev, and `/proc/asound/cards`. |
| Offline analysis | `PhaseBasedMotion.py` additionally imports `cv2` and `scipy`; OpenCV is not listed in `requirements.txt`. |

`environment.yml` is a full exported conda environment from a macOS development machine and includes a hard-coded `prefix`.

## Repository Structure

| Path | Purpose |
|---|---|
| `server.py` | Python WebSocket, Flask, and real-time audio backend. |
| `.env.pcb1`, `.env.pcb2` | Backend environment files for the two PCB services. |
| `systemd/haptic-pcb1.service`, `systemd/haptic-pcb2.service` | Template service units filled by `systemd/install.sh`. |
| `systemd/install.sh` | Installs both systemd services and the ALSA udev rule. |
| `systemd/89-alsa-usb-order.rules` | Stable ALSA card names based on USB port position. |
| `src/App.js` | React routes. |
| `src/Components/Circle` | Continuous manual haptic control and actuator charts. |
| `src/Components/Absolute` | Absolute threshold experiment. |
| `src/Components/Localization` | Localization accuracy experiment. |
| `src/Components/TwoPointDiscrimination` | Two-point discrimination experiment. |
| `src/Components/Input` | Manual per-actuator amplitude sliders. |
| `src/data/buttonPositions.json` | Button overlays for `overear`, `bracelet`, and `necklace`. |
| `public/images` | Device diagrams used by experiments. |
| `Data`, `Data Analysis R Code` | Collected psychophysical data and analysis scripts. |
| `PhaseBasedMotion.py` | Offline experimental vibration/video analysis, not part of runtime. |

## Installation

### Backend

Run on the haptic Raspberry Pi or Linux host from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If using conda/mamba:

```bash
mamba create -n haptichearing python=3.13 -y
mamba activate haptichearing
python -m pip install -r requirements.txt
```

### React Frontend

Run on the development/browser host from the repository root:

```bash
npm install
npm start
```

The older React app runs at:

```text
http://localhost:3000
```

## Configuration

`server.py` loads an env file from its first command-line argument. If no argument is supplied, it tries `./.env`.

| Variable | Current examples | Meaning |
|---|---|---|
| `REACT_APP_DEBUG` | `false` | If true, skip audio output and run WebSocket/Flask only. |
| `REACT_APP_NUMBER_ACTUATOR` | `8` | Number of output channels/actuators expected by backend. |
| `REACT_APP_MAPPING` | `0,1,3,7,6,2,4,5` | Logical actuator index to physical audio channel mapping. |
| `REACT_APP_FREQ` | `170` | Sine carrier frequency in Hz. |
| `REACT_APP_SAMPLE_RATE` | `48000` | Audio sample rate. |
| `REACT_APP_WINDOW_SAVING` | `10000` | Flask `/data` rolling window in ms. |
| `REACT_APP_SERVER_URL` | `http://127.0.0.1:5000` | Used by older React charting pages. |
| `WS_PORT` | `8000` / `8001` | Backend WebSocket listen port. |
| `FLASK_PORT` | `5000` / `5001` | Backend Flask listen port. |
| `ALSA_DEVICE_NAME` | `HapticPCB1` / `HapticPCB2` | Preferred ALSA card name. |
| `ALSA_DEVICE_INDEX` | `0` default | Fallback device index if no name is set. |


Before relying on the dual-PCB services, edit `systemd/89-alsa-usb-order.rules` to match the actual USB ports on the haptic Pi:

```bash
cat /proc/asound/cards
```

## Running Manually

Run PCB1:

```bash
# Run on the haptic Pi from the haptic-hearing repo root
source .venv/bin/activate
python server.py .env.pcb1
```

Run PCB2:

```bash
# Run on the haptic Pi from the haptic-hearing repo root
source .venv/bin/activate
python server.py .env.pcb2
```

Run without opening audio hardware:

```bash
# Run on a development host or haptic Pi
source .venv/bin/activate
REACT_APP_DEBUG=true python server.py .env.pcb1
```

Useful older React routes:

| Route | Purpose |
|---|---|
| `/` | Animated home page. |
| `/circle?DEVICE_TYPE=necklace` | Continuous circular manual-control interface. |
| `/input` | Manual amplitude sliders. |
| `/absolute?DEVICE_TYPE=necklace&PID=1` | Absolute threshold experiment. |
| `/localization?DEVICE_TYPE=necklace&PID=1` | Localization accuracy experiment. |
| `/two-point?DEVICE_TYPE=necklace&PID=1` | Two-point discrimination experiment. |

Most older React routes connect to `localhost:8000`; if the browser is not running on the haptic Pi, that URL points to the browser machine rather than the Pi.

## Running As Systemd Services

Run on the haptic Raspberry Pi from the repository root:

```bash
sudo ./systemd/install.sh
```

If the installer cannot find the `haptichearing` Python environment:

```bash
sudo HAPTIC_PYTHON=/path/to/haptichearing/bin/python ./systemd/install.sh
```

After installation, reboot once so the udev card names apply:

```bash
sudo reboot
```

Check services:

```bash
cat /proc/asound/cards
systemctl status haptic-pcb1 haptic-pcb2
journalctl -u haptic-pcb1 -f
journalctl -u haptic-pcb2 -f
```

Restart services:

```bash
sudo systemctl restart haptic-pcb1 haptic-pcb2
```

## Runtime Interfaces

| Interface | Host | Address | Payload |
|---|---|---|---|
| PCB1 WebSocket | Haptic Pi | `ws://0.0.0.0:8000` | JSON amplitude frames. |
| PCB1 Flask data | Haptic Pi | `http://0.0.0.0:5000/data` | Recent received frames. |
| PCB2 WebSocket | Haptic Pi | `ws://0.0.0.0:8001` | JSON amplitude frames. |
| PCB2 Flask data | Haptic Pi | `http://0.0.0.0:5001/data` | Recent received frames. |
| Audio output | Haptic Pi | ALSA `HapticPCB1` / `HapticPCB2` | Multi-channel float32 audio. |
| HaptiStage haptic client | `stage-support` frontend | Configured there, commonly Pi `:8000` and `:8001` | Same JSON amplitude frames. |

## Example Input And Output Messages

WebSocket command accepted by `server.py`:

```json
{
  "amplitudes": [0.8, 0.0, 0.3, 0.0, 0.0, 0.5, 0.0, 0.0],
  "duration": 50,
  "timestamp": 1710000000000,
  "device": "belt"
}
```

| Field | Type | Meaning |
|---|---|---|
| `amplitudes` | number array | Logical actuator amplitudes. |
| `duration` | number | Duration in milliseconds. |
| `timestamp` | number | Logged and used for `/data` retention. |
| `device` | string | Metadata only in this backend. Device-specific cue logic lives upstream. |

`GET /data` returns a JSON array of recently received frames.

## Connectivity Verification 

1. Label PCB1 and PCB2.
2. Put each PCB in a fixed USB hub port.
3. Edit `systemd/89-alsa-usb-order.rules` for those ports.
4. Install services and reboot.
5. Confirm `cat /proc/asound/cards` shows `HapticPCB1` and `HapticPCB2`.
6. Send low-amplitude test frames first.
7. Verify logical-to-physical ordering and adjust `REACT_APP_MAPPING` in `.env.pcb1` and `.env.pcb2`.
8. Restart services after environment changes:

```bash
sudo systemctl restart haptic-pcb1 haptic-pcb2
```

## Testing And Debugging

Frontend tests:

```bash
npm test
```

The current test is the default Create React App placeholder and is not a meaningful validation of the current UI.

Backend debug mode:

```bash
source .venv/bin/activate
REACT_APP_DEBUG=true python server.py .env.pcb1
```

Useful checks:

```bash
ss -ltn | grep -E ':8000|:8001|:5000|:5001'
cat /proc/asound/cards
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### Troubleshooting

| Symptom | Likely cause | Check/fix |
|---|---|---|
| `Device 'HapticPCB1' not found` | Udev rule does not match current USB port or reboot has not applied it. | Edit `89-alsa-usb-order.rules`, reinstall/reload, reboot, then check `cat /proc/asound/cards`. |
| Backend selects a device with too few channels | Wrong ALSA card or fallback index. | Check `ALSA_DEVICE_NAME`, `ALSA_DEVICE_INDEX`, and `sounddevice.query_devices()`. |
| WebSocket client cannot connect | Wrong host/port, backend not running, or browser using `localhost` on the wrong machine. | Check `ss -ltn`, service logs, and client URL. |
| No vibration despite received messages | Debug mode, zero amplitudes, wrong channel mapping, muted output, or hardware wiring. | Check env file, backend logs, and send a known low-amplitude pattern. |
| Dropouts with two PCBs | USB bandwidth or power problem. | Use a powered multi-TT USB hub and reduce other USB load. |
| Port conflict with `uwb_app` | `uwb-server` also uses HTTP port `8000` if run on the same host. | Run on separate hosts or deliberately change one service. |

## Known Limitations

- Older React components mostly target only WebSocket port `8000`.
- Some older React experiment components are hard-coded for 6 actuators while backend env files configure 8.
- `server.py` trusts incoming JSON shape and does not clamp amplitude values.
- Runtime state and command history are in memory only.
- `environment.yml` is not portable because it includes a hard-coded macOS prefix.
- `PhaseBasedMotion.py` is offline experimental code and is not part of the runtime pipeline.
- No production frontend service is provided in this repository.

## Inherited And Project-Specific Work

This repository is a fork of `samchin/haptic-hearing-website`.

Inherited or experiment-oriented work includes the Create React App frontend, psychophysics experiment routes, collected data, R analysis scripts, and the placeholder test.

Project-specific runtime/deployment work includes the dual-PCB backend configuration, systemd units, ALSA naming rule, and support for HaptiStage/Sound2Haptic-style WebSocket amplitude output.

## Related Repositories

| Repository | Relationship |
|---|---|
| `https://github.com/Dell-S/stage-support` | HaptiStage app that consumes UWB pose/sensor data, generates cues, and sends haptic frames to this backend. |
| `https://github.com/alinanila/uwb_app` | UWB localisation and sensor API consumed by HaptiStage. |
| `https://github.com/alinanila/uwb_wearable_pi` | Wearable IMU data source. |
| `https://github.com/samchin/haptic-hearing-website` | Upstream source for this fork. |

