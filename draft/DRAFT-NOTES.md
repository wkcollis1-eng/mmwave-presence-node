# mmWave Presence Node — firmware and HA draft

**Rev 0.1 draft — 2026-09-05.** Against design doc Rev 1.4.
Nothing here has been compiled, validated against a running HA, or deployed.

> **2026-09-05, later:** the LD2410C datasheet and serial protocol were reviewed
> against these drafts. It found **three real defects in this package** — invented
> factory-default thresholds, two non-existent gate thresholds, and a backwards
> wiring warning — plus six corrections the design document needs. All code
> fixes are applied. See **[LD2410C-DOC-REVIEW.md](LD2410C-DOC-REVIEW.md)**.

---

## 0. Answered 2026-09-05 — nothing left blocking

### Resolved

| | |
|---|---|
| Family room loads | `switch.family_room`, `switch.family_room_2` ("Lamp 1"), `switch.family_room_3` ("Lamp 2") — **all three**, TP-Link Kasa **HS103** on `tplink` |
| Office load | `switch.office_lamp` — **also an HS103**, same firmware build (50:D4:F7:91:19:D9) |
| Family room zone | `climate.main_floor` + `binary_sensor.main_floor_motion` / `_occupancy` |
| Office zone | `climate.upstairs` + `binary_sensor.upstairs_motion` / `_occupancy` |
| Thermostats | **`homekit_controller`, not the ecobee cloud integration** |

**Correcting myself:** I wrote that `switch.dehumidifier` was the only switchable
load "in the registry". It was the only one in `ENTITIES.md`, which is a curated
subset. The registry holds 1,784 entities. The claim was wrong as stated.

Four consequences, all now in the code:

1. **R4a is satisfiable with no BOM change.** `tplink` reports real switch
   state, so no current sensing is needed. But it *polls*: §4.3's 2 s command
   window is too tight for a Wi-Fi plug and would read our own commands as
   manual intervention, silently suppressing automatic control until the room
   emptied. It is now `input_number.mmw_<room>_cmd_window`, default 10 s, **to
   be set from the A8 measurement** and recorded in the §5.8 baseline.
2. **HS103 has no energy monitoring** (that is the HS110/KP115 line). Not needed
   here, but it removes current sensing as a fallback if the plug ever stops
   reporting.
3. **The alarm flashes a mechanical relay.** 0.4–0.5 s half-periods are not
   deliverable over Wi-Fi and every cycle is two relay operations on each of
   *three* plugs. Retimed to 1.5 s, default flash count 10 → 6 (**36 relay
   operations per alarm**), max 30 → 15. Each flash edge is now three round
   trips, so if the lamps visibly step rather than flash together, raise the
   half-period before cutting the count — ragged flashing reads as a
   malfunction, and an alarm that looks broken gets ignored. Real strobing
   needs a dimmable bulb, not a plug.
4. **The office zone assumption was wrong** and is corrected. Had it shipped,
   every office move threshold would have been derived against the wrong
   blower — invisibly, because the data still looks clean.

### Nothing left blocking

All four loads — one office, three family room — are Kasa HS103 on `tplink`,
same model and same firmware build.
That is a genuine simplification: **one device class across both rooms**, so the
R4a command window, the poll behaviour and the relay timing are a single set of
facts rather than two. The stub is gone — a stub kept alongside the real entity
is a second source of truth for the same fact, which is how they diverge.

One asymmetry worth knowing: `sensor.office_lamp_signal_strength` is *disabled*
in the registry, where its family room siblings are enabled. Nothing depends on
it, but if you want Wi-Fi telemetry on that plug you will need to enable it.

---

## 0a. The thermostat sensors — worth more than they look

They are a **second opinion on the data, never an input to the lights.** PIR
cannot see a motionless person, which is the entire reason the radar exists;
putting it in the control path would reintroduce the failure R1 exists to
prevent. Three uses, in descending order of value:

### Corroborated empty — the big one

`E_clutter` is P99.5 of the empty class. A tail percentile is exactly the
statistic that a handful of contaminated samples can move, and the contamination
mechanism is obvious once stated: you get up, you forget to tap the label, and
ten minutes of *you* land in the distribution that defines an empty room.

`binary_sensor.mmw_<room>_empty_corroborated` requires both the radar **and** the
thermostat to agree, and `mmwave_calibrate.py --corroborate <entity>` intersects
the empty class with it.

**Demonstrated, not asserted.** Synthetic data, 90 minutes labelled empty, with
10 minutes of that secretly occupied:

| run | E_clutter (g3 still) | SM | verdict |
|---|---|---|---|
| without `--corroborate` | 58.5 | 0.49 | `OVERLAP — STOP TUNING` |
| with `--corroborate` | 15.5 | 1.86 | T = 19, usable |

Eleven percent contamination was enough to condemn a good gate and send you back
to §5.1 to move a sensor that was fine. **Run the analysis both ways.** If the
thresholds move much, the uncorroborated empty class was contaminated, and what
you have learned is about your labelling discipline as much as about the room.

Note *occupancy*, not *motion*, is the signal on the empty side: occupancy holds
after the last motion, so it stays true through someone sitting quietly — which
is exactly when PIR would otherwise wrongly certify an empty room. Corroborating
with motion would endorse the error it exists to catch. Motion is ANDed in only
as a fast disqualifier.

### A non-circular label check

The contradiction detector previously asked the radar whether the radar's own
training labels were wrong. It now also asks the thermostat, which is a
different sensor on a different integration. One-way only: motion ON proves
somebody is there; motion OFF proves nothing.

### Dropout candidate

`binary_sensor.mmw_<room>_dropout_candidate` — thermostat occupied, radar empty
for 10 minutes. **Candidate, not proof**: the thermostat is elsewhere on the
floor and its occupancy holds long after somebody leaves. But it is the only
dropout evidence available from a sensor that is not the radar, and §5.9.3's
`L(T)` is computed on the radar's own energies and inherits any fault in them.
If these cluster at one seat or one time of day, that is R1 failing.

