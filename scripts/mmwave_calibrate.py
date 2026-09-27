#!/usr/bin/env python3
"""
mmwave_calibrate.py — derive LD2410C gate thresholds from labelled HA data.

Design doc: mmwave-presence-node-design.md Rev 1.4, sections 5.3 and 5.9.
Closes open item 8 ("write the §5.9 analysis script and commit it with the
config"). Rev 0.1 DRAFT 2026-09-05 — NOT RUN AGAINST REAL DATA.
Rev 0.2 2026-09-26 — time-weighted. Proven on synthetic data only.
Rev 0.3 2026-09-26 — settle window after each label change; a gate whose L(T)
exceeds its budget is no longer reported OK. Proven on synthetic data only.

R13 RECORD, 2026-09-26: Rev 0.1 computed every statistic over recorder ROWS.
The recorder writes a row only when a state CHANGES, so a gate holding one
value for a minute gave one row and a gate flickering between two values gave
twelve: the percentiles were weighted by how often a value changed, not by how
long it held. On the office node's first labelled desk run (534 s,
2026-09-26) g5_still's median was 46 by row and 98 by time [M]. The same
defect under-read L(T) (a value held longer than max_gap_s broke the run),
made the collection-B blower fraction a fraction of LABEL CHANGES, and gave
the label still in force when the database was copied zero minutes. Rev 0.2
reads every series as the step function it is, on one grid (resample()).

WHAT THIS DOES, and why it is a script rather than a query
-----------------------------------------------------------------------------
§5.9.5 gives Flux templates for the two percentiles. Those two numbers are the
INPUT to the method, not the method. The actual selection needs a threshold
sweep, a longest-run-below-threshold statistic, and an autocorrelation — none of
which are one-line aggregations, and all of which have to be reproducible from
version control rather than from a Grafana panel somebody remembers building.

    E_clutter = P99.5( empty room )        <- false positives come from here
    E_signal  = P5( occupied, motionless ) <- false negatives come from here
    T0        = sqrt(E_clutter * E_signal) <- a starting estimate, nothing more
    FPR(T), FNR(T), L(T)                   <- the operating curve, which is the
                                              actual basis for the choice
    SM = E_signal / E_clutter              <- if <= 1, STOP. No threshold works.

SELECTION RULE (§5.9.2): the detector fires on energy > threshold, so lower is
more sensitive. A false negative — the light going off on someone reading — is
much more expensive than a lamp on five minutes too long. So: the LOWEST T that
holds FPR acceptable, subject to L(T) < IDLE_TIMEOUT / 3.

WHY NOT mean +/- k*sigma: gate energies are bounded 0-100 and heavily
right-skewed. The mean is not where the action is and sigma is not meaningful;
the quantities of interest are the tails.

DATA SOURCE
-----------------------------------------------------------------------------
Reads the Home Assistant recorder database directly. There is no InfluxDB in
this config — §5.9.5's Flux templates assume a `homeassistant` bucket that does
not exist here — so the recorder IS the store, and its 14-day purge window is
the collection deadline.

    COPY THE DATABASE FIRST. Do not point this at a live home-assistant_v2.db
    while HA is writing to it.
        ha> cp /config/home-assistant_v2.db /tmp/cal.db
    A read against the live file in WAL mode can block the recorder, and the
    recorder blocking is how you lose the tail of your own collection.

USAGE
-----------------------------------------------------------------------------
    python mmwave_calibrate.py --db /tmp/cal.db --room office
    python mmwave_calibrate.py --db /tmp/cal.db --room family \
        --idle-timeout 300 --emit esphome
"""

from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field

try:
    import numpy as np
except ImportError:
    sys.exit("numpy is required: python -m pip install numpy")


# =============================================================================
# Configuration
# =============================================================================

# Which labels mean what. These are the input_select options from
# packages/mmwave_presence.yaml, slugified by sensor.mmw_<room>_cal_class.
EMPTY_LABELS = {"no_one_present"}

SEAT_LABELS = {
    "office": {"sitting_at_desk"},
    "family": {
        "sitting_on_couch",
        "sitting_in_armchair",
        "sitting_at_kitchen_table",
    },
}

# Motion classes drive the MOVE thresholds; seats drive the STILL thresholds.
# §5.4: they are independently settable and the failure modes are different, so
# they are never derived from the same population.
MOTION_LABELS = {
    "office": {"moving_in_office", "entering_office"},
    "family": {"working_in_kitchen", "walking_through"},
}

ENTITY_PREFIX = {"office": "office_mmwave", "family": "family_mmwave"}

N_GATES = 9
GATE_DEPTH_M = 0.75  # Appendix A; protocol V1.07 Table 8, factory default

# RESAMPLING (Rev 0.2). Every series is sampled on one 1 s grid. 1 s rather
# than the gate log period because that period is runtime-adjustable (5 s for
# the passive collection, 1 s for focused seat runs) and a mixed collection
# needs a single grid.
GRID_S = 1.0
# Used only where number.<prefix>_gate_log_period has no history: the
# `gate_log_period` substitution in esphome/mmwave-node-common.yaml. The report
# says how much live data it was assumed for.
DEFAULT_GATE_PERIOD_S = 5.0
# Counts are SNAPSHOTS - grid seconds divided by the publish period in force -
# not grid points: a 5 s value read five times on a 1 s grid is still one
# observation, and 1/n below is only honest if n counts observations.
MIN_SNAPSHOTS = 100

