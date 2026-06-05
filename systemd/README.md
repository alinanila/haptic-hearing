# Dual-belt deployment (Raspberry Pi)

Runs **two `server.py` instances** — one per haptic PCB — as systemd services that
auto-start on boot and restart on crash:

| Belt | PCB  | Role     | env file     | WS / Flask |
|------|------|----------|--------------|------------|
| 1    | PCB1 | lower    | `.env.pcb1`  | 8000 / 5000 |
| 2    | PCB2 | upper    | `.env.pcb2`  | 8001 / 5001 |

## Hardware requirement

The two PCBs are USB sound cards. Running both 8-channel streams at once needs a
**multi-TT USB hub** (e.g. any USB 3.0 hub — check with
`lsusb -v -d <id> | grep -i bDeviceProtocol` → want `Multiple TTs`). A single-TT
hub (most Pi-Zero USB-hub pHATs, chip `1a40:0101`) can only drive one belt at a
time. A *powered* hub is recommended when both belts drive motors hard.

## Install

```bash
sudo ./systemd/install.sh
```

This fills in your user / repo path / Python interpreter, installs both services,
installs the ALSA-naming udev rule, and enables them.

**Before relying on it, set the USB ports** in
[`89-alsa-usb-order.rules`](89-alsa-usb-order.rules) — the cards have no serial,
so they're named by which port they're in. See the comments in that file
(`cat /proc/asound/cards` to find your ports), then reboot.

## Manage

```bash
sudo systemctl restart haptic-pcb1 haptic-pcb2
systemctl status  haptic-pcb1 haptic-pcb2
journalctl -u haptic-pcb1 -f
```

## Undo

```bash
sudo systemctl disable --now haptic-pcb1 haptic-pcb2
sudo rm /etc/systemd/system/haptic-pcb{1,2}.service && sudo systemctl daemon-reload
sudo rm /etc/udev/rules.d/89-alsa-usb-order.rules
```

## Related: IMU service

The BNO085 IMU runs via `uwb_app`'s `pose_server` (the `uwb-server` service) on the
same Pi. Two fixes there: `sensor_listener` now receives the wearable over **UDP
:5570** (was ZMQ), and `pose_server`'s HTTP moved to **:8080** (`POSE_SERVER_PORT`)
so it doesn't clash with the haptic belt on :8000. The wearable's `SERVER_IP` must
point at this Pi. (Those changes live in the `uwb_app` repo.)
