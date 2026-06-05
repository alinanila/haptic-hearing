#!/usr/bin/env bash
set -euo pipefail

# Install the two-belt haptic servers as systemd services (auto-start on boot)
# plus the ALSA card-naming udev rule. Run on the Raspberry Pi:
#
#   sudo ./systemd/install.sh
#
# Override the Python interpreter if auto-detection fails:
#   sudo HAPTIC_PYTHON=/path/to/haptichearing/bin/python ./systemd/install.sh

SERVICE_DIR="/etc/systemd/system"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
HOME_DIR="$(eval echo "~${RUN_USER}")"

# Find the haptichearing env's python (handles nested conda envs/ paths too).
PYTHON="${HAPTIC_PYTHON:-$(find "$HOME_DIR" -maxdepth 7 -path '*/haptichearing/bin/python' 2>/dev/null | head -1)}"
if [[ -z "$PYTHON" ]]; then
  echo "Could not find the haptichearing env python." >&2
  echo "Re-run with: sudo HAPTIC_PYTHON=/path/to/haptichearing/bin/python ./systemd/install.sh" >&2
  exit 1
fi

echo "user=$RUN_USER  repo=$REPO_DIR  python=$PYTHON"

for n in 1 2; do
  echo "installing haptic-pcb${n}.service ..."
  sed -e "s|__USER__|${RUN_USER}|g" \
      -e "s|__REPO_DIR__|${REPO_DIR}|g" \
      -e "s|__PYTHON__|${PYTHON}|g" \
      "$REPO_DIR/systemd/haptic-pcb${n}.service" \
    | sudo tee "$SERVICE_DIR/haptic-pcb${n}.service" >/dev/null
done

echo "installing ALSA card-naming udev rule ..."
echo "  >> REVIEW the USB ports in systemd/89-alsa-usb-order.rules for your rig first! <<"
sudo cp "$REPO_DIR/systemd/89-alsa-usb-order.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules

sudo systemctl daemon-reload
sudo systemctl enable --now haptic-pcb1 haptic-pcb2

echo
echo "done. verify:"
echo "  cat /proc/asound/cards                    # expect HapticPCB1 + HapticPCB2"
echo "  systemctl status haptic-pcb1 haptic-pcb2"
echo "  ss -ltn | grep -E ':8000|:8001'"
echo "(reboot once so the udev names apply at boot)"
