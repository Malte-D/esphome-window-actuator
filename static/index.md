# About

ESPHome Tilt Window Opener motorises an ordinary tilt-and-turn window with two 3D-printed units,
two 12 V servos (DSSERVO DS51150) and an ESP8266. In Home Assistant the window appears as a `cover` that tilts
the window open and closes it again, including turning the handle.

<img src="https://raw.githubusercontent.com/Malte-D/esphome-tilt-window-opener/main/docs/media/demo.webp" width="432" alt="Animation of the tilt window opener" />

Parts list, printed parts and the assembly guide are in the
[GitHub repository](https://github.com/Malte-D/esphome-tilt-window-opener).

# Installation

Connect the Wemos D1 mini via USB and click the button below to install the pre-built firmware
directly from the browser (Chrome or Edge). After flashing, enter your Wi-Fi credentials; Home
Assistant will then discover the device. Calibrate the servo positions as described in the
[README](https://github.com/Malte-D/esphome-tilt-window-opener#calibration).

<esp-web-install-button manifest="./manifest.json"></esp-web-install-button>

<script type="module" src="https://unpkg.com/esp-web-tools@9/dist/web/install-button.js?module"></script>
