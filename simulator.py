#!/usr/bin/env python3
"""
Airsoft GBB Ballistics Simulator
=================================
Simulates a 6 mm plastic BB fired from a Gas Blow Back (GBB) Airsoft gun.

Configurable parameters
-----------------------
  Gun    : barrel length, barrel inner diameter, chamber volume, gas pressure (psi)
  Hop-up : rubber hardness (Shore A), bucking contact pressure, on/off
  BB     : mass (g), surface polish (0–1)
  Launch : angle (degrees above horizontal)
  Env    : temperature, altitude, wind speed & direction
"""

import sys
import math
import textwrap

try:
    import physics
except ImportError:
    print("ERROR: physics.py not found – make sure it is in the same directory.")
    sys.exit(1)


# ─── Colour helpers (ANSI, disabled on Windows without colour support) ────────

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def bold(t):    return _c("1",    t)
def green(t):   return _c("32",   t)
def yellow(t):  return _c("33",   t)
def cyan(t):    return _c("36",   t)
def magenta(t): return _c("35",   t)
def red(t):     return _c("31",   t)


# ─── Pretty-print helpers ─────────────────────────────────────────────────────

def _section(title: str):
    width = 58
    print()
    print(cyan("─" * width))
    print(cyan(f"  {title}"))
    print(cyan("─" * width))


def _row(label: str, value, unit: str = ""):
    print(f"  {label:<34} {bold(str(value))} {unit}")


