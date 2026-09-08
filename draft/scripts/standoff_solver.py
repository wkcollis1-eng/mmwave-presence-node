#!/usr/bin/env python3
"""
standoff_solver.py — pick the nylon standoff for the radar window gap.

Design doc §3.4. The antenna-to-window distance H is the one dimension the whole
mechanical design turns on, and it is set by a part that comes in discrete
heights. This picks from what is actually purchasable rather than quoting an
optimum nobody can buy.

    H = D_internal - S - t_carrier - H_header - t_module

Target from the MANUFACTURER, not from theory — HLK datasheet V1.00 §8.3,
verbatim: "If there is enough space, it is preferred to recommend 1 times or 1.5
times the wavelength… For example, 12.4 or 18.6mm is recommended for 24.125GHz…
Error control: +/-1.2mm".

1.5 lambda is unreachable here: it needs H = 18.64, i.e. S = 3.2 mm, and the
back of the carrier already needs 6.48 mm of standoff to clear the USB-C shell.
So 1 lambda it is.

Run:  python standoff_solver.py
      python standoff_solver.py --depth 26.4      # after measuring the box
"""
import argparse

LAMBDA = 12.427      # mm, 24.125 GHz free space (Appendix A)
TOL = 1.2            # mm, HLK DS §8.3 "error control"

T_CARRIER = 1.60     # carrier PCB, as fabricated
H_HEADER = 2.54      # radar's 5-pin header insulator
BACK_CLEARANCE = 6.48  # carrier underside to lowest feature (USB-C shell), §3.4
BASE_RIM = 20.0      # enclosure base rim height, §3.4
MODULE_TOP_ABOVE_PCB = 2.1  # antenna face to tallest feature, approx

AVAILABLE = [8.0, 9.0, 9.5, 10.0, 10.5]


def gap(depth, standoff, t_module):
    return depth - standoff - T_CARRIER - H_HEADER - t_module