---

## 1. What is in the drop

| File | Goes to | Lines |
|---|---|---|
| `esphome/mmwave-node-common.yaml` | `/config/esphome/` | 761 |
| `esphome/mmwave-office-node.yaml` | `/config/esphome/` | 49 |
| `esphome/mmwave-family-node.yaml` | `/config/esphome/` | 52 |
| `packages/mmwave_presence.yaml` | `/config/packages/` | 1322 |
| `dashboards/mmwave-office.yaml` | `/config/dashboards/views/` | 274 |
| `dashboards/mmwave-family.yaml` | `/config/dashboards/views/` | 354 |
| `scripts/mmwave_calibrate.py` | `/config/scripts/` | 823 |
| **`esphome/mmwave-bench.yaml`** | `/config/esphome/` | **608** — bench rig, self-contained |
| **`dashboards/mmwave-bench.yaml`** | `/config/dashboards/views/` | **397** |

All six YAML files parse. The Python compiles and has been **run end to end
against a synthetic recorder database with known answers** — see §7.

**One firmware.** `mmwave-node-common.yaml` is the whole node. The two device
files contain nothing but substitutions and an `!include`. Choosing the room is
choosing which device file you flash.

Secrets needed in `esphome/secrets.yaml` (only `api_encryption_key` exists
today): `wifi_ssid`, `wifi_password`, `ap_password`, `ota_password`. The
basement node inlines its credentials; these use `!secret` instead, which is the
better habit given the repo is public — worth converting the basement node too,
separately.

---

## 2. Departures from the design document

Five, each argued at its site in the code. Three are firmware, two are method.

### 2.1 `delayed_on: 200ms` removed from the hardware OUT pin

§4.1 specifies `filters: [ delayed_on: 200ms, delayed_off: 2s ]` on the GPIO10
binary sensor. **R2 gives the whole system a 1000 ms median budget.** That
filter spends 20% of it debouncing a push-pull CMOS output driven by a
microcontroller. There is no mechanical contact on that path; R1 is fault-
current limiting (§3.3), not an RC. `delayed_off: 2s` stays — it only lengthens
the trailing edge, where latency is free.

*If A1 shows spurious short pulses on OUT, put it back — but measure first.*

### 2.2 The VEML7700 sensor key is `ambient_light`, not `lux`

§4.1's skeleton uses `lux:`. The ESPHome `veml7700` platform exposes
`ambient_light`. Verify against the pinned version at §5.11 before flashing —
this is exactly the class of thing §5.11 exists for.

### 2.3 The two timeouts are prevented from adding

**This is the one I would put money on biting.** The module's own `timeout`
holds `has_target` on after the person leaves. HA then waits its own idle
timeout. *These add.* Family room at 300 s module + 300 s HA is a ten-minute
hold, A5 fails, and both files look correct in isolation.

Resolution: the module timeout is short (30 s) — enough to bridge the radar's
own tracking dropouts, and the sane fallback when HA is down (§7). The room
timeout lives in HA as a **total**, and the automation subtracts:

```jinja
{% set total = states('input_number.mmw_family_idle_timeout') | float(300) %}
{% set mod   = states('number.family_mmwave_radar_timeout')   | float(30)  %}
{{ [total - mod, 0] | max }}
```

So the dashboard number is the number of seconds the lights stay on. Change
either one and the arithmetic follows.

### 2.4 The false-positive target comes from A6, not from P99.5

§5.9 defines `E_clutter = P99.5(collection B)`, which invites setting the sweep
target to the matching FPR of 0.005. At 1 Hz that is **~18 above-threshold
samples per hour**. A6 requires *zero* false triggers in two hours.

```
FPR_target < 1 / (2 h × 3600 s/h × 1 sample/s) = 1.4e-4
```

P99.5 stays as the diagnostic it was defined to be; the sweep target comes from
the acceptance test it has to pass. `--fpr-target` overrides it.

**And a consequence worth stating plainly:** the smallest false-positive rate a
sample can *demonstrate* is 1/n. Six hours of empty-room data at 5 s sampling is
4,320 samples per gate, so it can certify no better than 2.3e-4. The report says
so rather than quietly reporting a target it cannot support. **This is the
strongest argument for running the collection for days instead of hours**, and
it is a better argument than "more data is better".

### 2.5 Seat visibility is judged against the empty *median*, not the empty P99.5

My first version tested occupancy as `median_still(seat) > P99.5(empty)`. Run
against synthetic data containing a deliberately shadowed seat, it reported
`UNOCCUPIED — leave at factory` instead of §5.9.4's `SM ≤ 1 — STOP TUNING`.
That is the most important verdict in the method being silently downgraded to a
shrug. Occupancy is now median lift over the empty median, and there is a
separate per-seat table whose only job is to answer *is this seat seen at all*.

### 2.6 No `initial:` on any tunable helper

`initial:` on an `input_*` helper **disables state restoration** — the helper is
forced back to that value on every HA restart. On a threshold derived from 72
hours of collection that is not a default, it is a silent revert, and the only
symptom is a node that gets worse after an update. `watchdog.yaml` uses
`initial:` throughout, so this breaks with local convention deliberately; those
are fixed operational limits, these are commissioned values.

They come up `unknown` until set, which is honest — it says nobody has
commissioned this room yet. Every template reading them carries an explicit
fallback, and the intended starting values are listed in the file.

Two exceptions, both argued in place: the quiet-hours `input_datetime` pair
(a window with no value is worse than one re-seeding to 01:00–05:00) and the two
`auto_enable` booleans (after a restart, automatic lighting should come back
*on*; coming back disabled is a silent loss of function).

---

## 3. Recorder cost — this changed a design decision

18 gate series per node, and they only exist in engineering mode (§6.1).

