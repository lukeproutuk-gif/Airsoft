"""
Airsoft BB Ballistics Physics Engine

Models a 6mm plastic BB fired from a Gas Blow Back (GBB) system.

Physics stages:
  1. Gas expansion in chamber -> pressure force on BB
  2. Barrel travel (friction, gas leakage around BB)
  3. Hop-up rubber interaction (backspin / Magnus force)
  4. External ballistics (drag, Magnus lift, gravity, wind)
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ─── Constants ───────────────────────────────────────────────────────────────

BB_DIAMETER_M   = 0.006       # 6 mm
BB_RADIUS_M     = 0.003
AIR_DENSITY     = 1.225       # kg/m³  (sea level, 15 °C)
GRAVITY         = 9.80665     # m/s²
AIR_VISCOSITY   = 1.81e-5     # Pa·s  (dynamic viscosity at 15 °C)
PSI_TO_PA       = 6894.757    # 1 psi = 6894.757 Pa
GAMMA_AIR       = 1.4         # ratio of specific heats


# ─── Parameter dataclasses ───────────────────────────────────────────────────

@dataclass
class GunParams:
    """Parameters describing the GBB gun hardware."""
    barrel_length_mm: float     = 300.0   # mm
    barrel_inner_dia_mm: float  = 6.04    # mm – typical tight bore
    chamber_volume_cc: float    = 2.5     # cm³
    gas_pressure_psi: float     = 120.0   # psi (green gas ≈ 115-130 psi)
    gas_pressure_ambient_psi: float = 14.696  # atmospheric

@dataclass
class HopUpParams:
    """Parameters describing the hop-up unit."""
    rubber_hardness_shore_a: float = 60.0   # Shore A (40=soft … 80=hard)
    bucking_pressure_gf: float     = 150.0  # gram-force pressing on BB
    active: bool                   = True

@dataclass
class BBParams:
    """Parameters describing the BB projectile."""
    mass_g: float    = 0.20    # grams
    polish: float    = 0.9     # 0.0 (rough) … 1.0 (mirror polish)
    # derived
    mass_kg: float   = field(init=False)
    radius_m: float  = field(init=False)

    def __post_init__(self):
        self.mass_kg  = self.mass_g / 1000.0
        self.radius_m = BB_RADIUS_M   # always 6 mm BB

@dataclass
class EnvParams:
    """Ambient environment."""
    temperature_c: float  = 15.0
    altitude_m: float     = 0.0
    wind_speed_ms: float  = 0.0    # head/tail wind (positive = headwind)
    wind_angle_deg: float = 0.0    # 0=headwind, 90=crosswind from left


# ─── Internal ballistics (barrel stage) ──────────────────────────────────────

def _air_density_at_altitude(alt_m: float, temp_c: float) -> float:
    """ISA-approximate air density."""
    temp_k = temp_c + 273.15
    p0     = 101325.0
    # Barometric formula (troposphere)
    p      = p0 * (1 - 2.2557e-5 * alt_m) ** 5.2559
    rho    = p / (287.058 * temp_k)
    return rho


def simulate_barrel(gun: GunParams, hop: HopUpParams, bb: BBParams,
                    env: EnvParams, dt: float = 1e-6):
    """
    Simulate the BB's acceleration through the barrel using a
    simplified adiabatic gas expansion model.

    Returns:
        muzzle_velocity_ms  – speed at barrel exit (m/s)
        spin_rps            – backspin in revolutions/second
    """
    barrel_m   = gun.barrel_length_mm  / 1000.0
    bore_r     = (gun.barrel_inner_dia_mm / 2.0) / 1000.0
    bore_area  = math.pi * bore_r ** 2

    # Leakage gap area (difference between bore and BB cross-section)
    bb_area    = math.pi * bb.radius_m ** 2
    leak_ratio = max(0.0, 1.0 - bb_area / bore_area)   # 0=perfect seal

    # Initial gas state
    p_init_pa  = gun.gas_pressure_psi * PSI_TO_PA
    p_atm_pa   = gun.gas_pressure_ambient_psi * PSI_TO_PA
    V0         = gun.chamber_volume_cc * 1e-6            # m³

    # Friction coefficient (barrel + BB polish)
    # Higher polish → lower friction
    mu_barrel  = 0.15 * (1.0 - bb.polish * 0.7)

    # Hop-up contact friction (converts linear KE → spin)
    # Softer rubber + higher pressure → more spin
    hop_mu     = 0.0
    if hop.active:
        # Normalise Shore A (40–80) to 0–1 and invert (softer=more grip)
        hardness_norm = (hop.rubber_hardness_shore_a - 40.0) / 40.0
        grip          = (1.0 - hardness_norm * 0.5) * (hop.bucking_pressure_gf / 200.0)
        hop_mu        = max(0.0, min(grip, 0.8))

    # Integration
    x   = 0.0      # position in barrel (m)
    v   = 0.0      # velocity (m/s)
    t   = 0.0

    # Track gas volume as BB moves
    while x < barrel_m:
        # Current gas volume = initial chamber + swept barrel volume
        V_gas  = V0 + bore_area * x

        # Adiabatic pressure
        p_gas  = p_init_pa * (V0 / V_gas) ** GAMMA_AIR

        # Net pressure force on BB
        p_net  = max(p_gas - p_atm_pa, 0.0)
        F_gas  = p_net * bb_area

        # Friction (normal force ≈ pressure × bore area, reduced by polish)
        F_fric = mu_barrel * p_net * bb_area

        # Leakage penalty (reduce effective force)
        F_net  = F_gas * (1.0 - leak_ratio * 0.3) - F_fric

        a      = F_net / bb.mass_kg

        v += a * dt
        x += v * dt
        t += dt

        # Safety: if velocity goes negative (shouldn't happen), stop
        if v < 0:
            v = 0.0
            break

    muzzle_velocity = v

    # ── Spin from hop-up ──────────────────────────────────────────────────
    # The hop-up nub contacts the BB over a small arc near the muzzle.
    # We model the impulse as a torque applied over ~5 mm of travel.
    # Angular impulse ≈ hop friction force × radius × contact time
    contact_dist_m  = 0.005
    contact_time_s  = contact_dist_m / max(muzzle_velocity, 1.0)
    F_hop_n         = (hop.bucking_pressure_gf / 1000.0) * GRAVITY  # N
    torque          = hop_mu * F_hop_n * bb.radius_m
    I_bb            = 0.4 * bb.mass_kg * bb.radius_m ** 2  # solid sphere
    angular_accel   = torque / I_bb
    omega           = angular_accel * contact_time_s       # rad/s

    # Cap spin: linear surface speed cannot exceed muzzle velocity
    omega_max = muzzle_velocity / bb.radius_m
    omega     = min(omega, omega_max * 0.8)

    spin_rps  = omega / (2 * math.pi)

    return muzzle_velocity, spin_rps


# ─── External ballistics ─────────────────────────────────────────────────────

def _drag_coefficient(reynolds: float, polish: float) -> float:
    """
    Approximate Cd for a sphere as function of Reynolds number and surface finish.
    Smooth sphere transitions around Re≈4e5; rough sphere slightly higher Cd.
    """
    # Rough baseline Cd
    if reynolds < 1e3:
        cd = 24.0 / reynolds if reynolds > 0 else 1.0
    elif reynolds < 2e5:
        cd = 0.44
    else:
        cd = 0.1   # supercritical (unlikely for BB)

    # Polish reduces Cd slightly (smoother surface → later boundary separation)
    cd *= (1.0 - polish * 0.06)
    return cd


def simulate_flight(muzzle_velocity: float,
                    spin_rps: float,
                    gun: GunParams,
                    bb: BBParams,
                    env: EnvParams,
                    launch_angle_deg: float = 0.0,
                    dt: float = 0.0005,
                    max_time: float = 5.0):
    """
    Simulate external ballistics from muzzle to ground (y=0).

    Returns list of state dicts: {t, x, y, vx, vy, speed, spin_rps}
    """
    rho   = _air_density_at_altitude(env.altitude_m, env.temperature_c)
    area  = math.pi * bb.radius_m ** 2
    mass  = bb.mass_kg

    # Wind components (positive x = downrange)
    wind_rad   = math.radians(env.wind_angle_deg)
    wind_vx    = -env.wind_speed_ms * math.cos(wind_rad)
    wind_vy    = 0.0

    angle_rad  = math.radians(launch_angle_deg)
    vx = muzzle_velocity * math.cos(angle_rad)
    vy = muzzle_velocity * math.sin(angle_rad)

    x, y  = 0.0, 1.5   # typical 1.5 m barrel height
    t     = 0.0
    omega = spin_rps * 2 * math.pi   # rad/s

    # Spin decay (air resistance on rotating sphere)
    I_bb      = 0.4 * mass * bb.radius_m ** 2
    spin_drag_coeff = 0.5 * rho * area * bb.radius_m

    trajectory = []

    while t < max_time and y >= 0.0:
        speed = math.sqrt(vx**2 + vy**2)
        if speed < 0.01:
            break

        # Relative velocity to air
        vrx = vx - wind_vx
        vry = vy - wind_vy
        vr  = math.sqrt(vrx**2 + vry**2)

        re  = rho * vr * (2 * bb.radius_m) / AIR_VISCOSITY
        cd  = _drag_coefficient(re, bb.polish)

        # Drag force (opposing motion)
        Fd  = 0.5 * rho * vr**2 * cd * area
        Fdx = -Fd * (vrx / vr)
        Fdy = -Fd * (vry / vr)

        # Magnus / lift force (backspin produces upward lift)
        # F_Magnus = C_L * 0.5 * rho * v² * A
        # C_L ≈ 0.5 * (r * omega / v)  (empirical for spheres)
        if vr > 0.1:
            cl   = 0.5 * (bb.radius_m * omega / vr)
            cl   = min(cl, 0.5)
            Fm   = 0.5 * rho * vr**2 * cl * area
            # Direction: spin axis = z (into page), velocity = x → Magnus force = y (up)
            # More precisely: F = rho * Gamma × v  but simplified here to 2-D
            Fmx  =  Fm * ( vry / vr)   # cross product component
            Fmy  =  Fm * (-vrx / vr) * math.copysign(1.0, omega)
        else:
            Fmx = Fmy = 0.0

        # Gravity
        Fgy = -mass * GRAVITY

        # Accelerations
        ax  = (Fdx + Fmx) / mass
        ay  = (Fdy + Fmy + Fgy) / mass

        vx += ax * dt
        vy += ay * dt
        x  += vx * dt
        y  += vy * dt

        # Spin decay
        spin_drag = spin_drag_coeff * omega * bb.radius_m
        domega    = -(spin_drag / I_bb) * dt
        omega    += domega * math.copysign(1.0, omega) if abs(omega) > 0.01 else 0.0

        t += dt

        trajectory.append({
            "t":       round(t, 5),
            "x":       round(x, 4),
            "y":       round(y, 4),
            "vx":      round(vx, 4),
            "vy":      round(vy, 4),
            "speed":   round(math.sqrt(vx**2 + vy**2), 4),
            "spin_rps": round(omega / (2 * math.pi), 2),
        })

    return trajectory
