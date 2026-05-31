# Haptic Hearing

A toolkit for driving wearable haptic actuators from the browser. A React web app captures and processes audio or sensor data, sends amplitude commands over WebSocket to a Python backend, which generates real-time multi-channel audio output to drive vibrotactile actuators.

---

## Installation

### Step 1: Clone the repository

```bash
git clone git@github.com:samchin/haptic-hearing-website.git
cd haptic-hearing-website
```

### Step 2: Create mamba environment

```bash
# Create mamba environment from environment.yml
# This will create an environment named 'haptichearing' in your default mamba envs location
mamba env create -f environment.yml -n haptichearing

# Activate the environment
mamba activate haptichearing
```

**Note:** If the above fails due to the hardcoded prefix in environment.yml, you can create the environment manually:

```bash
mamba create -n haptichearing python=3.13.1 -y
mamba activate haptichearing
mamba install --file <(grep -v "^prefix:" environment.yml | grep -v "^name:" | grep "^  -" | sed 's/^  - //') -c conda-forge -c anaconda -y
pip install audioop-lts==0.2.1 sounddevice==0.5.1
```

### Step 3: Install npm dependencies

```bash
npm install
```

### Step 4: Run the application

You'll need **two terminals**:

**Terminal 1 (Backend Server):**
```bash
mamba activate haptichearing
python server.py
```

**Terminal 2 (Frontend):**
```bash
npm run start
```

The app will be available at [http://localhost:3000](http://localhost:3000)

---

## Quick Copy-Paste (All-in-One)

```bash
git clone git@github.com:samchin/haptic-hearing-website.git
cd haptic-hearing-website

mamba env create -f environment.yml -n haptichearing
mamba activate haptichearing

npm install

# Then run in two terminals:
# Terminal 1: mamba activate haptichearing && python server.py
# Terminal 2: npm run start
```

---

## System Architecture

The system has two main parts: a **React frontend** that determines what haptic patterns to play, and a **Python backend** that turns those commands into real-time audio signals driving the actuators.

```
┌─────────────────────┐     WebSocket (JSON)     ┌─────────────────────┐
│                     │ ───────────────────────▶  │                     │
│   React Frontend    │                           │   Python Backend    │
│   (localhost:3000)  │                           │   (server.py)       │
│                     │  GET /data (Flask:5000)   │                     │
│                     │ ◀───────────────────────  │                     │
└─────────────────────┘                           └────────┬────────────┘
                                                           │
                                                   sounddevice OutputStream
                                                           │
                                                           ▼
                                                  ┌─────────────────────┐
                                                  │  Multi-channel      │
                                                  │  Audio Interface    │
                                                  │  (≥8 channels)     │
                                                  └────────┬────────────┘
                                                           │
                                                    Analog audio signals
                                                           │
                                                           ▼
                                                  ┌─────────────────────┐
                                                  │  Vibrotactile       │
                                                  │  Actuators          │
                                                  │  (necklace / ears)  │
                                                  └─────────────────────┘
```

### Data flow step by step

1. **Frontend → WebSocket → Backend.** The React app sends JSON messages over WebSocket containing per-channel amplitude values, a duration, and metadata:
   ```json
   {
     "amplitudes": [0.8, 0.0, 0.3, 0.0, 0.0, 0.5, 0.0, 0.0],
     "duration": 50,
     "timestamp": 1700000000000,
     "device": "necklace"
   }
   ```
   Each entry in `amplitudes` corresponds to one actuator channel (0.0 = off, 1.0 = full intensity). `duration` is how long to play this frame in milliseconds.

2. **Conversion to audio frames.** The backend converts each message into a block of audio samples: `duration_ms * SAMPLE_RATE / 1000` frames. Each frame is a sine wave at each channel's amplitude.

3. **Audio callback.** `sounddevice` runs a callback-based `OutputStream` that pulls from a queue of pending amplitude data and generates sine wave samples on demand. This keeps latency low — samples are synthesized in real time rather than pre-buffered.

4. **Hardware output.** The generated multi-channel audio is sent to the system's audio interface. The server automatically selects the first device with at least 8 output channels. Each actuator is wired to a separate output channel.

### Key configuration

- **`MAPPING` environment variable** — Maps logical actuator indices to physical output channels on the audio interface. This lets you use the same code with different hardware layouts (e.g., necklace vs. over-ear device) by just changing the mapping.
- **`blocksize=0`** — Lets the audio backend choose the optimal block size for lowest latency.
- **Flask endpoint (`GET /data` on port 5000)** — Serves logged amplitude data so the frontend can display visualizations of what's being sent to the actuators.

---

## Sending Data from Your Own Code

### Requirements

The only requirement for driving the actuators is that `server.py` is running — you do **not** need the React frontend. Just start the backend:

```bash
mamba activate haptichearing
python server.py
```

Any program that can open a WebSocket connection and send JSON can control the haptics.

### WebSocket message format

Connect to the WebSocket server (default: `ws://localhost:8765`) and send JSON messages with this structure:

```json
{
  "amplitudes": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "duration": 50,
  "timestamp": 1700000000000,
  "device": "necklace"
}
```

| Field        | Type       | Description                                                                 |
|------------- |----------- |---------------------------------------------------------------------------- |
| `amplitudes` | `float[]`  | Per-channel amplitude values, 0.0 (off) to 1.0 (max). Array length should match the number of actuator channels. |
| `duration`   | `int`      | How long to play this frame, in milliseconds.                              |
| `timestamp`  | `int`      | Unix timestamp in milliseconds (used for logging).                         |
| `device`     | `string`   | Device identifier, e.g. `"necklace"` or `"overear"`. Used for channel mapping. |

### Python example

```python
import asyncio
import json
import websockets

async def send_haptics():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as ws:

        # Buzz actuator 0 at full intensity for 200ms
        await ws.send(json.dumps({
            "amplitudes": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "duration": 200,
            "timestamp": 0,
            "device": "necklace"
        }))

        # Brief pause, then buzz actuators 0 and 5 together
        await asyncio.sleep(0.25)
        await ws.send(json.dumps({
            "amplitudes": [0.6, 0.0, 0.0, 0.0, 0.0, 0.6, 0.0, 0.0],
            "duration": 200,
            "timestamp": 0,
            "device": "necklace"
        }))

asyncio.run(send_haptics())
```

---

## Hardware Setup

The server expects a multi-channel audio interface with at least 8 output channels. On startup, it scans available audio devices and selects the first one that meets this requirement. Each output channel drives one vibrotactile actuator.

To check which device the server selects, look at the console output when `server.py` starts. If you need to use a different device or channel layout, set the `MAPPING` environment variable before starting the server.