def _ask(prompt: str, default, cast=float, choices=None):
    """Prompt user for a value with a default fallback."""
    default_str = str(default)
    if choices:
        choice_str = "/".join(choices)
        full_prompt = f"  {prompt} [{choice_str}] (default {default_str}): "
    else:
        full_prompt = f"  {prompt} (default {default_str}): "
    try:
        raw = input(full_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if raw == "":
        return default
    if choices:
        if raw.lower() in [c.lower() for c in choices]:
            return raw.lower()
        print(yellow(f"    → Invalid choice, using default: {default_str}"))
        return default
    try:
        return cast(raw)
    except ValueError:
        print(yellow(f"    → Could not parse '{raw}', using default: {default_str}"))
        return default


def _ask_bool(prompt: str, default: bool) -> bool:
    d = "y" if default else "n"
    ans = _ask(prompt, d, cast=str, choices=["y", "n"])
    return ans == "y"


# ─── Configuration wizard ─────────────────────────────────────────────────────

def configure_params():
    print()
    print(bold("╔══════════════════════════════════════════════════════╗"))
    print(bold("║      AIRSOFT GBB BALLISTICS SIMULATOR  v1.0         ║"))
    print(bold("╚══════════════════════════════════════════════════════╝"))
    print(textwrap.dedent("""
    Configure your GBB setup below.
    Press ENTER to accept the default value shown in parentheses.
    """))

    # ── Gun ──────────────────────────────────────────────────────────────────
    _section("GUN  (Gas Blow Back)")
    barrel_mm   = _ask("Barrel length (mm)",           300.0)
    bore_mm     = _ask("Barrel inner diameter (mm)",   6.04)
    chamber_cc  = _ask("Chamber volume (cc / cm³)",    2.5)
    pressure    = _ask("Gas pressure (psi)",           120.0)

    gun = physics.GunParams(
        barrel_length_mm        = barrel_mm,
        barrel_inner_dia_mm     = bore_mm,
        chamber_volume_cc       = chamber_cc,
        gas_pressure_psi        = pressure,
    )

    # ── Hop-up ───────────────────────────────────────────────────────────────
    _section("HOP-UP")
    hop_active  = _ask_bool("Hop-up active?",          True)
    hardness    = _ask("Rubber hardness (Shore A, 40=soft … 80=hard)", 60.0)
    bk_pressure = _ask("Bucking contact pressure (gram-force)",        150.0)

    hop = physics.HopUpParams(
        rubber_hardness_shore_a = hardness,
        bucking_pressure_gf     = bk_pressure,
        active                  = hop_active,
    )

    # ── BB ───────────────────────────────────────────────────────────────────
    _section("BB PROJECTILE  (6 mm)")
    bb_mass   = _ask("BB mass (grams)",                          0.20)
    bb_polish = _ask("Surface polish  (0.0 = rough, 1.0 = mirror)", 0.9)
    bb_polish = max(0.0, min(1.0, bb_polish))

    bb = physics.BBParams(mass_g=bb_mass, polish=bb_polish)

    # ── Launch ───────────────────────────────────────────────────────────────
    _section("LAUNCH CONDITIONS")
    launch_angle = _ask("Launch angle (degrees above horizontal)", 0.0)

    # ── Environment ──────────────────────────────────────────────────────────
    _section("ENVIRONMENT")
    temp_c      = _ask("Air temperature (°C)",       15.0)
    altitude_m  = _ask("Altitude (m above sea level)", 0.0)
    wind_ms     = _ask("Wind speed (m/s)",            0.0)
    wind_dir    = _ask("Wind direction (0=headwind, 90=crosswind from left)", 0.0)

    env = physics.EnvParams(
        temperature_c  = temp_c,
        altitude_m     = altitude_m,
        wind_speed_ms  = wind_ms,
        wind_angle_deg = wind_dir,
    )

    return gun, hop, bb, env, launch_angle


# ─── Results display ──────────────────────────────────────────────────────────

def print_summary(gun, hop, bb, env, launch_angle,
                  muzzle_v, spin, trajectory):
    _section("CONFIGURATION SUMMARY")
    _row("Barrel length",              f"{gun.barrel_length_mm:.1f}",     "mm")
    _row("Barrel bore",                f"{gun.barrel_inner_dia_mm:.2f}",  "mm")
    _row("Chamber volume",             f"{gun.chamber_volume_cc:.2f}",    "cc")
    _row("Gas pressure",               f"{gun.gas_pressure_psi:.1f}",     "psi")
    _row("Hop-up active",              "Yes" if hop.active else "No")
    _row("Rubber hardness",            f"{hop.rubber_hardness_shore_a:.0f}", "Shore A")
    _row("Bucking contact pressure",   f"{hop.bucking_pressure_gf:.0f}",  "gf")
    _row("BB mass",                    f"{bb.mass_g:.3f}",                "g")
    _row("BB surface polish",          f"{bb.polish:.2f}",                "(0–1)")
    _row("Launch angle",               f"{launch_angle:.1f}",             "°")
    _row("Air temperature",            f"{env.temperature_c:.1f}",        "°C")
    _row("Altitude",                   f"{env.altitude_m:.0f}",           "m")
    _row("Wind",                       f"{env.wind_speed_ms:.1f} m/s @ {env.wind_angle_deg:.0f}°")

    _section("MUZZLE PERFORMANCE")

    fps = muzzle_v * 3.28084
    joules = 0.5 * bb.mass_kg * muzzle_v**2

    _row("Muzzle velocity",            f"{muzzle_v:.2f}",   "m/s")
    _row("Muzzle velocity",            f"{fps:.1f}",        "FPS")
    _row("Muzzle energy",              f"{joules:.4f}",     "J")
    _row("Backspin",                   f"{spin:.1f}",       "rev/s  (RPS)")
    _row("Backspin",                   f"{spin*60:.0f}",    "RPM")

    if not trajectory:
        print(red("\n  No trajectory data – BB did not leave the barrel."))
        return

    max_range  = trajectory[-1]["x"]
    max_height = max(p["y"] for p in trajectory)
    flight_t   = trajectory[-1]["t"]
    impact_v   = trajectory[-1]["speed"]

    # Find range where BB crosses 1.0 m height on descent
    hop_range = 0.0
    for i in range(1, len(trajectory)):
        if trajectory[i-1]["y"] >= 1.0 >= trajectory[i]["y"]:
            hop_range = trajectory[i]["x"]
            break

    _section("FLIGHT SUMMARY")
    _row("Total range (ground impact)",f"{max_range:.2f}",  "m")
    _row("Total range",                f"{max_range/0.9144:.1f}", "yards")
    _row("Peak height",                f"{max_height:.3f}", "m")
    _row("Time of flight",             f"{flight_t:.3f}",   "s")
    _row("Impact speed",               f"{impact_v:.2f}",   "m/s")

    _section("TRAJECTORY TABLE  (every 5 m)")
    header = f"  {'Range (m)':>10}  {'Height (m)':>10}  {'Speed (m/s)':>12}  {'Spin RPS':>10}  {'Time (s)':>9}"
    print(cyan(header))
    print(cyan("  " + "─" * (len(header) - 2)))

    prev_mark = -1
    for pt in trajectory:
        mark = int(pt["x"] / 5)
        if mark != prev_mark:
            prev_mark = mark
            ht_str  = f"{pt['y']:.3f}"
            spd_str = f"{pt['speed']:.2f}"
            rps_str = f"{pt['spin_rps']:.1f}"
            t_str   = f"{pt['t']:.3f}"
            x_str   = f"{pt['x']:.1f}"
            print(f"  {x_str:>10}  {ht_str:>10}  {spd_str:>12}  {rps_str:>10}  {t_str:>9}")

    # Energy at every 5 m
    _section("KINETIC ENERGY  (every 5 m)")
    print(cyan(f"  {'Range (m)':>10}  {'KE (J)':>10}  {'KE drop %':>10}"))
    print(cyan("  " + "─" * 38))
    ke0 = 0.5 * bb.mass_kg * trajectory[0]["speed"] ** 2
    prev_mark = -1
    for pt in trajectory:
        mark = int(pt["x"] / 5)
        if mark != prev_mark:
            prev_mark = mark
            ke  = 0.5 * bb.mass_kg * pt["speed"] ** 2
            pct = (1 - ke / ke0) * 100 if ke0 > 0 else 0
            print(f"  {pt['x']:>10.1f}  {ke:>10.4f}  {pct:>9.1f}%")

    print()


def print_ascii_trajectory(trajectory, width=70, height=20):
    """Render a simple ASCII plot of the trajectory."""
    if not trajectory:
        return

    max_x = trajectory[-1]["x"]
    max_y = max(p["y"] for p in trajectory)
    max_y = max(max_y, 2.0)   # at least 2 m height scale

    _section("TRAJECTORY PLOT")
    print(f"  Height axis: 0 – {max_y:.2f} m   |   Range axis: 0 – {max_x:.1f} m")
    print()

    grid = [[" "] * width for _ in range(height)]

    for pt in trajectory:
        col = int(pt["x"] / max_x * (width - 1))
        row = int((1.0 - (pt["y"] / max_y)) * (height - 1))
        col = max(0, min(width - 1, col))
        row = max(0, min(height - 1, row))
        grid[row][col] = "·"

    # Ground line
    ground_row = int((1.0 - (0.0 / max_y)) * (height - 1))
    ground_row = min(ground_row, height - 1)

    for r, line in enumerate(grid):
        prefix = "│" if r < height - 1 else "└"
        row_str = "".join(line)
        if r == 0:
            print(f"  {max_y:5.1f}m {prefix}{row_str}")
        elif r == height // 2:
            mid_h = max_y / 2
            print(f"  {mid_h:5.1f}m {prefix}{row_str}")
        elif r == ground_row:
            print(f"  {'0.0':>6}m └{'─'*width}")
        else:
            print(f"         {prefix}{row_str}")

    print(f"          {'0':>5}" + " " * (width - 10) + f"{max_x:.1f}m")
    print()


# ─── Main loop ────────────────────────────────────────────────────────────────

def main():
    while True:
        gun, hop, bb, env, launch_angle = configure_params()

        print()
        print(bold("  Running simulation…"))

        muzzle_v, spin = physics.simulate_barrel(gun, hop, bb, env)
        trajectory     = physics.simulate_flight(muzzle_v, spin, gun, bb, env,
                                                  launch_angle_deg=launch_angle)

        print_summary(gun, hop, bb, env, launch_angle, muzzle_v, spin, trajectory)
        print_ascii_trajectory(trajectory)

        print()
        again = _ask_bool("Run another simulation?", True)
        if not again:
            print(bold("\n  Thanks for using the Airsoft GBB Simulator. Stay safe!\n"))
            break


if __name__ == "__main__":
    main()