| period | rows/h/node | rows/day/node | 72 h, two nodes |
|---|---|---|---|
| 1 s | 64,800 | 1,555,200 | 9.3 M (~1.4 GB) |
| 2 s | 32,400 | 777,600 | 4.7 M |
| **5 s** | **12,960** | **311,040** | **1.9 M (~280 MB)** |
| 10 s | 6,480 | 155,520 | 0.9 M |

For scale: the basement TH node contributes ~58k rows/day, and that is described
in `configuration.yaml` as needing churn control. A 72-hour collection at 1 Hz
is about **27× that, per node**, into a 14-day purge window that will hold every
row.

So the gate publish period is a **runtime number** (`number.<room>_mmwave_gate_log_period`),
not a compile-time `throttle:`. Default 5 s for the passive collection; turn it
down to 1 s for the focused 10-minute seat runs, where `L(T)` is a *time*
measurement and a 5 s period quantises it to ±5 s.

5 s costs little statistically: the synthetic run measured a decorrelation lag
of 7 s, so 1 Hz sampling of that signal is collecting correlated samples that
inflate *n* without adding information. The script reports the real lag from
your data — check it before trusting the 5 s choice.

**Also note:** §5.9.5's Flux queries target `bucket: "homeassistant"`. There is
no InfluxDB in this config. The recorder is the store, its 14-day purge is the
deadline, and `mmwave_calibrate.py` reads the SQLite file directly. If you would
rather have Influx, that is a separate decision and the Flux templates become
live again.

---

## 4. The 48–72 hour collection, as designed

§5.3 asks for three bounded runs (1 h, 1 h, 10 min per seat). You want a passive
48–72 h collection instead. Those are compatible, but not identical, and the
difference matters:

**What the passive collection gives you that the bounded runs do not:**
seasonal-ish coverage of HVAC cycling, real occupancy patterns, and enough
empty-room samples to certify a low false-positive rate at all.

**What it does not give you, and you still have to do deliberately:**

1. **`L(T)` needs unbroken seated runs.** A 90-minute evening on the couch is
   ideal and passive. But at least one **deliberate 10-minute motionless run per
   seat at 1 s gate period** is worth doing, because that is the measurement R1
   actually rests on.
2. **Move thresholds need labelled motion.** "Walking through" and "working in
   kitchen" will accumulate slowly and in short fragments. The script will say
   `INSUFFICIENT` until each has ≥100 samples per gate — at 5 s that is 8.3
   minutes of *labelled* motion. Plan a deliberate walking pass (§5.2a's grid
   sweep doubles as this).
3. **Collection B is the one that matters and it is a subset here.** The report
   prints the fraction of empty-room samples that had the blower running and
   warns below 10%. In September in Connecticut you may get very little. §6.3
   already says to re-run collection B in heating season — expect to.

**Order of operations:**

```
§5.0 bench bring-up          <- unchanged, do it first
§5.1 placement and aim       <- geometry before thresholds, always
§5.2a coverage sweep         <- BEFORE any threshold work. Doubles as the
                                labelled motion collection.
  |
  v  flash, deploy package, set gate period 5 s
48-72 h passive collection   <- live normally; tap the labels
  |
  +-- interleave: 10 min motionless per seat at 1 s gate period
  |
  v
cp home-assistant_v2.db /tmp/cal.db
python scripts/mmwave_calibrate.py --db /tmp/cal.db --room family --idle-timeout 300
  |
  +-- exit 2 => a seat is shadowed. STOP. Go back to §5.1. Do not tune.
  +-- exit 1 => a gate overlaps. Same answer.
  +-- exit 0 => paste --emit esphome into the device file, commit, reflash
  |
  v
§5.7 acceptance tests A1-A12
```

The dashboards carry a **collection coverage** section with `history_stats`
sensors per label, so the gap that would otherwise surface at analysis time
surfaces on day one. Targets: 6 h empty spanning a heating or cooling cycle,
1 h per seat including one unbroken 10-minute run.

---

## 5. The alarm, and the one thing it cannot do

Family room, quiet hours (helpers, default 01:00–05:00, midnight-wrap safe).

**It fires only on a genuine arrival.** The trigger is an off→on transition
*and* the room must have been continuously empty for five minutes first:

```jinja
{{ (as_timestamp(now()) - as_timestamp(trigger.from_state.last_changed)) > 300 }}
```

Someone asleep on the couch since midnight never produces an off→on edge, so
they cannot trigger it. A momentary radar dropout *does* produce one — and
without that five-minute test the house would strobe at someone sleeping in it.
This is also why §5.9.3's `L(T)` budget matters here: any dropout approaching
five minutes is already a threshold failure, and SPC will have flagged it.

**Two warning blinks, then a grace period, then the real sequence.** A radar
cannot tell a resident from an intruder, and the family room is on the way to
the kitchen. Two blinks says *I saw you* to someone getting a glass of water and
gives them ~20 s to hit **DISARM TONIGHT** — a deliberately oversized button on
the family room view, because someone standing in the dark being flashed at by
their own house has no patience for navigation. Disarm clears itself at the end
of quiet hours, not at a fixed time, so it cannot expire mid-window.

**It ships disarmed** (`initial: false`). Arm it after A6 has passed. An alarm
built on a node with uncalibrated thresholds will fire on the furnace.

**What it cannot do:** distinguish a person from a large dog, or a resident from
anyone else. If there are pets in the family room, say so — the answer is
probably a distance/gate restriction plus a minimum dwell, and it is worth
designing rather than discovering at 02:00.

---

## 6. Enhancements included, beyond §4

