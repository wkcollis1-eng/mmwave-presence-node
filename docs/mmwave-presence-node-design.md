# mmWave Presence Lighting Node — Design Document

**Rev 1.6 — September 2026 — W. Collis**
Targets: office and family room, East Hampton CT

*Rev 1.5 → 1.6: **first bench session with real hardware — 2026-09-07.** Everything below marked as measured was taken off the rig, not reasoned from a datasheet. Seven corrections and one retraction.*

*__§5.0 step 0.3 is no longer a gate.__ `Radar firmware` was measured at **403 s** to populate. The MAC and `gate_resolution` arrive from the same deferred config read. The instruction "if it is blank, nothing else means anything — go back to the crossover" is therefore wrong for the first seven minutes of every boot, and following it literally would have someone tearing down correct wiring. `UART healthy` now keys on engineering-mode gate frames, which prove both directions of the UART in seconds, and the whole gate went from 6 min 43 s to 15 s.*

*__§5.0 step 0.4's pass criterion was unverifiable and is replaced.__ `switch.radar_bluetooth` read `off` while the module was demonstrably advertising and connected to the Hi-Link iPhone app, then read `on` after a reflash with the radio untouched. Two different answers about one unchanged radio: **it is not a readback.** Every "confirm" in the off→reboot→confirm→on→reboot→confirm→off round trip reads that switch, so as written the entire verification passes regardless of what the module did. The pass criterion is now external — the app can no longer discover the module.*

*__§5.0's open question on UART/BLE concurrency is closed: they coexist.__ Ten polls over 30 s with the app connected showed continuous distance updates and zero stale reads. That is what makes the app usable as the instrument step 0.4 now depends on.*

*__§4.2 gains a deferral rule, and it is not cosmetic.__ The light is sampled once at the empty→occupied edge and never re-evaluated while occupied. Consuming that edge with no reading therefore discards the only chance an occupancy has to decide. Measured: a node that booted into an occupied room consumed the edge before its light sensor had a value, never commanded the lamp, and could not revisit the decision until the room had been empty for a full idle timeout. **Production has the same race** — the VEML7700 polls at 10 s, and its idle timeout is 90 s (office) or 300 s (family room). The rule is now: no reading means stay EMPTY and retry, so the decision is deferred rather than discarded.*

*__Engineering mode is volatile and at least three things drop it.__ A threshold push (21 config-mode entries and exits), a `Radar restart` (module reboot), and any module power loss. `on_boot` covers only ESP boot. Measured 2026-09-07: after a push the photodiode and all 18 gate energies read `unknown` for 5 min 21 s with nothing reporting it. **This is a production defect, not a bench one** — `mmwave-node-common.yaml` fires `push_commissioned_state` at boot, so every production startup silently kills the gate telemetry §6.1 exists to sample.*

*__R9 is proven, and more strongly than expected.__ All 21 commissioned values were scrambled to distinct wrong numbers, the node rebooted, and the boot-time push restored **21/21** from the substitutions — a completely mis-configured radar rebuilt entirely from version control. The 21 writes complete in about two seconds. Gates 0 and 1 accepted the scrambled static values despite PR Table 7 marking them not settable, so the WRITE path reaches them even though the module ignores what it stores.*

*__RETRACTED — §3.6's 5.6 m acceptance target is incompatible with the gating this room needs.__ Three false lamp events were traced to a person in the bathroom next door, detected through the wall at 7.4–10.3 ft. Per-gate energies separate the cases completely (bathroom in gates 3–4, office entry in gates 0–2), but only by capping the move path at gate 2 — 7.4 ft. A 5.6 m detection requirement and a 3.75 m gate cannot both hold. **Which of the two is wrong is not yet decided and is the most consequential open item in this document.** Note also that every threshold in that analysis was taken with the module on a bench; none of it transfers to the final mounted geometry, and §5.9 is redone from scratch after mounting.*

*Rev 1.4 → 1.5: **first review against the primary Hi-Link documents AND the ESPHome `ld2410` component schema** — datasheet V1.00, serial protocol V1.07 (both in the repo), and the component's own `__init__.py`. Six corrections: §3.2 pin numbering was inverted relative to the manufacturer's; §3.6 records that the 5.6 m target exceeds Hi-Link's own headline range; §5.1 records that both mounting heights sit below Hi-Link's guidance; §5.0 step 0.4 gains the reboot the Bluetooth command actually requires; §0 strikes a row whose premise was wrong; §5.3a corrects "not reachable" to "not reachable from ESPHome". §8 rewritten with first-party citations, including the standoff target — previously the most load-bearing secondhand number in the document. Firmware defaults in §4.1 corrected against protocol Table 7.*

*Rev 1.3 → 1.4: §3 updated to the as-fabricated board (44.0 × 33.0 mm, three mounting holes, VEML7700 moved off-board to a colour-coded I²C header); §10 replaced with the as-ordered BOM and actual costs; new §3.9 assembly notes for the pre-soldered XIAO; §5.0 gains a module-inspection step ahead of first power-on.*

**Primary sources.** `LD2410C Docs/HLK LD2410C … Data Sheet V1.00.pdf` (**DS**) and `LD2410C Docs/HLK-LD2410C Serial communication protocol V1.07.pdf` (**PR**). Where they disagree, PR wins: it is two years newer and it documents the commands the module obeys. Claims below cite one or the other; anything still marked "photo" or "per owner" has not been checked against them.

**A third source, and it is not interchangeable with the other two.** The ESPHome `ld2410` component has its own schema, and it answers a *different question*. PR says what the hardware honours; the component says what the code generator will accept. They diverge — gates 0 and 1 take no static sensitivity in the module, yet `still_threshold` is `cv.Required` in every gate block, so the correct YAML declares a value the hardware ignores. **Checking one and assuming the other is how a config that is right about the radar fails to build, or builds and controls nothing.** Both are cited below where they differ.

---

## 0. Module selection

Node one builds on the **HLK-LD2410C**. Rev 1.1 named the LD2412 as preferred; that was reversed in Rev 1.3 and stands.

| Claimed LD2412 advantage | Status |
|---|---|
| ~~Built-in light sensor~~ | ❌ **Struck — the premise is false.** The LD2410C has a photodiode too (PR §2.2.18), reported in engineering-mode data. Not a differentiator in either direction. The VEML7700 still wins on its own merits (§5.6): calibrated lux, not a 0–255 count, and aimable independently of the antenna. |
| Confirmable auto-calibration | Moot — auto-cal rejected on R9 grounds (§5.3a) |
| 9 m range vs 6 m | Real but unneeded — 5.6 m target covers the family room |
| 14 gates, selectable resolution | Real, modest |

Against that, Screek — who manufacture an LD2412-based product, discontinued their LD2410-based one, and have every commercial incentive to say otherwise — published:

> "The response time is a bit slower than the Gen1 series (based on the LD2410C, say 1MS), maybe **2-3 seconds** in some cases."

Testimony against interest, and a direct failure against **R2**. At 1.2–1.4 m/s walking pace that's 2.4–4.2 m travelled before detection — most of the way across the family room, in the dark.

**Possible mechanism, hypothesis only.** Improved static sensitivity plausibly comes from longer temporal integration, which costs response time. Consistent with HLK's stated explanation that LD2412 ranging was "weakened in favour of enhanced overall radar detection." *This is an engineering hypothesis, not a published description of the internal DSP, and nothing in this document depends on it.*

**R1 and R2 pull against each other**, and the two module generations sit on opposite sides of that trade. §5.10 settles it with data from this room. An LD2412S was not purchased for the first build; the A/B is deferred.

---

## 1. The unattended moment

> **It is 23:00. The family room is dark and empty. A person walks in and sits down to read. The light comes on within one second, stays on for the next ninety minutes while they barely move, and goes off some minutes after they leave. Nobody touches a switch. Nobody is available to fix anything.**

Not "the sensor has 99.9% uptime." A node that is powered and online but drops the still-target at minute forty has failed the moment of demand — and so has one that takes three seconds to notice someone walked in.

### 1.1 Requirements

| # | Requirement | Verified by |
|---|---|---|
| R1 | Detect a motionless seated adult anywhere in the room, indefinitely | §5.9 sustained-dropout metric, A2 |
| **R2** | **Median system latency ≤ 1.0 s, P95 ≤ 1.5 s** | **A1 (measured, n ≥ 30)** |
| R3 | Do not turn on when the room is already lit | A3 |
| R4 | Do not oscillate | A4 |
| R4a | Manual intervention is detected independently of the presence automation and suppresses automatic control until the room returns to EMPTY | A8 |
| R5 | Do not trigger on non-human motion | §5.4, A6 |
| R6 | Limit detection through the wall into the hallway | §5.2, A7 |
| R7 | Degrade to a known state, not a random one | §7, A11 |
| R8 | Telemeter the slow variable that will eventually end it | §6 |
| R9 | Commissioned state must be reproducible from version control | §5.3a, §5.11 |

**R1 and R2 are in tension.** Both are satisfiable in a 5.6 m room, but only by measurement.

### 1.2 The slow variable

Furniture moves. Seasonal HVAC turns a quiet gate into a noisy one. Lamps age and get replaced. The radar window fouls. **Design response:** log per-gate energies and lux continuously at the baseline rate (§6.1), and define the drift responses in advance (§6.3).

---

## 2. System architecture

```
                  ┌──────────────── Zulkit ABS enclosure ────────────────┐
   room  ◄────────┤  clear lid (radar window)                            │
                  │       ▲ ~12 mm air gap                               │
                  │  ┌────┴─────┐                                        │
                  │  │  LD2410C │            ┌──────────┐                │
                  │  └────┬─────┘            │ VEML7700 │ on QT cable,   │
                  │  ═════╪═══ carrier PCB ══╪══════════╪═ far side of   │
                  │       │  F.Cu = GND plane │          │  the box      │
                  │  ┌────┴──────────────────┐└─────┬────┘               │
                  │  │  XIAO ESP32-C3 (back) ├──I²C──┘                   │
                  │  └────────────────┬──────┘                           │
                  │      10 mm standoffs                                 │
                  └──────────────────┬───────────────────────────────────┘
                                     │ USB-C
                                     ▼
                         Wi-Fi ──► Home Assistant ──► lamp
```

The carrier's front-copper ground pour sits between the radar and the ESP32-C3 — a continuous backplane behind the radar, open space in front, and separation from the 2.4 GHz radio. An earlier side-by-side layout put the two 1.4 mm apart with nothing between them; abandoned.

**The light sensor is deliberately off-board.** On-carrier it sat 3.41 mm from the module edge — the same class of near-field problem as that abandoned layout. On a 150 mm cable it lives in the ~26 mm of free box length on the far side, and can be aimed independently of the radar.

**2.4 GHz coexistence.** The XIAO has BLE and so does the radar, ~10 mm apart in a sealed box. Configuration happens over UART, so **disable the radar module's Bluetooth at commissioning and verify it survives a power cycle** (§5.0). One less radio, one less unauthenticated config path.

**The other radio is the ESP's own Wi-Fi, and this design has not proven it is harmless.** Screek — who ship an ESP32-S2 and an LD2410C inside a 13.8 mm enclosure — publish that they lowered Wi-Fi TX power to 15 dB, ran the CPU at 80 MHz instead of 240, and chose `power_save_mode: LIGHT` over `NONE`, all "in order to adapt to work in a small space." That is a commercial manufacturer paying a latency and link-margin cost to quiet the ESP next to the radar.

This design's answer is geometric rather than electrical: a continuous ground plane between the two, on opposite faces of the carrier, 10 mm of standoff, in a 27 mm cavity. That should be worth more than Screek's 13.8 mm allows — **but "should" is a hypothesis, and A12a (§5.7) is the measurement that settles it.** If the empty-room gate floor drops when Wi-Fi TX power is reduced, the plane is not doing the job and Screek's mitigations are the remedy, cheapest first: `output_power` costs R2 nothing, `power_save_mode: LIGHT` costs it directly.

---

## 3. Hardware

### 3.1 Board

| | |
|---|---|
| Size | **44.0 × 33.0 mm**, 2-layer, 1 oz, 1.6 mm |
| Area | 2.251 in² → **$11.25 for three, $3.75 each** at OSH Park |
| Mounting | **3 × M3 NPTH** at H1 (43.50, 76.00), H2 (80.70, 76.20), H3 (80.80, 49.70) — edge clearance 1.75 / 1.55 / 1.45 mm respectively. **Reconciled against the board 2026-09-07**; the previous row read (43.1, 76.4), (80.9, 76.4), (80.9, 49.6) with "1.6 mm each", which drifted up to 0.4 mm from the as-drawn positions and stated a uniform clearance the board does not have. H2 and H3 sit under U2's courtyard by design — see the nylon-fastener note in §3.9 |
| Vias | 67 total, **16 under the module**, largest gap 5.39 mm (< λg = 5.96 mm) |
| Front copper | pads and vias only — **no traces**; unbroken GND plane |
| Back copper | all routing; 1 mm power, 0.25 mm signal, 0.2 mm clearance |

**1 oz / 1.6 mm, not the 2 oz / 0.8 mm service.** At 24.125 GHz skin depth is 0.425 µm, so 1 oz is already 82 skin depths — 2 oz buys nothing electrically. And 0.8 mm is 1/8 the flexural rigidity (scales as t³), which is the wrong direction for a vertically mounted board carrying a cantilevered radar where flex changes the antenna-to-window distance.

### 3.2 Interconnect

Module pin order, printed on the antenna face: **TX RX OUT GND VCC**. On the board the pads run VCC → TX from y 56.89 to 67.05.

**Pin numbers below are Hi-Link's, corrected in Rev 1.5.** DS §4.2 Table 1 numbers these pins in the *same* order as the silkscreen — pin 1 is TX, pin 5 is VCC. Rev 1.4 and earlier numbered them the other way round (1 = VCC … 5 = TX), which contradicted the datasheet a reader would have open beside this table.

**Nothing on the fabricated board is affected.** The prose above is a physical layout statement and is correct: the pads run VCC → TX, which matches the module's printed order once it is seated facing the right way. Only the numbering column was inverted. But this is the same hazard as the naming convention two paragraphs down, one level up — a pin *number* is ambiguous across two documents in exactly the way a net called "TX" is ambiguous across a crossover.

