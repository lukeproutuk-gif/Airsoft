# Airsoft GBB Ballistics Simulator

Simulates a **6 mm plastic BB** fired from a **Gas Blow Back (GBB)** Airsoft gun.

## Quick start

```
python3 simulator.py
```

No third-party libraries required – pure Python 3 standard library.

## Physics model

### Internal ballistics (inside the barrel)
- Adiabatic gas expansion from chamber through barrel bore
- Leakage gap between BB diameter (6.00 mm) and barrel bore (configurable)
- Barrel friction modulated by BB surface polish
- Hop-up bucking contact modelled as an impulse torque near the muzzle

### External ballistics (in-flight)
- **Drag** – Reynolds-number-dependent sphere Cd, adjusted for BB polish
- **Magnus / hop-up lift** – backspin produces an upward force counteracting gravity
- **Gravity**
- **Wind** – configurable speed and direction (headwind / crosswind)
- **Spin decay** – aerodynamic torque slows the BB's rotation over time

## Configurable parameters

| Category | Parameter | Unit |
|----------|-----------|------|
| Gun      | Barrel length | mm |
| Gun      | Barrel inner diameter (bore) | mm |
| Gun      | Chamber volume | cc |
| Gun      | Gas pressure | **psi** |
| Hop-up   | Rubber hardness | Shore A (40–80) |
| Hop-up   | Bucking contact pressure | gram-force |
| Hop-up   | Active / inactive | – |
| BB       | Mass | grams |
| BB       | Surface polish | 0.0 (rough) → 1.0 (mirror) |
| Launch   | Angle above horizontal | degrees |
| Env      | Air temperature | °C |
| Env      | Altitude | m |
| Env      | Wind speed | m/s |
| Env      | Wind direction | degrees (0=headwind) |

## Outputs

- Muzzle velocity (m/s and FPS)
- Muzzle energy (Joules)
- Backspin (RPS and RPM)
- Full trajectory table (range, height, speed, spin every 5 m)
- Kinetic energy decay table
- ASCII trajectory plot
