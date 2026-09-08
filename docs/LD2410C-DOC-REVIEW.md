# LD2410C document package — review against the drafts

**2026-09-05.** Sources, both now in `draft/LD2410C Docs/`:

| | |
|---|---|
| **DS** | HLK-LD2410C *Life Presence Sensor Module Data Sheet* **V1.00**, 2022-11-07, 19 pp |
| **PR** | HLK-LD2410C *Serial Communication Protocol* **V1.07**, 27 pp (revision table runs to 1.08, 2024-11-22) |
| **AF** | Adafruit VEML7700 guide, 32 pp (added 2026-09-05) |

Also in the folder, reviewed 2026-09-07:

- **`HLK-LD2410 Tool EN`** — HLKRadarTool itself. `LD2410 Tool.exe` (4.2 MB),
  `libfftw3-3.dll` (the tool runs its own FFT), libusb and USB-serial DLLs. Log
  files are named `XenD103Tool_*`, an apparent legacy name for this radar
  family — relevant to §5.0 step 0.0, which tells you to check the silkscreen
  for unexpected version markings. **`appConfig.xml` produced a real finding —
  see §1.1a.**
- **`LEDMatrixControl1.3.2.zip`** — a Unity application dated **2016-08-14**
  (`UnityEngine.dll`, Mono runtime, `CSCore` audio library). Unrelated to this
  project in every respect; it is in the folder by accident. 15.8 MB of noise in
  a documentation directory — move it out.
- `HLK-LD2410C-3D图` — the STEP model. Reviewed; see §3.4c in the design doc,
  where it disagrees with the physical part on board thickness.

**Where the two disagree, PR wins.** It is two years newer and it documents the
commands the module actually obeys. DS V1.00 predates four protocol revisions.

---

## 1. Defects this found in my own drafts — all now fixed

### 1.1 The factory default thresholds I shipped were invented

> ### CORRECTED 2026-09-07 — this heading was wrong. They were not invented.
>
> `HLK-LD2410 Tool EN/appConfig.xml`, opened two days later, contains:
>
> ```xml
> MotionSensing    ="50, 50, 40, 40, 40, 40, 30, 30, 30, "
> MotionLessSensing="0,  0,  40, 40, 40, 40, 15, 15, 15, "
> ```
>
> **That is the set I wrote, identically, all eighteen values.** They came from
> a real and documented source — Hi-Link's own Windows tool — not from nowhere.
> I called them invented because I had checked against PR Table 7 and found a
> mismatch, and concluded the numbers had no provenance rather than that they
> might have a *different* one. Checking one authority and inferring absence
> from it is the same error class as §1.2 below, where PR and the ESPHome schema
> also turned out to answer different questions.
>
> **The reconciliation, which is the part worth keeping:** the two sources are
> both correct about different things. See §1.1a.

`mmwave-node-common.yaml` carried a block commented *"Hi-Link factory defaults,
restated explicitly so the flashed state is KNOWN"*. **Gates 3–8 disagree with
PR Table 7.** PR Table 7 (p.15):

| gate | move | still | | gate | move | still |
|---|---|---|---|---|---|---|
| 0 | 50 | *not settable* | | 5 | 15 | 30 |
| 1 | 50 | *not settable* | | 6 | 15 | 20 |
| 2 | 40 | 40 | | 7 | 15 | 20 |
| 3 | 30 | 40 | | 8 | 15 | 20 |
| 4 | 20 | 30 | | | | |

What I had: move roughly flat at 40 across all gates, still at 15 for gates 6–8.
The real table has move **falling** with range (50 → 15) and still **higher** at
distance (20, not 15).

The consequence was not cosmetic. A freshly flashed node would have been
markedly *deafer to a distant motionless person* than a factory-default one —
which is the R1 failure, shipped as the default state of an uncalibrated node,
in the exact configuration you would run while collecting the data meant to fix
it.

### 1.1a "Factory default" is ambiguous — there are two sets, and they answer different questions