| LD2410C | Signal | Direction | XIAO | GPIO | ESPHome |
|---|---|---|---|---|---|
| 1 | UART_Tx | module → ESP | D3 | GPIO5 | `uart: rx_pin` |
| 2 | UART_Rx | ESP → module | D2 | GPIO4 | `uart: tx_pin` |
| 3 | OUT | module → ESP | D10 | GPIO10 | binary_sensor, via R1 |
| 4 | GND | — | GND | — | |
| 5 | VCC | 5 V in | **VBUS** | — | **not 3V3** — see §9 |

**Identify every pin by its silkscreen label, never by position or by number.** VCC and TX sit at opposite ends of a five-pin header, so counting from the wrong end puts 5 V on TX. That is the one wiring error on this module that destroys something, and it is the error a reversed numbering table invites.

**Power.** DS §7: 5 V, supply capacity **> 200 mA**, average operating current **79 mA**. DS §4.2's pin table says "5~12V (advise 5V)". USB's 500 mA covers it with margin.

**PH1 — light sensor, right-angle 4-pin, colour-coded on silk:**

| pad | label | XIAO | GPIO |
|---|---|---|---|
| 1 | 3V3 (RED) | 3V3 | — |
| 2 | GND (BLACK) | GND | — |
| 3 | SCL (YELLOW) | D5 | GPIO7 |
| 4 | SDA (BLUE) | D4 | GPIO6 |

Colours match the Qwiic/STEMMA QT convention. **The pin *order* deliberately does not** — it was chosen for cleaner routing, and the silkscreen colour labels are the interface instead.

> **Build constraint: only a flying-lead QT cable works.** Adafruit 4397 terminates in four independent female sockets, so each wire is placed by colour. A molded 4-pin housing cable would connect power backwards and destroy the sensor. Record this in the repo README and in a comment beside the I²C block in the ESPHome config — the board tells you the colours but not why, and the config gets read first.

**Naming convention:** nets are named for the *module's* pin, never the ESP's. A net called simply "TX" is ambiguous in a crossover and caused two errors during design.

### 3.3 Pin selection constraints

| Pin | GPIO | Use | Note |
|---|---|---|---|
| D0 | 2 | — | **Strapping** |
| D1 | 3 | free | ADC1 — break out to a test pad |
| D2 | 4 | UART tx | |
| D3 | 5 | UART rx | ADC2, not ADC1 |
| D4 | 6 | SDA | |
| D5 | 7 | SCL | |
| D6 | 21 | — | **U0TXD** — ROM prints the boot log here |
| D7 | 20 | — | U0RXD |
| D8 | 8 | — | **Strapping** |
| D9 | 9 | — | **Strapping** — low at reset enters serial bootloader |
| D10 | 10 | RADAR_OUT | |

RADAR_OUT is a **push-pull output that sits LOW whenever the room is empty** — normal at power-on. On GPIO9 the node would boot into download mode in an empty room and work fine when someone stands in front of it: a bug that hides from the person testing it.

*Rev 1.5 nuance:* that idle level is the **factory default, not a hardware property**. PR §2.2.18's third configuration byte selects it — `0x00` = OUT idles low, `0x01` = OUT idles high. **The pin choice is unaffected, which is rather the point:** GPIO10 is safe under either polarity, whereas a design that had leaned on the default to justify a strapping pin would have been resting on a parameter someone can change over UART.

`R1 = 1 kΩ` provides **fault-current limiting**, holding contention to ~3.3 mA if GPIO10 is ever driven opposite the module's OUT state. It bounds current; it does not make a wrong pin configuration safe.

### 3.4 Mechanical stack

λ at 24.125 GHz = **12.427 mm**. Target H = 1λ, ±1.2 mm. (1.5λ is unreachable in a 27 mm cavity with components on both faces.)

```
H = D_internal − S − t_board − H_header − t_module
H = 27 − S − 1.6 − 2.54 − 1.0 = 21.86 − S
```

Allowed S: **8.23 to 10.63 mm**. Optimum 9.43 mm.

| z | element |
|---|---|
| 0.00 | box floor |
| 10.00 | standoff |
| 11.60 | carrier PCB |
| 14.14 | header insulator |
| **15.14** | **antenna face** |
| 27.00 | window inner surface |

**H = 11.86 mm** with a 1.0 mm module PCB; **11.26 mm** if it measures 1.6 mm. Both inside the window, but at 1.6 mm go to **9 mm standoffs** (H = 12.26 mm). Decided by calipers at §5.0.

#### 3.4a Standoff selection — solved, Rev 1.5

**Module thickness is now 1.0 mm on manufacturer evidence.** HLK's own STEP model (`LD2410C Docs/HLK-LD2410C-3D图.zip`) contains the 22.00 × 16.00 mm outline with faces at z = 0.000 and z = **0.989 mm**. That is a nominal CAD figure, not an as-built one — PCB thickness tolerance is typically ±10% — so §5.0 step 0.9 still wants calipers. But the assumption is no longer an assumption.

Available nylon standoffs: **8, 9, 9.5, 10, 10.5 mm**. Computed by `scripts/standoff_solver.py`:

| S | H at t=1.0 | error | phase | H at t=1.6 | error |
|---|---|---|---|---|---|
| 8.0 | 13.860 | +1.433 | 83° | 13.260 | +0.833 |
| **9.0** | 12.860 | +0.433 | 25° | **12.260** | **−0.167** |
| **9.5** | **12.360** | **−0.067** | **3.9°** | 11.760 | −0.667 |
| 10.0 | 11.860 | −0.567 | 33° | 11.260 | −1.167 |
| 10.5 | 11.360 | −1.067 | 62° | 10.760 | **+1.667 — outside** |

- **At 1.0 mm — fit 9.5 mm.** H = 12.360, just **0.067 mm** off one wavelength, which is 3.9° of round-trip phase. That is as close as a discrete part can get.
- **At 1.6 mm — fit 9.0 mm.** H = 12.260, 0.167 mm off.
- **If buying only one size — buy 9.0 mm.** It is the only choice inside the ±1.2 mm window for *both* thicknesses with a worst case of 0.433 mm. 9.5 also survives both (worst 0.667 mm); 8.0 and 10.5 each fail one case.

Back-side clearance is satisfied throughout: the carrier's lowest feature sits 6.48 mm below the board, so even 8 mm leaves 1.52 mm to the box floor, and shorter standoffs only increase clearance at the 20 mm base rim.

#### 3.4b Resolved with the measured enclosure — fit 10 mm

**Measured 2026-09-06:** internal depth **69/64 in = 27.384 ± 0.397 mm**, cover thickness **8/64 in = 3.175 ± 0.397 mm**. Both by hand rule, hence the 1/64 in tolerance.

*Interpretation, stated so it can be corrected in one word:* the 27.384 mm is taken as the **total** internal depth — base floor to the inner surface of the lid — which is the D_internal this stack uses and matches the 20 + 7 mm the listing implies. The base alone would read ~20 mm, so the number itself supports the reading. **If it was the base only, everything below shifts by 7 mm and the answer changes completely.**

The extra 0.384 mm over the assumed 27.0 is enough to move the answer a whole size:

| S | H at 26.987 | H at 27.781 | worst error | worst phase | |
|---|---|---|---|---|---|
| 8.0 | 13.847 | 14.641 | 2.214 | 128° | can fall outside |
| 9.0 | 12.847 | 13.641 | 1.214 | 70° | **can fall outside** |
| 9.5 | 12.347 | 13.141 | 0.714 | 41° | in spec across the band |
| **10.0** | **11.847** | **12.641** | **0.580** | **34°** | **in spec — best** |
| 10.5 | 11.347 | 12.141 | 1.080 | 63° | in spec across the band |

**Fit 10.0 mm.** At the nominal depth H = 12.244 mm, 0.183 mm from one wavelength (10.6° of round-trip phase). More importantly it is the choice that stays furthest inside HLK's ±1.2 mm window **anywhere the true depth might actually be** — 0.580 mm worst case against 9.5 mm's 0.714 mm. A measurement with error bars does not pick a part; the worst case inside those bars does.

Note what the band excludes: **9.0 mm can fall outside the window** at the top of the tolerance, and 9.0 mm was last revision's recommendation under the nominal 27.0 mm. That is the sensitivity working exactly as advertised.

**This vindicates the original stack.** §3.4's z-table was built at S = 10 mm and was closer to correct than the 9.5 mm derived from the nominal 27.0 mm figure. The measurement did not overturn the design; it overturned an intermediate recommendation made from a listing.

#### 3.4c The module arrived — and it contradicts HLK's own CAD. Fit 9.5 mm.

**Measured 2026-09-06, hand rule: between 3/64 and 4/64 in = 1.191 to 1.588 mm.** HLK's STEP model says **0.989 mm**. Those ranges do not overlap.

**When the CAD and the part in your hand disagree, the part wins.** A vendor 3D model is nominal, is often built for envelope checking rather than dimensional truth, and is sometimes simply wrong. §5.0 step 0.9 exists because of exactly this possibility, and it has now paid for itself before the board was even fitted.

Two honest caveats in the other direction: a rule graduated in 1/64 in (0.397 mm) is a poor instrument for a ~1 mm dimension, and pressing it across a board with copper pours and solder mask reads slightly over. So the defensible position is not "the board is 1.4 mm" — it is **"t lies somewhere in 1.0 to 1.6 mm and nothing here can narrow it further."** Standard PCB stock is 0.8 / 1.0 / 1.2 / 1.6 mm; 3/64 in is 1.2 mm to within the reading error and 4/64 in is 1.6 mm, so those two are the likely truth.

**The answer is the standoff that does not care which.**

| t | best size | its error | **9.5 mm gives** |
|---|---|---|---|
| 1.00 mm (STEP) | 10.0 | −0.183 | **+0.317** |
| 1.20 mm (3/64 in) | 9.5 | +0.117 | **+0.117** |
| 1.60 mm (4/64 in) | 9.0 | +0.217 | **−0.283** |

Across the joint band — depth 26.987–27.781 **and** thickness 1.0–1.6 mm:

| S | H min | H max | worst error | |
|---|---|---|---|---|
| 8.0 | 13.247 | 14.641 | 2.214 | can fall outside |
| 9.0 | 12.247 | 13.641 | 1.214 | **can fall outside** |
| **9.5** | **11.747** | **13.141** | **0.714** | **in spec everywhere** |
| 10.0 | 11.247 | 12.641 | 1.180 | in spec, but only just |
| 10.5 | 10.747 | 12.141 | 1.680 | can fall outside |

**Fit 9.5 mm.** Worst case 0.714 mm — 41° of round-trip phase — anywhere in the plausible space, against 10.0 mm's 1.180 mm which sits almost on HLK's limit. It is never the single best choice at any one thickness, and that is precisely the point: **it is the only size that is comfortably right whichever of the three the board turns out to be.**

*The recommendation has moved 9.5 → 10.0 → 9.5 across three measurements. Worth noting why that is not thrashing:* the first was a point estimate from a product listing, the second a point estimate from a measured depth, and this one is a robustness argument over two acknowledged uncertainties. Same number as the first, arrived at for a reason that will survive the next measurement.

#### 3.4d Full tolerance stack-up — 9.5 mm is the only size that survives it

The bands in §3.4b–c sweep the two dimensions that were *measured*. The stack has five terms, and the other three were being carried as exact:

| contributor | ± mm | status |
|---|---|---|
| enclosure depth | 0.397 | **measured** — hand rule, 1/64 in |
| module thickness | 0.300 | **disputed** — CAD 0.989 vs rule 1.19–1.59 |
| carrier PCB (1.60 mm) | **0.152** | **OSH Park core spec, ±6 mil** — but see §3.4f |
| header insulator (2.54 mm) | 0.150 | assumed equal to the pitch — **never measured** |
| standoff | 0.100 | typical nylon tolerance + screw compression |
| **worst case, linear** | **1.107** | all five conspire in the same direction |
| **realistic, RSS** | **0.553** | independent errors, root-sum-square |

*Treating an unmeasured assumption as exact is how a stack-up comes out comfortable on paper and marginal in the box.* Carrying all five:

| S | nominal H | error | worst case | RSS |
|---|---|---|---|---|
| 9.0 | 12.944 | +0.517 | **BREACHES by 0.424** | inside, +0.130 |
| **9.5** | **12.444** | **+0.017** | **INSIDE, +0.076** | **inside, +0.630** |
| 10.0 | 11.944 | −0.483 | **BREACHES by 0.390** | inside, +0.164 |

**So yes — 9.5 mm covers everything, and it is the only size that does.** Two things worth being precise about, because "covers everything" can mean two different things:

- **Nominal H = 12.444 mm, +0.017 mm from one wavelength.** At the centre of all five uncertainties this is as close to exact as the stack can be. That is luck as much as design — but it is the reason the margins below work out.
- **The worst-case margin is +0.076 mm, which is thin.** It requires all five errors to align in the same direction, which is why the RSS figure of +0.630 mm is the one to plan around. But it is not zero, and neither 9.0 nor 10.0 can say that: both leave HLK's window under the same assumptions.

**The two unmeasured terms are the ones worth closing, and both parts are already in hand.** The carrier PCB is on the bench and the radar header (PH1-05-UA) is in the BOM. Calipers on those two remove 0.16 and 0.15 from the stack for about thirty seconds of work — and more importantly they convert two assumptions into measurements, which is the difference between a margin you can quote and one you are hoping about.

#### 3.4e Header insulator measured — 6/64 in, and the reading confirms 2.54 mm

**Measured 2026-09-06: "closer to 6/64 in" = 2.381 mm.** Assumed value was 2.54 mm.

**These agree, and the arithmetic is the reason:** 2.54 mm is **6.40/64 in**. On a rule graduated in 64ths, a 2.54 mm part sits between 6/64 (2.381) and 7/64 (2.778) and lands nearer the 6. So "closer to 6/64" is precisely what a correct 2.54 mm insulator reads — which is also the nominal body height for a 0.1 in header, and PH1-05-UA is a 0.1 in header. The measurement corroborates the assumption rather than replacing it.

Both readings run anyway, because the difference is not nothing:

