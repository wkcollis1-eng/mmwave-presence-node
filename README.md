<div align="center">

# mmWave Presence Lighting Node

**24 GHz Radar Presence Sensing for Room Lighting**

[![Hardware: CERN-OHL-S v2](https://img.shields.io/badge/Hardware-CERN--OHL--S%20v2-orange.svg)](LICENSE-HARDWARE)
[![Code: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE-CODE)
[![Docs: CC BY 4.0](https://img.shields.io/badge/Docs-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![PCB](https://img.shields.io/badge/PCB-44%20%C3%97%2033%20mm-blueviolet.svg)](#hardware)
[![Status](https://img.shields.io/badge/Status-Bench%20validated-yellow.svg)](#status)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-EA4AAA.svg?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/wkcollis1-eng)

</div>

A 24 GHz radar presence sensor that turns a room's lamps on when someone walks in
and off some minutes after they leave — including for a person sitting still, in
the dark, reading, whom a PIR sensor cannot see.

An **HLK-LD2410C** radar and an **Adafruit VEML7700** light sensor on a **Seeed XIAO
ESP32-C3** carrier board, running **ESPHome**, with the control logic in **Home
Assistant**.

![Board, top](hardware/mmWave%20Presence%20Lighting%20Node_TOP.png)

---

## The problem this is built for

> It is 23:00. The family room is dark and empty. A person walks in and sits down
> to read. The light comes on within one second, stays on for the next ninety
> minutes while they barely move, and goes off some minutes after they leave.
> Nobody touches a switch. Nobody is available to fix anything.

That is the acceptance test, not "99.9% uptime". A node that is powered and online
but drops the still-target at minute forty has failed the moment of demand — and so
has one that takes three seconds to notice someone walked in. The reasoning behind
every threshold, and the measurements that set them, are in
**[docs/mmwave-presence-node-design.md](docs/mmwave-presence-node-design.md)**.

## Status

| | |
|---|---|
| Design document | **Rev 1.6**, September 2026 |
| PCB | **Fabricated and populated.** 44.0 × 33.0 mm, 2-layer, three built |
| Bench validation | First session against real hardware **2026-09-07** — seven corrections and one retraction folded back into Rev 1.6 |
| Firmware / HA config | **Rev 0.1 drafts.** The office and family node configs compile; the package and dashboards are not yet running against a live Home Assistant |
| Deployment | Not yet mounted in either room |

The most consequential open question is recorded honestly in the design document
§0: **the 5.6 m detection target and the gate-2 (7.4 ft) cap needed to reject a
person in the next room cannot both hold**, and which of the two is wrong has not
been decided.

## Repository layout

```
docs/          Design document, draft notes, the LD2410C documentation review,
               and the Hi-Link / Adafruit primary sources they cite
hardware/      KiCad 10 board, 3D models, gerbers, enclosure DXF, BOM
esphome/       Node firmware — common config plus per-node overlays
packages/      Home Assistant package: the control logic and its helpers
dashboards/    Home Assistant views for commissioning and monitoring
scripts/       Calibration and config-checking tools
```

`esphome/`, `packages/`, `dashboards/` and `scripts/` deliberately mirror the
layout under Home Assistant's `/config`, so a path named in the notes means the
same thing here and on the target.

## Hardware

| | |
|---|---|
| Board | 44.0 × 33.0 mm, 2-layer, 1 oz copper, 1.6 mm FR4 |
| Front copper | Pads and vias only, no traces — unbroken ground plane under the radar |
| Back copper | All routing. 1 mm power, 0.25 mm signal, 0.2 mm clearance |
| Mounting | 3 × M3 NPTH; H2 and H3 sit under U2's courtyard by design — use nylon fasteners |
| Vias | 67 total, 16 under the module, largest gap 5.39 mm (below λg = 5.96 mm) |

**1 oz / 1.6 mm, not 2 oz / 0.8 mm.** At 24.125 GHz the skin depth is 0.425 µm, so
1 oz is already 82 skin depths and 2 oz buys nothing electrically. 0.8 mm has 1/8
the flexural rigidity, which is the wrong direction for a vertically mounted board
carrying a cantilevered radar where flex changes the antenna-to-window distance.

### Radar interconnect

Module pin order, printed on the antenna face: **TX RX OUT GND VCC**.

| LD2410C | Signal | Direction | XIAO | GPIO |
|---|---|---|---|---|
| 1 | UART_Tx | module → ESP | D3 | GPIO5 |
| 2 | UART_Rx | ESP → module | D2 | GPIO4 |
| 3 | OUT | module → ESP | D10 | GPIO10 (via R1) |
| 4 | GND | — | GND | — |
| 5 | VCC | 5 V in | **VBUS**, not 3V3 | — |

> **Identify every pin by its silkscreen label, never by position or number.**
> VCC and TX sit at opposite ends of a five-pin header, so counting from the wrong
> end puts 5 V on TX. That is the one wiring error on this module that destroys
> something.

### PH1 — light sensor header

| pad | label | XIAO | GPIO |
|---|---|---|---|
| 1 | 3V3 (RED) | 3V3 | — |
| 2 | GND (BLACK) | GND | — |
| 3 | SCL (YELLOW) | D5 | GPIO7 |
| 4 | SDA (BLUE) | D4 | GPIO6 |

The colours match the Qwiic/STEMMA QT convention. **The pin order deliberately does
not** — it was chosen for cleaner routing, and the silkscreen colour labels are the
interface instead.

> ### Build constraint: only a flying-lead QT cable works
>
> Adafruit **4397** terminates in four independent female sockets, so each wire is
> placed by colour. **A molded 4-pin housing cable connects power backwards and
> destroys the sensor.** The board tells you the colours but not why.

**Cut the VEML7700's power-LED jumper before the sensor goes near the enclosure.**
The Adafruit 4162 carries a green power LED on the same face as the photodiode.
This is a sealed box: an ambient-light sensor locked in the dark with its own light
source is partly measuring that source, and because the offset is constant it
presents as a calibration rather than a fault.

**The light sensor is off-board on a 150 mm cable, by design.** On-carrier it sat
3.41 mm from the module edge — a near-field problem — and it could not be aimed
independently of the radar.

## Working on the board

Open `hardware/mmWave Presence Lighting Node.kicad_pro` in **KiCad 10**. All in-repo
3D models resolve through `${KIPRJMOD}/3d/`, so a fresh clone renders the full
assembly with no path fixing.

Two things to know before you file a bug against the board:

1. **There is no schematic.** The project is board-only, so KiCad cannot run
   connectivity or clearance DRC against a netlist — every error across seven
   revisions was found by reading coordinates. Building the schematic is open item
   §9.5 and is the one gate still running on human attention.
2. **`kicad-cli pcb drc` reports 16 violations, and that is the expected baseline** —
   3 errors, 13 warnings, 0 unconnected items. **Compare against this baseline
   rather than expecting zero.** It breaks down as:

   | n | severity | rule | why it is accepted |
   |---|---|---|---|
   | 2 | error | `courtyards_overlap` | H2 and H3 sit under U2's courtyard **by design** — see §3.1 and the nylon-fastener note in §3.9 |
   | 1 | error | `npth_inside_courtyard` | same cause: a mounting hole inside the module's courtyard |
   | 4 | warning | `silk_over_copper` | cosmetic, reviewed |
   | 2 | warning | `silk_edge_clearance` | cosmetic, reviewed |
   | 6 | warning | `lib_footprint_mismatch` | stock footprints deliberately modified in place (C1 relocated for U.FL clearance, 3D models attached) |
   | 1 | warning | `lib_footprint_issues` | U2 — its footprint is stored inline in the board with no library behind it |

## Third-party assets

Full detail, including the terms that apply to each, is in
**[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**. These files are *not*
covered by this repository's own licences.

> **One file is non-commercial.** The LD2410C radar mesh
> (`hardware/3d/LD2410C mmWave Sensor.step` and its snapshot directory) is
> CC BY-NC 4.0. It is a 3D viewer mesh only — it is not in the gerbers, so it
> does not restrict manufacturing this board. For commercial use, delete those
> paths and render U2 with the Hi-Link model instead.

| Asset | Origin | Note |
|---|---|---|
| `hardware/3d/LD2410C mmWave Sensor.step` | Ben Cooney, via [GrabCAD](https://grabcad.com/library/ld2410c-mmwave-sensor-1) | **CC BY-NC 4.0** — non-commercial; licence image ships in `ld2410c-mmwave-sensor-1.snapshot.2/` |
| `hardware/3d/HLK-LD2410C-3D图/` | Hi-Link | Manufacturer 3D model |
| `hardware/3d/Adafruit VEML7700.zip` | SnapMagic | Part models remain SnapMagic's intellectual property |
| `docs/LD2410C Docs/*.pdf` | Hi-Link, Adafruit | Datasheet, serial protocol V1.07, VEML7700 guide |
| `hardware/3d/Seeed-Studio-XIAO-ESP32-C3.step` | Seeed Studio | |

Where the Hi-Link datasheet and the serial protocol document disagree, the protocol
document wins: it is two years newer and it documents the commands the module obeys.

## Credentials

Every credential in this repository resolves through ESPHome `!secret`, and the
`secrets.yaml` those resolve against lives in the Home Assistant config, **not
here**. Git history has been scanned and contains no plaintext SSID, PSK, API
encryption key or OTA password in any commit.

---

## License

Three licences, because this repository holds three different kinds of work:

| Content | Paths | Licence |
|---|---|---|
| Hardware design | `hardware/` | [CERN-OHL-S v2](LICENSE-HARDWARE) |
| Code | `esphome/`, `packages/`, `dashboards/`, `scripts/` | [MIT](LICENSE-CODE) |
| Documentation | `docs/`, this README | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

See **[LICENSE](LICENSE)** for the full breakdown and attribution examples, and
**[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)** for the vendor files that
none of the above covers.

CERN-OHL-S is strongly reciprocal: build the board, sell it, modify it — but if
you convey a modified design or a product made from it, the modified source has
to be available under the same terms.

```
Copyright (C) 2026 William K. Collis

This source describes Open Hardware and is licensed under the CERN-OHL-S v2.

You may redistribute and modify this source and make products using it under
the terms of the CERN-OHL-S v2 (https://ohwr.org/cern_ohl_s_v2.txt).

This source is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY, INCLUDING
OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A PARTICULAR PURPOSE.
Please see the CERN-OHL-S v2 for applicable conditions.

Source location: https://github.com/wkcollis1-eng/mmwave-presence-node
```

---

## 💝 Support This Project

[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-%E2%9D%A4-EA4AAA?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/wkcollis1-eng)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/wkcollis)

If this design document or the commissioning method saved you time on your own
presence-sensing build, sponsorship funds continued instrumentation, hardware
and documentation.