| gate | PR Table 7 | Tool `appConfig.xml` | |
|---|---|---|---|
| g0 | 50 / *not settable* | 50 / 0 | agree |
| g1 | 50 / *not settable* | 50 / 0 | agree |
| g2 | 40 / 40 | 40 / 40 | agree |
| g3 | 30 / 40 | 40 / 40 | **differ** |
| g4 | 20 / 30 | 40 / 40 | **differ** |
| g5 | 15 / 30 | 40 / 40 | **differ** |
| g6 | 15 / 20 | 30 / 15 | **differ** |
| g7 | 15 / 20 | 30 / 15 | **differ** |
| g8 | 15 / 20 | 30 / 15 | **differ** |

Also: no-one duration **5 s** (PR Table 7) vs **3 s** (`OffTime`, tool), and
`MotionGateMax="9"` in the tool against PR §2.2.3's settable range of **2–8**.

**Neither is wrong. They are defaults of different things:**

- **PR Table 7** is headed *"Factory default configuration values"* — a claim
  about what is in the **module's NVM when it ships**.
- **`appConfig.xml`** holds the **PC tool's UI defaults** — what the tool
  pre-populates its fields with, and therefore what it will **write** if
  somebody opens it and clicks apply.

**The practical consequence is a hazard, and it sharpens §5.3a.** Running
HLKRadarTool and hitting apply without touching anything does not "restore
factory defaults" — it writes a *third* configuration, different from both the
module's shipped state and the committed YAML, including a 3 s no-one duration.
The design already declines to use that tool as the configuration path on R9
grounds; this is an independent, concrete reason.

**And it makes "what are the defaults?" the wrong question.** The only
unambiguous answer comes from the module: press `query_params` and read back
what it actually holds. The firmware does that automatically after the R9 push
(§4.1), which is now doing more work than it was designed for.

*The firmware keeps PR Table 7*, because the protocol document is a statement
about the hardware and has been the more reliable source throughout this review
— it beat the datasheet on the settable gate range. But the values are a
starting point that §5.9 replaces, so the choice matters less than knowing the
two sets exist.

### 1.2 Gates 0 and 1 have no static sensitivity at all

PR Table 7 marks static sensitivity for both **"-(not settable)"**. Gates 0–1
cover 0–1.5 m — too close for the module to offer static thresholding.

I had declared `g0.still_threshold` and `g1.still_threshold` in both firmwares
and had the analysis script derive values for them. That is worse than a missing
feature: two HA entities that accept a value, appear to work, and change
nothing — inviting you to tune against a control that is not connected.

**AMENDED — the first fix was wrong, and the correction is the lesson.**
I removed both `still_threshold` blocks on the strength of PR alone. ESPHome's
schema makes `still_threshold` `cv.Required` in *every* gate block, g0 and g1
included (`components/ld2410/number/__init__.py`), so that config **would not
compile** — caught later by `esphome config`, not by reading.

They are now declared and set to **0**, which is also ESPHome's documented
default for these two gates, and understood to be inert. The analysis script
emits `0` for them with a comment rather than omitting the key, because omitting
it breaks the build.

**The general point, now in the design doc header:** the vendor protocol and the
component schema answer *different questions*. PR says what the hardware
honours; the schema says what the generator will accept. Checking one and
assuming the other is how a config that is right about the radar fails to build,
or builds and controls nothing.

### 1.3 My bench wiring warning was backwards

I wrote that the LD2410C's *"pin numbering runs opposite to the silkscreen
order"*. **It does not.** DS §4.2 Table 1 numbers them in the same order as the
silkscreen: `1 UART_Tx, 2 UART_Rx, 3 OUT, 4 GND, 5 VCC`.

I took that from the design document's §3.2 table, which numbers the same pins
`1 VCC … 5 TX` — the reverse of the manufacturer's. See §2.1 below.

The *practical* instruction was right and is unchanged: identify every pin by
its silkscreen label, never by position. VCC and TX are at opposite ends of a
five-pin header.

### 1.4 Bluetooth needs a reboot to actually turn off

PR §2.2.12: *"the Bluetooth function of the module is **on by default**… After
receiving this command, **a reboot is required for the function to take
effect**."*

Both my firmwares and design doc §5.0 step 0.4 treated the power cycle as a
*persistence check*. It is part of the operation. Turn it off, reboot, **then**
verify — otherwise the radio is still advertising while the switch reads off.
DS §6.3 also gives the BLE config password as the default **"HiLink"**, which
sharpens §2's argument for disabling it in a sealed box.

### 1.5 The module has its own photodiode — added to the bench rig

