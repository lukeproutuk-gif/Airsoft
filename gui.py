#!/usr/bin/env python3
"""
Airsoft GBB Ballistics Simulator – Retro Flash-Style GUI
=========================================================
Run:  python3 gui.py

Requires:  pygame  (pip install pygame)
           physics.py in the same directory
"""

import math
import sys
import pygame
import physics

# ─── Palette ─────────────────────────────────────────────────────────────────

BG          = (10,  12,  20)
PANEL_BG    = (18,  22,  38)
BORDER      = (0,  200, 120)
BORDER_DIM  = (0,   80,  50)
TEXT_MAIN   = (0,  255, 160)
TEXT_DIM    = (0,  140,  90)
TEXT_LABEL  = (180, 220, 255)
TEXT_WHITE  = (230, 240, 255)
TEXT_WARN   = (255, 200,  40)
TEXT_ERR    = (255,  60,  60)
FIRE_BTN    = (255,  80,   0)
FIRE_HOV    = (255, 130,  30)
FIRE_TXT    = (255, 255, 200)
RESET_BTN   = (30,   60,  90)
RESET_HOV   = (50,   90, 130)
TRAJ_LINE   = (0,  120,  80)
TRAJ_DOT    = (255, 220,   0)
GROUND      = (30,  80,  40)
SKY_TOP     = (10,  18,  40)
SKY_BOT     = (20,  35,  70)
INPUT_BG    = (8,   14,  28)
INPUT_ACT   = (15,  25,  50)
INPUT_BORD  = (0,  150,  90)
INPUT_SEL   = (0,  200, 120)
SCANLINE    = (0,    0,   0, 35)

# ─── Layout constants ─────────────────────────────────────────────────────────

W, H        = 1100, 680
PANEL_W     = 280
CANVAS_X    = PANEL_W + 10
CANVAS_W    = W - PANEL_W - 20
CANVAS_Y    = 10
CANVAS_H    = H - 170
STATS_Y     = CANVAS_Y + CANVAS_H + 8
STATS_H     = 80
BTN_Y       = STATS_Y + STATS_H + 8
BTN_H       = 44

FPS_SIM     = 60
ANIM_SPEED  = 1.5       # simulation seconds per real second during playback


# ─── Tiny bitmap font substitute – use pygame's SysFont ──────────────────────

def load_fonts():
    return {
        "title":  pygame.font.SysFont("Courier New", 20, bold=True),
        "label":  pygame.font.SysFont("Courier New", 13, bold=True),
        "small":  pygame.font.SysFont("Courier New", 11),
        "input":  pygame.font.SysFont("Courier New", 13),
        "stats":  pygame.font.SysFont("Courier New", 15, bold=True),
        "stat_v": pygame.font.SysFont("Courier New", 15),
        "btn":    pygame.font.SysFont("Courier New", 18, bold=True),
        "big":    pygame.font.SysFont("Courier New", 22, bold=True),
        "range":  pygame.font.SysFont("Courier New", 12),
    }


# ─── UI helpers ───────────────────────────────────────────────────────────────

def draw_rect_border(surf, rect, color, width=1, radius=3):
    pygame.draw.rect(surf, color, rect, width, border_radius=radius)

def draw_rect_fill(surf, rect, color, radius=3):
    pygame.draw.rect(surf, color, rect, border_radius=radius)

def blit_text(surf, fonts, key, text, pos, color, anchor="topleft"):
    img = fonts[key].render(text, True, color)
    r   = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))


# ─── Input field ──────────────────────────────────────────────────────────────

