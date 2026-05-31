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

load_dotenv("./.env")

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
# Retrieve environment variables
DEBUG = False
FREQ = int(os.getenv("REACT_APP_FREQ", 200))
SAMPLE_RATE = int(os.getenv("REACT_APP_SAMPLE_RATE", 2000))
NUMBER_ACTUATORS = int(os.getenv("REACT_APP_NUMBER_ACTUATOR", 0))

WINDOW_SIZE = int(os.getenv("REACT_APP_WINDOW_SAVING", 10000))

# Parse MAPPING as a dictionary
mapping_str = os.getenv("REACT_APP_MAPPING", "0,1,2,3,4,5,6,7")
# # mapping_str = ("1,2,3,4.5,6")
# # mapping_str = ("2,3,4,5,6,7")
#mapping_str = ("2,3,5,7,6,4") # OVER THE EAR

MAPPING = {i: int(v) for i, v in enumerate(mapping_str.split(","))}

df = pd.DataFrame({
})
# Global variable for amplitudes
amplitude_array = []
phase = 0.0           # Phase accumulator for the sine wave
phase_increment = (2 * np.pi * FREQ) / SAMPLE_RATE

if not DEBUG:
    import sounddevice as sd

    def connect():
        # Attempt to find a device with at least 8 output channels
        device_id = None
        for i, device in enumerate(sd.query_devices()):
            if device['max_output_channels'] >= 8:
            # if device['max_output_channels'] == 2: 
                device_id = i
                break
        if device_id is None:
            raise RuntimeError("No suitable output device found with at least 16 channels.")

        sd.default.device = (None, device_id)
        print(f"Selected audio output device with output channels: {sd.query_devices(device_id)['max_output_channels']}")
        print(sd.default.device)
        

import numpy as np

def audio_callback(outdata, frames, time, status):
    """
    Audio callback function for sounddevice to generate sine waves with varying amplitudes per channel.
    
    Args:
        outdata (numpy.ndarray): Output buffer to fill with audio data
        frames (int): Number of frames to generate
        time (CData): Time information (from sounddevice)
        status (CallbackFlags): Status flags
        
    Global variables used:
        phase (int): Current phase of the sine wave
        amplitude_array (list): List of [duration, amp_ch1, amp_ch2, ...] arrays
        MAPPING (list): Channel mapping for output
    """
    global phase, amplitude_array
    
    if status:
        print("Stream status:", status)
    
    # Initialize output buffer with zeros
    outdata.fill(0)
    
    # Keep track of how many frames we've processed
    frames_processed = 0
    
    while len(amplitude_array) > 0 and frames_processed < frames:
        # Get current amplitude array data
        duration = amplitude_array[0][0]
        remaining_frames = frames - frames_processed
        this_frames = min(duration, remaining_frames)
        
        # Generate time indices for this block
        t = (np.arange(this_frames) + phase) * phase_increment
        phase += this_frames
        
        # Generate base sine wave
        sine_wave = np.sin(t)
        
        # Apply amplitudes to each channel
        channel_data = amplitude_array[0][1:]
        for i, amplitude in enumerate(channel_data):
            if i < len(MAPPING):
                outdata[frames_processed:frames_processed + this_frames, MAPPING[i]] = sine_wave * amplitude
        
        # Update counters and check if we're done with current amplitude array
        frames_processed += this_frames
        amplitude_array[0][0] -= this_frames
        
        if amplitude_array[0][0] <= 0:
            amplitude_array.pop(0)
            
    return


async def handler(websocket):
    print("Client connected.")
    global amplitude_array, df

    amplitude_array = []
    duration_array = [0] * NUMBER_ACTUATORS


    async for message in websocket:
        data = json.loads(message)
        print("Received data:", data)
        # Update the global amplitude array
    
        duration = data["duration"]*SAMPLE_RATE/1000
        duration = int(duration)
        amplitude_array.append([duration] + data["amplitudes"])
        timestamp = data["timestamp"]
        device_type = data["device"]

        # Update the global dataframe
        new_data = pd.DataFrame([{
            "device": device_type,
            "timestamp": timestamp,
            "amplitudes": data["amplitudes"],
            "duration": data["duration"],
        }])

        df = pd.concat([df, new_data], ignore_index=True)
        df = df[df["timestamp"] > timestamp - WINDOW_SIZE]


async def main():
    #launch a new thread for the HTTP server
    print("Starting Flask server on port 5000")
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000)).start()

    async with websockets.serve(handler, "0.0.0.0", 8000):
        print("WebSocket server listening on ws://0.0.0.0:8000")
        await asyncio.Future()  # run forever

app = flask.Flask(__name__)
CORS(app)

@app.route('/data', methods=['GET'])
def data():
    global df
    return df.to_json(orient='records')


if __name__ == "__main__": 
    if len(MAPPING) != NUMBER_ACTUATORS:
        raise ValueError("Number of actuators in MAPPING does not match NUMBER_ACTUATORS")

    if not DEBUG:
        connect()  
        print("Running in audio output mode.")
        with sd.OutputStream(samplerate=SAMPLE_RATE,
                            channels=sd.query_devices(sd.default.device[1])['max_output_channels'],
                            callback=audio_callback, blocksize=0):
            asyncio.run(main())
    else:
        print("Running in debug mode. No audio output will be generated.")
        asyncio.run(main())
