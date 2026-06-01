import asyncio
import websockets
import json
import numpy as np
import pandas as pd
import flask
from flask_cors import CORS
import threading
from dotenv import load_dotenv
import os
import logging
import sys
import threading as _threading

# Load env file passed as argument, or default .env
env_file = sys.argv[1] if len(sys.argv) > 1 else "./.env"
load_dotenv(env_file)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

DEBUG = os.getenv("REACT_APP_DEBUG", "false").lower() == "true"
FREQ = int(os.getenv("REACT_APP_FREQ", 200))
SAMPLE_RATE = int(os.getenv("REACT_APP_SAMPLE_RATE", 48000))
NUMBER_ACTUATORS = int(os.getenv("REACT_APP_NUMBER_ACTUATOR", 8))
WINDOW_SIZE = int(os.getenv("REACT_APP_WINDOW_SAVING", 10000))
WS_PORT = int(os.getenv("WS_PORT", 8000))
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
ALSA_DEVICE_NAME = os.getenv("ALSA_DEVICE_NAME", None)
ALSA_DEVICE_INDEX = int(os.getenv("ALSA_DEVICE_INDEX", 0))

mapping_str = os.getenv("REACT_APP_MAPPING", "0,1,2,3,4,5,6,7")
MAPPING = {i: int(v) for i, v in enumerate(mapping_str.split(","))}

df = pd.DataFrame({})
amplitude_array = []
phase = 0.0
phase_increment = (2 * np.pi * FREQ) / SAMPLE_RATE

if not DEBUG:
    import sounddevice as sd

    def connect():
        devices = sd.query_devices()

        if ALSA_DEVICE_NAME:
            # Map ALSA card name to device index via /proc/asound/cards
            device_id = None
            try:
                with open("/proc/asound/cards", "r") as f:
                    cards = f.read()
                for line in cards.splitlines():
                    if ALSA_DEVICE_NAME in line:
                        # Line format: " 0 [HapticPCB1      ]: ..."
                        card_index = int(line.strip().split()[0])
                        # Find matching sounddevice entry for hw:<card_index>
                        hw_str = f"hw:{card_index},"
                        for i, device in enumerate(devices):
                            if hw_str in device['name']:
                                device_id = i
                                break
                        break
            except Exception as e:
                print(f"Warning: could not read /proc/asound/cards: {e}")

            if device_id is None:
                available = "\n".join(
                    f"  [{i}] {d['name']}"
                    for i, d in enumerate(devices)
                )
                raise RuntimeError(
                    f"Device '{ALSA_DEVICE_NAME}' not found in "
                    f"/proc/asound/cards.\n"
                    f"Available sounddevice entries:\n{available}"
                )
        else:
            device_id = ALSA_DEVICE_INDEX

        device = devices[device_id]
        print(f"Selected device [{device_id}]: {device['name']}")
        print(f"Output channels: {device['max_output_channels']}")

        if device['max_output_channels'] < NUMBER_ACTUATORS:
            raise RuntimeError(
                f"Device '{device['name']}' only has "
                f"{device['max_output_channels']} output channels, "
                f"need {NUMBER_ACTUATORS}."
            )
        sd.default.device = (None, device_id)


import threading as _threading

_array_lock = _threading.Lock()

def audio_callback(outdata, frames, time, status):
    global phase, amplitude_array
    if status:
        print("Stream status:", status)
    outdata.fill(0)
    frames_processed = 0

    with _array_lock:
        while len(amplitude_array) > 0 and frames_processed < frames:
            duration = amplitude_array[0][0]
            remaining_frames = frames - frames_processed
            this_frames = min(duration, remaining_frames)
            t = (np.arange(this_frames) + phase) * phase_increment
            phase += this_frames
            sine_wave = np.sin(t)
            channel_data = amplitude_array[0][1:]
            for i, amplitude in enumerate(channel_data):
                if i < len(MAPPING):
                    outdata[frames_processed:frames_processed + this_frames,
                            MAPPING[i]] = sine_wave * amplitude
            frames_processed += this_frames
            amplitude_array[0][0] -= this_frames
            if amplitude_array[0][0] <= 0:
                amplitude_array.pop(0)


async def handler(websocket):
    print("Client connected.")
    global amplitude_array, phase, df

    # Reset state on new connection
    with _array_lock:
        amplitude_array = []
        phase = 0.0

    async for message in websocket:
        data = json.loads(message)
        print("Received data:", data)
        duration = int(data["duration"] * SAMPLE_RATE / 1000)

        with _array_lock:
            amplitude_array.append([duration] + data["amplitudes"])

        timestamp = data["timestamp"]
        device_type = data["device"]
        new_data = pd.DataFrame([{
            "device": device_type,
            "timestamp": timestamp,
            "amplitudes": data["amplitudes"],
            "duration": data["duration"],
        }])
        df = pd.concat([df, new_data], ignore_index=True)
        df = df[df["timestamp"] > timestamp - WINDOW_SIZE]


async def main():
    print(f"Starting Flask server on port {FLASK_PORT}")
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=FLASK_PORT)
    ).start()
    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        print(f"WebSocket server listening on ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()


app = flask.Flask(__name__)
CORS(app)

@app.route('/data', methods=['GET'])
def data():
    global df
    return df.to_json(orient='records')


if __name__ == "__main__":
    if len(MAPPING) != NUMBER_ACTUATORS:
        raise ValueError(
            "Number of actuators in MAPPING does not match NUMBER_ACTUATORS"
        )
    if not DEBUG:
        connect()
        print("Running in audio output mode.")
        with sd.OutputStream(samplerate=SAMPLE_RATE,
                            device=sd.default.device[1],
                            channels=NUMBER_ACTUATORS,
                            callback=audio_callback,
                            blocksize=0,
                            dtype='float32') as stream:
            print(f"Stream opened: {stream.channels}ch @ "
                  f"{stream.samplerate}Hz on device {ALSA_DEVICE_INDEX}")
            asyncio.run(main())
    else:
        print("Running in debug mode.")
        asyncio.run(main())