| S | H at 2.54 | worst / RSS | H at 2.381 | worst / RSS |
|---|---|---|---|---|
| 9.0 | 12.944 | **out** −0.424 / in +0.130 | 13.103 | **out** −0.533 / **out** −0.017 |
| **9.5** | **12.444** | **in +0.076** / in +0.630 | **12.603** | −0.033 / **in +0.483** |
| 10.0 | 11.944 | **out** −0.390 / in +0.164 | 12.103 | **out** −0.181 / in +0.335 |

**9.5 mm remains the pick under either value, so the fit does not change.** Two qualifications:

- The −0.033 mm figure is **33 micrometres**, an order of magnitude below the resolution of every input feeding it, and it appears only in the linear worst case — the deliberately pessimistic construction where all five errors align. RSS, the realistic case, is +0.483 mm inside.
- **The stack-up behaved honestly.** §3.4d bracketed this term at 2.54 ± 0.15 (2.39–2.69). The reading of 2.381 sits a hair below that band, so the assumption was marginally optimistic but essentially right, and the term moved the margin by about the amount it was permitted to. That is what a tolerance bracket is for, and it is worth noting when one works.

#### 3.4f The OSH Park carrier tolerance — sourced, and it is a floor not a bound

Looked up rather than assumed. OSH Park 2-layer prototype stackup:

| layer | material | thickness |
|---|---|---|
| solder resist | ×2 | 0.1 mil each |
| copper | 1 oz | 1.4 mil each |
| **core** | **175Tg FR-4, Kingboard KB6167F** | **60 mil, ±6 mil** |
| **finished** | | **63 mil = 1.6 mm nominal** |

**±6 mil = ±0.1524 mm.** The §3.4d assumption of ±0.16 was right to within 8 µm, and substituting the sourced figure moves 9.5 mm's worst-case margin from +0.076 to **+0.084 mm**. Nothing changes.

**But read what that tolerance is attached to.** It is quoted on the **core**, and OSH Park publish *no* finished-board thickness tolerance at all. The core is 60 of the 63 mil, so it dominates — but copper plating and solder-mask variation sit on top of it and are unquantified. **±0.152 mm is therefore a floor on the finished tolerance, not a bound**, and a stack-up that treats it as a bound is quietly optimistic in the direction where 9.5 mm has least room.

That is an argument for measuring rather than specifying. **Three fabricated carriers are on the bench**; calipers on one of them replaces a floor-with-unknown-excess by a number, and it is the same thirty seconds already recommended for the header.

**This is now the highest-leverage remaining measurement**, because it moves the *top* of the band where 9.5 mm has least room. Calipers on the header settle 2.381 against 2.54 in seconds. It will not change the standoff; it will change whether the worst-case margin is quoted as +0.076 or −0.033, and only one of those is a number worth writing in the baseline.

#### 3.4g How comfortable is it, actually?

**The window is ±1.2 mm ABSOLUTE, not 1.2%.** DS §8.3 reads *"Error control: ±1.2mm"*. One-point-two percent of 12.427 mm would be ±0.149 mm — eight times tighter, and the worst-case stack would miss it by a factor of seven. The distinction is worth holding onto, because a percentage misread here converts a comfortable design into an apparently failing one.

Against the real ±1.2 mm, at S = 9.5 mm and nominal H = 12.444 mm:

| construction | ± mm | margin | |
|---|---|---|---|
| linear worst case | 1.099 | **+0.084** | inside, but 84 µm is not "comfortable" |
| **RSS of the bounds** | **0.551** | **+0.632** | **inside, and genuinely comfortable** |

Expressed as coverage rather than as a margin:

- If the five tolerances are **hard uniform bounds**, σ = 0.318 mm and the window is **±3.72σ** — about **200 ppm** of assemblies outside.
- If they are **3σ vendor bounds** (the usual reading of a published spec), σ = 0.184 mm and the window is **±6.4σ** — effectively zero.

**So: comfortable, and the word is earned by the RSS construction.** The linear worst case assumes all five errors sit at their extremes simultaneously *and in the same direction*, which for independent terms is the 200 ppm tail above — a sanity check that passes, not the operating number.

Two things keep this from being a closed question. **Two of the five terms are not measured** (carrier PCB, header insulator — the latter has a consistent reading but not a caliper). And the carrier figure is a **floor rather than a bound** (§3.4f), so the RSS is optimistic by an amount nobody has quantified. Measuring both would make the design comfortable on *any* construction, including the pessimistic one, which is a better place to be than comfortable on the one you chose.

#### 3.4h What the solved standoff does and does not predict

**It does not predict performance, and this section exists to stop a future reader assuming it does.**

What the number means, stated as phase, which is the quantity the standoff actually sets:

| | mm | round-trip phase |
|---|---|---|
| nominal error at S = 9.5 mm | 0.017 | **1.0°** |
| RSS spread | 0.551 | 31.9° |
| linear worst case | 1.099 | 63.7° |
| **HLK's ±1.2 mm allowance** | 1.200 | **69.5°** |

The RSS spread is **46% of the manufacturer's own tolerance**; the pessimistic construction is 92%. The window is centred to within a degree.

**That is a statement about a mechanical dimension, not about detection.** §8 withdrew *"radome loss as a quantitative figure"* and *"range as a calculated value"* for reasons that have not changed: the slab model assumed εr, ignored loss, ignored incidence angle across a ±60° cone, and ignored multiple reflections. Appendix A pins the 58°/mm figure as *"standing-wave phase only — not a cavity mode"*. Hi-Link recommend 1λ or 1.5λ without publishing a mechanism, so there is nothing here to extrapolate from honestly.

**The useful conclusion is narrower and worth stating plainly: the standoff is now solved and non-limiting.** §3.4 opens by calling H *"the one dimension the whole mechanical design turns on"*. It no longer is. It is the best-characterised term in the build and it has been removed from the list of candidate explanations for anything §5 goes on to measure.

**What determines performance instead**, in descending order and all of it already in this document:

| rank | factor | where |
|---|---|---|
| 1 | **Mounting height** — office at 0.75 m against DS §5.4's 1.5–2 m wall-mount guidance, whose pattern figures are drawn for 1.5 m. The largest documented deviation in the build | §5.1 |
| 2 | **Angle off boresight** — "angle matters far more" than window loss; a person at the ±60° cone edge is materially closer to the limit | §3.5 |
| 3 | **Gate thresholds** — factory defaults until §5.9 runs. The most headroom and the most work | §5.9 |
| 4 | **Clutter** — HVAC air movement; the near wall behind the office desk | §3.7, §5.4 |
| 5 | **The lid's actual εr** — still unknown; §3.5 accepted 3 mm without it | §3.5 |

And the framing that governs how a range shortfall should be read: **5.6 m exceeds Hi-Link's own headline 5 m figure**, so §5.2a is testing whether the part beats its datasheet, not whether the installation is competent. A miss there points at the module before it points at the aim.

*Note what calipers on the MODULE would and would not buy.* It is the second-largest term, but shrinking it also moves the nominal: at t = 1.0 the nominal error becomes +0.317 and the top-end margin tightens, at t = 1.6 it becomes −0.283 and the bottom tightens. The disputed range happens to be centred near optimal for 9.5 mm, so resolving it changes the confidence rather than the choice. **Fit 9.5 mm either way.**

**Lid thickness 3.175 mm does not enter this calculation at all.** H is measured to the *inner* surface of the window, so the lid's thickness sits entirely above the gap. It matters to §3.5's transmission argument, where the measured 3.175 mm sits marginally closer to the half-wave transparent point (~3.85 mm) than the assumed 3.0 mm did — a small improvement, and the decision to accept the lid is unchanged.

Back side: **6.48 mm** measured to the lowest feature (USB-C shell), leaving 3.52 mm floor clearance at S = 10 mm.

Box internal is 20 mm in the base plus 7 mm in the cover. Everything lives inside the base — module top ~17.2 mm against a 20 mm rim — so the cover lifts off without disturbing the stack.

**Board placement:** put the left edge **1.55 mm from the inner wall** so the USB-C receptacle sits flush and a shell-sized cutout works. That leaves the radar ~5 mm off-centre on the long axis, against ~18 mm of tolerance. The short axis is the binding one: cone radius 20.54 mm against a 25.95 mm half-width, so **5.4 mm of centring tolerance**.

### 3.5 Radar window

The clear lid is the window. Slab modelling indicates thickness matters and that ~3 mm sits in a reasonable region — between the quarter-wave worst case near 1.9 mm and the half-wave transparent point near 3.85 mm.

**Decision: accept the 3 mm lid.** Shimming toward half-wave recovers little; a poor bond line costs more.

*Figures come from a lossless-slab, normal-incidence model with an assumed dielectric constant. Real behaviour depends on actual εr and loss, incidence angle across the beam, thickness tolerance, and multiple reflections. At the ±60° cone edge, reflection is strongly polarisation-dependent and the effective path lengthens. Treat the modelling as indicating the right thickness region, not as a loss prediction.*

- **The radar looks out the clear lid, never the black base.** Use unpigmented plastic in the radar path. Avoid metallic films, conductive coatings, foil labels.
- **No metal in the window path.**

For scale: Screek's 1U is 13.8 mm deep externally and cannot hit a 12.4 mm standoff, yet ships as a working product.

### 3.6 Range: an acceptance target

**Design range: 5.6 m (18 ft).** This is a **test requirement**, not a link-budget guarantee — earlier revisions quoted a range derived from an assumed dielectric constant, and that precision wasn't supported.

Retained as directionally useful: window and standoff both impose modest penalties; received power goes as 1/R⁴ so sub-dB losses have small range consequence; ~12 dB of round-trip loss halves the range. **Angle matters far more** — a person at the ±60° cone edge is materially closer to the limit than one on boresight.

**Rev 1.5 — the target sits above Hi-Link's headline figure, and the datasheet contradicts itself.**

| source | figure |
|---|---|
| DS §1, §2.1 | "the farthest sensing distance can reach **5 meters**" |
| DS §7 parameter table | "Detection distance **0.75 m ~ 6 m**, adjustable" |
| geometry | 8 gates × 0.75 m = 6.0 m; max-gate setting tops out at 8 (PR §2.2.3) |

**5.6 m lies between the two.** Nothing collapses — §3.6 already insists this is a test requirement rather than a link-budget guarantee — but the consequence needs stating plainly, because it changes how a failure should be read:

> **§5.2a is testing whether this part beats its own datasheet, not whether the installation is competent.** If the far end of the family room does not make 5.6 m, the first hypothesis is the part, not the aim. That is the opposite of the usual reading, and getting it backwards means re-aiming a sensor that was already pointed correctly.

**Rev 1.6 — the room measured off the architectural plan, and the target slightly under-covers it.**

Drawing A101 (*Edgewater Hill Lot 15, dream developers, 1.31.2021*) gives **LIVING ROOM 17'-7" × 15'-2"**, with the fireplace centred on the 15'-2" east wall. The node sits on that mantel, so it looks **west along the 17'-7" dimension** with roughly 7'-7" of room either side of boresight:

| target | distance | gate |
|---|---|---|
| far wall, on boresight | 17'-7" = **5.36 m** | 7 (5.25–6.00 m) |
| far corners, diagonal | 19'-2" = **5.84 m** | 7 |

**MEASURE THE TARGET AGAINST OCCUPIABLE SPACE, NOT GEOMETRIC EXTENT.** The raw corner figure of 5.84 m exceeds the 5.6 m target, which on its own reads as a miss. It is not, because **nobody can stand there** — the far end carries counters and appliances (owner, 2026-09-07), so the furthest a person reaches is a counter depth short of the boundary:

