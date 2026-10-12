[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/QuadNL/casazapp-tv-homeassistant.svg)](https://github.com/QuadNL/casazapp-tv-homeassistant/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Ko-Fi][ko_fi_shield]][ko_fi]

<img width="600" height="auto" alt="casazapp-tv-logo-light" src="https://github.com/user-attachments/assets/8d88dc9f-e830-4ae2-a31e-693001ff49bc" />

# CasaZapp TV

The best TV player, in your home just got even better.

For all information and instructions visit https://casazapp.tv.

CasaZapp TV gives you the best set-topbox experience you want. It runs on docker, so your
channel lists, favourites, recordings and watch history stay with you in sync across all your devices.

There are two parts:

- **The server**, a Docker image. It keeps your playlists, fetches the programme guide, records,
  and serves the web app you use in a browser or install on your phone as a PWA.
- **The Android app**, for Google TV, Chromecast with Google TV, Android TV boxes and Android
  phones. It pairs with your server, or works on its own with a playlist on the device.

This repository only contains the Home Assistant integration for the CasaZapp TV server.

## The integration

Brings your CasaZapp TV server into Home Assistant:

- **See what plays:** a media player per device that watches, with the channel, the programme
  and its progress, and a Now playing sensor.
- **Recordings:** what records now and next, how many are planned, and the space left on the
  recordings disk.
- **Your providers:** when a subscription ends, how many connections are in use, the last sync.
- **Control from automations:** plan, stop and remove recordings, and stop a stream.
- **Play on your speakers and TVs:** radio, channels and recordings from the media browser, on
  any speaker or player Home Assistant knows.
- **Server updates:** an update entity tells you when a newer CasaZapp TV server is out.

You need a CasaZapp TV server 0.5.7 or newer, Home Assistant 2026.10 or newer, and an API key from
the server (Settings → Account → API keys). The recordings disk, the providers and server updates
show with a key of a profile that looks after the server.

## Installing via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=QuadNL&repository=CasaZapp-TV-homeassistant&category=integration)

or

1. Go to HACS → ⋮ (top right) → Custom repositories.
1. Add this repository (`https://github.com/QuadNL/CasaZapp-TV-homeassistant`), type **Integration**.
1. Search for **CasaZapp TV** and download it.
1. Restart Home Assistant.
1. Go to Settings → Devices & services.
1. Add the **CasaZapp TV** integration, with your server's address and the API key.

On the same network Home Assistant may find the server by itself; then only the key is asked.

## Installing by hand

1. Download `casazapp_tv.zip` from the
   [latest release](https://github.com/QuadNL/CasaZapp-TV-homeassistant/releases/latest).
1. Make the folder `/config/custom_components/casazapp_tv/` and unpack the zip into it.
1. Restart Home Assistant, then add the integration as above.

## More

- The full guide: [casazapp.tv/docs/home-assistant](https://casazapp.tv/docs/home-assistant.html)
- The API for your own scripts: [casazapp.tv/api](https://casazapp.tv/api)
- Questions and problems: [issues](https://github.com/QuadNL/CasaZapp-TV-release/issues)

## Disclaimer

CasaZapp TV is a generic media player application designed to play user-provided content. CasaZapp TV does not provide, distribute, store, or own any media, streams, channels, or playlists.

Users must supply their own content via legal streaming links, URLs, or playlists. CasaZapp TV is not affiliated with any content provider, third-party IPTV service, or broadcaster, and does not endorse or condone the streaming of copyrighted material without proper authorization.

The user assumes full responsibility for all content played through the CasaZapp TV application.

## Support the project

If you enjoy using CasaZapp TV, please consider to buy me a coffee. 

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/U2W120MCVZ)

[ko_fi_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Ko-Fi&color=F16061&logo=ko-fi&logoColor=white
[ko_fi]: https://ko-fi.com/U2W120MCVZ