def solve(depth, t_module, label):
    print(f"\n{'='*74}")
    print(f"  {label}   (module PCB = {t_module:.2f} mm, box internal depth = {depth:.2f} mm)")
    print(f"{'='*74}")
    ideal_s = depth - LAMBDA - T_CARRIER - H_HEADER - t_module
    print(f"  ideal standoff for H = 1 lambda = {LAMBDA:.3f} mm  ->  S = {ideal_s:.3f} mm")
    print(f"  acceptable S window (+/-{TOL} mm on H)             ->  "
          f"{ideal_s - TOL:.2f} .. {ideal_s + TOL:.2f} mm")
    print()
    print(f"  {'S (mm)':>7} {'H (mm)':>8} {'err':>8} {'phase':>8} {'back clr':>9}  verdict")
    print(f"  {'-'*7} {'-'*8} {'-'*8} {'-'*8} {'-'*9}  {'-'*28}")
    best = None
    for s in AVAILABLE:
        h = gap(depth, s, t_module)
        err = h - LAMBDA
        # 58 deg/mm round-trip phase at 24.125 GHz (Appendix A): 2 * 360 / lambda
        phase = abs(err) * 2 * 360.0 / LAMBDA
        back = s - BACK_CLEARANCE
        inside = abs(err) <= TOL
        if back <= 0:
            v = "FAILS - hits the box floor"
        elif not inside:
            v = f"OUTSIDE the +/-{TOL} mm window"
        elif abs(err) <= 0.2:
            v = "*** BEST - essentially exact"
        elif abs(err) <= 0.7:
            v = "good"
        else:
            v = "inside, but near the edge"
        if inside and back > 0 and (best is None or abs(err) < abs(best[1] - LAMBDA)):
            best = (s, h)
        print(f"  {s:7.1f} {h:8.3f} {err:+8.3f} {phase:7.1f}d {back:9.2f}  {v}")
    if best:
        print(f"\n  -> pick {best[0]:.1f} mm   (H = {best[1]:.3f} mm, "
              f"{abs(best[1]-LAMBDA):.3f} mm from 1 lambda)")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=float, default=27.384,
                    help="enclosure internal depth, mm (measured 69/64 in = 27.384)")
    ap.add_argument("--depth-tol", type=float, default=0.397,
                    help="+/- tolerance on the depth, mm (1/64 in = 0.397)")
    a = ap.parse_args()

    b10 = solve(a.depth, 1.00, "CASE A — STEP file / measured 1.0 mm module")
    b16 = solve(a.depth, 1.60, "CASE B — backup, if it measures 1.6 mm")

    print(f"\n{'='*74}")
    print("  ROBUSTNESS — which single standoff survives BOTH thicknesses?")
    print(f"{'='*74}")
    print(f"  {'S (mm)':>7} {'H @1.0':>9} {'H @1.6':>9} {'worst err':>10}  both inside?")
    print(f"  {'-'*7} {'-'*9} {'-'*9} {'-'*10}  {'-'*12}")
    robust = []
    for s in AVAILABLE:
        h1 = gap(a.depth, s, 1.00)
        h2 = gap(a.depth, s, 1.60)
        w = max(abs(h1 - LAMBDA), abs(h2 - LAMBDA))
        ok = w <= TOL and s > BACK_CLEARANCE
        if ok:
            robust.append((w, s))
        print(f"  {s:7.1f} {h1:9.3f} {h2:9.3f} {w:10.3f}  {'YES' if ok else 'no'}")
    if robust:
        robust.sort()
        print(f"\n  -> most robust single choice: {robust[0][1]:.1f} mm "
              f"(worst-case error {robust[0][0]:.3f} mm across both thicknesses)")

    # ---- worst case across the MEASUREMENT TOLERANCE ------------------------
    # A measurement with error bars does not pick a standoff; the WORST CASE
    # inside those bars does. +/-1/64 in is +/-0.397 mm, a large fraction of the
    # step between adjacent sizes - so the honest question is not "which S is
    # best at the nominal depth" but "which S is least bad anywhere the true
    # depth might actually be".
    lo, hi = a.depth - a.depth_tol, a.depth + a.depth_tol
    print()
    print("=" * 74)
    print(f"  TOLERANCE BAND - depth {a.depth:.3f} +/- {a.depth_tol:.3f} mm "
          f"({lo:.3f} .. {hi:.3f}), module 1.0 mm")
    print("=" * 74)
    print(f"  {'S (mm)':>7} {'H at min':>9} {'H at max':>9} {'worst err':>10} "
          f"{'phase':>8}  verdict")
    print(f"  {'-'*7} {'-'*9} {'-'*9} {'-'*10} {'-'*8}  {'-'*26}")
    ranked = []
    for s_ in AVAILABLE:
        h_lo, h_hi = gap(lo, s_, 1.00), gap(hi, s_, 1.00)
        w = max(abs(h_lo - LAMBDA), abs(h_hi - LAMBDA))
        ph = w * 2 * 360.0 / LAMBDA
        ok = w <= TOL and s_ > BACK_CLEARANCE
        if ok:
            ranked.append((w, s_))
        print(f"  {s_:7.1f} {h_lo:9.3f} {h_hi:9.3f} {w:10.3f} {ph:7.1f}d  "
              f"{'in spec across the band' if ok else 'CAN FALL OUTSIDE'}")
    if ranked:
        ranked.sort()
        print()
        print(f"  -> {ranked[0][1]:.1f} mm minimises the worst case: "
              f"{ranked[0][0]:.3f} mm anywhere in the band")
        if len(ranked) > 1:
            print(f"     runner-up {ranked[1][1]:.1f} mm at {ranked[1][0]:.3f} mm")
    print()

    # ---- JOINT worst case: depth AND module thickness both uncertain ---------
    # The STEP model says 0.989 mm. A hand rule on the physical part says
    # between 3/64 and 4/64 in = 1.191 .. 1.588 mm. Those do not overlap, and
    # when CAD and the part in your hand disagree, the part wins - a vendor's
    # 3D model is nominal and sometimes simply wrong.
    #
    # But a rule at 1/64 resolution is a poor instrument for a ~1 mm dimension,
    # so the honest position is that t is somewhere in 1.0 .. 1.6, and the pick
    # should be whichever standoff is least bad ACROSS THAT WHOLE RANGE as well
    # as across the depth band. Standard PCB stock is 0.8 / 1.0 / 1.2 / 1.6, and
    # 4/64 in = 1.588 mm is 1.6 mm to within the reading error - so 1.2 or 1.6
    # are the likely true values.
    T_RANGE = (1.00, 1.60)
    lo, hi = a.depth - a.depth_tol, a.depth + a.depth_tol
    print()
    print("=" * 74)
    print(f"  JOINT BAND - depth {lo:.3f}..{hi:.3f} mm, module {T_RANGE[0]:.2f}..{T_RANGE[1]:.2f} mm")
    print("=" * 74)
    print(f"  {'S (mm)':>7} {'H min':>8} {'H max':>8} {'worst err':>10} {'phase':>8}  verdict")
    print(f"  {'-'*7} {'-'*8} {'-'*8} {'-'*10} {'-'*8}  {'-'*26}")
    joint = []
    for s_ in AVAILABLE:
        h_max = gap(hi, s_, T_RANGE[0])     # deepest box, thinnest board
        h_min = gap(lo, s_, T_RANGE[1])     # shallowest box, thickest board
        w = max(abs(h_min - LAMBDA), abs(h_max - LAMBDA))
        ph = w * 2 * 360.0 / LAMBDA
        ok = w <= TOL and s_ > BACK_CLEARANCE
        if ok:
            joint.append((w, s_))
        print(f"  {s_:7.1f} {h_min:8.3f} {h_max:8.3f} {w:10.3f} {ph:7.1f}d  "
              f"{'in spec everywhere' if ok else 'CAN FALL OUTSIDE'}")
    if joint:
        joint.sort()
        print()
        print(f"  -> {joint[0][1]:.1f} mm is the robust pick: worst case "
              f"{joint[0][0]:.3f} mm across BOTH uncertainties")
    print()
    print("  and at each plausible standard PCB thickness, at the nominal depth:")
    for t in (1.00, 1.20, 1.60):
        pick = min(AVAILABLE, key=lambda x: abs(gap(a.depth, x, t) - LAMBDA))
        e = gap(a.depth, pick, t) - LAMBDA
        e95 = gap(a.depth, 9.5, t) - LAMBDA
        print(f"    t = {t:.2f} mm  ->  best {pick:4.1f} mm (err {e:+.3f}) "
              f"| 9.5 mm gives {e95:+.3f}")
    print()

    print(f"\n{'='*74}")
    print("  SENSITIVITY — the box depth is the dominant unknown")
    print(f"{'='*74}")
    print("  §8 still lists the 27 mm internal depth as \"listing — MEASURE\".")
    print("  dS/dD = 1.00, so every 1 mm of error in the box depth moves the")
    print("  optimum standoff by a full 1 mm — larger than the difference between")
    print("  any two adjacent sizes you can buy. Measure the box before ordering.")
    print()
    for d in (a.depth - 1, a.depth - 0.5, a.depth, a.depth + 0.5, a.depth + 1):
        s_ideal = d - LAMBDA - T_CARRIER - H_HEADER - 1.00
        pick = min(AVAILABLE, key=lambda s: abs(gap(d, s, 1.00) - LAMBDA))
        err = gap(d, pick, 1.00) - LAMBDA
        print(f"    depth {d:5.1f} mm  ->  ideal S {s_ideal:5.2f}  ->  buy {pick:4.1f} mm "
              f"(err {err:+.3f})")