| | What | Why |
|---|---|---|
| **Two-path skew** | `sensor.<room>_mmwave_presence_path_skew`, signed ms between the OUT-wire edge and the UART edge | §6.2 calls the two paths disagreeing the most useful diagnostic the node produces, but only detects it once it is *total*. The skew is a continuous measure of the same thing, free, and drifts before it breaks. |
| **On-node disagreement detector** | Computed in the node, not in HA | It survives the HA outage it might be diagnosing (§7 "component stalls"). 300 s threshold, because brief disagreement is expected and normal — a detector that fires on it trains you to ignore it. |
| **Lux staleness gate** | `binary_sensor.<room>_mmwave_lux_stale`, and both lighting automations refuse to act while it is on | §7 asks for the alert. Without the *gate*, a dead VEML7700 holds its last value forever, and if that value was low the lamp comes on in a sunlit room every time — with no symptom except a lamp being on. |
| **Label contradiction detector** | Alerts when the label says empty but presence has held for a minute | §5.3: "the empty class must be a genuinely empty room". A mislabelled empty run does not produce a slightly wrong threshold — it puts a person's micro-Doppler into the distribution whose P99.5 becomes `E_clutter`, raising every move threshold and producing a node that quietly stops detecting people. |
| **Stale-label auto-downgrade** | 10 min of confirmed absence downgrades a seat label to "no one present" | The same failure in the other direction: a seat label left set after you get up puts an empty room into the OCCUPIED class and drags `E_signal` down. Downgrade only — the machine can tell nobody is there; it cannot tell which chair you are in. |
| **Automatic HVAC covariate** | `sensor.mmw_<room>_cal_class` = `label\|blower\|lamp` | §5.3 wanted `empty` and `empty_hvac` as two labels. Asking a human to remember whether the blower was running is asking for a value the system already knows — and it will be wrong exactly during a January heating cycle, which is the collection B that drives every move threshold. |
| **One composite class string** | Same sensor | The analysis does one group-by instead of a four-way time join across four entities updating at four different rates. Joining after the fact is where this kind of study usually goes wrong. |
| **Runtime gate log period** | `number.<room>_mmwave_gate_log_period` | §3 above. |
| **`power_save_mode: none`** | Wi-Fi | ESP32 defaults to LIGHT, parking the radio between DTIM beacons — tens to low hundreds of ms added to the packet carrying the presence edge, out of a 1000 ms budget, on a mains-powered node. |
| **`api: reboot_timeout: 0s`** | | R7. A node that reboots every 15 min because HA is down turns one outage into a flapping node and destroys the telemetry that would explain it. |
| **Opt-in radar auto-recover** | Default OFF | Restarting the radar after 10 min of UART stall is the right move, but it causes a real dropout in an occupied room. Opt in after A10. |
| **Offset SPC windows** | Office 03:10, family 03:40 | Two 18-series bursts on the same second is the collision class `ha_audit`'s `eod-concurrent` check exists to catch. |

---

## 7. What was actually verified, and what was not

Per the definition-of-done: a parser is not evidence.

**Verified:**
- All six YAML files parse (`yaml.safe_load` with HA/ESPHome tag handling).
- The YAML anchor for the 18 gate filters resolves identically at `g0` and `g8`.
- `mmwave_calibrate.py` compiles and **runs end to end** against a synthetic
  recorder database built with known answers: gate 3 occupied
  (empty ~N(8,3), seated ~N(45,10)) with a deliberate 25 s dropout injected.
  It recovered `E_clutter = 16.0`, `E_signal = 28.2`, chose **T = 21**,
  FPR 0, FNR 0.013, and **L(T) = 24 s** — the injected dropout, found. SM 1.76
  correctly reported as MARGINAL. Decorrelation lag 7.0 s.
- That test is what caught the two method defects in §2.4 and §2.5.

**Not verified — do not treat any of this as working:**
- No ESPHome compile. Component keys, `internal_temperature`, the
  `debug`/`reset_reason` text sensor, template `number` options, and the
  `select: distance_resolution` block are all from documentation, not from a
  build. §5.11 exists for exactly this.
- No `check_config`, no HA deploy, no entity read-back. **Every entity id in
  the package is inferred from a naming pattern**, which `ENTITIES.md` says in
  as many words never to do. They cannot be resolved until the nodes exist —
  reconcile after first flash and regenerate `ENTITIES.md`.
- The `for:` templates in the two "empty → off" automations are the highest-risk
  YAML in the package. Test them by watching the trace, not by reading them.
- `light.office_lamp` and `light.family_room_lights` do not exist. Nothing runs
  until §0 question 1 is answered.
- The alarm has never flashed anything.

---

## 8. Suggested next steps

1. Answer the two questions in §0.
2. Finish §5.0 bench bring-up on node 1 — it gates the standoff decision (§3.4)
   and the 3.3 V-variant check (§9 item 1), both of which are irreversible.
3. Flash the office node, reconcile entity ids, deploy the package to a
   **sandbox copy** first, then `check_config`, then read the entities back.
4. Run §5.2a's coverage sweep before touching a threshold. If a seat is
   shadowed, everything downstream is wasted effort.
5. Start the passive collection with the gate period at 5 s.
6. Add the two `pipelines.yaml` entries if the daily SPC window should be
   covered by the stale-detector machinery — it is a daily capture in every
   sense that file means, and it is the R8 early-warning mechanism.


---

## 9. The bench rig (added 2026-09-05, hardware arriving 2026-09-06)

`esphome/mmwave-bench.yaml` + `dashboards/mmwave-bench.yaml`. **Self-contained** —
no `!include`, no packages, no I²C, no VEML7700. Flash the one file.

It is not the production firmware with parts removed. Four deliberate
inversions, because a bench session and an unattended room want opposite things:

| | bench | production |
|---|---|---|
| Engineering mode | **ON at boot** (after a 3 s UART settle) | OFF — §6.1 duty cycle |
| Logging | **DEBUG** | INFO |
| Gate threshold `initial_value` | **none** — read what the module actually holds | set from §5.9, pushed on boot (R9) |
| Node name | `mmwave-bench` → `bench_*` entities | `office_*` / `family_*` |

The name is what keeps this safe to run alongside everything else: no entity can
collide with a production node, so nothing you do on the bench can disturb the
office or family room config, and vice versa. **Do not deploy
`packages/mmwave_presence.yaml` against this node** — that package expects a
light sensor and a room.