PR §2.2.18: *"This module comes with a photo diode that can be used to detect
the output light sensing value"*, carried in the engineering-mode target data.

**This does not change the VEML7700 decision and should not.** It is a raw
0–255 photodiode count, not calibrated lux, so any threshold set against it is
specific to one part in one orientation and transfers to nothing — portability
across nodes and across a sensor swap is precisely why §5.6 chose the VEML7700.
It also looks wherever the antenna looks, whereas the VEML7700 is on a 150 mm
cable and aimed deliberately (§2).

But it is free, and **it gives you a light channel on the bench tomorrow with no
I²C and no VEML7700.** Added to `mmwave-bench.yaml`, flagged as possibly absent
from some ESPHome releases.

---

## 2. Corrections the design document needs

### 2.1 §3.2 pin numbering is inverted relative to the manufacturer

| | pin 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **DS §4.2 Table 1** | UART_Tx | UART_Rx | OUT | GND | VCC |
| **design doc §3.2** | VCC | GND | OUT | UART_Rx | UART_Tx |

**The fabricated PCB is not affected.** §3.2's prose — *"the pads run VCC → TX
from y 56.89 to 67.05"* — is a physical layout statement and is consistent with
the module's printed order once it is plugged in facing the right way. Only the
numbering column is reversed.

It still needs fixing, because the table is what someone reads while holding a
jumper, and it contradicts the datasheet they will have open next to it. Note
the design doc's own §3.2 warning that a net called simply "TX" is ambiguous and
"caused two errors during design" — this is the same hazard one level up.

### 2.2 The 5.6 m design range sits above the manufacturer's headline figure

DS is internally inconsistent:

- §1 and §2.1: *"the farthest sensing distance can reach **5 meters**"*, *"The
  longest sensing distance is up to 5 meters"*
- §7 parameter table: *"Detection distance **0.75 m ~ 6 m**, adjustable"*

Nine gates × 0.75 m = 6.75 m of gate coverage, and the max-gate setting tops out
at 8. So the geometry allows 6 m; the marketing text claims 5 m.

**The design's 5.6 m acceptance target lies between the two.** §3.6 is already
careful that this is *"a test requirement, not a link-budget guarantee"*, so
nothing collapses — but the document should say plainly that the target exceeds
Hi-Link's own headline range, and that §5.2a is therefore testing whether the
part beats its datasheet, not whether the installation is competent. That is a
different question and it changes how a failure should be read.

Relevant: DS §5.5 warns the *"longest distance will also fluctuate slightly"*
with target size, state and RCS.

### 2.3 Both planned mounting heights are below Hi-Link's guidance

DS §5.4, wall-mount: **height 1.5–2 m**, 5 m range, with the detection-pattern
figures drawn for 1.5 m. Ceiling mount: 2.6–3 m.

The planned installs (§5.1):

| install | height | vs guidance |
|---|---|---|
| Family room, mantel | 1.3 m | 0.2 m low |
| Office, desk | 0.75 m | **half the minimum** |