# SETTLE WINDOW (Rev 0.3). A label is pressed from inside the room, so the
# seconds after each change still hold the transition it announces: whoever
# pressed "no one present" is walking out. Office node, 2026-09-26: in the
# first 10 s after each of the 2 empty labels, max(g2-g5 still) read 99 and 98,
# and by 10 s it was <= 14 [M, n=2 segments, 5 s snapshots]. With a few hundred
# empty snapshots P99.5 IS the maximum, so those seconds set E_clutter on their
# own. 15 s = the 10 s observed + one 5 s period of margin [D]. n=2 is thin:
# re-measure on the heartbeat firmware and change this number, not the data.
DEFAULT_SETTLE_S = 15.0

# STATIC SENSITIVITY IS INERT ON GATES 0 AND 1.
# Protocol V1.07 Table 7 marks both "-(not settable)" — 0-1.5 m is too close for
# the module to threshold statically. Deriving a value would produce a number
# the hardware ignores: the report would look complete and two rows would be
# fiction.
#
# BUT ESPHome's schema makes still_threshold cv.Required in every gX block, g0
# and g1 included, so the substitution must still EXIST or the device file will
# not compile. The emitter therefore writes 0 for these — ESPHome's own
# documented default — and the report says why rather than staying silent.
NO_STILL_THRESHOLD_GATES = {0, 1}
INERT_STILL_VALUE = 0

# Selection targets.
#
# THE FPR TARGET IS NOT 0.005, and the reason matters.
# P99.5 is how E_clutter is DEFINED (§5.9), which invites setting the sweep
# target to the matching 0.005. That would be a per-SAMPLE rate at 1 Hz — about
# 18 above-threshold samples per hour. A6 requires ZERO false triggers in two
# hours with the HVAC running. Reconciling the two:
#
#     FPR_target < 1 / (2 h * 3600 s/h * 1 sample/s) = 1.4e-4
#
# so that the EXPECTED number of false samples across the whole A6 window is
# below one. E_clutter's P99.5 stays as the diagnostic it was defined to be;
# the sweep target comes from the acceptance test it has to pass.
DEFAULT_FPR_TARGET = 1.4e-4
DEFAULT_IDLE_TIMEOUT = {"office": 90, "family": 300}

# A seat "occupies" a gate when its median still energy rises meaningfully above
# the EMPTY median in that gate. Comparing against the empty P99.5 instead (the
# obvious first attempt) silently reclassifies a shadowed seat as an unoccupied
# gate — which converts §5.9.4's stop condition into a shrug.
OCCUPANCY_LIFT = 3.0  # energy counts above the empty-room median

# §5.9.4 margin bands.
SM_COMFORTABLE = 2.0
SM_UNUSABLE = 1.0


# =============================================================================
# Recorder access
# =============================================================================