### The wiring hazard, restated because it is the one that destroys hardware

The LD2410C's **pin numbering runs opposite to its silkscreen order**. The
antenna face is printed `TX RX OUT GND VCC`; the datasheet numbers those pins
5, 4, 3, 2, 1. So VCC is pin 1 but sits at the *far* end of the header. Count
from the wrong end with a 5 V jumper in hand and it lands on TX.

**Identify every pin by its silkscreen label, never by position.**

Four more, in the file at length: VCC is 5 V not 3V3 (with the §9-item-1 caveat
about an unconfirmed 3.3 V-only "v1.1" — check the silkscreen reads plain
`LD2410C` before powering); the UART is crossed and every net is named for the
*module's* pin; OUT must not touch D9/GPIO9 or the node boots into the
bootloader whenever the room is empty; and there is no 1 kΩ series resistor on
jumpers, so GPIO10 stays input-only.

### Board assumption

Defaulted to `seeed_xiao_esp32c3`, because that is what the BOM ordered (two,
pre-soldered) and what the carrier is designed around. If a generic C3 devkit
turns up instead, change `board_type` to `esp32-c3-devkitm-1` and delete the
`logger: hardware_uart: USB_SERIAL_JTAG` line if the board has a CH340/CP2102
bridge rather than native USB. Raw GPIO numbers do not change; only the pad
labels do. This assumption announces itself — wrong board is a compile error or
a silent serial log, not a subtle bug — so it is not logged as an open question.

### What to get out of the session

Beyond §5.0 pass/fail, three things worth having:

1. **Path skew.** Both presence readings come off the same radar by different
   routes. The signed skew is a direct measure of what the UART decode costs,
   against R2's 1000 ms median budget.
2. **The distance envelope** (`Closest`/`Furthest detection seen`). Walk around;
   the far number is the first real measurement against the 5.6 m acceptance
   target, which §3.6 is explicit is a *test requirement*, not a link budget.
3. **Radar PCB thickness, with calipers** — §5.0 step 0.9. 1.0 vs 1.6 mm decides
   10 mm vs 9 mm standoffs, the standoffs are still unordered (§9 item 2), and
   they set the antenna-to-window geometry the whole mechanical design turns on.
   Measure it while the board is in your hand.


---

## 10. Validation run, 2026-09-05 — what a real validator found

Nothing in §7 above counted as evidence: a YAML parser answers "is this
well-formed", not "will this build". ESPHome is not installed on the Windows box
and the add-on's binary is not reachable over the `H:` share — `/config/esphome`
holds the *configs*, not the compiler — so **esphome 2026.8.2 was installed into
a scratch venv** and `esphome config` run against all three firmwares.

It found three hard failures. All three would have surfaced at the bench.

### 10.1 The bench file had a sensor without its component

`text_sensor: platform: debug` requires a top-level `debug:` component. The
production firmware has one; the bench file never did. Hard config failure, not
a warning. One line to fix, and it would have cost the first ten minutes of
tomorrow.

### 10.2 `initial_value` / `restore_value` are not valid on the ld2410 number platform — and that left a hole under R9

The production firmware set both on all 21 number entities. They belong to
`number: platform: template`; the ld2410 platform uses plain
`number.number_schema()`, which has neither. The config did not compile.

**The important part is what fixing it exposed.** Those entities *mirror* what
the module holds in NVM and write to it when changed. They do not push a value
at boot. So declaring thresholds in YAML never put them in the radar —

> R9 says "commissioned state must be reproducible from version control." With
> the config as written, that would have been **true of the file and false of
> the hardware**: the numbers in git, the radar running on whatever was in its
> NVM, and every review of the YAML reporting compliance. That is the precise
> failure R9 exists to prevent, wearing the costume of satisfying it.

The push is now explicit — `script.push_commissioned_state`, fired once per boot
on the first `version` string the radar reports. That trigger is deliberate: it
is the same signal that proves the UART is locked (§5.0 step 0.3), and pushing
21 parameters into a UART that has not come up writes nothing while reporting
success.

**Consequence, and it is intended:** a threshold tuned from the HA dashboard is
lost at the next reboot, because the YAML wins. Tune from HA to explore; commit
to the per-device file to keep it.

Also learned from the schema: `timeout`, `max_move_distance_gate` and
`max_still_distance_gate` are `cv.Inclusive` in one group — specify any and you
must specify all three.

### 10.3 Seven dashboard entity ids referenced entities that will never exist

Every dashboard id is a prediction from a naming pattern, which `ENTITIES.md`
says never to trust. They cannot be resolved against the registry before the
hardware exists — but they **can be derived**, because ESPHome's generation is
deterministic: `slugify(device_friendly_name + " " + entity_name)`.

`scripts/xcheck_entities.py` (in the scratchpad) does that and diffs it against
every id the dashboards reference. It found:

- **2 in the bench view.** I had named two entities `"g0 still threshold
  (inert)"`, and the parenthetical slugified straight into the id
  (`..._g0_still_threshold_inert`). This is the *same mistake* I had already
  fixed once this session, when gate ranges in names produced
  `..._g0_move_0_00_0_75_m`. Qualifiers belong on the dashboard label, where a
  human reads them — never in the name, which is also an address.
- **5 in the family view.** The `history_stats` sensors take their entity_id
  from `name`, not from `unique_id`. I wrote short unique_ids
  (`mmw_family_hours_couch`) and referenced *those*; HA will create
  `mmw_family_hours_on_couch` from the name.

A wider check now resolves every reference against all three sources that can
supply one — the firmwares (210 entities), the package (52), and the live
registry (1,790):

```
mmwave-bench      70 refs   OK
mmwave-office     45 refs   OK
mmwave-family     69 refs   OK
package cites 68 entity ids; 0 unresolved
```