class InputField:
    def __init__(self, rect, label, default, suffix="", cast=float,
                 lo=None, hi=None):
        self.rect    = pygame.Rect(rect)
        self.label   = label
        self.suffix  = suffix
        self.cast    = cast
        self.lo      = lo
        self.hi      = hi
        self.text    = str(default)
        self.default = str(default)
        self.active  = False
        self.error   = False
        self.cursor_vis = True
        self._cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if not self.active:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.active = False
            elif event.unicode in "0123456789.-":
                self.text += event.unicode
        self._validate()

    def _validate(self):
        try:
            v = self.cast(self.text)
            self.error = (self.lo is not None and v < self.lo) or \
                         (self.hi is not None and v > self.hi)
        except (ValueError, TypeError):
            self.error = bool(self.text)

    def value(self):
        try:
            v = self.cast(self.text)
            if self.lo is not None: v = max(self.lo, v)
            if self.hi is not None: v = min(self.hi, v)
            return v
        except (ValueError, TypeError):
            return self.cast(self.default)

    def update(self, dt):
        if self.active:
            self._cursor_timer += dt
            if self._cursor_timer > 0.5:
                self._cursor_timer = 0
                self.cursor_vis = not self.cursor_vis
        else:
            self.cursor_vis = False

    def draw(self, surf, fonts):
        bg  = INPUT_ACT if self.active else INPUT_BG
        bc  = TEXT_ERR  if self.error  else (INPUT_SEL if self.active else INPUT_BORD)
        draw_rect_fill(surf, self.rect, bg, radius=2)
        draw_rect_border(surf, self.rect, bc, radius=2)
        display = self.text + ("|" if self.active and self.cursor_vis else "")
        tc = TEXT_ERR if self.error else (TEXT_MAIN if self.active else TEXT_WHITE)
        txt_img = fonts["input"].render(display, True, tc)
        surf.blit(txt_img, (self.rect.x + 4, self.rect.y + 3))
        if self.suffix:
            sx = self.rect.right + 3
            sy = self.rect.y + 3
            blit_text(surf, fonts, "small", self.suffix, (sx, sy), TEXT_DIM)


class CheckField:
    def __init__(self, rect, label, default=True):
        self.rect    = pygame.Rect(rect)
        self.label   = label
        self.checked = default

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.checked = not self.checked

    def value(self):
        return self.checked

    def draw(self, surf, fonts):
        bc = TEXT_MAIN if self.checked else BORDER_DIM
        draw_rect_fill(surf, self.rect, INPUT_BG, radius=2)
        draw_rect_border(surf, self.rect, bc, radius=2)
        if self.checked:
            inner = self.rect.inflate(-4, -4)
            draw_rect_fill(surf, inner, TEXT_MAIN, radius=1)
        v_text = "ON" if self.checked else "OFF"
        v_col  = TEXT_MAIN if self.checked else TEXT_DIM
        blit_text(surf, fonts, "small", v_text,
                  (self.rect.right + 4, self.rect.y + 2), v_col)