def load_series(db_path: str, entity_ids: list[str]) -> dict[str, tuple]:
    """Return {entity_id: (timestamps float64, states object array)}.

    HA >= 2023.4 keeps entity ids in `states_meta` and joins by metadata_id.
    Older databases carry entity_id on `states` directly; both are handled
    because a database restored from an old backup is exactly the sort of thing
    that turns up mid-collection.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = None
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    modern = "states_meta" in tables

    out: dict[str, tuple] = {}
    for eid in entity_ids:
        if modern:
            cur.execute(
                """
                SELECT s.last_updated_ts, s.state
                  FROM states AS s
                  JOIN states_meta AS m ON m.metadata_id = s.metadata_id
                 WHERE m.entity_id = ?
                   AND s.last_updated_ts IS NOT NULL
                 ORDER BY s.last_updated_ts
                """,
                (eid,),
            )
        else:
            cur.execute(
                """
                SELECT last_updated_ts, state
                  FROM states
                 WHERE entity_id = ?
                   AND last_updated_ts IS NOT NULL
                 ORDER BY last_updated_ts
                """,
                (eid,),
            )
        rows = cur.fetchall()
        if not rows:
            out[eid] = (np.empty(0), np.empty(0, dtype=object))
            continue
        ts = np.fromiter((r[0] for r in rows), dtype="float64", count=len(rows))
        st = np.array([r[1] for r in rows], dtype=object)
        out[eid] = (ts, st)

    con.close()
    return out


def to_float(states: np.ndarray) -> np.ndarray:
    """Numeric states, with unknown/unavailable/None as NaN."""
    vals = np.full(states.shape, np.nan, dtype="float64")
    for i, s in enumerate(states):
        if s in (None, "unknown", "unavailable", ""):
            continue
        try:
            vals[i] = float(s)
        except (TypeError, ValueError):
            pass
    return vals


def step_lookup(
    class_ts: np.ndarray, class_val: np.ndarray, query_ts: np.ndarray
) -> np.ndarray:
    """The class in force at each query time.

    A label is a step function: it holds from the moment it is set until it is
    changed. `searchsorted(side='right') - 1` gives the last change at or before
    each sample. Samples before the first label get "" and are dropped.

    Doing the join THIS way, rather than by binning both series onto a common
    grid, is deliberate: binning would silently reassign the samples either side
    of a label change, and those are exactly the samples where somebody was
    getting up out of a chair.
    """
    if class_ts.size == 0:
        return np.full(query_ts.shape, "", dtype=object)
    idx = np.searchsorted(class_ts, query_ts, side="right") - 1
    out = np.full(query_ts.shape, "", dtype=object)
    valid = idx >= 0
    out[valid] = class_val[idx[valid]]
    return out


def resample(ts: np.ndarray, vals: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """The value in force at each grid time; NaN before the first row.

    ADDED 2026-09-26 (Rev 0.2). A recorder row is not a sample: it is the start
    of an interval of unknown length, written only because the state changed.
    Reading the value in force at each grid instant turns rows back into a time
    series, so every statistic downstream is weighted by time. It is the same
    instantaneous read step_lookup() does for labels, not a binning, so that
    docstring's point about samples either side of a label change still holds.
    """
    out = np.full(grid.shape, np.nan, dtype="float64")
    if ts.size == 0:
        return out
    idx = np.searchsorted(ts, grid, side="right") - 1
    ok = idx >= 0
    out[ok] = vals[idx[ok]]
    return out


# =============================================================================
# Statistics
# =============================================================================


def pct(x: np.ndarray, q: float) -> float:
    """Percentile with linear interpolation, NaN-safe. Empty -> NaN."""
    x = x[~np.isnan(x)]
    return float(np.percentile(x, q)) if x.size else float("nan")


def longest_run_below(
    ts: np.ndarray, vals: np.ndarray, thresh: float, max_gap_s: float = 5.0
) -> float:
    """L(T): longest continuous interval, in seconds, with value < T.

    §5.9.3. This is the metric that matches R1, and P5 is not: P5 says 5% of
    samples fall below a level, not whether they are scattered through the run
    or form one ninety-second gap. The idle timeout bridges scattered dropouts.
    It does not bridge one long one.

    `max_gap_s` breaks the run across sampling gaps — an engineering-mode window
    that closed, a reboot, a Wi-Fi stall. Without it a 6-hour hole between two
    below-threshold samples reads as a 6-hour dropout, and the whole gate gets
    condemned on the strength of a missing cable.

    On the Rev 0.2 grid a gap is a masked stretch (engineering mode off, sensor
    unavailable, another label). Rev 0.1 fed this recorder rows, so a value
    merely HELD for more than max_gap_s also broke the run - and a dropout that
    sat at one value for a minute read as a 0 s run. That is the direction that
    passes a gate it should fail.
    """
    if ts.size == 0:
        return 0.0
    below = vals < thresh
    longest = cur_start = 0.0
    prev_t = None
    in_run = False
    for t, b in zip(ts, below):
        if prev_t is not None and (t - prev_t) > max_gap_s:
            in_run = False  # sampling gap: the run cannot be verified
        if b:
            if not in_run:
                in_run, cur_start = True, t
            longest = max(longest, t - cur_start)
        else:
            in_run = False
        prev_t = t
    return float(longest)


def autocorr_report(
    ts: np.ndarray, vals: np.ndarray, max_lag_s: int = 120
) -> tuple[float, float, int]:
    """(decorrelation lag s, effective N, raw N) for one labelled run.

    §5.3 withdrew the earlier "N=150 from an assumed 4 s decorrelation" claim
    and replaced it with "compute the autocorrelation and report the observed
    lag". This is that computation.

    Lag is the first lag at which the ACF falls inside the +/- 2/sqrt(n) white
    noise band — the standard test, and stricter than a 1/e crossing on a series
    with a long shoulder. N_eff uses the Bartlett / Anderson correction
        N_eff = N / (1 + 2 * sum(rho_k))
    which is what makes a percentile from 600 correlated samples honest about
    being worth rather fewer.
    """
    x = vals[~np.isnan(vals)]
    n = x.size
    if n < 30:
        return float("nan"), float("nan"), n

    dt = float(np.median(np.diff(ts))) if ts.size > 1 else 1.0
    if not (dt > 0):
        dt = 1.0

    x = x - x.mean()
    denom = float(np.dot(x, x))
    if denom == 0:  # a gate pinned at one value
        return 0.0, float(n), n

    max_lag = min(int(max_lag_s / dt), n // 4)
    band = 2.0 / math.sqrt(n)
    rho = [1.0]
    lag_s = float("nan")
    for k in range(1, max_lag + 1):
        r = float(np.dot(x[:-k], x[k:]) / denom)
        rho.append(r)
        if math.isnan(lag_s) and abs(r) < band:
            lag_s = k * dt

    tail = [r for r in rho[1:] if abs(r) >= band]
    n_eff = n / (1.0 + 2.0 * sum(tail)) if (1.0 + 2.0 * sum(tail)) > 0 else float(n)
    return lag_s, float(n_eff), n


@dataclass
class GateResult:
    gate: int
    channel: str  # "move" or "still"
    e_clutter: float = float("nan")
    e_signal: float = float("nan")
    t0: float = float("nan")
    threshold: float = float("nan")
    fpr: float = float("nan")
    fnr: float = float("nan")
    l_t: float = float("nan")
    sm: float = float("nan")
    margin: float = float("nan")
    verdict: str = ""
    driving_class: str = ""
    n_clutter: int = 0
    n_signal: int = 0
    acf_lag_s: float = float("nan")
    n_eff: float = float("nan")
    notes: list[str] = field(default_factory=list)


def sweep(
    clutter: np.ndarray,
    signal: np.ndarray,
    sig_ts: np.ndarray,
    fpr_target: float,
    l_limit: float,
) -> tuple[float, float, float, float, list[str]]:
    """§5.9.2. Returns (T, FPR, FNR, L(T), notes)."""
    notes: list[str] = []
    clutter = clutter[~np.isnan(clutter)]
    signal_clean = signal[~np.isnan(signal)]
    if clutter.size == 0 or signal_clean.size == 0:
        return (
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            ["no data in one of the two classes"],
        )

    best = None
    over = 0
    for t in range(0, 101):
        fpr = float((clutter > t).mean())
        fnr = float((signal_clean < t).mean())
        if fpr <= fpr_target:
            lt = longest_run_below(sig_ts, signal, float(t))
            if lt < l_limit:
                best = (float(t), fpr, fnr, lt)
                break  # lowest T that holds: the selection rule
            # Rev 0.3: one note, not one per T. L(T) cannot fall as T rises
            # (more samples sit below a higher T), so every T above this one
            # fails too; the per-T notes were ~60 identical lines once the
            # L(T) verdict put them in the report.
            over += 1
            if over == 1:
                notes.append(
                    f"T={t} met the FPR target but L(T)={lt:.0f}s exceeds the "
                    f"{l_limit:.0f}s budget; kept searching upward"
                )
    if over > 1:
        notes.append(f"... and likewise for the {over - 1} T values above it")

    if best is None:
        # Nothing satisfies both. Report the FPR-only choice and say so loudly —
        # this is usually geometry, not tuning (§5.9.4).
        for t in range(0, 101):
            fpr = float((clutter > t).mean())
            if fpr <= fpr_target:
                fnr = float((signal_clean < t).mean())
                lt = longest_run_below(sig_ts, signal, float(t))
                notes.append(
                    "NO T SATISFIES BOTH FPR AND L(T). Reported T meets the "
                    "FPR target only. Do not tune around this — check geometry."
                )
                return float(t), fpr, fnr, lt, notes
        notes.append("NO T MEETS THE FPR TARGET AT ALL. Gate is contaminated.")
        return float("nan"), float("nan"), float("nan"), float("nan"), notes

    return (*best, notes)


# =============================================================================
# Main analysis
# =============================================================================


def analyse(
    db: str,
    room: str,
    idle_timeout: float,
    fpr_target: float,
    corroborator: str | None = None,
    settle_s: float = DEFAULT_SETTLE_S,
) -> tuple[list[GateResult], dict]:
    prefix = ENTITY_PREFIX[room]
    class_entity = f"sensor.mmw_{room}_cal_class"
    eng_entity = f"switch.{prefix}_radar_engineering_mode"
    period_entity = f"number.{prefix}_gate_log_period"

    gate_entities = [
        f"sensor.{prefix}_g{g}_{ch}" for g in range(N_GATES) for ch in ("move", "still")
    ]
    wanted = [class_entity, eng_entity, period_entity] + gate_entities
    if corroborator:
        wanted.append(corroborator)
    series = load_series(db, wanted)

    cls_ts, cls_raw = series[class_entity]
    if cls_ts.size == 0:
        sys.exit(
            f"No history for {class_entity}. Either the package is not loaded, "
            f"the room name is wrong, or the collection has not started."
        )
    # cal_class is "label|blower|lamp"; the label is what defines the class and
    # blower/lamp are covariates carried alongside it.
    cls_label = np.array([str(s).split("|")[0] for s in cls_raw], dtype=object)
    cls_blower = np.array(
        [(str(s).split("|") + ["", ""])[1] for s in cls_raw], dtype=object
    )

    # CORROBORATED EMPTY. E_clutter is a tail percentile of the empty class,
    # and a tail percentile is exactly the statistic a few contaminated
    # samples can move. When a second, independent sensor is available -
    # here the thermostat's own occupancy - intersecting the empty class with
    # its agreement removes the samples where somebody was in the room and
    # the label had not caught up.
    #
    # It is opt-in and reported, never silent: the whole point is to run the
    # analysis BOTH ways and see whether the thresholds move. If they move a
    # lot, the uncorroborated empty class was contaminated and you have just
    # learned something about your own labelling discipline.
    corr_ts = corr_val = None
    if corroborator:
        corr_ts, corr_raw = series[corroborator]
        if corr_ts.size == 0:
            sys.exit(f"--corroborate given but {corroborator} has no history")
        corr_val = np.array([str(x) for x in corr_raw], dtype=object)

    # ---- one grid, and which instants carry LIVE gate energies (Rev 0.2) -----
    # Outside engineering mode the gate sensors do not go unavailable: they
    # HOLD their last value. Rev 0.1 was blind to that by accident - no change,
    # no row - but forward-filling would count hours of one stale value, so
    # every gate sample is masked by the engineering-mode switch explicitly.
    # Rev 0.3: on the heartbeat firmware (mmwave-node-common.yaml Rev 0.3) they
    # read unknown instead [I until observed]. The mask stays: data recorded on
    # the older firmware still holds.
    eng_ts, eng_raw = series[eng_entity]
    if eng_ts.size == 0:
        sys.exit(
            f"No history for {eng_entity}. Without it a live gate energy cannot "
            f"be told from a stale held one, and nothing below would mean "
            f"anything."
        )
    t_end = max(float(s[0][-1]) for s in series.values() if s[0].size)
    grid = np.arange(float(cls_ts[0]), t_end + GRID_S, GRID_S)
    eng_on = (
        step_lookup(eng_ts, np.array([str(x) for x in eng_raw], dtype=object), grid)
        == "on"
    )
    labels = step_lookup(cls_ts, cls_label, grid)
    # ---- settle window (Rev 0.3) - see DEFAULT_SETTLE_S ----------------------
    # Timed from changes of the LABEL only: cal_class also changes when the
    # blower or the lamp does, and nobody crossed the room when the furnace lit.
    settled = np.ones(grid.size, dtype=bool)
    if settle_s > 0:
        t_chg = cls_ts[np.r_[True, cls_label[1:] != cls_label[:-1]]]
        i = np.searchsorted(t_chg, grid, side="right") - 1
        since = grid - t_chg[np.maximum(i, 0)]
        settled = (i < 0) | (since >= settle_s)
    settle_min = float((~settled & eng_on & (labels != "")).sum()) * GRID_S / 60.0
    labels[~settled] = ""  # "" = dropped, as before any label
    blower = step_lookup(cls_ts, cls_blower, grid)
    agree = (
        step_lookup(corr_ts, corr_val, grid) == "on" if corr_ts is not None else None
    )

    per_ts, per_raw = series[period_entity]
    period = resample(per_ts, to_float(per_raw), grid)
    unknown_period = np.isnan(period) | (period <= 0)
    period[unknown_period] = DEFAULT_GATE_PERIOD_S

    def n_snap(mask: np.ndarray) -> int:
        """Snapshots, not grid points - see MIN_SNAPSHOTS."""
        return round(float((GRID_S / period[mask]).sum()))

    seats = SEAT_LABELS[room]
    motions = MOTION_LABELS[room]
    l_limit = idle_timeout / 3.0  # §5.9.3

    results: list[GateResult] = []
    diag: dict = {
        "blower_on_fraction_when_empty": float("nan"),
        "class_minutes": defaultdict(float),
        "seat_gate": {},
        "seat_lift": {},  # {seat: {gate: median lift over empty}}
        "n_empty_max": 0,  # sets the smallest certifiable FPR
        "corroborator": corroborator,
        "corr_dropped": 0,
        "corr_kept": 0,
        # the publish period that n snapshots were taken at; the report turns
        # n back into hours and FPR into false snapshots per hour with it
        "sample_period_s": (
            float(np.median(period[eng_on])) if eng_on.any() else DEFAULT_GATE_PERIOD_S
        ),
        "period_assumed_h": float((unknown_period & eng_on).sum()) * GRID_S / 3600.0,
        "settle_s": settle_s,
        "settle_min": settle_min,  # live labelled minutes the window dropped
    }

    is_empty = np.isin(labels, list(EMPTY_LABELS))

    # --- how much of the empty class had the blower running -------------------
    # §5.3 collection B is "the one people skip and it drives false positives."
    # Here it is not a separate run, it is a subset of the passive collection —
    # so the thing to check is whether that subset EXISTS.
    # CHANGED 2026-09-26: a fraction of live empty TIME. Rev 0.1 took it over
    # cal_class rows, i.e. over label and blower CHANGES.
    empty_live = is_empty & eng_on
    if empty_live.any():
        diag["blower_on_fraction_when_empty"] = float(
            (blower[empty_live] == "blower_on").mean()
        )

    # --- minutes per class ----------------------------------------------------
    # CHANGED 2026-09-26: minutes with engineering mode on, i.e. USABLE data.
    # Rev 0.1 summed gaps between cal_class rows, which gave the label still in
    # force when the database was copied zero minutes.
    for lab in np.unique(labels[eng_on]):
        if lab:
            diag["class_minutes"][lab] = (
                float((labels[eng_on] == lab).sum()) * GRID_S / 60.0
            )

    for g in range(N_GATES):
        for ch in ("move", "still"):
            if ch == "still" and g in NO_STILL_THRESHOLD_GATES:
                r = GateResult(gate=g, channel=ch)
                r.verdict = "NOT SETTABLE"
                r.notes.append(
                    "the module does not accept a static sensitivity for this "
                    "gate (protocol V1.07 Table 7), but ESPHome requires the "
                    "key, so 0 is emitted to keep the device file compiling. "
                    "The gate ENERGY is still reported and still worth "
                    "watching in §6.3 — there is just no threshold to set."
                )
                results.append(r)
                continue
            eid = f"sensor.{prefix}_g{g}_{ch}"
            ts, raw = series[eid]
            r = GateResult(gate=g, channel=ch)

            if ts.size == 0:
                r.verdict = "NO DATA"
                r.notes.append(
                    "no samples — gate energies exist only in engineering mode "
                    "(§6.1). Check switch.<room>_mmwave_calibration_hold."
                )
                results.append(r)
                continue

            vals = resample(ts, to_float(raw), grid)
            vals[~eng_on] = np.nan  # held, stale - see the grid above
            live = ~np.isnan(vals)

            empty_m = is_empty & live
            if agree is not None:
                before = n_snap(empty_m)
                empty_m = empty_m & agree
                diag["corr_dropped"] += before - n_snap(empty_m)
                diag["corr_kept"] += n_snap(empty_m)
            # STILL thresholds come from seats; MOVE thresholds from motion.
            sig_labels = seats if ch == "still" else motions
            sig_m = np.isin(labels, list(sig_labels)) & live

            r.n_clutter = n_snap(empty_m)
            r.n_signal = n_snap(sig_m)
            diag["n_empty_max"] = max(diag["n_empty_max"], r.n_clutter)

            r.e_clutter = pct(vals[empty_m], 99.5)
            r.e_signal = pct(vals[sig_m], 5.0)

            if r.n_clutter < MIN_SNAPSHOTS or r.n_signal < MIN_SNAPSHOTS:
                r.verdict = "INSUFFICIENT"
                r.notes.append(
                    f"n_empty={r.n_clutter}, n_signal={r.n_signal} snapshots; "
                    f"need >={MIN_SNAPSHOTS} in each before a tail percentile "
                    f"means anything"
                )
                results.append(r)
                continue

            # Which seat is worst in this gate? A gate threshold has to serve
            # every seat that lands in it, so the binding constraint is the
            # WEAKEST occupying seat, not the average one. Averaging here is how
            # you get a node that works in three chairs and drops you in the
            # fourth.
            #
            # Occupancy is judged on median LIFT over the empty median, not
            # against the empty P99.5. Against the P99.5 a seat whose signal is
            # buried in that gate's clutter reads as "nobody sits here", and the
            # §5.9.4 stop condition never fires — the single most consequential
            # verdict in the method gets quietly downgraded to a shrug.
            if ch == "still":
                empty_med = pct(vals[empty_m], 50.0)
                worst_p5, worst_seat = float("inf"), ""
                for seat in sorted(sig_labels):
                    m = (labels == seat) & live
                    if n_snap(m) < MIN_SNAPSHOTS:
                        continue
                    lift = pct(vals[m], 50.0) - empty_med
                    diag["seat_lift"].setdefault(seat, {})[g] = lift
                    if lift < OCCUPANCY_LIFT:
                        continue  # this seat is not seen in this gate
                    p5 = pct(vals[m], 5.0)
                    if p5 < worst_p5:
                        worst_p5, worst_seat = p5, seat
                if worst_seat:
                    r.e_signal, r.driving_class = worst_p5, worst_seat
                    diag["seat_gate"].setdefault(worst_seat, []).append(g)
                else:
                    r.verdict = "UNOCCUPIED"
                    r.notes.append(
                        "no seat's median still energy rises "
                        f"{OCCUPANCY_LIFT:.0f} counts above this gate's "
                        "empty-room median — nobody is seen here. Leave the "
                        "still threshold at its factory value rather than "
                        "deriving one from noise. (If a seat SHOULD be here, "
                        "read the per-seat table: it is shadowed, not absent.)"
                    )
                    results.append(r)
                    continue

            if r.e_clutter > 0 and r.e_signal > 0:
                r.t0 = math.sqrt(r.e_clutter * r.e_signal)
                r.sm = r.e_signal / r.e_clutter

            # §5.9.4: the most important line in the section.
            if not math.isnan(r.sm) and r.sm <= SM_UNUSABLE:
                r.verdict = "OVERLAP — STOP TUNING"
                r.notes.append(
                    f"SM={r.sm:.2f} <= 1: the occupied and empty distributions "
                    f"overlap and NO threshold works. The seat is shadowed, or "
                    f"a strong static reflector has raised the residue floor "
                    f"here (§5.4). Move or re-aim the sensor and go back to "
                    f"§5.1. Do not pick a number from this gate."
                )
                results.append(r)
                continue

            t, fpr, fnr, lt, notes = sweep(
                vals[empty_m], vals[sig_m], grid[sig_m], fpr_target, l_limit
            )
            r.threshold, r.fpr, r.fnr, r.l_t = t, fpr, fnr, lt
            r.notes.extend(notes)
            if not math.isnan(t):
                r.margin = r.e_signal - t
            # Rev 0.3: when no T meets both FPR and L(T), sweep() returns the
            # FPR-only T with a note - but the verdict below was set from SM
            # alone, so the gate read OK, the note was never printed (not in
            # the flagged list) and the exit code was 0. Found 2026-09-26 on
            # synthetic data: g2_still L(T) 44 s against a 30 s budget, "OK".
            if not math.isnan(t) and lt >= l_limit:
                r.verdict = "L(T) OVER BUDGET — check geometry"

            if ch == "still" and r.driving_class:
                m = (labels == r.driving_class) & live
                r.acf_lag_s, r.n_eff, _ = autocorr_report(grid[m], vals[m])

            if not r.verdict:
                if math.isnan(r.sm):
                    r.verdict = "CHECK"
                elif r.sm > SM_COMFORTABLE:
                    r.verdict = "OK"
                else:
                    r.verdict = "MARGINAL — bias low, watch in §6.3"
            results.append(r)

    return results, diag


# =============================================================================
# Reporting
# =============================================================================


def fmt(x: float, nd: int = 1) -> str:
    return (
        "—"
        if (x is None or (isinstance(x, float) and math.isnan(x)))
        else f"{x:.{nd}f}"
    )


def report_md(
    results: list[GateResult],
    diag: dict,
    room: str,
    idle_timeout: float,
    fpr_target: float,
) -> str:
    L = []
    L.append(f"# Gate threshold derivation — {room}")
    L.append("")
    L.append(
        f"- idle timeout: **{idle_timeout:.0f} s**  ->  "
        f"L(T) budget **{idle_timeout / 3:.0f} s** (§5.9.3)"
    )
    L.append(f"- FPR target: **{fpr_target:.4f}**")
    L.append("")

    frac = diag["blower_on_fraction_when_empty"]
    if diag.get("corroborator"):
        kept, dropped = diag["corr_kept"], diag["corr_dropped"]
        total = kept + dropped
        pctd = (100.0 * dropped / total) if total else 0.0
        L.append("## Corroborated empty")
        L.append("")
        L.append(
            f"Empty class intersected with `{diag['corroborator']}`: "
            f"**{dropped:,} of {total:,} samples dropped ({pctd:.1f}%)**."
        )
        L.append("")
        if pctd > 20:
            L.append(
                "> More than a fifth of the samples labelled empty had "
                "an independent sensor disagreeing. Treat the labelling "
                "discipline as the finding here, not just the thresholds "
                "- and compare these numbers against an uncorroborated "
                "run before trusting either."
            )
            L.append("")
    L.append("## Collection B coverage")
    L.append("")
    if math.isnan(frac):
        L.append("**No empty-room data at all.** Nothing below is supported.")
    elif frac < 0.10:
        L.append(
            f"**WARNING — only {frac * 100:.1f}% of the empty-room samples had "
            f'the blower running.** §5.3: *"Collection B is the one people '
            f"skip and it drives false positives. The move threshold must "
            f"clear the register's Doppler, not the quiet-room floor.\"* "
            f"Every move threshold below is derived from a quiet room and will "
            f"produce false triggers the first time the system runs hard. "
            f"Extend the collection across a heating or cooling cycle."
        )
    else:
        L.append(
            f"{frac * 100:.1f}% of empty-room samples had the blower "
            f"running — collection B is represented."
        )
    L.append("")

    L.append("## Minutes per class")
    L.append("")
    L.append("Engineering mode on only - the minutes that carry gate energies.")
    L.append("")
    L.append("| class | minutes |")
    L.append("|---|---|")
    for lab, mins in sorted(diag["class_minutes"].items(), key=lambda kv: -kv[1]):
        L.append(f"| {lab} | {mins:.0f} |")
    L.append("")
    if diag.get("settle_s", 0) > 0:
        L.append(
            f"The first {diag['settle_s']:.0f} s after every label change "
            f"is excluded from every class ({diag['settle_min']:.1f} min "
            f"of live labelled data) - see DEFAULT_SETTLE_S."
        )
        L.append("")

    # ---- what this much data can and cannot certify -------------------------
    # The smallest false-positive rate a sample can DEMONSTRATE is 1/n. Asking
    # the sweep for a rate below that does not get you a better threshold, it
    # gets you a threshold sitting on the largest empty-room value observed,
    # with no evidence about what happens above it. This is the single strongest
    # argument for running the collection for days rather than hours, and it
    # belongs in the report rather than in somebody's head.
    n_e = diag["n_empty_max"]
    period = diag["sample_period_s"]
    L.append("## What this much empty-room data can certify")
    L.append("")
    if n_e:
        floor = 1.0 / n_e
        hours = n_e * period / 3600.0
        L.append(
            f"- empty-room samples: **{n_e:,}** "
            f"({hours:.1f} h at {period:.0f} s/sample)"
        )
        L.append(f"- smallest demonstrable FPR: **{floor:.2e}** (= 1/n)")
        L.append(f"- requested FPR target: **{fpr_target:.2e}**")
        if diag["period_assumed_h"] > 0:
            L.append(
                f"- **WARNING: the gate publish period had no history for "
                f"{diag['period_assumed_h']:.1f} h of live data; "
                f"{DEFAULT_GATE_PERIOD_S:.0f} s was ASSUMED there.** "
                f"If it was really 1 s, n above is 5x too small."
            )
        if fpr_target < floor:
            need_h = (1.0 / fpr_target) * period / 3600.0
            L.append("")
            L.append(
                f"> **The target is below what this sample can demonstrate.** "
                f"Every threshold below therefore sits at or just above the "
                f"largest empty-room energy observed, and nothing here says "
                f"what the rate actually is — only that it was not seen in "
                f"{hours:.1f} h. Certifying {fpr_target:.1e} needs about "
                f"**{need_h:.0f} h** of empty-room samples per gate. Extend "
                f"the collection, or state the achieved bound rather than the "
                f"target."
            )
    L.append("")

    for ch, title, src in (
        ("still", "STILL thresholds — the R1 channel", "seated, motionless"),
        ("move", "MOVE thresholds — the false-trigger channel", "walking / working"),
    ):
        L.append(f"## {title}")
        L.append("")
        L.append(f"E_signal drawn from: {src}")
        L.append("")
        L.append(
            "| gate | range m | E_clutter P99.5 | E_signal P5 | T0 | "
            "**T** | FPR | false/h | FNR | L(T) s | SM | M | verdict |"
        )
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in [x for x in results if x.channel == ch]:
            lo = r.gate * GATE_DEPTH_M
            # FPR is a per-sample rate; per hour is the number a human can
            # actually compare against A6's "zero false triggers in 2 h".
            rate = (
                (r.fpr * 3600.0 / diag["sample_period_s"])
                if not math.isnan(r.fpr)
                else float("nan")
            )
            L.append(
                f"| g{r.gate} | {lo:.2f}–{lo + GATE_DEPTH_M:.2f} | "
                f"{fmt(r.e_clutter)} | {fmt(r.e_signal)} | {fmt(r.t0)} | "
                f"**{fmt(r.threshold, 0)}** | {fmt(r.fpr, 5)} | "
                f"{fmt(rate, 2)} | {fmt(r.fnr, 4)} | {fmt(r.l_t, 0)} | "
                f"{fmt(r.sm, 2)} | {fmt(r.margin)} | {r.verdict} |"
            )
        L.append("")

    # ---- per-seat visibility, which is where §5.9.4's STOP really lives -----
    if diag["seat_lift"]:
        L.append("## Per-seat visibility — is each seat SEEN at all?")
        L.append("")
        L.append(
            "Median still energy above the empty-room median, per gate. "
            "A seat with no gate above the occupancy floor is not a "
            "threshold problem: **it is shadowed, and §5.9.4 says stop "
            "tuning and move the sensor.** Bad geometry is not a bad "
            "threshold."
        )
        L.append("")
        L.append("| seat | best gate | lift | verdict |")
        L.append("|---|---|---|---|")
        for seat, gates in sorted(diag["seat_lift"].items()):
            if not gates:
                continue
            bg = max(gates, key=lambda k: gates[k])
            lift = gates[bg]
            if lift < OCCUPANCY_LIFT:
                v = "**SHADOWED — go back to §5.1, do not tune**"
            elif lift < 2 * OCCUPANCY_LIFT:
                v = "weak — re-aim if convenient, watch in §6.3"
            else:
                v = "seen"
            L.append(f"| {seat} | g{bg} | {lift:+.1f} | {v} |")
        L.append("")

    L.append("## Autocorrelation and effective sample size (§5.3)")
    L.append("")
    L.append("| gate | seat | decorrelation lag s | N_eff |")
    L.append("|---|---|---|---|")
    for r in results:
        if r.channel == "still" and r.driving_class:
            L.append(
                f"| g{r.gate} | {r.driving_class} | "
                f"{fmt(r.acf_lag_s, 1)} | {fmt(r.n_eff, 0)} |"
            )
    L.append("")
    L.append(
        "A P5 estimated from a few dozen EFFECTIVE samples has a wide "
        "confidence interval however many raw rows sit behind it. This "
        "table is what replaced the withdrawn N=150 claim."
    )
    L.append("")

    flagged = [
        r
        for r in results
        if r.verdict.startswith(("OVERLAP", "NO DATA", "INSUFFICIENT", "L(T)"))
    ]
    # "NOT SETTABLE" is deliberately not flagged: it is a property of the
    # hardware, not a problem with the collection, and nothing about it changes
    # however long you run.
    if flagged:
        L.append("## Gates needing attention")
        L.append("")
        for r in flagged:
            L.append(f"### g{r.gate} {r.channel} — {r.verdict}")
            for n in r.notes:
                L.append(f"- {n}")
            L.append("")
    return "\n".join(L)


def report_esphome(results: list[GateResult], room: str) -> str:
    """The substitutions block to paste into the per-device ESPHome file.

    This is R9 made concrete: the commissioned state leaves the analysis as YAML
    that goes into git and gets flashed, not as numbers typed into a phone app
    and stored in module NVM where nothing can diff them.
    """
    by = {(r.gate, r.channel): r for r in results}
    L = [
        f"  # --- COMMISSIONED {room.upper()} THRESHOLDS ---",
        "  # generated by scripts/mmwave_calibrate.py — do not hand-edit;",
        "  # re-run the script and commit the new output instead (§6.3).",
    ]
    for g in range(N_GATES):
        for ch in ("move", "still"):
            r = by.get((g, ch))
            if r is not None and r.verdict == "NOT SETTABLE":
                # Emit it anyway: ESPHome requires the key even though the
                # module ignores the value. Omitting it breaks the build.
                L.append(
                    f'  g{g}_{ch}: "{INERT_STILL_VALUE}"'
                    f"   # inert — module ignores static sensitivity here"
                )
                continue
            if r is None or math.isnan(r.threshold):
                L.append(
                    f"  # g{g}_{ch}: NOT DERIVED — {r.verdict if r else 'missing'}"
                )
                continue
            if r.verdict.startswith("L(T)"):
                # A number exists but fails §5.9.3: pasting it would ship a
                # seat that drops out before the idle timeout.
                L.append(
                    f"  # g{g}_{ch}: NOT DERIVED — {r.verdict} "
                    f"(FPR-only T {r.threshold:.0f}, "
                    f"L(T) {fmt(r.l_t, 0)}s)"
                )
                continue
            L.append(
                f'  g{g}_{ch}: "{int(round(r.threshold))}"'
                f"   # SM {fmt(r.sm, 2)}, M {fmt(r.margin)}, "
                f"L(T) {fmt(r.l_t, 0)}s"
            )
    return "\n".join(L)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--db", required=True, help="path to a COPY of home-assistant_v2.db")
    p.add_argument("--room", required=True, choices=["office", "family"])
    p.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help="total room idle timeout in seconds (sets the L(T) budget)",
    )
    p.add_argument("--fpr-target", type=float, default=DEFAULT_FPR_TARGET)
    p.add_argument(
        "--corroborate",
        metavar="ENTITY_ID",
        default=None,
        help="restrict the empty class to intervals where this "
        "entity is 'on' - e.g. "
        "binary_sensor.mmw_family_empty_corroborated, which "
        "requires the thermostat to agree the room is empty",
    )
    p.add_argument(
        "--settle",
        type=float,
        default=DEFAULT_SETTLE_S,
        help="seconds after each label change excluded from every "
        "class; 0 turns the window off (Rev 0.3)",
    )
    p.add_argument("--emit", choices=["md", "esphome", "both"], default="both")
    a = p.parse_args()

    idle = a.idle_timeout or DEFAULT_IDLE_TIMEOUT[a.room]
    results, diag = analyse(a.db, a.room, idle, a.fpr_target, a.corroborate, a.settle)

    if a.emit in ("md", "both"):
        print(report_md(results, diag, a.room, idle, a.fpr_target))
    if a.emit == "both":
        print("\n---\n")
    if a.emit in ("esphome", "both"):
        print(report_esphome(results, a.room))

    # Exit non-zero if anything says stop, so this can gate a commit rather than
    # being a report somebody reads optimistically.
    shadowed = [
        seat
        for seat, gates in diag["seat_lift"].items()
        if gates and max(gates.values()) < OCCUPANCY_LIFT
    ]
    if shadowed:
        print(
            f"\nSTOP: seats not visible to the radar: {', '.join(shadowed)}",
            file=sys.stderr,
        )
        return 2
    if any(r.verdict.startswith(("OVERLAP", "L(T)")) for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