# =============================================================================
# FULL TOLERANCE STACK-UP
# -----------------------------------------------------------------------------
# "9.5 mm covers all the measurements plus errors" — does it? The band analyses
# above sweep only TWO contributors, the enclosure depth and the module
# thickness, because those are the two that were measured. The stack has five
# terms and the other three have been carried as exact numbers:
#
#     H = D_internal - S - t_carrier - H_header - t_module
#
#   t_carrier  1.60 mm   OSH Park 2-layer: 0.1 mil resist + 1.4 mil Cu + 60 mil
#                        175Tg FR-4 core (Kingboard KB6167F) + 1.4 mil Cu + 0.1
#                        mil resist = 63 mil = 1.6 mm nominal. The ONLY published
#                        tolerance is +/-6 mil (0.1524 mm) ON THE CORE. OSH Park
#                        publish NO finished-board tolerance, so 0.1524 is a
#                        FLOOR, not a bound - copper plating and mask variation
#                        sit on top of it. NEVER MEASURED on the actual boards.
#   H_header   2.54 mm   The radar header's insulator body (PH1-05-UA, in the
#                        BOM). Assumed to equal the 2.54 mm pitch. Plausible,
#                        and seating adds only in one direction. NEVER MEASURED.
#   S          9.5 mm    Nylon standoffs carry roughly +/-0.1 mm, plus whatever
#                        the screws compress.
#
# Treating an unmeasured assumption as exact is how a stack-up comes out
# comfortable on paper and marginal in the box.
# =============================================================================