The office node at 0.75 m firing 19° upward at a seated torso is well outside
the geometry the datasheet's patterns describe. §5.2a's coverage sweep is the
right mitigation and already exists — but the deviation should be *recorded* as
a deviation, so that a coverage hole at the desk is diagnosed as geometry
(§5.9.4's "bad geometry is not a bad threshold") rather than chased in
thresholds.

### 2.4 §0 — the built-in light sensor is not an LD2412 differentiator

§0's comparison table lists "Built-in light sensor" as a *claimed LD2412
advantage*, dispositioned "Moot — VEML7700 gives calibrated lux".

**The disposition is right; the premise is wrong.** The LD2410C has a photodiode
too (PR §2.2.18). The row should be struck rather than answered — the module
selection does not turn on it in either direction.

### 2.5 §5.3a — auto-calibration IS in the protocol

§5.3a says auto-cal is *"Not reachable from ESPHome — the `ld2410` component
exposes only `factory_reset`, `restart`, `query_params`"*. True of ESPHome, and
the decision to reject it stands entirely on the **R9** ground, which is the
strong one.

But the capability is in the module and in the protocol: PR §2.2.20 *"Start
performing background noise detection and automatic sensitivity
configuration"*, with §2.2.21 to poll status, added in **V1.07 (2024-08-05)**.

Two things follow. First, "not reachable" is a statement about today's ESPHome,
not the hardware — a future component release could expose it, and the R9
argument needs to be the one recorded, because it is the one that will still be
true. Second, PR confirms the mechanism §5.3a warns about: the routine *"will
automatically configure the sensitivity value of each distance door based on the
detected background noise value"* — it **overwrites the committed thresholds in
NVM**. Worth noting that our `restore_value: true` numbers push the YAML values
back at the next boot, so ESPHome partially defends against this by accident.

### 2.6 The OUT pin's idle level is configurable, not fixed

§3.3's argument for GPIO10 over GPIO9 rests on *"RADAR_OUT is a push-pull output
that sits LOW whenever the room is empty — normal at power-on."*

That is the **factory default**, not a hardware property. PR §2.2.18, third
configuration byte: `0x00` = OUT defaults low (high on target); `0x01` = OUT
defaults high (low on target).

**The pin choice is still right** — GPIO10 is safe under either polarity, which
is rather the point. But the reasoning should say "defaults low, and that
default is a configurable parameter", or the conclusion looks more load-bearing
on an assumption than it is.

---

## 3. Confirmed from the primary source — previously secondhand

| claim | status |
|---|---|
| Operating voltage **DC 5 V**, IO level 3.3 V | ✅ DS §7 and §5.1. Pin table adds "5~12V (advise 5V)" |
| Default baud **256000**, 1 stop, no parity | ✅ DS §5.1, PR p.7; PR Table 6 index 0x0007 |
| Gate depth **0.75 m**, 9 gates | ✅ DS §5.2, PR Table 8 — 0.75 m is the factory default; 0.2 m selectable |
| Max-gate settable range **2–8** | ✅ PR §2.2.3. Design doc §5.2's "minimum settable gate is 2" is right; **DS p.8's "1 to 8" is the wrong one** |
| Sensitivity 0–100 per gate, independently settable | ✅ DS §5.2 |
| Thresholds persist in NVM, not re-learned at boot | ✅ DS §5.2 "will not be lost when the power is turned off"; PR §2.2.3 |
| Engineering mode **volatile**, off at power-on | ✅ PR §2.2.5 "lost when power is lost" — confirms the bench firmware must enable it in `on_boot` |
| Detection angle **±60°** | ✅ DS §7 |
| **Radome H = 1λ or 1.5λ; 12.4 or 18.6 mm at 24.125 GHz; ±1.2 mm** | ✅ **DS §8.3 verbatim.** Appendix A's standoff target is now first-party, not inferred |
| Metal backplane shields the back lobe | ✅ DS §5.5, and it confirms §3.7's logic: the concern is *moving* objects behind the radar |
| Radar shake is indistinguishable from room motion | ✅ DS §5.5 — confirms §5.1 "weight the box" |
| Clutter sources: animals, swinging curtains, plants at an air outlet, fans, A/C | ✅ DS §5.5 — matches §5.4's table |
| No-one duration range **0–65535 s**, default **5 s** | ✅ PR §2.2.3, Table 7 |
| Max move/still gate default **8** | ✅ PR Table 7 |

### New numbers the design document does not carry

- **Average operating current 79 mA**; supply capacity **> 200 mA** (DS §7).
  USB's 500 mA covers it comfortably. Worth adding to §10 / the power budget.
- **Sweep bandwidth 250 MHz** (DS §7) → theoretical range resolution
  `c/2B` = 0.6 m, consistent with the 0.75 m gate depth being a real physical
  limit rather than a chosen quantisation.
- **Sensitivity = 100 blanks a gate entirely** (DS §5.2, PR p.8): *"if the
  sensitivity of a certain distance gate is set to 100, the effect of not
  recognizing the target under the distance gate can be achieved."* This is a
  second, finer R6 mechanism than the max-gate cap — it blanks *one* gate rather
  than truncating everything past it. Noted in the firmware; deliberately **not**
  automated in the analysis script, because blanking a gate inside the room
  creates a dead zone, and that has to be a human decision.

### A documentation bug in PR itself

PR §2.2.16 Table 8 defines `0x0000` = 0.75 m and `0x0001` = 0.2 m, then the text
immediately below says *"Factory default value is 0x0001, which is 0.75m"* —
contradicting its own table. Table 7 independently gives the default as 0.75 m,
so **0.75 m is the default** and the index in that sentence is wrong. Harmless,
but do not take a resolution index from that line. (Section numbering is also
duplicated — two consecutive sections are both labelled 2.2.18.)

---

## 4. What is still unverified

Nothing here has been through a compiler or touched hardware. The document
review resolves *what the module does*; it says nothing about whether ESPHome's
`ld2410` component exposes it the way I have written it. In particular:

- the `light:` key on the ld2410 sensor platform — the module supports it, but
  ESPHome may only wire it up for the LD2412
- whether ESPHome rejects, ignores, or silently accepts a write to the
  non-existent g0/g1 still thresholds — moot now, since they are removed
- `internal_temperature`, `debug`/`reset_reason`, and the template `number`
  block, all still doc-sourced

§5.11's version freeze exists for exactly this gap.


---

## 5. VEML7700 (Adafruit 4162) — one action item, five confirmations

### 5.1 ACTION: cut the power-LED jumper before assembly

AF p.7:

> **Power LED** — In the upper right corner, above the STEMMA connector, on the
> front of the board, is the power LED, labeled `on`. It is a green LED.
> **LED jumper** — This jumper is located on the back of the board. Cut the
> trace on this jumper to cut power to the "on" LED.

**An ambient-light sensor is going into a sealed box with its own light source
on the same face as its photodiode.** The enclosure base is black ABS and the
lid is clear, so the LED's light is not free to escape and some of it returns to
the detector.

Why this is not a rounding error:

- §5.6 puts `THRESHOLD_ON` at **~18 lx**, and the part resolves **0.0036 lx per
  count** (AF p.3). It will absolutely register the LED.
- The offset is **constant**, so it does not look like a fault. It looks like a
  calibration. It would be measured during the 24 h in-situ lux profile, folded
  into the commissioned threshold, and never questioned — until a replacement
  sensor with a cut jumper reads differently and the threshold no longer
  transfers. That portability is the entire reason this part was chosen over a
  phototransistor (§5.6), and an uncut LED quietly spends it.
- It also breaks the §5.0 step 0.6 cross-check against the basement node, which
  is the only sanity check the light path gets before commissioning.

Now in the firmware comment, §3.9 assembly, and §5.0 step 0.6 — which gains a
**cover-the-sensor, expect ~0 lx** test, because that is the cheap way to prove
the jumper is actually cut rather than assuming it.

### 5.2 Confirmed

| claim | status |
|---|---|
| I²C address **0x10** | ✅ AF p.24 |
| Calibrated lux, "more consistent readings between" sensors | ✅ AF p.3 — the §5.6 portability argument, first-party |
| Range 0 – ~120 k lx, 16-bit, **0.0036 lx/count** | ✅ AF p.3 |
| Vin accepts **3–5 V**; "give it the same power as the logic level of your microcontroller" | ✅ AF p.6. XIAO is 3.3 V logic → PH1 pad 1 to 3V3 is right, and the onboard LDO handles it |
| 3Vo output can source 100 mA | ✅ AF p.7 — unused here, but it is a spare 3.3 V tap if ever needed |
| ESPHome applies Vishay's non-linear high-lux compensation | ✅ **source-verified**: `veml7700.cpp` runs the `6.0135e-13·x³ …` polynomial above 1000 lx and always at gain 1/8 or 1/4. §6.3's "daytime peak declines >20% over a season" therefore trends *corrected* values, which is what makes it comparable year to year |
| ESPHome keys `ambient_light`, `actual_gain`, `actual_integration_time`, `auto_mode` | ✅ **proven by compile** — office and family nodes build |

### 5.3 One thing to watch, not yet a problem

AF p.29: *"the raw ALS value … should be between 100 and 10000"* for good
readings, and the library default is gain 1/8 with a 100 ms integration time —
the *least* sensitive combination, chosen for daylight.

At the dark end where the ~18 lx decision lives, that default would put the raw
count near the bottom of its range. `auto_mode: true` is set in the firmware and
should range the gain up in the dark, but **that is an assumption about the
component, not a measurement.** The two diagnostic sensors already exposed —
`actual_gain` and `actual_integration_time` — exist to check it: read them while
the room is at ~18 lx and confirm the part has moved off 1/8 gain. If it has
not, set gain and integration time explicitly rather than trusting auto.
