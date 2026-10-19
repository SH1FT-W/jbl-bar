<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme-title-dark.png" />
  <img src="docs/images/readme-title-light.png" alt="JBL Bar: Your soundbar, fully local. A soundbar with its subwoofer below a TV in warm evening light (AI-generated scene)." />
</picture>

<p>Local control for JBL soundbars with JBL One in Home Assistant.<br/>
Fast, complete, no cloud.</p>

[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FSH1FT-W%2Fjbl-bar%2Fmain%2Fcustom_components%2Fjbl_bar%2Fmanifest.json&query=%24.version&label=version&style=flat-square&color=FF6A00&labelColor=111111)](https://github.com/SH1FT-W/jbl-bar/releases/latest)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.9%2B-FF6A00?style=flat-square&labelColor=111111&logo=homeassistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-custom%20repository-FF6A00?style=flat-square&labelColor=111111)](https://hacs.xyz)
[![IoT class](https://img.shields.io/badge/iot-local%20polling-FF6A00?style=flat-square&labelColor=111111)](https://developers.home-assistant.io/docs/creating_integration_manifest/#iot-class)
[![Quality scale](https://img.shields.io/badge/quality%20scale-platinum%20(self--assessed)-FF6A00?style=flat-square&labelColor=111111)](custom_components/jbl_bar/quality_scale.yaml)
[![License](https://img.shields.io/badge/license-Apache%202.0-FF6A00?style=flat-square&labelColor=111111)](LICENSE)

<p><a href="https://sh1ft-w.github.io/jbl-bar"><b>Website</b></a> &nbsp;·&nbsp; <a href="#new">New</a> &nbsp;·&nbsp; <a href="#features">Features</a> &nbsp;·&nbsp; <a href="#entities">Entities</a> &nbsp;·&nbsp; <a href="#installation">Install</a> &nbsp;·&nbsp; <a href="#migration-from-jbl_integration">Migration</a> &nbsp;·&nbsp; <a href="#troubleshooting">Troubleshooting</a> &nbsp;·&nbsp; <a href="CHANGELOG.md">Changelog</a></p>

</div>

<br/>

JBL Bar controls soundbars of the **JBL Bar series** (Bar 300, 500, 700, 800, 1000, 1300 and the MK2 models) over the same local interface the JBL One app uses. Every command was read from the app itself and tried out, one by one, on a **Bar 1000** (firmware 25.52, JBL One 3.0).

It replaces the HACS integration `jbl_integration` and **keeps its entity IDs**, so automations, dashboards and energy sensors keep working without a single change.

> [!NOTE]
> JBL Bar is an independent project. It is not affiliated with, endorsed by or sponsored by Harman International, JBL or Linkplay. JBL is a trademark of Harman International Industries, Incorporated.

<br/>

<a id="new"></a>
<sub><b>JUST ARRIVED</b></sub>
## Sturdier, quieter, and counted by the calendar.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme-cards-new-dark.png" />
  <img src="docs/images/readme-cards-new-light.png" alt="Quiet in standby (26.10.2): while the bar sleeps, Home Assistant only asks whether it is on, switch it on and playback and settings are read right away. Odd lists, no error (26.10.2): unknown entries in the bar's EQ preset or rear speaker lists are skipped, the valid ones stay, a missing EQ band gives a clear message instead of a crash. Host names work (26.10.2): set up with a host name instead of an IP address, the audio format events now get through too. Calendar versions (26.10.1): year, month and the release of that month, 26.10.2 is the second release of October 2026." />
</picture>

Every change, release by release, in the [changelog](CHANGELOG.md).

<a id="features"></a>
## Features

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme-cards-features-dark.png" />
  <img src="docs/images/readme-cards-features-light.png" alt="A real media player: on and off, volume, mute, source (TV, HDMI, Bluetooth), play and pause, next and previous, title, artist and cover art while streaming. True power state: read straight from the bar instead of guessed from what is playing. 7-band EQ and presets: JBL SIGNATURE, VOCAL, ENERGETIC, CHILL and your own preset, every band from 125 Hz to 8 kHz adjustable on its own. Sound switches: night mode, Smart mode, PureVoice and feedback tones. Audio sync and sleep timer: delay the sound by up to 250 ms, switch off after 15 minutes up to 2 hours. Rear speakers: battery, charging, docked and connected, each rear as its own device. Dolby Atmos and audio format: whether Atmos is coming in and in which format, pushed instantly by a UPnP event. Adapts and starts instantly: features a model does not know are never created, the event subscription runs in the background." />
</picture>

<a id="entities"></a>
## Entities

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme-cards-entities-dark.png" />
  <img src="docs/images/readme-cards-entities-light.png" alt="Media player: media_player.jbl_bar_1000 is the main control. Switches: power, nightmode, smart_mode, pure_voice and feedback_tone. Volume and EQ bands: volume from 0 to 100 percent in 3 percent steps, 125hz to 8000hz from -6 to +6 dB (125 Hz down to -9 dB), changing a band creates your own preset. Audio sync and selects: audio_sync from 0 to 250 ms, eq_preset and sleep_timer with the remaining time as an attribute. Sensors: source, audio_format, atmos_level, left_battery and right_battery. Binary sensors and buttons: atmos_active, left and right charging, docked and online; buttons atmos, bass, moment, calibration and rear." />
</picture>

All IDs start with the device name, for example `switch.jbl_bar_1000_nightmode`, and are the same as in `jbl_integration`. Entity names are available in English and German.

<details>
<summary>All entity IDs (for a bar named "JBL Bar 1000")</summary>

```
media_player.jbl_bar_1000
switch.jbl_bar_1000_power            switch.jbl_bar_1000_nightmode
switch.jbl_bar_1000_smart_mode       switch.jbl_bar_1000_pure_voice
switch.jbl_bar_1000_feedback_tone
number.jbl_bar_1000_volume           number.jbl_bar_1000_audio_sync
number.jbl_bar_1000_125hz … number.jbl_bar_1000_8000hz
select.jbl_bar_1000_eq_preset        select.jbl_bar_1000_sleep_timer
sensor.jbl_bar_1000_source           sensor.jbl_bar_1000_audio_format
sensor.jbl_bar_1000_atmos_level
sensor.jbl_bar_1000_left_battery     sensor.jbl_bar_1000_right_battery
binary_sensor.jbl_bar_1000_atmos_active
binary_sensor.jbl_bar_1000_left_charging   binary_sensor.jbl_bar_1000_right_charging
binary_sensor.jbl_bar_1000_left_docked     binary_sensor.jbl_bar_1000_right_docked
binary_sensor.jbl_bar_1000_left_online     binary_sensor.jbl_bar_1000_right_online
button.jbl_bar_1000_atmos            button.jbl_bar_1000_bass
button.jbl_bar_1000_moment           button.jbl_bar_1000_calibration
button.jbl_bar_1000_rear
```

</details>

## Installation

### HACS (custom repository)

1. In HACS, open the three dots menu, choose **Custom repositories** and add `https://github.com/SH1FT-W/jbl-bar` with the type **Integration**.
2. Search for **JBL Bar**, download it and restart Home Assistant.

### Manual

1. Download the [latest release](https://github.com/SH1FT-W/jbl-bar/releases/latest).
2. Copy the folder `custom_components/jbl_bar` into `/config/custom_components/` and restart Home Assistant.

Requires Home Assistant 2026.9 or newer.

## Setup

1. The bar is discovered automatically (**Settings > Devices & services > Discovered**). Otherwise choose **Add integration > JBL Bar** and enter its IP address.
2. If the bar gets a new IP address later, use **three dots > Reconfigure**.

> [!TIP]
> For the audio format the bar has to reach Home Assistant: in Home Assistant's network settings the internal URL should be an IP address (the default on most installations).

## Migration from `jbl_integration`

1. Delete the old integration and remove it in HACS. This frees its entity IDs.
2. Install JBL Bar and restart Home Assistant.
3. Add the bar. All previous IDs are back; new are the media player, audio sync, sleep timer, feedback tones, source and the Atmos sensors.

Only the raw values that were disabled by default (`play_medium`, `transport_state`, …) and the source and volume buttons are gone. The media player does that now.

## Good to know

- **Sleep timer** is only accepted while the bar is on. In standby the bar ignores it.
- **Rear volume** does not change while the rear speakers are docked to the bar, so there is no entity for it (yet).
- **Atmos level** can only be cycled with the button. The firmware has no way to set it directly.
- **Source HDMI** wakes the bar even when nothing is connected to the HDMI input.
- **Tested on the Bar 1000 only.** The other models of the series speak the same interface; features a model does not know are not created.
- **Polling every 10 seconds.** Changes made on the bar itself (remote control) therefore show up with up to 10 seconds delay; only the audio format arrives instantly as an event.

## Troubleshooting

- **All entities "unavailable".** The bar does not answer at its IP address. Check in your router whether it got a new one and enter it with **three dots > Reconfigure**. A single dropout (for example while going to standby) is bridged.
- **Audio format stays empty.** The bar cannot reach Home Assistant. Check the internal URL in the network settings (an IP address, not a host name) and whether a firewall blocks port 8123 from the bar's network.
- **Rear speakers missing.** They appear as soon as the bar reports them, also later on. Rears the bar no longer knows can be deleted on their device page.
- **Diagnostics:** **Settings > Devices & services > JBL Bar > three dots > Download diagnostics**. IP address, MAC address and serial number are left out.
- **Debug log:**

  ```yaml
  logger:
    logs:
      custom_components.jbl_bar: debug
  ```

When you open an [issue](https://github.com/SH1FT-W/jbl-bar/issues), please attach the diagnostics file.

## Removal

1. **Settings > Devices & services > JBL Bar > three dots > Delete** (for each bar). The event subscription unsubscribes from the bar on the way out.
2. Delete the folder `/config/custom_components/jbl_bar` (or remove the repository in HACS) and restart Home Assistant.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme-cards-how-dark.png" />
  <img src="docs/images/readme-cards-how-light.png" alt="HTTPS + certificate: state, settings, EQ and source through the bar's local API, every 10 seconds. UPnP / SOAP: title, cover, volume and mute through the bar's media renderer. UPnP events: the bar pushes the audio format to Home Assistant the moment it changes." />
</picture>

The integration polls the state every 10 seconds, the settings once a minute and right after every change. In standby it only asks for the power state.

The bar's local API only talks to clients that present the JBL One app's client certificate. The certificate in `custom_components/jbl_bar/certs/` comes from [MrBearPresident/JBL_Soundbar](https://github.com/MrBearPresident/JBL_Soundbar) (MIT License, Copyright (c) 2025 Jerre Latruwe); thanks for the groundwork. Protocol notes, including the firmware's pitfalls, are in [`CLAUDE.md`](CLAUDE.md) (German).

## Development

```bash
python -m pytest -q -p no:logging        # fake bar in tests/common.py, no real bar needed
uvx ruff check . && uvx ruff format --check .
uvx mypy@2.3.1 --python-executable <venv>/bin/python
python tools/pruefe-uebersetzungen.py    # strings.json against translations/*.json
```

Install the test requirements with `pip install -r requirements_test.txt`. The same checks run on GitHub Actions for every push and pull request, plus HACS validation and hassfest.

## License

[Apache License 2.0](LICENSE), Copyright 2026 SH1FT-W.

The client certificate in `custom_components/jbl_bar/certs/` is third-party material under the MIT License, see [`certs/LICENSE`](custom_components/jbl_bar/certs/LICENSE) and [`NOTICE`](NOTICE).