# ─── Main App ─────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Airsoft GBB Ballistics Simulator")
        self.screen = pygame.display.set_mode((W, H))
        self.clock  = pygame.time.Clock()
        self.fonts  = load_fonts()

        # ── Input fields ────────────────────────────────────────────────────
        self.fields = self._build_fields()

        # ── Simulation state ────────────────────────────────────────────────
        self.trajectory   = []
        self.muzzle_v     = 0.0
        self.spin_rps     = 0.0
        self.anim_time    = 0.0   # simulated time into trajectory
        self.playing      = False
        self.sim_ready    = False
        self.anim_idx     = 0

        # ── Canvas surfaces ─────────────────────────────────────────────────
        self.canvas_rect  = pygame.Rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H)
        self.stats_rect   = pygame.Rect(CANVAS_X, STATS_Y,  CANVAS_W, STATS_H)

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_w = 160
        gap   = 20
        total = btn_w * 2 + gap
        bx    = CANVAS_X + (CANVAS_W - total) // 2
        self.fire_rect  = pygame.Rect(bx,          BTN_Y, btn_w, BTN_H)
        self.reset_rect = pygame.Rect(bx + btn_w + gap, BTN_Y, btn_w, BTN_H)

        self._run_simulation()   # pre-compute with defaults

    # ── Field layout ──────────────────────────────────────────────────────────

    def _build_fields(self):
        px = 10
        fw = 80   # field width
        fh = 20
        lh = 34   # line height
        ix = px + 170

        def F(row, lbl, val, suf="", lo=None, hi=None):
            y = row * lh
            return InputField((ix, y, fw, fh), lbl, val, suf, float, lo, hi)

        def C(row, lbl, val=True):
            y = row * lh
            return CheckField((ix, y, 36, fh), lbl, val)

        return {
            # Gun
            "barrel_mm":   F(2,  "Barrel Length",   300.0, "mm",  100, 650),
            "bore_mm":     F(3,  "Bore Dia",          6.04, "mm",  6.00, 6.20),
            "chamber_cc":  F(4,  "Chamber Vol",        2.5, "cc",   1.0, 10.0),
            "pressure":    F(5,  "Gas Pressure",     120.0, "psi",  50, 300),
            # Hop-up
            "hop_active":  C(7,  "Hop-Up Active",    True),
            "hardness":    F(8,  "Hardness",           60.0, "ShA", 40, 80),
            "bk_press":    F(9,  "Bucking Press",     150.0, "gf",  50, 500),
            # BB
            "mass_g":      F(11, "BB Mass",            0.20, "g",  0.12, 0.50),
            "polish":      F(12, "Polish",              0.90, "0-1", 0.0, 1.0),
            # Launch
            "angle":       F(14, "Launch Angle",        0.0, "°",  -10, 30),
            # Env
            "temp_c":      F(16, "Temperature",        15.0, "°C", -20, 50),
            "altitude_m":  F(17, "Altitude",            0.0, "m",    0, 4000),
            "wind_ms":     F(18, "Wind Speed",           0.0, "m/s",  0, 20),
            "wind_dir":    F(19, "Wind Dir",             0.0, "°",    0, 360),
        }

    # ── Simulation ────────────────────────────────────────────────────────────

    def _run_simulation(self):
        f = self.fields
        gun = physics.GunParams(
            barrel_length_mm     = f["barrel_mm"].value(),
            barrel_inner_dia_mm  = f["bore_mm"].value(),
            chamber_volume_cc    = f["chamber_cc"].value(),
            gas_pressure_psi     = f["pressure"].value(),
        )
        hop = physics.HopUpParams(
            rubber_hardness_shore_a = f["hardness"].value(),
            bucking_pressure_gf     = f["bk_press"].value(),
            active                  = f["hop_active"].value(),
        )
        bb  = physics.BBParams(
            mass_g  = f["mass_g"].value(),
            polish  = f["polish"].value(),
        )
        env = physics.EnvParams(
            temperature_c  = f["temp_c"].value(),
            altitude_m     = f["altitude_m"].value(),
            wind_speed_ms  = f["wind_ms"].value(),
            wind_angle_deg = f["wind_dir"].value(),
        )
        self.muzzle_v, self.spin_rps = physics.simulate_barrel(gun, hop, bb, env)
        self.trajectory = physics.simulate_flight(
            self.muzzle_v, self.spin_rps, gun, bb, env,
            launch_angle_deg=f["angle"].value()
        )
        self.bb_mass_kg = bb.mass_kg
        self.sim_ready  = True
        self.anim_idx   = 0
        self.anim_time  = 0.0

    # ── Trajectory → canvas coords ────────────────────────────────────────────

    def _traj_to_canvas(self, pt):
        """Map trajectory point (x metres, y metres) to canvas pixel coords."""
        traj  = self.trajectory
        max_x = max(p["x"] for p in traj) if traj else 50.0
        max_y = max(p["y"] for p in traj) if traj else 3.0
        max_y = max(max_y, 2.0)
        pad   = 30

        cx = self.canvas_rect.x + pad + (pt["x"] / max_x) * (self.canvas_rect.w - pad*2)
        # y=0 is ground; canvas y increases downward
        cy = self.canvas_rect.y + self.canvas_rect.h - pad - \
             (pt["y"] / (max_y + 0.5)) * (self.canvas_rect.h - pad*2)
        return int(cx), int(cy)

    # ── Draw trajectory path ──────────────────────────────────────────────────

    def _draw_trajectory_path(self, surf, up_to_idx):
        traj = self.trajectory
        if len(traj) < 2:
            return
        pts = [self._traj_to_canvas(traj[i]) for i in range(0, min(up_to_idx+1, len(traj)))]
        if len(pts) >= 2:
            # Draw with fading alpha by drawing onto a temp surface
            for i in range(1, len(pts)):
                t = i / max(len(pts)-1, 1)
                col = lerp_color(TRAJ_LINE, (0, 200, 100), t)
                pygame.draw.line(surf, col, pts[i-1], pts[i], 2)

    # ── Draw canvas (sky + ground + trajectory) ───────────────────────────────

    def _draw_canvas(self, surf):
        cr = self.canvas_rect

        # Sky gradient (simple two-band)
        mid_y = cr.y + cr.h * 2 // 3
        pygame.draw.rect(surf, SKY_TOP,  (cr.x, cr.y, cr.w, mid_y - cr.y))
        pygame.draw.rect(surf, SKY_BOT,  (cr.x, mid_y, cr.w, cr.y + cr.h - mid_y))

        # Ground strip
        ground_y = cr.y + cr.h - 30
        pygame.draw.rect(surf, GROUND, (cr.x, ground_y, cr.w, 30))
        # Grass tufts
        for gx in range(cr.x + 10, cr.x + cr.w, 14):
            pygame.draw.line(surf, (50, 140, 60),
                             (gx, ground_y), (gx-2, ground_y-5), 1)
            pygame.draw.line(surf, (50, 140, 60),
                             (gx, ground_y), (gx+2, ground_y-5), 1)

        # Scanlines overlay (every 3 px)
        scan_surf = pygame.Surface((cr.w, cr.h), pygame.SRCALPHA)
        for sy in range(0, cr.h, 3):
            pygame.draw.line(scan_surf, (0,0,0,25), (0, sy), (cr.w, sy))
        surf.blit(scan_surf, cr.topleft)

        # Canvas border
        draw_rect_border(surf, cr, BORDER, width=2, radius=4)

        if not self.sim_ready or not self.trajectory:
            blit_text(surf, self.fonts, "label", "NO DATA – PRESS FIRE",
                      cr.center, TEXT_DIM, anchor="center")
            return

        # Full ghost path (dim)
        traj = self.trajectory
        all_pts = [self._traj_to_canvas(p) for p in traj]
        if len(all_pts) >= 2:
            for i in range(1, len(all_pts)):
                pygame.draw.line(surf, TRAJ_LINE, all_pts[i-1], all_pts[i], 1)

        # Animated path (bright, up to current index)
        self._draw_trajectory_path(surf, self.anim_idx)

        # BB dot
        if 0 <= self.anim_idx < len(traj):
            pt   = traj[self.anim_idx]
            bx, by = self._traj_to_canvas(pt)
            # Glow
            glow = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 220, 0, 60), (10,10), 9)
            surf.blit(glow, (bx-10, by-10))
            pygame.draw.circle(surf, TRAJ_DOT, (bx, by), 5)
            pygame.draw.circle(surf, (255,255,255), (bx, by), 2)

        # Axis labels
        if traj:
            max_x = traj[-1]["x"]
            # Range markers
            for mx in [0, max_x*0.25, max_x*0.5, max_x*0.75, max_x]:
                dummy = {"x": mx, "y": 0.0}
                px_, _ = self._traj_to_canvas(dummy)
                pygame.draw.line(surf, BORDER_DIM,
                                 (px_, ground_y), (px_, ground_y+4), 1)
                blit_text(surf, self.fonts, "range", f"{mx:.0f}m",
                          (px_, ground_y+6), TEXT_DIM, anchor="midtop")

    # ── Draw left panel ───────────────────────────────────────────────────────

    def _draw_panel(self, surf):
        px, lh = 10, 34

        def row_y(r): return r * lh + 8

        draw_rect_fill(surf, (0, 0, PANEL_W, H), PANEL_BG, radius=0)
        draw_rect_border(surf, (0, 0, PANEL_W, H), BORDER_DIM, width=1)

        # Title
        blit_text(surf, self.fonts, "title", "GBB BALLISTICS",
                  (PANEL_W//2, 10), BORDER, anchor="midtop")

        sections = [
            (1,  "── GUN ──────────────────"),
            (6,  "── HOP-UP ───────────────"),
            (10, "── BB (6mm) ─────────────"),
            (13, "── LAUNCH ───────────────"),
            (15, "── ENVIRONMENT ──────────"),
        ]
        for row, title in sections:
            blit_text(surf, self.fonts, "small", title,
                      (px, row_y(row)), BORDER_DIM)

        labels = {
            "barrel_mm":  "Barrel Length",
            "bore_mm":    "Bore Dia",
            "chamber_cc": "Chamber Vol",
            "pressure":   "Gas Pressure",
            "hop_active": "Hop-Up",
            "hardness":   "Hardness",
            "bk_press":   "Bucking Press",
            "mass_g":     "BB Mass",
            "polish":     "Polish",
            "angle":      "Launch Angle",
            "temp_c":     "Temperature",
            "altitude_m": "Altitude",
            "wind_ms":    "Wind Speed",
            "wind_dir":   "Wind Dir",
        }
        rows = {
            "barrel_mm":2,"bore_mm":3,"chamber_cc":4,"pressure":5,
            "hop_active":7,"hardness":8,"bk_press":9,
            "mass_g":11,"polish":12,
            "angle":14,
            "temp_c":16,"altitude_m":17,"wind_ms":18,"wind_dir":19,
        }
        for key, field in self.fields.items():
            r = rows[key]
            y = row_y(r)
            field.rect.y = y
            field.rect.x = 170
            blit_text(surf, self.fonts, "label", labels[key],
                      (px+4, y+3), TEXT_LABEL)
            field.draw(surf, self.fonts)

        # Muzzle readout at bottom of panel
        by = row_y(21)
        draw_rect_border(surf, (px, by, PANEL_W-px*2, 60), BORDER_DIM, radius=3)
        blit_text(surf, self.fonts, "small", "MUZZLE",
                  (PANEL_W//2, by+4), TEXT_DIM, anchor="midtop")
        fps_val = self.muzzle_v * 3.28084
        ke_val  = 0.5 * (self.fields["mass_g"].value()/1000) * self.muzzle_v**2
        blit_text(surf, self.fonts, "stats", f"{fps_val:.0f} FPS",
                  (PANEL_W//2, by+18), TEXT_WARN, anchor="midtop")
        blit_text(surf, self.fonts, "small", f"{self.muzzle_v:.1f} m/s  |  {ke_val:.3f} J",
                  (PANEL_W//2, by+38), TEXT_MAIN, anchor="midtop")
        blit_text(surf, self.fonts, "small",
                  f"Spin: {self.spin_rps*60:.0f} RPM",
                  (PANEL_W//2, by+50), TEXT_DIM, anchor="midtop")

    # ── Draw stats bar ────────────────────────────────────────────────────────

    def _draw_stats(self, surf):
        sr = self.stats_rect
        draw_rect_fill(surf, sr, PANEL_BG, radius=4)
        draw_rect_border(surf, sr, BORDER_DIM, radius=4)

        if not self.trajectory:
            return

        idx = min(self.anim_idx, len(self.trajectory)-1)
        pt  = self.trajectory[idx]

        speed_fps = pt["speed"] * 3.28084
        ke        = 0.5 * self.bb_mass_kg * pt["speed"]**2

        stats = [
            ("SPEED",  f"{pt['speed']:.1f} m/s  ({speed_fps:.0f} fps)"),
            ("RANGE",  f"{pt['x']:.2f} m  ({pt['x']/0.9144:.1f} yd)"),
            ("HEIGHT", f"{pt['y']:.3f} m"),
            ("ENERGY", f"{ke:.4f} J"),
            ("SPIN",   f"{pt['spin_rps']*60:.0f} RPM"),
            ("TIME",   f"{pt['t']:.3f} s"),
        ]

        col_w = sr.w // len(stats)
        for i, (lbl, val) in enumerate(stats):
            cx = sr.x + col_w * i + col_w // 2
            blit_text(surf, self.fonts, "small", lbl,
                      (cx, sr.y + 8), TEXT_DIM, anchor="midtop")
            blit_text(surf, self.fonts, "stats", val,
                      (cx, sr.y + 24), TEXT_MAIN, anchor="midtop")

        # Progress bar
        if self.trajectory:
            prog = self.anim_idx / max(len(self.trajectory)-1, 1)
            bar_rect = pygame.Rect(sr.x+10, sr.y+sr.h-14, sr.w-20, 8)
            draw_rect_fill(surf, bar_rect, (20, 40, 30), radius=4)
            fill_w = int(bar_rect.w * prog)
            if fill_w > 0:
                draw_rect_fill(surf,
                               pygame.Rect(bar_rect.x, bar_rect.y, fill_w, bar_rect.h),
                               BORDER, radius=4)

    # ── Draw buttons ──────────────────────────────────────────────────────────

    def _draw_buttons(self, surf):
        mx, my = pygame.mouse.get_pos()

        # FIRE / PAUSE
        fire_hov = self.fire_rect.collidepoint(mx, my)
        fire_col = FIRE_HOV if fire_hov else FIRE_BTN
        draw_rect_fill(surf, self.fire_rect, fire_col, radius=6)
        draw_rect_border(surf, self.fire_rect, (255,160,80), radius=6)
        if self.playing:
            label = "⏸  PAUSE"
        elif self.anim_idx > 0 and self.anim_idx >= len(self.trajectory)-1:
            label = "▶  REPLAY"
        else:
            label = "▶  FIRE!"
        blit_text(surf, self.fonts, "btn", label,
                  self.fire_rect.center, FIRE_TXT, anchor="center")

        # RESET
        reset_hov = self.reset_rect.collidepoint(mx, my)
        reset_col = RESET_HOV if reset_hov else RESET_BTN
        draw_rect_fill(surf, self.reset_rect, reset_col, radius=6)
        draw_rect_border(surf, self.reset_rect, (80,130,180), radius=6)
        blit_text(surf, self.fonts, "btn", "■  RESET",
                  self.reset_rect.center, TEXT_LABEL, anchor="center")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        dt = 0.0
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                # Keyboard shortcut: Space = fire/pause, R = reset
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self._on_fire()
                    elif event.key == pygame.K_r:
                        self._on_reset()
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()

                # Buttons
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.fire_rect.collidepoint(event.pos):
                        self._on_fire()
                    elif self.reset_rect.collidepoint(event.pos):
                        self._on_reset()

                # Input fields
                for field in self.fields.values():
                    field.handle_event(event)

                # Re-compute simulation on any field change (when not playing)
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if not self.playing:
                        self._run_simulation()

            # Update cursor blink
            for field in self.fields.values():
                if hasattr(field, "update"):
                    field.update(dt)

            # Advance animation
            if self.playing and self.trajectory:
                self.anim_time += ANIM_SPEED * dt
                # Find the index whose .t is closest to anim_time
                while (self.anim_idx < len(self.trajectory)-1 and
                       self.trajectory[self.anim_idx]["t"] < self.anim_time):
                    self.anim_idx += 1
                if self.anim_idx >= len(self.trajectory)-1:
                    self.playing = False

            # ── Draw ────────────────────────────────────────────────────────
            self.screen.fill(BG)

            # Left panel
            panel_surf = self.screen.subsurface(pygame.Rect(0, 0, PANEL_W, H))
            self._draw_panel(panel_surf)

            self._draw_canvas(self.screen)
            self._draw_stats(self.screen)
            self._draw_buttons(self.screen)

            # Top-right HUD
            blit_text(self.screen, self.fonts, "small",
                      "SPACE=FIRE  R=RESET  ESC=QUIT",
                      (W - 10, 6), BORDER_DIM, anchor="topright")

            pygame.display.flip()
            dt = self.clock.tick(FPS_SIM) / 1000.0

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_fire(self):
        if self.playing:
            self.playing = False
            return
        # If finished, replay
        if self.anim_idx >= len(self.trajectory)-1:
            self._run_simulation()
            self.anim_idx  = 0
            self.anim_time = 0.0
        self.playing = True

    def _on_reset(self):
        self.playing   = False
        self._run_simulation()
        self.anim_idx  = 0
        self.anim_time = 0.0


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().run()