def stackup(depth=27.384, d_tol=0.397, t_mod_lo=1.00, t_mod_hi=1.60,
            t_carrier=1.60, c_tol=0.1524, h_header=2.54, hh_tol=0.15,
            standoff=9.5, s_tol=0.10):
    import math
    t_mod = (t_mod_lo + t_mod_hi) / 2.0
    t_tol = (t_mod_hi - t_mod_lo) / 2.0
    h_nom = depth - standoff - t_carrier - h_header - t_mod

    terms = [("enclosure depth", d_tol, "measured, hand rule 1/64 in"),
             ("module thickness", t_tol, "DISPUTED: CAD 0.989 vs rule 1.19-1.59"),
             ("carrier PCB", c_tol, "OSH Park core spec +/-6 mil — see note"),
             ("header insulator", hh_tol, "assumed 2.54 mm — NOT MEASURED"),
             ("standoff", s_tol, "typical nylon tolerance + screw compression")]

    print("=" * 74)
    print(f"  FULL STACK-UP at S = {standoff} mm")
    print("=" * 74)
    print(f"  nominal H = {h_nom:.3f} mm   (target {LAMBDA:.3f}, "
          f"error {h_nom - LAMBDA:+.3f} mm)")
    print()
    print(f"  {'contributor':<20} {'+/- mm':>8}  note")
    print(f"  {'-'*20} {'-'*8}  {'-'*44}")
    for name, tol, note in terms:
        print(f"  {name:<20} {tol:8.3f}  {note}")
    linear = sum(t for _, t, _ in terms)
    rss = math.sqrt(sum(t * t for _, t, _ in terms))
    print(f"  {'-'*20} {'-'*8}")
    print(f"  {'WORST CASE (linear)':<20} {linear:8.3f}  all five conspire the same way")
    print(f"  {'REALISTIC (RSS)':<20} {rss:8.3f}  independent, root-sum-square")
    print()
    win_lo, win_hi = LAMBDA - TOL, LAMBDA + TOL
    for label, tol in (("worst case", linear), ("RSS", rss)):
        lo, hi = h_nom - tol, h_nom + tol
        ok = lo >= win_lo and hi <= win_hi
        m = min(lo - win_lo, win_hi - hi)
        print(f"  {label:<12} H = {lo:6.3f} .. {hi:6.3f}   "
              f"{'INSIDE' if ok else 'BREACHES'} the {win_lo:.3f}..{win_hi:.3f} window"
              f"   margin {m:+.3f} mm")
    return h_nom, linear, rss



if __name__ == "__main__":
    main()
    print()
    for _s in (9.0, 9.5, 10.0):
        stackup(standoff=_s)
        print()