### 10.4 Where validation stands now

| | |
|---|---|
| `esphome config`, all three firmwares | ✅ **VALID** (esphome 2026.8.2) |
| All 184 dashboard entity references | ✅ resolve to a real source |
| All 68 package entity citations | ✅ resolve |
| YAML parse, all 8 files | ✅ |
| `mmwave_calibrate.py` | ✅ compiles; two-direction synthetic test passes |
| `esphome config` on **Bill's own 2026.4.3** | ✅ all three VALID — see §10.6 |
| **`esphome compile`, bench firmware** | ✅ `Successfully compiled program.` Flash 53.6%, RAM 33.6% |
| **`esphome compile`, office node** | ✅ `Successfully compiled program.` Flash 55.0%, RAM 34.2% |
| **`esphome compile`, family node** | ✅ `Successfully compiled program.` Flash 54.9%, RAM 34.2% |
| HA `check_config` / deploy | ❌ not run — package is still a draft |

`esphome config` validates schema, substitutions, component dependencies and id
resolution. It does **not** compile the lambdas. A full `esphome compile` is the
only thing that does, and it needs the ESP-IDF toolchain.

**Compile status: ACHIEVED for all three firmwares.**

First attempt failed with `ERROR: MSys/Mingw is not supported` — ESP-IDF's
installer rejects the Git Bash environment. All six toolchain packages had
downloaded fine; only the environment check refused. Re-run from native
PowerShell:

```
INFO Successfully compiled program.
RAM:   [===       ]  33.6% (used 107,840 of 321,296 bytes)
Flash: [=====     ]  53.6% (used 983,332 of 1,835,008 bytes)
```

Artifacts at `C:\esphome_build\mmwave-benchuild\` — `firmware.elf`,
`firmware.factory.bin` (1.00 MB), `firmware.ota.bin` (0.94 MB).

**So the lambdas compile.** `std::isfinite`, `.state.empty()`, the float/int32
casts in the skew publishes, and the `ha_time.now()` wall-clock arithmetic all
build against the real ESP-IDF toolchain for `seeed_xiao_esp32c3`. That was the
last doc-sourced guess in the bench path.

Headroom is comfortable — a third of RAM and half the app partition — which
matters because the bench file carries DEBUG logging, all 18 gate series and
the extra instrumentation the production build does not.

*Method note: verify a compile by its ARTIFACTS, not its exit code.* The first
run reported `[exited with code 0]` while having failed — that was the shell
pipeline's status, not esphome's. `firmware.elf` with a current timestamp is the
evidence; the exit code is not.

### 10.5 Two checkers now live with the config

Both are committed next to the YAML rather than left as one-off scratch work,
because they answer questions that recur every time an entity is renamed:

| script | what it answers |
|---|---|
| `scripts/check_entity_ids.py` | does every dashboard and package entity reference resolve against the firmwares, the package, or the live registry? |
| `scripts/check_templates.py` | does every Jinja template parse, and do the `for:` duration templates render to a valid `HH:MM:SS` across the whole input_number range? |

`check_templates.py` also renders the two idle-timeout templates against six
cases including `module timeout > room total` (floors at zero rather than going
negative) and a one-hour total (does not overflow the minutes field). 71
templates, 0 syntax errors, 6/6 duration cases correct.


### 10.6 Two things found while compiling, both practical

**You already have a local ESPHome workflow, and this belongs in it.**
`C:/Users/wkcol/esphome/` has its own venv (`venv/Scripts/esphome.exe`), your
three node YAMLs, a `secrets.yaml`, and a populated `.esphome`. The scratch venv
I built was redundant. **The mmWave files should live there**, alongside
`basement-th-node.yaml`, not in a temp directory — same place, same secrets, same
build cache.

**Your ESPHome is 2026.4.3; I had validated against 2026.8.2.** Four months
apart, and §5.11 exists precisely because LD2410/ESPHome compatibility
regressions have shipped. Re-ran all three configs through *your* binary:

```
mmwave-bench.yaml          VALID on 2026.4.3
mmwave-office-node.yaml    VALID on 2026.4.3
mmwave-family-node.yaml    VALID on 2026.4.3
```

So the configs are portable across both. The **compiles** were done on 2026.8.2,
so the binary you flash from 2026.4.3 is not byte-identical to what was built
here — but every schema key, component dependency and id resolves on both.

**Three secrets are missing from your `esphome/secrets.yaml`.** It currently has
`wifi_ssid` and `wifi_password`. These firmwares also reference:

| key | what to put there |
|---|---|
| `api_encryption_key` | generate a fresh 32-byte base64 key — do **not** reuse the basement node's |
| `ota_password` | any strong string |
| `ap_password` | fallback-AP password, ≥8 chars |

I have not written them. They are credentials, they are yours to choose, and
`secrets.yaml` is the one file in this project I should not be editing on your
behalf.

*(Note the basement node inlines its Wi-Fi credentials and API key directly in
its YAML rather than using `!secret`. Given `home-assistant-config` is a public
repo, converting it is worth doing — separately, and deliberately.)*


---

## 11. Community projects reviewed, 2026-09-05

Surveyed for tested code and ideas rather than starting from first principles.
Sources: [EverythingSmartHome/everything-presence-lite], [ApolloAutomation/MSR-2],
[tobsch/ld2410], [iharosi/esphome-presence-sensor], [yohaybn/esphome-multi-presence],
plus the ESPHome LD2410 docs and HA core issue #123732.

**Headline: nothing out there does the thing this project is actually about.**
Every configuration found is *firmware only* — it exposes the LD2410's entities
to HA and stops. None of them derive thresholds from data, none carry a latch
against the lamp lighting its own sensor, none detect manual override, and none
cross-check presence against a second sensor. The community's collective advice
on calibration is "budget twenty minutes and tune the gates by eye until the
false triggers stop." That is not a criticism of those projects — it is a fair
description of what a general-purpose device can offer. But it does mean §5.9
has no prior art to borrow, and the analysis script stays the novel part.

### 11.1 Adopted

**`esphome: min_version:`** — from [tobsch/ld2410]. §5.11 says "pin the ESPHome
version explicitly rather than tracking latest" and then relies on somebody
remembering. `min_version: 2026.4.3` makes the build **fail** on anything older,
which is the difference between a policy and a gate. Set to Bill's installed
version, which is also the floor these configs were validated against. Raise it
deliberately, after re-running A1/A2/A6 — never as a side effect of an upgrade.

**`glass_attenuation_factor`** — prompted by the Everything Presence Lite's lux
*offset* entity, then corrected. EPL offers an additive trim; the ESPHome
veml7700 component has a **multiplicative** one
(`veml7700.cpp: apply_glass_attenuation_`), and multiplicative is the physically
right shape because attenuation scales rather than offsets. An additive trim is
correct at exactly one light level.

This matters more than it looks. §5.6's entire case for the VEML7700 over a
phototransistor is that ~18 lx means the same thing on every node and survives a
sensor swap — and that quietly assumes the number is **room** lux. The part sits
behind an enclosure wall, so it reports room lux × transmission. Uncorrected, the
threshold is portable only between nodes in identical boxes, which is a much
weaker claim than the design rests on. §5.0 step 0.6 already stages the exact
comparison needed to measure it; the value now goes in the §5.8 baseline, and a
lid change invalidates it.

### 11.2 Rejected, and why the reasons are worth keeping

| pattern | seen in | why not here |
|---|---|---|
| `delta: 5` filter on the lux sensor | Everything Presence Lite | EPL publishes lux as *information*; this design makes a *control decision* on it at 18 lx. A delta filter means a drift from 22 → 18.5 lx publishes nothing, so HA still believes 22 while the room is below threshold. Same reasoning that rejected `delta` on the gate energies, different consequence. |
| `bluetooth_proxy` / `esp32_ble_tracker` | tobsch/ld2410 | A genuinely good use of a mains-powered ESP32 in a room — but §2 spends real effort removing 2.4 GHz activity from a sealed box 10 mm from a 24 GHz radar, including disabling the module's own BLE. Adding a continuously scanning BLE radio would undo that deliberately. |
| UART on **GPIO20/21** | tobsch **and** iharosi — both | Those are U0RXD/U0TXD on the ESP32-C3. §3.3 avoids them because the ROM prints the boot log there, which then goes into the radar's RX at every boot. Usually harmless; the radar discards it. But this is the community's *default* pattern and it is worth recording that the design departs from it knowingly, not accidentally. GPIO4/5 stay. |
| Status LED on **GPIO2** | iharosi | GPIO2 is a strapping pin. Fine as an output, but §3.3's caution stands, and an LED inside a sealed box is invisible anyway. |

### 11.2a Screek — the one that actually changed the design

`screekworkshop/screek-human-sensor` on GitHub, `1u/` (their LD2410C product,
already cited in §0 and §3.5). Their README is four sentences and two of them
matter.

> *"In order to adapt to work in a small space, we made some optimizations:
> including adjusting the WIFI transmit mode (we lowered it to 15dB), and
> downconverting the ESP32 to 80Mhz."*

Their firmware confirms it: `output_power: 15dB`, `board_build.f_cpu:
80000000L`, and — pointedly — `# power_save_mode: NONE` **commented out** with
`power_save_mode: LIGHT` active instead. That last one is the direct opposite of
the choice here, made by someone shipping the product.