| measured to | on boresight | far corner |
|---|---|---|
| geometric room extent | 5.36 m | 5.84 m |
| **occupiable space** (−24" counter) | **4.75 m** | **5.23 m** |

**5.23 m sits inside the 5.6 m target with about 0.37 m of margin.** So §3.6 covers the space that matters, and §5.2a's acceptance walk should be conducted to the counter face rather than the wall.

Two caveats on that arithmetic. 24" is a standard base-cabinet depth; **a refrigerator or range run is 30–36" and would push the occupiable limit further in**, giving more margin, not less. And the correction only applies where fixtures actually run — an open corner has none, so **the walk should establish the true furthest standing point rather than assume the counter line is continuous.**

The general point is worth keeping even after this room is commissioned: **a detection-range requirement measured to a wall over-specifies the problem** wherever anything occupies the perimeter. Furniture, counters and appliances all buy range back for free.

Note also that the corners sit only **23° off boresight** — well inside the ±60° cone. So §3.6's "angle matters far more" caveat, true in general, is **not** the binding constraint in this room. Range is.

**THE WEST SIDE HAS NO WALL, AND THAT IS A DECISION RATHER THAN A DEFECT.**

The plan shows no partition between the living room and the **KITCHEN (17'-5" × 18'-7")** — it is one continuous space, broken only by an island. The sightline from the mantel does not stop at 17'-7"; it runs on roughly another 17 ft. At the module's ~6 m ceiling the radar reaches about two feet past the living room boundary, which is where the island is.

That matters because **the living room's far wall and the kitchen's near boundary are the same plane at 5.36 m.** Unlike the office — where the bathroom sits in gates 3–4 and a person entering sits in gates 0–2, cleanly separable — here the wanted and unwanted returns are *coincident in range*. No max-gate setting distinguishes them, and there is no wall to attenuate one of them.

> **DECIDED 2026-09-07 (owner): someone at the kitchen island COUNTS as "living room occupied".** The great room is one space for lighting purposes. Detection into the kitchen is therefore **correct behaviour, not a false trigger**, and there is nothing to tune out.

Three consequences follow, and they are the reason this is written down:

1. **The family node wants the LARGEST gate setting, not a restrictive one** — gate 8, so the far corners at 5.84 m are covered with margin and the island is reached deliberately.
2. **R6 (limiting through-wall detection) does not apply on the west side**, because there is no wall there. It applies to the north and east exterior walls only, and to the office node in full.
3. **§3.6's 5.6 m is a FAMILY-ROOM requirement and is not an office one.** The office needs the opposite — a bathroom shares its wall, and bench work on 2026-09-07 showed that rejecting it requires capping the *move* path at gate 2 (2.25 m). A single global acceptance range would be wrong for both rooms. The per-device substitution files are what carry that difference, and this is the clearest case of why they exist.

DS §5.5 adds that the "longest distance will also fluctuate slightly" with target size, state and RCS — so expect the measured envelope to vary between people, not just between placements.

**Coverage is established experimentally in §5.2a.**

### 3.7 Back-lobe treatment

All three planned locations have the box's back against an **exterior wall**, so the copper-tape backplane discussed earlier is **not required**. The back-lobe concern was moving targets behind the radar; an exterior wall has none, and the wall itself is a static return that clutter cancellation removes.

One nuance: the office desk unit sits at 0.75 m with the wall close behind — a stronger, nearer static return than a mantel at 1.3 m. Still static, still cancelled, but if §5.4 shows an odd gate-0 or gate-1 floor at the desk, look here first.

**Second suspect, added Rev 1.5: the node's own Wi-Fi.** An unexplained floor is not necessarily in the room. A12a (§5.7) distinguishes the two cheaply — clutter in the room does not care what the ESP's transmitter is doing, so a floor that moves with `output_power` is coming from inside the box.

### 3.8 Ground margin around the module

3.87 mm top, 4.11 mm right, 7.08 mm bottom. **4 mm is convention, not a Hi-Link spec** — their manual asks for a metal backplane and gives no dimension.

λ/4 = 3.1 mm is the conventional floor; below that a plane mostly diffracts at its edges. λ/2 = 6.2 mm is meaningfully better; beyond ~1 λ is diminishing returns. The carrier plane is a *secondary* shield behind the module's own ground, which is why 3–4 mm is defensible here.

Ranked higher than margin, if effort is available: plane continuity (have it), stitching density under the module (16 vias, 5.39 mm — adequate), and gate blanking in §5.4, which removes back-lobe artifacts by threshold regardless of geometry.

### 3.9 Assembly

**The XIAO is the pre-soldered version.** Consequences:

- **Header height is fixed by Seeed**, not chosen. §3.4 assumes a 2.54 mm insulator — **measure the as-built board-to-board gap** and correct H if it differs.
- **Verify which way the pins protrude** and by how much before attempting to fit it.
- If the pins are soldered directly into the carrier, **the XIAO becomes permanent**. Consider female sockets on the carrier instead if you want it removable.

**Trim the radar header pins flush** with the module's top surface after soldering. Untrimmed they stand ~1.5 mm proud of the antenna face — 0.12 λ of exposed conductor at the aperture edge.

**Order** (constraints, not preferences):
1. Mounting screws — inaccessible once the radar is fitted; nylon button or pan head
2. R1, C1–C3, PH1 on B.Cu
3. XIAO, then the radar header

**Cut the VEML7700's power-LED jumper before the sensor goes anywhere near the box.** The Adafruit 4162 carries a green power LED on the same face as the photodiode, lit whenever the board is powered, and a jumper on the back exists to disable it (Adafruit guide pp.7, 24). This assembly is a *sealed enclosure*: an ambient-light sensor locked in the dark with its own light source is partly measuring that source. §5.6 puts THRESHOLD_ON at ~18 lx and the part resolves 0.0036 lx/count, so a stray offset of a lux or two is a material fraction of the decision — and being constant, it presents as a calibration rather than a fault. It would be baked into the commissioned threshold and never questioned. Cut it, then confirm at §5.0 step 0.6 that a covered sensor reads ~0.

**Nylon screws and standoffs throughout.** Metal standoffs would run vertically through the back-lobe region; nylon avoids that and makes the two screw heads near the module footprint a non-issue. Torque finger-tight — M3 nylon strips easily, and these fasteners are inaccessible after assembly.

**U.FL routing.** The XIAO's antenna connector sits beside C1/C2. C1 was relocated to open a ~3.5 mm channel; route the pigtail straight out of the connector for 5–10 mm before any bend, then strain-relieve with RTV over the connector body and first few millimetres. Fix the antenna to the inner wall on the far side from the radar — the same ~26 mm of free box that holds the light sensor.

---

## 4. Firmware

### 4.1 Configuration skeleton

Verify entity names against the pinned ESPHome version (§5.11).

```yaml
i2c:
  sda: GPIO6          # PH1 pad 4 — BLUE
  scl: GPIO7          # PH1 pad 3 — YELLOW
  frequency: 100kHz   # 400 kHz unnecessary for a 10 s poll
  # NOTE: PH1 is colour-coded, not Qwiic pin-ordered.
  #       Use a flying-lead QT cable (Adafruit 4397) ONLY.
  #       A molded 4-pin housing cable reverses power.

uart:
  id: uart_radar
  tx_pin: GPIO4       # -> LD2410C pin 4 (UART_Rx)
  rx_pin: GPIO5       # <- LD2410C pin 5 (UART_Tx)
  baud_rate: 256000   # documented factory default
  parity: NONE
  stop_bits: 1

ld2410:
  uart_id: uart_radar
  id: radar

switch:
  - platform: ld2410
    engineering_mode:
      name: "Engineering mode"
      id: eng_mode
      restore_mode: ALWAYS_OFF     # production default — §6.1
    bluetooth:
      name: "Radar Bluetooth"
      restore_mode: ALWAYS_OFF     # verify persistence, §5.0

binary_sensor:
  - platform: ld2410
    has_target:        { name: "Presence" }
    has_moving_target: { name: "Moving" }
    has_still_target:  { name: "Still" }
  - platform: gpio                 # hardware path, independent of UART
    pin: GPIO10
    name: "Presence (hardware OUT)"
    id: radar_out
    filters: [ delayed_on: 200ms, delayed_off: 2s ]

sensor:
  - platform: ld2410
    moving_distance: { name: "Moving distance" }
    still_distance:  { name: "Still distance" }
    moving_energy:   { name: "Moving energy" }
    still_energy:    { name: "Still energy" }
    g0: { move_energy: {name: "g0 move"}, still_energy: {name: "g0 still"} }
    # ... g1 through g8 — 18 series, engineering mode only
  - platform: veml7700
    ambient_light: { name: "Ambient light", id: lux }   # NOT `lux:` — Rev 1.5
    update_interval: 10s

number:                 # thresholds live HERE, in git — R9
  - platform: ld2410
    timeout: { name: "Timeout" }                    # 0–65535 s, default 5
    max_move_distance_gate: { name: "Max move gate" }   # range 2–8, default 8
    max_still_distance_gate: { name: "Max still gate" } # range 2–8, default 8
    # g0..g8 move_threshold AND still_threshold, from §5.9.
    # g0/g1 still_threshold is INERT but MANDATORY. Two sources, both right
    # about their own domain: PR Table 7 marks static sensitivity for gates 0
    # and 1 "-(not settable)" — the MODULE ignores it at 0–1.5 m. ESPHome makes
    # `still_threshold` cv.Required in every gX block regardless. Omit it and
    # the config does not compile; set it and nothing happens. Declare it as 0.
```

Structure the two rooms as a shared `common.yaml` plus per-device files using ESPHome's `packages:` remote_package mechanism.

**Factory defaults, for the flashed-but-uncalibrated state (PR Table 7, p.15).** Stated explicitly so a node that has never been through §5.9 says so in its own YAML rather than inheriting whatever is in module NVM:

| gate | move | still | | gate | move | still |
|---|---|---|---|---|---|---|
| 0 | 50 | 0 *(inert)* | | 5 | 15 | 30 |
| 1 | 50 | 0 *(inert)* | | 6 | 15 | 20 |
| 2 | 40 | 40 | | 7 | 15 | 20 |
| 3 | 30 | 40 | | 8 | 15 | 20 |
| 4 | 20 | 30 | | | | |

Note the shape before copying it: **move sensitivity falls with range (50 → 15) while still sensitivity stays high in the mid gates.**

**⚠️ "Factory default" is ambiguous — there are two published sets.** `LD2410C Docs/HLK-LD2410 Tool EN/appConfig.xml`, Hi-Link's own Windows tool, carries a *different* table:

| | g0 | g1 | g2 | g3 | g4 | g5 | g6 | g7 | g8 |
|---|---|---|---|---|---|---|---|---|---|
| **PR Table 7** move | 50 | 50 | 40 | 30 | 20 | 15 | 15 | 15 | 15 |
| **Tool** move | 50 | 50 | 40 | **40** | **40** | **40** | **30** | **30** | **30** |
| **PR Table 7** still | — | — | 40 | 40 | 30 | 30 | 20 | 20 | 20 |
| **Tool** still | 0 | 0 | 40 | 40 | **40** | **40** | **15** | **15** | **15** |

Also 5 s (PR) vs 3 s (`OffTime`, tool) for the no-one duration, and `MotionGateMax="9"` in the tool against PR §2.2.3's settable range of 2–8.

**Neither is wrong; they are defaults of different things.** PR Table 7 is headed *"Factory default configuration values"* — the module's NVM as shipped. `appConfig.xml` holds the tool's **UI** defaults — what it will *write* if somebody opens it and clicks apply.

**Two consequences.** First, an independent reason for §5.3a's decision: opening HLKRadarTool and applying without touching anything does not restore factory state, it writes a *third* configuration — different from both the module's shipped values and the committed YAML, with a 3 s timeout. Second, **"what are the defaults?" is the wrong question.** The only unambiguous answer comes from the module: press `query_params` and read back. The §4.1 push does that automatically, which is the check that makes the ambiguity harmless.

This table is PR Table 7, because the protocol document is a statement about the hardware and has been the more reliable source throughout (it beat the datasheet on the settable gate range). The values are a starting point that §5.9 replaces.

### 4.2 Control logic

**Rule: light level is sampled once, at the dark→occupied transition, and latched.**

```
state EMPTY_DARK:
    on presence:  if lux < THRESHOLD_ON:  lamp ON;  latch = TRUE
                  goto OCCUPIED

state OCCUPIED:
    lux is NOT evaluated while in this state
    on no-presence for IDLE_TIMEOUT:
        if latch: lamp OFF; latch = FALSE
        goto EMPTY_*  (re-sample lux to decide which)
```

If the node re-evaluated ambient light while the lamp it controls is on, and the lamp pushed the reading over threshold, it would turn the lamp off, go dark, and turn it back on. Forever. Hence the latch.

**Starting threshold: ~18 lx.** The basement VEML7700 reads **23–25 lx** with the lights on and dim — a level at which nobody would reach for a switch — so the transition sits just below. Because the VEML7700 outputs calibrated lux, that number transfers directly to these nodes and to any replacement sensor. That portability is what an uncalibrated phototransistor could not give and is the reason it was chosen.

### 4.3 Manual override detection (R4a)

**Source of truth: the controlled switch's own reported state.** A change the node did not initiate is a manual intervention.

```
on switch_state_change:
    if change was not commanded by this node within the last 2 s:
        manual_override = TRUE
        latch = FALSE

on room EMPTY for IDLE_TIMEOUT:
    manual_override = FALSE
```

Implementation depends on the switch: a smart relay reporting state is the clean case; a dumb lamp on a smart plug needs current sensing. **Whichever is used must be recorded in the baseline** — R4a is satisfied by a working detection path, not by intent.

---

## 5. Commissioning and calibration

A sequence. Order matters — later steps assume earlier ones passed.

### 5.0 Bench bring-up

| Step | Action | Pass |
|---|---|---|
| **0.0** | **Inspect the module before first power-on.** Confirm the silkscreen reads plain `LD2410C` with no other version marking; confirm 2.54 mm pin pitch and the TX/RX/OUT/GND/VCC order; measure VCC-to-GND resistance out of circuit. | see §9 item 1 |
| 0.1 | Power on USB. Measure VBUS at the module's VCC pin | 4.75–5.25 V |
| 0.2 | Confirm UART lock at 256000 | version reads back; 9600 is a contingency, not an equal default |
| 0.3 | Record radar firmware version | §5.11 |
| 0.4 | **GATED ON 0.2 AND 0.3 PASSING.** Disable module Bluetooth, **then reboot the module, then confirm still disabled** | reboot is REQUIRED for the command to take effect. BT is the recovery channel for a broken UART — do not close it before the UART is proven |
| 0.5 | Enable engineering mode; confirm 18 gate series appear | §5.9 depends on it |
| 0.6 | Confirm VEML7700 at 0x10; **cover the sensor completely and confirm it reads ~0 lx**; then compare against the basement node under similar light | dark reading ~0 confirms the LED jumper is cut; calibrated lux should agree |
| 0.7 | Wave a hand at 0.5 m | `has_moving_target` toggles, **and `Self-test passed` latches true** — see below |
| 0.8 | Verify OUT tracks presence | `radar_out` agrees with `has_target` |
| 0.9 | **Measure radar PCB thickness** | decides 10 mm vs 9 mm standoff (§3.4) |
| 0.10 | **Measure lid thickness** | update §3.5 |
| 0.11 | **Measure XIAO board-to-board gap as pre-soldered** | correct §3.4 if not 2.54 mm |
| 0.12 | Record as-built antenna-to-window and antenna-to-backplane | §5.10 control |

**Step 0.4 is not a persistence check — the reboot is part of the operation.** PR §2.2.12: *"the Bluetooth function of the module is **on by default**… After receiving this command, **a reboot is required for the function to take effect**."* Skip the reboot and the radio is still advertising while the switch reads off. Two further facts from the same source: an out-of-the-box module is advertising until this runs, and DS §6.3 gives the BLE configuration password as the default **"HiLink"**. That is the whole of §2's argument for shutting it down inside a sealed box — an unauthenticated config path with a known password, on a device with no other physical access.

**Steps 0.2, 0.3, 0.7 and 0.8 collapse into one entity.** Borrowed from Apollo Automation's MSR-2 factory test, which gates each sensor on producing a *plausible value* rather than merely being present — for the radar, `has_target && detection_distance > 10`. The bench firmware carries this as a latching `Self-test passed` sensor, and it is a stronger criterion than "the UART answered": **a module with a damaged antenna, a blocked aperture, or thresholds left at 100 will answer `query_params` perfectly and detect nothing.** UART health proves the crossover and the baud rate. Only a detection proves the radar.

**The Hi-Link iPhone app is the better fallback, and it expires at step 0.4.**

The module ships with Bluetooth **on** (PR §2.2.12), so the app works from first power-on with no preparation. Against the PC tool it wins on every axis that matters during bring-up: no USB-TTL adapter, no unwiring, and — the decisive one — **it is a parallel channel over the air.** ESPHome can be running and connected while the app is also connected. The PC tool requires removing the ESP to test the module, so it cannot separate *module dead* from *ESP wiring wrong* without a rewire in between; the app separates them with nothing touched.

> If `Radar firmware` is blank in ESPHome while the app shows the module reporting targets, the fault is in the UART wiring or the ESP. Conclusively, in seconds, without disturbing the rig.

*Unknown, worth observing:* whether the module streams UART and BLE concurrently without interference. PR describes them as parallel config channels but does not promise simultaneous operation. If connecting the app disturbs the UART, that is itself a finding.

**SEQUENCING — this dependency is load-bearing, not incidental.**

Step 0.4 disables Bluetooth, which closes this channel. It is recoverable — ESPHome exposes the `bluetooth` switch and PR §2.2.12 gives the command — but **recoverable only over the UART.**

> **Do not disable Bluetooth until the UART path is proven.** Disable it before 0.2/0.3 pass and then have the UART fail, and you have shut your own escape hatch: the channel you would use to diagnose the fault is the channel the fault has taken away.

The order below already places 0.4 after 0.3. Treat that as a gate rather than a sequence.

##### The fail-safe, in five parts

**The hazard is real and there is no hardware escape.** DS §4.2: the module has five pins — TX, RX, OUT, GND, VCC. **No reset pin, no boot pin.** A module unreachable over both UART and Bluetooth is unrecoverable, full stop.

But enumerating what can break UART reachability *while leaving a module worth recovering* narrows it to almost nothing:

| failure | does Bluetooth save it? |
|---|---|
| wiring or solder fault | no — fix the wire |
| ESP dead or misflashed | no — fix the ESP |
| module's UART peripheral dead | no — the radar is dead regardless |
| **baud rate changed** | **yes — and it is essentially the only one** |
| NVM corrupted mid-write | yes, but unquantifiable |

So the escape hatch guards one realistic failure. **Better to remove its cause than to preserve the hatch** — and then keep the hatch as well, since it is nearly free.

**1. Remove the cause. `baud_rate` is not exposed in either firmware.** The ld2410 select platform offers it; both configs omit it, and that omission is now a documented decision at the site rather than an accident someone tidies up. One accidental tap on a dropdown should not be able to strand a part that has no reset pin.

**2. Prove the hatch reopens *before* closing it.** Step 0.4 becomes a round trip:

> BT **off** → reboot → confirm off → BT **on** → reboot → confirm on → BT **off** → reboot → confirm off

Two extra reboots. It converts *"I believe I could turn this back on"* into *"I have turned it back on."* Anything that makes the switch one-way — a firmware quirk, an NVM fault — surfaces here, on a bench, with the module in your hand and the app still working.

**3. Do not disable Bluetooth on the bench at all — defer step 0.4 to assembly.** §2's coexistence case is about a *sealed enclosure with a 24 GHz antenna 10 mm from a Wi-Fi radio*. None of that is true of a module on jumpers. Keep BT on through bring-up, close it when the module goes into the box — by which point the UART has been proven for hours rather than minutes. The verification in part 2 still happens at the bench, where recovery is easy; only the final disable moves.

**4. Keep the second module factory-fresh.** The BOM bought a 2-pack. Leave the spare untouched — BT on, factory thresholds, never configured. It is a known-good reference instrument: if the first module behaves strangely, swapping it answers *"is this the module or is this me"* in one step. That is §6.2's two-independent-instruments principle applied to the part itself.

**5. If it happens anyway, the baud sweep recovers it without Bluetooth.** The documented rates are:

`9600 · 19200 · 38400 · 57600 · 115200 · 230400 · 256000 (default) · 460800`

`radar_baud` is a substitution at the top of `mmwave-bench.yaml`. Change it, reflash, watch `Radar firmware`. **Eight attempts, roughly ten minutes, using only what is already on the bench.** This is the reason part 1 matters more than part 2: the failure it guards is the one failure that is also recoverable by brute force.

**A use for the app beyond diagnosis: make §2's security argument concrete.** The module is advertising right now, with the BLE configuration password at its factory default of `HiLink` (DS §6.3). Connect to it with the app before step 0.4 and observe how little stands in the way. That is the abstract "one less unauthenticated config path" in §2 turned into something seen rather than asserted — and it is the best possible argument for why 0.4 exists, delivered thirty seconds before you carry it out.

The same discipline applies as to the PC tool: **read-only, no auto-calibration except under §5.3a's protocol.** The app can run the background-noise routine exactly as HLKRadarTool can, and the R9 objection is identical.

**HLKRadarTool — extracted and ready, deliberately unused.** The tool is in `LD2410C Docs/` and needs no installation (no installer, no registry; extract, run, delete). It is **not part of the bench sequence**, because that sequence exists to validate the ESPHome path — the one that runs in production — and a second tool in play means a success cannot be attributed and a failure has two suspects.

Its value is as a **tiebreaker**. It reaches the module through an entirely independent route: different host, different driver, different codebase, no ESP32. If `Radar firmware` stays blank after the crossover and 9600 have both been tried, the tool answers *is this module alive at all* — the same two-independent-instruments logic §6.2 applies to the two presence paths, used for bring-up instead.

**It requires a 3.3 V USB-TTL adapter**, wired to the module's TX/RX/GND with a separate 5 V feed. Confirm one is on hand *before* it is needed; without it this fallback does not exist.

Rules if it is run:

1. **Read-only. Connect, observe, do not apply.** Applying without changing anything writes a *third* configuration — neither the module's factory state nor the committed YAML, with a 3 s timeout (§4.1).
2. If anything is written, press `query_params` from ESPHome afterwards and reconcile against the YAML. The §4.1 push exists so git can reassert itself.
3. **Auto-calibration only under §5.3a's protocol** — room verified empty by something that is not the radar, values read back into the YAML, date logged.
4. Keep it in its own folder. Unsigned executable, manufacturer with no authorised distributor (§9 item 1), arriving via a Drive export rather than a signed download. Not a reason to refuse the vendor's own tool; a reason not to install it permanently.

**Step 0.5 note.** Engineering mode is **volatile**: PR §2.2.5, *"Engineering mode is off by default after the module is powered on, this configuration value is lost when power is lost."* It is not an NVM setting and cannot be left on — the firmware must re-enable it after every boot. This is why §6.1's duty cycle is a scheduled action rather than a stored state.

### 5.1 Placement and aim

Geometry first, thresholds second.

**Depression angle** = atan((h_sensor − h_torso) / d_target)

| Install | h_sensor | h_torso | d | angle |
|---|---|---|---|---|
| Family room, mantel | 1.3 m | 0.9 m (seated) | 4 m | **5.7° down** |
| Office, desk | 0.75 m | 1.2 m (seated) | 1.2 m | **19° up** |

Opposite tilts — feet under the rear edge for the mantel, front edge for the desk.

**Rev 1.5 — both installations sit below Hi-Link's mounting guidance. Recorded as a deviation.**

DS §5.4 gives wall-mount height as **1.5–2 m** (its detection-pattern figures are drawn for 1.5 m at 5 m range), and ceiling mount as 2.6–3 m.

| install | planned height | vs DS §5.4 |
|---|---|---|
| Family room, mantel | 1.3 m | 0.2 m low |
| Office, desk | 0.75 m | **half the minimum** |

The office node firing 19° upward at a seated torso from 0.75 m is well outside the geometry those patterns describe. Both placements are fixed by the room and are not being changed.

**Why this is recorded rather than fixed:** §5.2a's coverage sweep already establishes coverage empirically, which is the right mitigation and does not depend on the datasheet's figures. What the deviation buys is a *diagnosis rule*. If the sweep finds a hole, or if §5.9 returns `SM ≤ 1` at a seat, the height deviation is a live hypothesis and belongs in the same bucket as §5.9.4's "bad geometry is not a bad threshold" — not something to be chased in thresholds. Without this note, the deviation is invisible at exactly the moment it would explain the symptom.

- Clear the 0.5 m immediately in front. Clocks, frames and candles are strong near-field reflectors.
- **Weight the box.** Movement of the sensor is indistinguishable from movement in the room.
- **Aim the VEML7700 deliberately** and record where it points. On a 150 mm cable its view is a choice, not a consequence of board layout.

### 5.2 Range gate mapping

**Map by gate energy, not reported distance.** HLK state ranging is deliberately weakened in favour of detection. Per-gate energies are direct measurements; distance is derived and admitted poor.

Stand at measured floor marks at 0.75 m intervals, hold 30 s each, record which gate's `move_energy` rises.

**Set max move gate** to the first gate beyond the far wall — the R6 mitigation. **Settable range is 2–8**, confirmed at PR §2.2.3 ("configuration range 2~8"). *DS p.8 says "1 to 8" and is the wrong one* — another case where the older datasheet loses to the protocol document. Factory default for both max gates is 8, with a 5 s no-one duration (PR Table 7).

**A second, finer R6 mechanism: gate blanking.** DS §5.2 and PR p.8 — *"if the sensitivity of a certain distance gate is set to 100, the effect of not recognizing the target under the distance gate can be achieved."* Setting a gate's sensitivity to 100 blanks **that gate alone**, where the max-gate cap truncates everything beyond a point. Useful when §5.4 identifies one contaminated gate mid-range that the cap cannot reach without also discarding good range.

**Deliberately not automated.** Blanking a gate *inside* the room creates a dead zone, and a person standing in it is invisible — an R1 failure introduced by a tuning convenience. `scripts/mmwave_calibrate.py` reports gates as unoccupied but never emits 100 for them; that decision stays with a human looking at a floor plan.

Drywall attenuates 24 GHz but does not block it, and studs, plumbing and wiring make attenuation position-dependent. Gate capping reduces through-wall detection; A7 measures what remains.

### 5.2a Coverage sweep — before any threshold work

With default thresholds, log presence and all gate energies while:

1. Walking a grid across the room, ~1 m spacing
2. Repeating at standing and seated heights
3. Repeating close to each wall
4. Repeating beside and behind each major piece of furniture
5. Walking the hallway behind the wall

Produce a coverage map. **This exists to prevent hours spent making a marginal gate statistically beautiful when the problem is geometry.** Any dead zone is fixed by moving or re-aiming (§5.1), not by thresholds. This also produces the first real measurement against the 5.6 m target in §3.6.

### 5.3 Data collection

| # | Condition | Duration | Sets |
|---|---|---|---|
| **A** | Empty, HVAC off | 1 h | clean noise floor (reference) |
| **B** | **Empty, HVAC + fan running**, worst time of day | 1 h | **move thresholds** |
| **C** | Occupied, motionless, one run per seat | **10 min each** | **still thresholds** |

Collection B is the one people skip and it drives false positives. The move threshold must clear the register's Doppler, not the quiet-room floor.

**Why 10 minutes.** It captures multiple breathing and posture cycles and yields a robust empirical distribution. *Earlier revisions claimed ~150 effective independent observations from an assumed 4 s decorrelation. That inference was too strong — breathing rate does not establish independence in a signal subject to DSP filtering and target tracking.* Instead: **compute the autocorrelation of `still_energy` from collection C and report the observed decorrelation lag and effective sample size.** Free once the data exists.

**Label in-band.** An HA `input_select` — `empty` / `empty_hvac` / `seat_sofa_L` / `seat_sofa_R` / `seat_armchair` / `seat_desk` — set as each run starts, logged alongside the energies. The analysis becomes a group-by.

**Watch gate crosstalk.** A person at gate 4 raises energy in gates 3 and 5. The *empty* class must be a genuinely empty room.

### 5.3a Calibration hygiene — auto-calibration rejected

Per-gate thresholds live in module NVM and are **not** re-derived at power-on. Static-clutter cancellation is a running process with no memory across power cycles, and a motionless person's micro-Doppler survives it. **A power cycle in an occupied room does not "learn the person as furniture."**

What *does* bake a person in is running the automatic background-noise routine while occupied. That routine is user-invoked: leave the room, press **Auto** in HLKRadarTool, it starts after 10 s and runs ~60 s.

PR §2.2.20 confirms the mechanism this section warns about, in the manufacturer's own words: the routine *"will automatically calculate and record the energy value on each distance door under unmanned conditions… After the detection is completed, the sensitivity value of each distance door will be automatically configured based on the detected background noise value."* **It overwrites the committed thresholds in module NVM.** One useful accident of the §4.1 design: the `number` entities carry `restore_value: true`, so ESPHome pushes the YAML values back at the next boot — the git state reasserts itself without anyone intervening. Do not rely on that; it is a side effect, not a guard.

**Decision: do not use auto-calibration as the primary method.**

1. **Not reachable from ESPHome** — the `ld2410` component exposes only `factory_reset`, `restart`, `query_params`. *Rev 1.5: this is a statement about today's ESPHome, not about the hardware.* The capability is in the module and in the protocol — PR §2.2.20 *"Start performing background noise detection and automatic sensitivity configuration"*, with §2.2.21 to poll its status, both added in **PR V1.07 (2024-08-05)**. A future component release could expose it, so **reason 2 is the one that has to carry the decision**, because it is the one that will still be true then.
2. **It violates R9** — opaque values in device NVM, not in git, not diffable, don't survive a module swap.
3. **§5.9 produces the same thing as declared values in the YAML** — reviewable and reflashable in seconds.

If ever run as a cross-check: verify the room is empty independently first, read the values back into the YAML, log the date.

**A caution from the field about the R9 push itself.** Screek's published notes say they "abandoned setting it in the esphome and used the HLKRadarTool configuration instead" — i.e. a shipping manufacturer gave up on configuring the LD2410 over ESPHome and moved the parameters into module NVM out-of-band. That is precisely the R9 failure this document rejects, so the answer is not to copy them; but it is evidence that the ESPHome configuration path is finicky, and the boot-time push (§4.1) is the newest and least proven thing in this firmware.

**Mitigation, and it is already free:** the push script ends by pressing `query_params`, which makes the module re-report its ACTUAL parameters. So the verification is a read-back, not an assumption — at §5.0, push, query, and confirm the numbers HA shows match the YAML. If they do not, that is the finding, and it is better found on a bench than inferred from a node that seems to work.

### 5.4 Clutter identification

Static furniture is not the problem — FMCW clutter removal cancels stationary objects. A sofa has no micro-Doppler; a person does, even asleep.

Non-human *motion* is, and collection B finds it. Any gate with sustained move energy in an empty room is contaminated.

| Source | Fix |
|---|---|
| Supply register | raise that gate's **move** threshold only |
| Ceiling fan | as above, or re-aim so it is behind the radar |
| Curtains | as above |

Leave the **still** threshold alone — they are independently settable and the false trigger is a Doppler artifact.

Second-order: a strong static reflector leaves cancellation residue that raises the micro-Doppler floor *in that gate*. If §5.9 shows poor separation at a seat that isn't shadowed, this is the likely cause.

### 5.5 Idle timeout

| Room | Setting |
|---|---|
| Office | 60–120 s |
| Family room | 300 s+ |

Err long. The failure the occupant resents is the light going off on them. The failure nobody notices is it staying on five minutes too long. The timeout also sets the acceptance criterion in §5.9.3.

### 5.6 Light threshold

The VEML7700 outputs **calibrated lux**, so thresholds are portable across nodes and survive a sensor swap.

1. Cross-check against the basement node under similar light (§5.0 step 0.6).
2. Log lux over 24 h in situ with the lamp **off**.
3. `THRESHOLD_ON` ≈ **18 lx** — just below the 23–25 lx the basement reads when lit but dim.
4. `THRESHOLD_OFF` ~20% above, for hysteresis on the empty-room re-evaluation.

Then verify R4 directly: **turn the lamp on manually and confirm the reading is recorded but not acted upon.**

### 5.7 Acceptance test

| # | Test | Criterion |
|---|---|---|
| **A1** | **Entry latency, n ≥ 30.** Vary start location, approach angle, speed, time of day. Log **both** door→`radar_out` (sensor) and door→HA presence (system). Report n, min, median, P90, P95, max. | **system median ≤ 1.0 s, P95 ≤ 1.5 s** |
| A2 | Sit motionless in every seat, 15 min | No dropout |
| A3 | Enter lit room | Light does not switch |
| A4 | Occupy 30 min with lamp on | No oscillation; lux not re-evaluated |
| A5 | Leave room | Light off within timeout + 30 s |
| A6 | Empty, HVAC and fan running, 2 h | Zero false triggers |
| A7 | Walk the hallway behind the wall, 10 passes | Zero triggers |
| A8 | Manual switch override | Detection path fires (R4a); node yields until room next empty |
| A9 | Power cycle in an **empty** room | Boots and runs — validates §3.3 |
| A10 | Power cycle with someone **sitting still** | Recovers unaided. Expect a gap while ESP and radar boot and the UART syncs. Confirm no *persistent* dropout. |
| A11 | Disconnect Home Assistant, repeat A1 | Behavior per §7 |
| A12 | **Wi-Fi link.** RSSI at commissioning, radar idle, radar active, module BT on, module BT off | Set the limit from this node's own baseline |
| **A12a** | **Does this node's own Wi-Fi contaminate its radar?** Empty room, engineering mode, 10 min of gate energies at `output_power: 20dB` (default), then 10 min at `15dB`. Compare the per-gate empty-room medians and P99.5. | **No material change in the empty-room floor.** If the floor *drops* at 15 dB, the ESP is desensitising the receiver and §2's ground plane is not sufficient on its own |

**n ≥ 30 for A1.** With ten observations P95 *is* the maximum. At n = 30 there are 1.5 observations above it. R2 drove the module selection, so it deserves the sample size.

A9, A10 and A11 test the unattended moment specifically.

### 5.8 Baseline capture

- All gate move/still thresholds — **in the YAML, committed**
- Max move gate, max still gate, idle timeout
- **A1: n, min, median, P90, P95, max — sensor and system latency separately**
- A12 RSSI set
- Per-gate energy, collections A and B — median, MAD, P95, P99.5
- Per-gate still energy, collection C, per seat — P5, median, **and §5.9.3 sustained-dropout metrics**
- **Separation margin SM and absolute margin M per gate**
- **Measured autocorrelation lag and effective sample size**
- Lux 24 h profile; basement cross-check reading
- **As-built antenna-to-window and antenna-to-backplane**
- Manual-override detection mechanism used (R4a)
- **Version set per §5.11**

### 5.9 Threshold selection

**Do not use mean ± kσ.** Gate energies are bounded 0–100 and heavily right-skewed; the quantities of interest are the tails.

```
E_clutter = P99.5( collection B — empty, HVAC running )   ← false-positive driver
E_signal  = P5(    collection C — occupied, motionless )   ← false-negative driver
```

Named for the distribution, not the percentile — an external reviewer read the previous `E_hi`/`E_lo` naming backwards. `E_clutter < E_signal` when the gate is usable.

#### 5.9.1 Initial estimate

`T_0 = sqrt(E_clutter × E_signal)` — geometric because both distributions are right-skewed. **A starting estimate, not the selection method.**

#### 5.9.2 Threshold sweep — the actual method

For each candidate T from 0 to 100:

```
FPR(T) = fraction of collection B samples > T        # false triggers
FNR(T) = fraction of collection C samples < T        # dropouts
L(T)   = longest continuous interval in C with energy < T
```

Plot FPR and FNR against T. That operating curve is the defensible basis for the choice.

**Selection rule.** The detector fires on `energy > threshold`, so lower is more sensitive: fewer false negatives, more false positives. Since a false negative — the light going off on someone reading — costs far more than a lamp on five extra minutes, **choose the lowest T that holds FPR acceptable**. In practice T lands below `T_0`, toward `E_clutter`.

#### 5.9.3 Sustained dropout — the metric that matches R1

R1 says "indefinitely," which is temporal. P5 is not: it says 5% of samples fall below a level, not whether they're scattered or form one 90-second gap.

Compute the 30 s and 60 s rolling minima, and **`L(T)`, the longest continuous interval below threshold**.

```
L(T) < IDLE_TIMEOUT / 3
```

| Idle timeout | Max acceptable L(T) |
|---|---|
| 60 s | 20 s |
| 120 s | 40 s |
| 300 s | 100 s |

The idle timeout bridges momentary dropouts. If the longest gap approaches it, the light goes off on a stationary occupant regardless of what P5 says. The factor of three is margin for postures not captured in 10 minutes.

#### 5.9.4 Diagnostic margins

```
SM = E_signal / E_clutter      # separation margin
M  = E_signal − T              # absolute margin
```

| SM | Meaning | Action |
|---|---|---|
| **> 2** | Comfortable | Set T, move on |
| **1–2** | Marginal | Bias T low, watch in §6.3 |
| **≤ 1** | **Distributions overlap — no threshold works** | **Stop tuning.** Seat is shadowed or a reflector raised the residue floor. Move the sensor, return to §5.1. |

**Record M as well as SM.** Two gates can share an SM at very different absolute levels — E_clutter 10 / E_signal 30 and 40 / 120 both give SM = 3, but the second operates far higher in the dynamic range.

**The `SM ≤ 1` rule is the most important line in this section.** Bad geometry is not a bad threshold.

#### 5.9.5 Queries

Flux templates — adjust bucket, measurement and tag names to the local schema.

```flux
// E_clutter — empty, HVAC running, per gate
from(bucket: "homeassistant")
  |> range(start: <B_start>, stop: <B_stop>)
  |> filter(fn: (r) => r._measurement =~ /^g[0-8]_move$/)
  |> group(columns: ["_measurement"])
  |> quantile(q: 0.995, method: "estimate_tdigest")

// E_signal — occupied and motionless, per gate, per seat
from(bucket: "homeassistant")
  |> range(start: <C_start>, stop: <C_stop>)
  |> filter(fn: (r) => r._measurement =~ /^g[0-8]_still$/)
  |> filter(fn: (r) => r.seat == "sofa_L")
  |> group(columns: ["_measurement", "seat"])
  |> quantile(q: 0.05, method: "estimate_tdigest")
```

The sweep, `L(T)`, autocorrelation and margins are computed outside the query — a Python script **committed next to the YAML** so the derivation is reproducible, not just the answer.

### 5.10 Module A/B protocol — deferred

No LD2412S was purchased for the first build. Retained as a documented experiment.

**Control for mechanical geometry.** Different module sizes mean different antenna positions and different antenna-to-window distances. Record as-built dimensions for each build (§5.0 step 0.12) or geometry effects will be misattributed to module generation.

| | LD2410C | LD2412S |
|---|---|---|
| Antenna-to-window, as built | | |
| A1 sensor latency — median / P95 | | |
| A1 system latency — median / P95 | | |
| SM / M / L(T) at the far seat | | |
| Contaminated gates (collection B) | | |

### 5.11 Version freeze

"Same YAML" does not mean "same firmware." LD2410/ESPHome compatibility regressions have shipped, including UART-related ones.

Record and pin: ESPHome version, ESP-IDF/framework version, `ld2410` and `veml7700` component revisions, radar firmware version, YAML commit hash, threshold table.

Pin the ESPHome version explicitly rather than tracking latest. Upgrade deliberately, and re-run A1, A2 and A6 before trusting it.

**Rev 1.5 — mechanise it.** Both firmwares now carry `esphome: min_version: 2026.4.3`, so the build *fails* on anything older instead of relying on someone remembering this paragraph. That is the version installed on the Windows box and the floor both configs were validated against; they also pass on 2026.8.2.

The concrete case for this: HA core issue #123732 reports eight LD2410 sensors going to "unknown state" after ESPHome 2024.7.3 — **closed as *not planned*, with no root cause and no documented fix**. A regression that was never explained is worse than a known bug, because nothing tells you when it comes back. Raise the floor deliberately after re-running A1, A2 and A6, never as a side effect of an upgrade.

---

## 6. Telemetry

### 6.1 Rates and engineering-mode duty cycle

Per-gate energies exist **only in engineering mode**, which carries extra resource cost and shouldn't be left on indefinitely. But those energies are R8's early-warning mechanism and the input to every §6.3 response.

**Resolution: production runs with engineering mode off, plus a scheduled sampling window.**

| Mode | Eng. mode | Rate | Purpose |
|---|---|---|---|
| Production (default) | OFF | 1/min | presence, lux, RSSI |
| **Daily SPC window** | **ON, 10 min** | **1 Hz** | **per-gate baseline sample** |
| Event-triggered | ON | 1 Hz, 60–120 s | presence transitions |
| Diagnostic | ON | 1 Hz, 10 min | investigate a §6.3 trigger |
| Commissioning | ON | 1 Hz | §5.3 collections |

A daily 10-minute window gives 365 well-sampled points per gate per year — ample for seasonal drift. Schedule it at a fixed hour when the room is normally empty, so it doubles as a clean noise-floor observation.

**Volume, 18 gate-energy series only:**

| Rate | pts/day/node |
|---|---|
| 1 Hz continuous | 1,555,200 |
| 1/min continuous | 25,920 |
| **Daily 10-min at 1 Hz** | **10,800** |

Lux, both presence paths and RSSI add to these; the figures are the gate series alone.

### 6.2 The two-path cross-check

The two presence paths disagreeing is the most useful diagnostic this node produces. Both derive from the same radar but travel different routes into the ESP. Sustained disagreement means the UART desynced or the component stalled — a failure that would otherwise look like "the sensor stopped working."

### 6.3 SPC drift response — robust limits

Baseline statistics: median and MAD, plus P95 and P99.5, from the commissioning collections and the first 30 days of daily windows.

```
upper limit = median + 3 × 1.4826 × MAD      (σ-equivalent, robust)
or          = baseline P99.5                  (distribution-free, preferred for skewed series)
```

Drift detection: EWMA on the daily median (λ ≈ 0.2) for gradual drift, CUSUM for step changes. *Earlier revisions used 3σ on the raw signal, contradicting §5.9's own rejection of Gaussian assumptions.*

| Signal | Trigger | Response |
|---|---|---|
| Per-gate empty-room move energy above robust limit | EWMA excursion >3 days | New clutter. Investigate physically, **re-run collection B and §5.9**. |
| Per-gate still energy at a seat below robust lower limit | EWMA excursion >3 days | Sensitivity degrading or furniture moved. **Re-run collection C and §5.9.** |
| SM at any seat below 1.5 | — | Approaching unsolvable. Investigate geometry. |
| L(T) at any seat exceeds IDLE_TIMEOUT/3 | on re-measurement | R1 at risk. Re-run §5.9. |
| A1 median latency drifts >50% | vs baseline | Firmware change or radar degradation |
| Lux daytime peak declines steadily | >20% over a season | Window fouling. Clean the lid, re-check §5.6. |
| UART and OUT presence disagree | >5 min | Firmware or UART fault |
| RSSI degrades vs A12 baseline | >10 dB sustained | Antenna moved or enclosure disturbed |

Every response is **re-run a documented procedure and commit the new values** — never trigger an opaque auto-calibration. That is what R9 buys.

**Re-run collection B in heating season.** The register quiet in October runs constantly in January. This is the R8 slow variable and the most likely cause of a node that worked at commissioning and misbehaves four months later.

---

## 7. Degradation ladder

**Architectural classification.** Automatic lighting is **convenience functionality**. Manual lighting remains **authoritative and operationally independent**. Failure of the automation path is *loss of convenience with manual recovery*, not system failure.

| Failure | Consequence | Mitigation |
|---|---|---|
| Wi-Fi down | Automation unavailable | Wall switch authoritative |
| Home Assistant down | Automation unavailable | Wall switch authoritative |
| ESPHome component stalls | UART presence stale | Hardware OUT still valid; alert on disagreement (§6.2) |
| Power blip | Brief gap, then recovery | Verified by A10 |
| Radar module fails | No automatic presence | Wall switch; telemetry gap visible in Grafana |
| VEML7700 or its cable fails | I²C errors; no light reading | Sanity bound: if lux unavailable >1 h, hold the last valid value and alert |
| Node loses power | Lamp stays in last state | Wall switch |
| Module replaced | Thresholds restored from YAML in seconds | R9 |
| Light sensor replaced | **Threshold transfers unchanged** | calibrated lux — §5.6 |

**The open item.** The control decision lives in Home Assistant, putting HA between presence and photons. Options: accept it under the convenience framing; move the decision to the ESP driving a smart relay with HA observing; or a local relay on the node, which turns a low-voltage sensor into a mains device.

**Rev 1.5 adds a fourth option this document did not know about: the decision can live in the radar module itself.**

PR §2.2.18's light-sensing auxiliary control gates the OUT pin on the module's own photodiode. Its logic is worth reading closely, because it is *the same state machine as §4.2*:

> "The OUT pin output changes from unmanned to manned… needs to meet the following conditions: the radar detects the presence of a person **and** the light sensing auxiliary control logic condition is met. The OUT pin output changes from manned to unmanned… needs to meet the following requirements: **radar detects unmanned**."

Light is evaluated **only on the ON transition**. The OFF transition depends on presence alone. That is §4.2's latch — *"light level is sampled once, at the dark→occupied transition, and latched"* — implemented in the module's firmware, and arrived at independently by Hi-Link for the same reason: without it, a lamp that lights its own sensor oscillates forever.

**And it is reachable from ESPHome today — three keys, no custom component.** `number.light_threshold` (0–255, default 128), `select.light_function` (`off` / `low` / `above`, default `off`), and `select.out_pin_level` (`low` / `high`, default `low`) are all on the standard `ld2410` platform. This is a configuration change, not a development project. *(Distinct from §5.3a's auto-calibration, which remains genuinely unreachable from ESPHome — different command, different argument.)*

**Not adopted as primary, for three reasons that all still hold:**

1. The threshold is a 0–255 photodiode count, not lux. It is specific to one part in one orientation and transfers to nothing — the opposite of §5.6's portability argument.
2. It lives in module NVM. Opaque, not diffable, does not survive a module swap. **R9.**
3. The photodiode looks wherever the antenna looks. §2 moved the light sensor off-board precisely so it could be aimed independently. It is also **engineering-mode only** in ESPHome (`light` reads `unknown` otherwise), and §6.1 runs production with engineering mode off — so as a telemetry channel it is unavailable by design, though the module's internal OUT gating does not depend on ESPHome reading it.

**But it is a real degraded-mode floor, and it costs nothing to hold in reserve.** With OUT gated this way, a node with Wi-Fi down, HA down, or the ESP dead still drives a correct presence-and-dark signal on a wire. That is a strictly better failure mode than the ladder above describes, and it needs no mains hardware on the sensor board. Worth revisiting alongside the "move the decision to the ESP" option after a season, not before.

Recommendation: accept HA-in-the-loop for the first build, revisit after a season. Don't turn the first sensor into a mains appliance before the sensing is proven.

---

## 8. Verification log

| Item | Status | Source |
|---|---|---|
| **`Radar firmware` populates 403 s after boot, not at boot** | ✅ **measured 2026-09-07** | Bench rig. MAC and `gate_resolution` come from the same deferred config read. Gating commissioning on any of them costs ~6.7 min per boot; engineering-mode gate frames prove the same thing in seconds |
| **`switch.radar_bluetooth` is not a readback** | ✅ **measured 2026-09-07** | Read `off` while the module was connected to the Hi-Link app, `on` after a reflash with the radio untouched. §5.0 step 0.4's pass criterion moved to the app |
| **The module streams UART and BLE concurrently** | ✅ **measured 2026-09-07** | 10 polls / 30 s with the app connected: continuous updates, zero stale reads. Closes §5.0's "unknown, worth observing" |
| **Engineering mode does not survive a threshold push or a `Radar restart`** | ✅ **measured 2026-09-07** | Photodiode + all 18 gate energies `unknown` for 5 min 21 s after a push. PR §2.2.5 says volatile; this is what volatile costs. Production fires that push at boot |
| **R9: 21/21 restored from a fully scrambled radar by the boot push** | ✅ **measured 2026-09-07** | All 21 set to distinct wrong values, node rebooted, every one restored from substitutions. ~2 s for 21 writes |
| **Gates 0/1 accept static-sensitivity WRITES despite PR Table 7** | ✅ **measured 2026-09-07** | Scramble took on `g0_still`/`g1_still` and reverted cleanly. The module stores what it will not use — the write path is not the inert part |
| **End-to-end latency, presence → lamp physically on: 567 ms and 777 ms** | ✅ **measured 2026-09-07** | Node decision 278–777 ms (1 s control tick), HA → Kasa ~290 ms. Inside R2's 1000 ms median budget. This is the number R2 is actually about; the 2 ms path skew is not |
| **Two-path skew: 2 ms** | ✅ **measured 2026-09-07** | UART frame vs the OUT wire, rising edges 0–1 ms apart across five transitions. Falling edges differ by 2.0–2.7 s, which is the `delayed_off: 2s` filter and is why §6.2 uses a 300 s window |
| **Through-wall detection is real and was firing the lamp** | ✅ **measured 2026-09-07** | A person in the bathroom next door read 7.4–10.3 ft, gates 3–4, move energy 52 and 100 against thresholds of 30 and 20. Office entry is gates 0–2. §5.2's gate cap is not theoretical |
| **§6.1's SPC window closes correctly** | ⚠️ **close verified 2026-09-07, open and midnight wrap not** | Closer fired 24 s after boot with `(now − start + 1440) % 1440` = 20. The `on_time` open half has never run, and the midnight wrap the `+1440` exists for needs an overnight run |
| **Bench recorder cost: ~1.4 M rows/day at 1 s gates** | ✅ **measured 2026-09-07** | 18 gate series ≈ 44,500 rows/h alone. For scale the basement TH node is ~58,000/day and already carries exclusions. Gate period moved to 5 s; see `gate_log_period` in production |
| LD2410C pin order TX/RX/OUT/GND/VCC | ✅ | **DS §4.2 Table 1** + photo. Numbering is 1=TX … 5=VCC — §3.2's table was inverted before Rev 1.5 |
| **LD2410C operating voltage DC 5V, IO level 3.3V** | ✅ | **DS §7 and §5.1.** Supply capacity > 200 mA, average current 79 mA. DS §4.2 pin table adds "5~12V (advise 5V)". No documented 3.3V-only variant found |
| **Radome standoff H = 1λ or 1.5λ; 12.4 / 18.6 mm at 24.125 GHz; ±1.2 mm** | ✅ | **DS §8.3, verbatim.** Previously the most load-bearing secondhand number in this document — now first-party |
| Max move/still gate settable range 2–8 | ✅ | **PR §2.2.3.** DS p.8's "1 to 8" is the wrong one |
| No-one duration range 0–65535 s, default 5 s | ✅ | PR §2.2.3, PR Table 7 |
| Factory gate sensitivities (the table in §4.1) | ⚠️ **two sets exist** | **PR Table 7** (module NVM as shipped) and **`appConfig.xml`** in HLK's own Windows tool (the tool's write-on-apply defaults) disagree for gates 3–8, and on the no-one duration (5 s vs 3 s). Neither is wrong; they default different things. §4.1 |
| Static sensitivity inert on gates 0 and 1, but `still_threshold` is still mandatory in YAML | ✅ | **PR Table 7** ("-(not settable)") **and** ESPHome `components/ld2410/number/__init__.py` (`cv.Required` in every gX). Declare it as 0; the module ignores it |
| ESPHome applies `settle: 1000ms` to every ld2410 binary sensor by default | ✅ | `components/ld2410/binary_sensor.py`. **`settle` publishes the change immediately** then suppresses further changes for 1 s — it is not `delayed_on` and **does not spend any of R2's budget**. Do not "fix" it |
| ESPHome applies `throttle_with_priority: 1000ms` to every ld2410 sensor by default | ✅ | Declaring `filters:` REPLACES it — nothing is inherited |
| `out_pin_presence_status` binary sensor — the module reports its own OUT pin over UART | ✅ | ESPHome ld2410 binary_sensor platform. Engineering mode only. A **third** presence path, and a direct check on the OUT wiring |
| ESPHome `light` sensor and `light_threshold` / `light_function` / `out_pin_level` exist on the **ld2410** platform | ✅ | ESPHome ld2410 docs — not LD2412-only. `light` is 0–255, engineering mode only; `light_threshold` 0–255 default 128; `light_function` off/low/above; `out_pin_level` low/high default low |
| `timeout` default 5 s; max gates 2–8 default 8; `baud_rate` select exists | ✅ | ESPHome ld2410 number and select platforms — agrees with PR Table 7 |
| Sensitivity 100 blanks a single gate | ✅ | DS §5.2, PR p.8 — the finer R6 mechanism, §5.2 |
| Engineering mode is volatile, off at every power-on | ✅ | **PR §2.2.5** — "lost when power is lost"; must be re-enabled by firmware after each boot |
| Bluetooth ON by default; OFF needs a reboot to take effect | ✅ | **PR §2.2.12.** BLE config password defaults to "HiLink" (DS §6.3) — §5.0 step 0.4 |
| Background-noise auto-calibration exists in the protocol | ✅ | **PR §2.2.20 / §2.2.21**, added in PR V1.07 (2024-08-05). Overwrites gate sensitivities in NVM. Rejected on R9 grounds, not availability — §5.3a |
| OUT pin idle level is a configurable parameter | ✅ | **PR §2.2.18**, third config byte. Default is idle-low. §3.3's pin choice is safe under either |
| LD2410C has its own photodiode | ✅ | **PR §2.2.18** — value rides in engineering-mode data. 0–255 count, not lux; does not displace the VEML7700 (§5.6). Struck the §0 row that implied otherwise |
| Sweep bandwidth 250 MHz → c/2B = 0.6 m | ✅ | DS §7 — 0.75 m gate depth is a physical limit, not a chosen quantisation |
| Detection angle ±60° | ✅ | DS §7 |
| Metal backplane shields the back lobe; concern is *moving* objects behind | ✅ | DS §5.5 — confirms §3.7's reasoning |
| Radar shake is indistinguishable from room motion | ✅ | DS §5.5 — confirms §5.1's "weight the box" |
| Clutter sources: animals, curtains, plants at an air outlet, fans, A/C | ✅ | DS §5.5 — matches §5.4's table |
| LD2410C 16 × 22 mm, 2.54 mm pitch | ✅ | photo |
| Antenna = 1 TX + 1 RX patch | ✅ | photo |
| LD2410C default baud 256000, 8N1 | ✅ | Hi-Link protocol doc (9600–460800 supported) |
| LD2412 response 2–3 s slower than LD2410C | ✅ | Screek — testimony against interest |
| LD2412 ranging deliberately weakened | ✅ | HLK developers via Screek |
| Gate thresholds persist in NVM, not re-learned on boot | ✅ | Hi-Link docs + component behaviour |
| Background auto-cal is user-invoked, room must be empty | ✅ | HLKRadarTool procedure |
| ESPHome `ld2410` cannot trigger calibration | ✅ | component exposes 3 buttons |
| **Adafruit 4397 = JST-SH one end, female sockets the other** | ✅ | **Adafruit / RS / Jameco — the correct cable for a colour-coded header** |
| Qwiic colour convention red/black/blue/yellow = 3V3/GND/SDA/SCL | ✅ | Adafruit |
| VEML7700 I²C address 0x10, calibrated lux | ✅ | **Adafruit VEML7700 guide p.24** ("default I2C address of 0x10") |
| VEML7700 range 0–120k lx, 16-bit, resolution 0.0036 lx/count | ✅ | Adafruit guide p.3. The ~18 lx threshold sits far inside range with ample resolution |
| VEML7700 breakout accepts 3–5 V on Vin; "give it the same power as the logic level" | ✅ | Adafruit guide p.6. XIAO is 3.3 V logic, so PH1 pad 1 → 3V3 is correct |
| **VEML7700 board has an always-on green power LED, with a cuttable jumper** | ⚠️ **ACTION — cut it** | Adafruit guide p.7. A light sensor sealed in a dark box with its own LED. §3.9, §5.0 step 0.6 |
| ESPHome applies Vishay's non-linear high-lux compensation | ✅ | `components/veml7700/veml7700.cpp` — the 6.0135e-13 polynomial, applied above 1000 lx and always at gain 1/8 and 1/4. So §6.3's daytime-peak trend is on corrected values |
| ESPHome veml7700 keys `ambient_light` / `actual_gain` / `actual_integration_time` / `auto_mode` | ✅ | **proven by compile** — the office and family nodes build |
| ESP32-C3 strapping pins GPIO2/8/9 | ✅ | Espressif |
| OSH Park After Dark and 2 oz services both $5/in² | ✅ | OSH Park docs |
| Gerber set verified: closed outline, 0 silk-over-pad both sides, 0.50 mm copper-to-edge, correct plating attributes | ✅ | parsed 2026-09 |
| Box internal depth **27.384 ± 0.397 mm** (69/64 ± 1/64 in) | ✅ **measured 2026-09-06** | Hand rule. Supersedes the 27 mm listing. Read as the TOTAL internal depth, floor to lid inner surface — §3.4b |
| Lid thickness **3.175 ± 0.397 mm** (8/64 ± 1/64 in) | ✅ **measured 2026-09-06** | Hand rule. Does not affect H (which is to the window's inner surface); feeds §3.5's transmission argument, where it sits slightly closer to the half-wave point than 3.0 mm did |
| Radar PCB thickness — **CAD and part DISAGREE** | ⚠️ **conflict, unresolved** | HLK STEP model gives **0.989 mm** (22.00 × 16.00 outline, faces at z = 0.000 / 0.989). Hand rule on the received part gives **1.191–1.588 mm** (3/64–4/64 in). Non-overlapping. The part wins; the rule is coarse. **Calipers, §5.0 step 0.9.** §3.4c picks a standoff that is in spec across the whole disputed range, so the build is not blocked |
| **HLK's STEP model is not dimensionally reliable** | ⚠️ **new caution** | Follows from the row above. Do not use that CAD for any other clearance without checking it against the part — §3.4c |
| Radar header insulator **2.381–2.54 mm** | ✅ **measured, consistent with assumption** | Hand rule reads "closer to 6/64 in". 2.54 mm = 6.40/64 in, so the reading corroborates the assumed 2.54 mm rather than contradicting it. Calipers would settle it; §3.4e |
| Carrier PCB tolerance ±0.1524 mm (±6 mil) | ⚠️ **sourced, but a FLOOR** | OSH Park publish ±6 mil on the 60 mil **core** only; no finished-board tolerance is given, so plating and mask variation are unquantified on top. Measure a real board — §3.4f |
| **Standoff decision: 9.5 mm** | ✅ **decided 2026-09-06** | Only size inside HLK's ±1.2 mm window across the joint uncertainty in enclosure depth, module thickness and header height. Nominal H = 12.44 mm, +0.017 from 1λ. §3.4b–e, `scripts/standoff_solver.py` |
| XIAO pre-soldered header height | ⚠️ unknown | **measure — §5.0 step 0.11** |
| C1/C2/C3 lead pitch vs footprint | ⚠️ unverified | **§9 item 3** |
| Reports of an LD2410C "v1.1" that is 3.3 V-only | ⚠️ unconfirmed | Amazon reviews; **still nothing in DS or PR** — the primary documents describe only a 5 V part. §5.0 step 0.0 stands |
| **DS detection distance: 5 m (§1, §2.1) vs 6 m (§7 table)** | ⚠️ **the datasheet contradicts itself** | The 5.6 m target sits between them — §3.6 |
| DS §5.4 wall-mount height 1.5–2 m vs both planned installs | ⚠️ **deviation, accepted and recorded** | §5.1 |
| PR §2.2.16 resolution default index | ⚠️ **PR contradicts its own Table 8** | Table 8: 0x0000 = 0.75 m; the text below it says "default 0x0001, which is 0.75m". Table 7 independently gives 0.75 m, so 0.75 m is the default and that sentence's index is wrong |
| DS §7 "Dimensions 7mm x 35mm" | ❌ withdrawn | Contradicts DS §4.1's 16 × 22 mm, which matches the photo and the footprint. Treat the §7 row as an editing error |
| ~~Beam symmetry from antenna photo~~ | ❌ withdrawn | symmetric elements do not imply a symmetric installed pattern; coverage established in §5.2a |
| Radome loss as a quantitative figure | ❌ withdrawn | model indicates thickness region only (§3.5) |
| Range as a calculated value | ❌ withdrawn | 5.6 m is an acceptance target (§3.6) |
| Effective sample size N=150 | ❌ withdrawn | measure the autocorrelation (§5.3) |

---

## 9. Open items

1. **Inspect each radar module before first power-on (§5.0 step 0.0).** Hi-Link documentation is unambiguous — 5 V power, 3.3 V IO — but Amazon reviews describe a "v1.1" that is 3.3 V-only, and there is no authorised distributor for this part. U2 pin 1 is hard-wired to VBUS. **Recovery if a 3.3 V unit arrives: cut the VBUS trace at the pad and jumper to U1's 3V3 pin.** Know the fix before you need it.
2. **Order nylon standoffs and screws.** 10 mm M3 (or 9 mm — decided at §5.0 step 0.9), plus screws and nuts. **Not in either cart.** Buy an assortment (8/9/10/12 mm). This is the one component that sets the radar window geometry and it has been outstanding for four revisions.
3. **Verify cap lead pitch against footprints.** C1 is `C_Disc_D4.7mm_W2.5mm_P5.00mm` (5.00 mm) against FG28X5R1E106MRT00; C2/C3 are `P2.50mm` against K104K10X7RF53L2. Confirm before assembly.
4. ~~**Fix the duplicate `H1` reference designator**~~ — **RESOLVED 2026-09-07.** H1, H2 and H3 are now distinct in the board file, confirmed by parsing all ten footprint references: no duplicates remain.
5. **Build the schematic in Eeschema and generate the netlist.** The board has no net table, so KiCad cannot run connectivity or clearance DRC — every error across seven revisions was found by reading coordinates. This is the one gate still running on human attention.
6. ~~**Decide and implement the R4a manual-override detection path.**~~ ✅ **Closed 2026-09-05.** All four loads are TP-Link Kasa **HS103** plugs on the `tplink` integration — `switch.office_lamp`, and `switch.family_room` / `_2` / `_3` for the family room. The integration reports real switch state, so R4a is satisfied by state reporting and **no current sensing is needed** — no BOM change. One consequence: `tplink` polls, so §4.3's 2 s command window is too tight for a Wi-Fi plug and would read the node's own commands as manual intervention. It is now an `input_number` defaulting to 10 s, **to be set from the A8 measurement and recorded in the §5.8 baseline**.
7. ~~Build the HA `input_select` for §5.3 labelling before the first collection.~~ ✅ **Built** — `packages/mmwave_presence.yaml`. One deliberate change from §5.3's list: `empty` and `empty_hvac` are **not** two labels. HVAC state is stamped automatically from the room's own zone (family → `climate.main_floor`, office → `climate.upstairs`), because asking a human to remember whether the blower was running is asking for a value the system already knows — and it will be wrong exactly during a January heating cycle, which is the collection B that drives every move threshold.
8. ~~Write the §5.9 analysis script (sweep, L(T), autocorrelation, margins) and commit it with the config.~~ ✅ **Built** — `scripts/mmwave_calibrate.py`. Reads the recorder SQLite directly; **there is no InfluxDB in this config**, so §5.9.5's Flux templates target a bucket that does not exist and the recorder's 14-day purge is the collection deadline. Two method changes fell out of writing it, both in `DRAFT-NOTES.md` §2: the sweep's FPR target comes from **A6** (< 1.4e-4, so the expected false-sample count across the two-hour window is below one), not from the 0.005 that P99.5 invites; and seat occupancy is judged on median **lift over the empty median**, because testing against the empty P99.5 silently reclassifies a shadowed seat as an unoccupied gate and turns §5.9.4's stop condition into a shrug.
9. **NEW — the thermostats are an independent witness, and the empty class needs one.** Both Ecobees expose motion and occupancy over `homekit_controller` (local push, ~1 s, not a cloud poll): `binary_sensor.main_floor_motion` / `_occupancy` and `binary_sensor.upstairs_*`. `E_clutter` is a tail percentile, so a few contaminated samples move it — and the contamination mechanism is mundane: you get up, forget to tap the label, and ten minutes of *you* land in the distribution that defines an empty room. On synthetic data, **10 minutes of mislabelled occupancy inside a 90-minute empty run drove E_clutter 15.5 → 58.5 and SM 1.86 → 0.49, condemning a good gate as "OVERLAP — STOP TUNING"** — a false stop that would have sent someone to move a sensor that was fine. `mmwave_calibrate.py --corroborate` intersects the empty class with the thermostat's agreement. **Run the analysis both ways.** These sensors are PIR and stay out of the control path entirely: a PIR cannot see a motionless person, which is the whole reason this document specifies a radar.

**CANDIDATE, not yet accepted — extend the witness to collection C with iPhone room-presence. Recorded here to be refuted or confirmed on the first commissioning pass.** The thermostat PIR corroborates the *empty* class well: motion ⇒ not empty, and that is the direction that matters. It cannot corroborate the *occupied-motionless* class — a PIR going quiet through a 10-minute collection C run is indistinguishable from the subject having left, so a mid-run step-out silently contaminates `E_signal`'s lower tail and inflates SM. Same failure as above, opposite class. A phone carried on the subject and reported at **room level** (ESPresense / Bermuda / a fixed BLE beacon — **not** a home-level `device_tracker`, which cannot resolve the room) is the cheapest positive "subject still in the room" signal. Four caveats decide whether it earns its place: (1) it cleans the class *label*, not the interval — §5.3's autocorrelation lag and N_eff are what set the CI width and a presence entity does not touch them; (2) BLE room presence carries 5–30 s latency and dropout, so it can only gate long stable segments, never individual 1 Hz samples; (3) commissioning-only, never the control path — a phone left behind, a flat battery, or a guest with no phone all break it, the same discipline the PIR is held to; (4) a second corroborator shrinks the empty class further, and `E_clutter` is a P99.5 that already wants thousands of samples, so add it as an *optional additional* `--corroborate` witness and compare three ways (none / PIR / PIR+phone) rather than blindly intersecting. Verdict deferred to bring-up.

---

## 10. Bill of materials — as ordered

### 10.1 DigiKey

| # | Qty | DK P/N | MPN | Description | Unit | Ext |
|---|---|---|---|---|---|---|
| 1 | 10 | 2057-PH1-05-UA-ND | PH1-05-UA | Header vert 5POS 2.54 mm (U2) | $0.072 | $0.72 |
| 2 | 10 | BC5137-ND | K104K10X7RF53L2 | Cap 0.1 µF 50 V X7R radial (C2, C3) | $0.154 | $1.54 |
| 3 | 4 | 445-181283-ND | FG28X5R1E106MRT00 | Cap 10 µF 25 V **X5R** radial (C1) | $0.460 | $1.84 |
| 4 | 2 | 1528-2891-ND | 4162 | Adafruit VEML7700 STEMMA QT | $4.950 | $9.90 |
| 5 | 2 | 1528-4397-ND | 4397 | STEMMA QT cable, **female sockets**, 150 mm | $0.950 | $1.90 |
| 6 | 2 | 2057-PH1RA-04-UA-ND | PH1RA-04-UA | Header R/A 4POS 2.54 mm (PH1) | $0.170 | $0.34 |
| | | | | **DigiKey subtotal** | | **$16.24** |

### 10.2 Amazon

| Item | Qty | Ext |
|---|---|---|
| USB wall charger 5 V 2 A (2-pack) | 1 | $7.99 |
| USB-C cable 6 ft (3-pack) | 1 | $5.99 |
| LD2410C, Qoroos 2-pack (HomarTech) | 1 | $16.14 |
| XIAO ESP32-C3 **pre-soldered** (Seeed Official) | 2 | $21.98 |
| **Amazon order total** | | **$55.41** |

### 10.3 OSH Park

44.0 × 33.0 mm = 2.251 in² × $5.00 = **$11.25 for three**, free US shipping.

**Grand total: $82.90**

### 10.4 Per-unit cost

| Item | Qty/unit | Each | Per unit |
|---|---|---|---|
| XIAO ESP32-C3 pre-soldered | 1 | $10.990 | $10.99 |
| LD2410C | 1 | $8.070 | $8.07 |
| Adafruit VEML7700 (4162) | 1 | $4.950 | $4.95 |
| STEMMA QT cable (4397) | 1 | $0.950 | $0.95 |
| C1, 10 µF | 1 | $0.460 | $0.46 |
| C2 + C3, 0.1 µF | 2 | $0.154 | $0.31 |
| 5-pos header (U2) | 1 | $0.072 | $0.07 |
| 4-pos R/A header (PH1) | 1 | $0.170 | $0.17 |
| Carrier PCB | 1 | $3.752 | $3.75 |
| **Node subtotal** | | | **$29.72** |
| USB charger (2-pack) + cable (3-pack) | 1 | | $5.99 |
| **Delivered per unit** | | | **$35.71** |

Not included: enclosure (on hand), R1 (from stock), **standoffs (not yet ordered — §9 item 2)**, solder, wire.

### 10.5 What the order builds

**Two complete nodes** — XIAO, LD2410C, VEML7700, QT cable and R/A header are all quantity 2. Everything else covers 3–10 units. Three PCBs and three enclosures remain for a future third node.

### 10.6 Cost commentary

**The XIAO is now the largest line at 37% of node cost.** Pre-soldered from Amazon is $10.99 against $4.50 each in DigiKey's 3-pack — a **$6.49/unit premium**, or $12.98 across two nodes. It buys not soldering 14 pins twice, at the cost of a header height you didn't choose and, if the pins go straight into the carrier, a permanently mounted XIAO. See §3.9.

**The radar got cheaper.** Qoroos at $8.07 each vs EC Buying's $11.99 — a **$3.92/unit saving**. Note this is a single seller; the earlier recommendation to split across two sellers was not followed, so a bad batch takes out both nodes.

**Against buying.** Apollo's MSR-2 is $37.99 assembled, in a case, with firmware — and uses the same LD2410B-class radar. At $35.71 delivered, or $29.72 excluding the power supply the MSR-2 also omits, the DIY margin is thin and does not price the PCB spins or the time. **The case for building this is the design record and the repo, not the money.** Worth restating so the next cost comparison starts from an honest premise.

---

## Appendix A — Constants

| Quantity | Value | Note |
|---|---|---|
| Operating frequency | 24.125 GHz | |
| λ₀ | 12.427 mm | free space |
| λg in FR4 (εr 4.3) | 5.96 mm | via-spacing reference |
| Window standoff target | 12.43 mm (1λ), ±1.2 mm | **DS §8.3 verbatim** — "1 times or 1.5 times the wavelength… 12.4 or 18.6mm is recommended for 24.125GHz… Error control: ±1.2mm" |
| Standoff sensitivity | ~58°/mm round-trip phase | *standing-wave phase only — not a cavity mode* |
| Skin depth in copper | 0.425 µm | 1 oz = 82 skin depths |
| Range gate depth | 0.75 m | DS §7; PR Table 8 default. 0.2 m selectable |
| Sweep bandwidth | 250 MHz | DS §7 → c/2B = 0.6 m physical range resolution |
| Average operating current | 79 mA | DS §7; supply capacity > 200 mA |
| Max gate settable range | 2–8 | PR §2.2.3; factory default 8 |
| No-one duration | 0–65535 s, default 5 s | PR §2.2.3, Table 7 |
| **Design range** | **5.6 m (18 ft)** | **acceptance target, not a calculated result** |
| Round-trip loss to halve range | ~12 dB | from R ∝ T^¼ |
| Walking pace, indoors | 1.2–1.4 m/s | |
| MAD → σ-equivalent | 1.4826 | §6.3 |
| Sustained-dropout limit | L(T) < IDLE_TIMEOUT / 3 | §5.9.3 |
| A1 minimum sample size | n ≥ 30 | to support a P95 claim |
| Light threshold, starting | ~18 lx | basement reads 23–25 lx lit-but-dim |
| VEML7700 range / resolution | 0–120k lx / 0.0036 lx per count | Adafruit guide p.3 |
| VEML7700 Vin | 3–5 V, match the logic level | Adafruit guide p.6 → 3V3 on the XIAO |