**This is the first source that challenges a decision rather than confirming
one.** §2 treats 2.4 GHz coexistence as being about the *radar's* BLE and
answers it with a ground plane. Screek's evidence says the *ESP's own Wi-Fi* is
also a contaminant, and they paid latency and link margin to quiet it.

The design can probably afford to decline all three: Screek had 13.8 mm of total
enclosure depth, this has 27 mm with a continuous ground plane between the two
boards on opposite faces of the carrier. That *should* be worth more than what
Screek could buy. But "should" is a hypothesis, so it is now a measurement —
**new acceptance test A12a**: 10 minutes of empty-room gate energies at 20 dB,
10 minutes at 15 dB, compare the floors. Clutter in the room does not care what
the ESP's transmitter is doing, so **a floor that moves with `output_power` is
coming from inside the box.** Cheapest remedy first, since `output_power` costs
R2 nothing and `power_save_mode: LIGHT` costs it directly.

Also folded in: §3.7 gains the node's own Wi-Fi as a second suspect for an
unexplained near-gate floor, and §2 records the trade explicitly.

> *"we abandoned setting it in the esphome and used the HLKRadarTool
> configuration instead"*

A shipping manufacturer gave up on configuring the LD2410 over ESPHome and moved
the parameters into module NVM out-of-band. That is exactly the R9 failure this
design rejects, so it is not a pattern to copy — **but it is evidence that the
ESPHome configuration path is finicky, and the boot-time R9 push is the newest
and least proven thing in the production firmware.** The mitigation was already
there and is now explicit in §5.3a: the push ends with `query_params`, so
verification is a read-back rather than an assumption. Push, query, confirm the
numbers HA shows match the YAML — on a bench, not by inference from a node that
seems to work.

Two smaller confirmations: Screek also use `min_version:` (2025.5.1), which
independently supports adopting it; and they use an **LDR** for light, not a
calibrated part, which is the design §5.6 explicitly argues against.

### 11.2b Apollo Automation MSR-2 — a better bench pass criterion

`ApolloAutomation/MSR-2`, `Integrations/ESPHome/Core.yaml` — 1,047 lines of
production firmware for the device §10.6 already benchmarks against.

**Adopted: their factory self-test.** Apollo gate each sensor not on being
*present* but on producing a *plausible value*, and for the radar that is:

```cpp
return (id(radar_has_target).state == true && id(radar_detection_distance).state > 10);
```

Green LED if every sensor passes, red if not.

That is materially better than the bench rig's `UART healthy`, which only proves
the crossover and baud rate are right. **A module with a damaged antenna, a
blocked aperture, or thresholds left at 100 answers `query_params` perfectly and
detects nothing.** The bench firmware now carries a latching `Self-test passed`
entity — UART up *and* a real detection at a plausible distance — and it is the
first badge on the view. Latching is deliberate: it answers "has this rig EVER
worked", which on a bench being re-wired is the question you keep asking.
`Node restart` re-arms it.

**Confirmations worth having:**

- Apollo declare **all nine gates with both `move_threshold` and
  `still_threshold`**, g0 and g1 included — independent confirmation of the
  `cv.Required` finding, arrived at from the schema and now seen in shipping
  firmware.
- They do **not** push threshold values at boot either. Nobody in the survey
  does. The R9 push script remains the novel part, and §5.3a now records
  Screek's warning about that path along with the read-back that verifies it.
- `ignore_strapping_warning: true` appears on their GPIO9 input — so **ESPHome
  itself warns about strapping pins**. §3.3's caution is one the toolchain
  shares; this design never needs the flag, which is the point.
- `bluetooth_password.set` exists as an ESPHome action, and Apollo use it —
  they keep the radar's BLE and put a password on it. §2 disables it outright,
  which is the stronger choice for a sealed box with no service access, but it
  is worth knowing the middle option exists.
- UART on **GPIO21/20** again. That is **three of three** community projects on
  U0TXD/U0RXD. The design's GPIO4/5 is now a well-evidenced departure rather
  than an untested preference.

### 11.2c Who exposes the gate thresholds, and who pushes them — measured 2026-09-07

Prompted by a claim that needed checking before it was published: that other
projects had *given up* on setting gate variables from HA. Two of the three
contradict it. Counts below are from reading their shipped configs, not from
recollection.

| | per-gate thresholds in HA | `number.set` actions | source of truth |
|---|---|---|---|
| Apollo MSR-2 | **yes — all 18**, + timeout + both max gates | **0** | module NVM |
| Everything Presence Lite (ld2410-base) | **yes — all 18**, + timeout + both max gates | **0** | module NVM |
| Screek 1U | **no** — g0–g8 thresholds present but commented out | 0 | HLKRadarTool, out of band |
| **this project** | yes — all 18 | **21** | **git** |

**Exposing the thresholds to HA is the common pattern, not a rare one.** Any
claim of novelty resting on "you can set gate variables from Home Assistant" is
refuted by two shipping products in about five minutes. Do not publish it.

**Nobody pushes them, and that is the actual gap.** Zero `number.set` actions in
either Apollo's or EPL's configs. Their thresholds live in module NVM and in
whatever a user last typed into the UI; the YAML can declare values the radar
does not hold, and nothing detects the divergence.

That is not carelessness on their part — **the ESPHome `ld2410` number platform
works against it.** It accepts no `initial_value` and no `restore_value`, so
there is nothing to push *from*. Confirmed in Apollo's own file: it carries 15
`initial_value` and 16 `restore_value` entries and **not one of them is on a
radar number** — they are all on their own `template` numbers, because the
ld2410 platform will not take them. §4.1 reached the same conclusion from the
component source; this is the same hole seen from the other side, in production
firmware, by a vendor who plainly knows the component well.

**So the defensible claim is narrower and stronger than the one it replaces:**

> Gate thresholds settable from Home Assistant are common. Gate thresholds
> **held in version control, pushed into module NVM at boot, and verified by
> read-back** appear not to exist elsewhere — and the ESPHome component
> actively obstructs it, since its number platform has no initial value to push
> from.

Evidenced 2026-09-07 rather than asserted: all 21 commissioned values scrambled
to distinct wrong numbers, node rebooted, **21/21 restored from the
substitutions**, with `query_params` read-back as the proof rather than the log
line. §5.9's statistical derivation is the second half of the claim and is
**not yet run** — the honest position today is that the mechanism is proven and
the method is designed.

**One citation still needs pinning.** The design doc §5.0 quotes Screek as
having "abandoned setting it in the esphome and used the HLKRadarTool
configuration instead". Their commented-out thresholds are consistent with it,
but that wording is **not** in `1u/yaml/human-sensor-1u-github.yaml`. Find the
actual source — their docs site or a commit — before it appears in anything
published, or drop the quotation and cite the commented-out block instead,
which is directly checkable.

### 11.3 Independently confirmed

`power_save_mode: none` appears in both community configs — arrived at
separately here from R2's latency budget, and it is reassuring to find the same
conclusion reached by people with hardware in hand.

`wifi: reboot_timeout: 0s` (iharosi) is the one open trade. This design uses
`0s` on the **api** block (an HA outage must not flap the node) but keeps
**15 min** on wifi, so a wedged Wi-Fi stack still self-heals. Going to `0s`
there too would maximise local-path uptime at the cost of never recovering from
a hung radio without a power cycle. Left at 15 min; revisit if A12's RSSI work
turns up instability.

### 11.4 One thing the survey could not settle

HA core issue #123732 reports eight LD2410 sensors going to "unknown state"
after ESPHome **2024.7.3**, with the issue closed as *not planned* and no root
cause recorded. It is exactly the class of regression §5.11 was written about,
and its unresolved status is the argument for `min_version` plus re-running the
acceptance tests after any upgrade — a documented break with no documented fix
is worse than a known bug.

[EverythingSmartHome/everything-presence-lite]: https://github.com/EverythingSmartHome/everything-presence-lite
[ApolloAutomation/MSR-2]: https://github.com/ApolloAutomation/MSR-2
[tobsch/ld2410]: https://github.com/tobsch/ld2410
[iharosi/esphome-presence-sensor]: https://github.com/iharosi/esphome-presence-sensor
[yohaybn/esphome-multi-presence]: https://github.com/yohaybn/esphome-multi-presence
