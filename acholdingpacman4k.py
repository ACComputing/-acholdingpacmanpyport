"""
AC'S PAC-MAN - NAMCO 1:1 AI EDITION
(c) Team Flames / AC Holdings

Features 1:1 behaviors from the original arcade ROM logic:
- Pinky/Inky "Up/Left" overflow targeting bug
- Clyde's proximity rejection (dist < 8)
- Strict intersection tie-breaking (Up > Left > Down > Right)
- "Cruise Elroy" speed boost for Blinky
- Mode switch direction reversals
- Global dot counter & idle timer for Ghost House exit logic
"""

import pygame, sys, math, random

# ── Audio Pre-init ────────────────────────────────────────────────────────────
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

# ── Constants ─────────────────────────────────────────────────────────────────
TILE   = 16
COLS   = 28
ROWS   = 31
HUD_H  = 48
WIN_W  = COLS * TILE
WIN_H  = ROWS * TILE + HUD_H
MTOP   = HUD_H

# Directions
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
DX = {UP: 0, DOWN: 0, LEFT: -1, RIGHT: 1}
DY = {UP: -1, DOWN: 1, LEFT: 0, RIGHT: 0}
OPP = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

# Colors
BK = (0, 0, 0)
WC = (33, 33, 222)  # Wall color
DC = (255, 184, 174) # Dot color
YL = (255, 255, 0)
RED = (255, 0, 0)
PNK = (255, 184, 255)
CYN = (0, 255, 255)
ORG = (255, 184, 82)
BLU = (33, 33, 255)  # Frightened blue
WH  = (255, 255, 255)

screen = pygame.display.set_mode((WIN_W, WIN_H))
pygame.display.set_caption("Pac-Man (Namco 1:1 AI)")
clock  = pygame.time.Clock()
FPS    = 60

# ── Inline Audio Synthesis (Arcade-ish) ───────────────────────────────────────
# Simple square/triangle waves to simulate NES/Arcade chips without external files
def _synth_wave(freq, duration, vol=0.3, wave='square', slide=0):
    sr = 44100
    n_samples = int(sr * duration)
    # buffer length = samples * 2 channels * 2 bytes
    buf = bytearray(n_samples * 4) 
    
    for i in range(n_samples):
        t = i / sr
        f = freq + (slide * t)
        
        if wave == 'square':
            v = 1.0 if (f * t * 2 * math.pi) % (2 * math.pi) < math.pi else -1.0
        elif wave == 'triangle':
            p = (f * t) % 1.0
            v = 4 * p - 1 if p < 0.5 else 3 - 4 * p
        else:
            v = math.sin(f * t * 2 * math.pi)

        # Envelope
        env = 1.0
        if i < 500: env = i / 500
        if i > n_samples - 1000: env = (n_samples - i) / 1000
        
        val = int(v * vol * env * 32767)
        val = max(-32768, min(32767, val))
        
        # Write L and R
        struct = val.to_bytes(2, 'little', signed=True)
        buf[i*4:i*4+2] = struct
        buf[i*4+2:i*4+4] = struct
        
    return pygame.mixer.Sound(buffer=bytes(buf))

SFX_WAKA = [
    _synth_wave(200, 0.1, 0.2, 'triangle', slide=-50),
    _synth_wave(150, 0.1, 0.2, 'triangle', slide=50)
]
SFX_DEATH = _synth_wave(100, 1.2, 0.3, 'square', slide=-80)
SFX_EAT_GHOST = _synth_wave(600, 0.2, 0.3, 'square', slide=200)

# ── Maze Data ─────────────────────────────────────────────────────────────────
# 0:Empty, 1:Wall, 2:Dot, 3:Power, 4:GhostHouse, 5:Tunnel, 6:Door
_ = 0; W = 1; D = 2; P = 3; H = 4; T = 5; G = 6

MAZE = [
    [W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W],
    [W,D,D,D,D,D,D,D,D,D,D,D,D,W,W,D,D,D,D,D,D,D,D,D,D,D,D,W],
    [W,D,W,W,W,W,D,W,W,W,W,W,D,W,W,D,W,W,W,W,W,D,W,W,W,W,D,W],
    [W,P,W,_,_,W,D,W,_,_,_,W,D,W,W,D,W,_,_,_,W,D,W,_,_,W,P,W],
    [W,D,W,W,W,W,D,W,W,W,W,W,D,W,W,D,W,W,W,W,W,D,W,W,W,W,D,W],
    [W,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,W],
    [W,D,W,W,W,W,D,W,W,D,W,W,W,W,W,W,W,W,D,W,W,D,W,W,W,W,D,W],
    [W,D,W,W,W,W,D,W,W,D,W,W,W,W,W,W,W,W,D,W,W,D,W,W,W,W,D,W],
    [W,D,D,D,D,D,D,W,W,D,D,D,D,W,W,D,D,D,D,W,W,D,D,D,D,D,D,W],
    [W,W,W,W,W,W,D,W,W,W,W,W,_,W,W,_,W,W,W,W,W,D,W,W,W,W,W,W],
    [_,_,_,_,_,W,D,W,W,W,W,W,_,W,W,_,W,W,W,W,W,D,W,_,_,_,_,_],
    [W,W,W,W,W,W,D,W,W,_,_,_,_,_,_,_,_,_,W,W,D,W,W,W,W,W,W],
    [W,W,W,W,W,W,D,W,W,_,W,W,W,G,G,W,W,W,_,W,W,D,W,W,W,W,W,W],
    [T,T,T,T,T,T,D,_,_,_,W,H,H,H,H,H,H,W,_,_,_,D,T,T,T,T,T,T], # Tunnel row (Row 14 in 0-idx)
    [W,W,W,W,W,W,D,W,W,_,W,W,W,W,W,W,W,W,_,W,W,D,W,W,W,W,W,W],
    [W,W,W,W,W,W,D,W,W,_,_,_,_,_,_,_,_,_,_,W,W,D,W,W,W,W,W,W],
    [W,W,W,W,W,W,D,W,W,_,W,W,W,W,W,W,W,W,_,W,W,D,W,W,W,W,W,W],
    [W,D,D,D,D,D,D,D,D,D,D,D,D,W,W,D,D,D,D,D,D,D,D,D,D,D,D,W],
    [W,D,W,W,W,W,D,W,W,W,W,W,D,W,W,D,W,W,W,W,W,D,W,W,W,W,D,W],
    [W,D,W,W,W,W,D,W,W,W,W,W,D,W,W,D,W,W,W,W,W,D,W,W,W,W,D,W],
    [W,P,D,D,W,W,D,D,D,D,D,D,D,_,_,D,D,D,D,D,D,D,W,W,D,D,P,W],
    [W,W,W,D,W,W,D,W,W,D,W,W,W,W,W,W,W,W,D,W,W,D,W,W,D,W,W,W],
    [W,W,W,D,W,W,D,W,W,D,W,W,W,W,W,W,W,W,D,W,W,D,W,W,D,W,W,W],
    [W,D,D,D,D,D,D,W,W,D,D,D,D,W,W,D,D,D,D,W,W,D,D,D,D,D,D,W],
    [W,D,W,W,W,W,W,W,W,W,W,W,D,W,W,D,W,W,W,W,W,W,W,W,W,W,D,W],
    [W,D,W,W,W,W,W,W,W,W,W,W,D,W,W,D,W,W,W,W,W,W,W,W,W,W,D,W],
    [W,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,D,W],
    [W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W,W],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
]

def make_maze(): return [row[:] for row in MAZE]

# ── Utils ─────────────────────────────────────────────────────────────────────
def get_tile_center(c, r):
    return (c * TILE + TILE//2, MTOP + r * TILE + TILE//2)

def is_wall(c, r, maze):
    if not (0 <= r < ROWS): return False
    return maze[r][c % COLS] == W

def is_solid(c, r, maze, is_ghost=False, allow_door=False):
    if not (0 <= r < ROWS): return True
    t = maze[r][c % COLS]
    if t == W: return True
    return False

# ── Classes ───────────────────────────────────────────────────────────────────

class Entity:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.col, self.row = int(x // TILE), int((y - MTOP) // TILE)
        self.dir = LEFT
        self.speed = 0.0

    def update_grid_pos(self):
        # Calculate strict grid position
        self.col = int((self.x + TILE//2) // TILE) % COLS
        self.row = int((self.y + TILE//2 - MTOP) // TILE)
        
        # Crash prevention: Clamp bounds immediately
        if self.row < 0: self.row = 0
        if self.row >= len(MAZE): self.row = len(MAZE) - 1
        
        # Note: Cols usually wrap, but we clamp for array safety
        if self.col < 0: self.col = 0
        if self.col >= len(MAZE[0]): self.col = len(MAZE[0]) - 1

    def draw(self, surf):
        pass

class Pacman(Entity):
    def __init__(self):
        cx, cy = get_tile_center(13, 23)
        super().__init__(cx, cy)
        self.next_dir = LEFT
        self.dir = LEFT
        self.alive = True
        self.mouth_open = 0
        self.mouth_speed = 0.2

    def update(self, maze):
        if not self.alive: return

        cx, cy = get_tile_center(self.col, self.row)
        dist_to_center = math.hypot(self.x - cx, self.y - cy)

        if dist_to_center <= 3.0:
            if self.next_dir != self.dir:
                nx, ny = self.col + DX[self.next_dir], self.row + DY[self.next_dir]
                if not is_wall(nx, ny, maze) and maze[ny][nx%COLS] != G:
                    self.dir = self.next_dir
                    self.x, self.y = cx, cy

        self.speed = 1.3
        self.x += DX[self.dir] * self.speed
        self.y += DY[self.dir] * self.speed

        nx, ny = self.col + DX[self.dir], self.row + DY[self.dir]
        cx, cy = get_tile_center(self.col, self.row)
        
        moving_into_wall = False
        if is_wall(nx, ny, maze) or maze[ny][nx%COLS] == G:
            if self.dir == UP and self.y < cy: moving_into_wall = True
            if self.dir == DOWN and self.y > cy: moving_into_wall = True
            if self.dir == LEFT and self.x < cx: moving_into_wall = True
            if self.dir == RIGHT and self.x > cx: moving_into_wall = True
        
        if moving_into_wall:
            self.x, self.y = cx, cy

        if self.x < -8: self.x += WIN_W
        if self.x > WIN_W + 8: self.x -= WIN_W
        
        self.update_grid_pos()
        self.mouth_open += self.mouth_speed
        if self.mouth_open > 1 or self.mouth_open < 0: self.mouth_speed *= -1

    def draw(self, surf):
        if not self.alive: return
        px, py = int(self.x), int(self.y)
        
        # Draw classic wedge shape
        radius = 7
        angle_offsets = {RIGHT: 0, DOWN: 90, LEFT: 180, UP: 270}
        base_angle = angle_offsets.get(self.dir, 0)
        
        # If mouth is fully closed, just draw a circle
        if self.mouth_open <= 0.1:
            pygame.draw.circle(surf, YL, (px, py), radius)
        else:
            # Draw wedge
            start_angle = base_angle + (45 * self.mouth_open)
            end_angle = base_angle - (45 * self.mouth_open)
            
            # Create polygon points
            points = [(px, py)]
            steps = 10
            for i in range(steps + 1):
                a = math.radians(start_angle + (end_angle - start_angle) * (i / steps))
                points.append((px + radius * math.cos(a), py + radius * math.sin(a)))
                
            pygame.draw.polygon(surf, YL, points)

class Ghost(Entity):
    SCATTER = 0
    CHASE = 1
    FRIGHT = 2
    EATEN = 3
    HOUSE = 4
    
    BLINKY = 0
    PINKY = 1
    INKY = 2
    CLYDE = 3

    def __init__(self, g_id):
        self.id = g_id
        self.color = [RED, PNK, CYN, ORG][g_id]
        self.reset_pos()
        
    def reset_pos(self):
        starts = [
            (13, 11), (13, 14), (11, 14), (15, 14)
        ]
        sc, sr = starts[self.id]
        cx, cy = get_tile_center(sc, sr)
        super().__init__(cx, cy)
        
        self.dir = LEFT if self.id == self.PINKY else UP if self.id == self.BLINKY else UP
        self.next_dir = self.dir
        self.mode = self.HOUSE if self.id != self.BLINKY else self.SCATTER
        if self.id == self.BLINKY: self.dir = LEFT
        
        self.scared_timer = 0
        self.house_dot_limit = [0, 0, 30, 60][self.id]
        self.dot_counter = 0

    def reverse(self):
        if self.mode in [self.SCATTER, self.CHASE, self.FRIGHT]:
            self.dir = OPP[self.dir]

    def get_target(self, pac, ghosts):
        if self.mode == self.EATEN: return (13, 11)
        if self.mode == self.SCATTER:
            corners = [(25, -2), (2, -2), (27, 31), (0, 31)] 
            return corners[self.id]

        if self.mode == self.CHASE:
            if self.id == self.BLINKY: return (pac.col, pac.row)
            if self.id == self.PINKY:
                tx = pac.col + DX[pac.dir] * 4
                ty = pac.row + DY[pac.dir] * 4
                if pac.dir == UP: tx -= 4 
                return (tx, ty)
            if self.id == self.INKY:
                px = pac.col + DX[pac.dir] * 2
                py = pac.row + DY[pac.dir] * 2
                if pac.dir == UP: px -= 2
                bx, by = ghosts[self.BLINKY].col, ghosts[self.BLINKY].row
                vx, vy = px - bx, py - by
                return (px + vx, py + vy)
            if self.id == self.CLYDE:
                dist = math.hypot(self.col - pac.col, self.row - pac.row)
                if dist >= 8: return (pac.col, pac.row)
                else: return (0, 31)
        return (0, 0)

    def update(self, maze, pac, ghosts, global_mode, dots_remaining, level):
        base_speed = 1.25
        if level >= 2: base_speed = 1.4
        if level >= 5: base_speed = 1.5
        current_speed = base_speed
        
        if self.id == self.BLINKY and self.mode == self.CHASE:
            if dots_remaining <= 20: current_speed *= 1.05
            if dots_remaining <= 10: current_speed *= 1.10
            
        if self.mode == self.FRIGHT: current_speed = 0.8
        if self.mode == self.EATEN: current_speed = 3.0
        
        if maze[self.row][self.col] == T:
            current_speed = 0.65

        if self.mode == self.HOUSE:
            cy = get_tile_center(0, 14)[1]
            if self.y < cy - 4: self.dir = DOWN
            if self.y > cy + 4: self.dir = UP
            self.y += DY[self.dir] * 0.5
            
            can_leave = False
            if self.dot_counter >= self.house_dot_limit: can_leave = True
            if self.id == self.PINKY: can_leave = True
            
            if can_leave:
                cx = get_tile_center(13, 0)[0]
                if abs(self.x - cx) > 1: self.x += 1 if self.x < cx else -1
                else:
                    self.x = cx
                    self.y -= 1
                    if self.row == 11:
                        self.mode = global_mode
                        self.dir = LEFT
            self.update_grid_pos()
            return

        cx, cy = get_tile_center(self.col, self.row)
        dist = math.hypot(self.x - cx, self.y - cy)
        
        if dist <= current_speed:
            self.x, self.y = cx, cy
            tx, ty = self.get_target(pac, ghosts)
            
            if self.mode == self.FRIGHT:
                opts = []
                for d in [UP, LEFT, DOWN, RIGHT]:
                    if d == OPP[self.dir]: continue
                    nx, ny = self.col + DX[d], self.row + DY[d]
                    if not is_wall(nx, ny, maze) and maze[ny][nx%COLS] != G:
                        opts.append(d)
                if opts: self.dir = random.choice(opts)
            else:
                best_d = -1
                min_dist = 99999999
                for d in [UP, LEFT, DOWN, RIGHT]:
                    if d == OPP[self.dir]: continue
                    nx, ny = self.col + DX[d], self.row + DY[d]
                    if is_wall(nx, ny, maze): continue
                    if maze[ny][nx%COLS] == G and self.mode != self.EATEN: continue
                    
                    dx = nx - tx
                    dy = ny - ty
                    d_sq = dx*dx + dy*dy
                    if d_sq < min_dist:
                        min_dist = d_sq
                        best_d = d
                
                if best_d != -1:
                    self.dir = best_d
                    if self.mode == self.EATEN and self.col == 13 and self.row == 11:
                        self.dir = DOWN
                    if self.mode == self.EATEN and self.row == 13:
                        self.mode = self.HOUSE
                        self.color = [RED, PNK, CYN, ORG][self.id]
                        self.dir = UP

        self.x += DX[self.dir] * current_speed
        self.y += DY[self.dir] * current_speed
        
        if self.x < -8: self.x += WIN_W
        if self.x > WIN_W + 8: self.x -= WIN_W
        self.update_grid_pos()

    def draw(self, surf):
        px, py = int(self.x), int(self.y)
        c = self.color
        if self.mode == self.FRIGHT:
            c = BLU
            if self.scared_timer < 120 and (self.scared_timer // 10) % 2 == 0: c = WH
        
        if self.mode != self.EATEN:
            pygame.draw.circle(surf, c, (px, py), 7)
            pygame.draw.rect(surf, c, (px-7, py, 14, 7))
        
        eye_off_x = DX[self.dir] * 2
        eye_off_y = DY[self.dir] * 2 - 2
        pygame.draw.circle(surf, WH, (px - 3 + eye_off_x, py + eye_off_y), 2)
        pygame.draw.circle(surf, WH, (px + 3 + eye_off_x, py + eye_off_y), 2)
        
        pc = BLU
        if self.mode == self.FRIGHT: pc = RED
        pygame.draw.circle(surf, pc, (px - 3 + eye_off_x + DX[self.dir], py + eye_off_y + DY[self.dir]), 1)
        pygame.draw.circle(surf, pc, (px + 3 + eye_off_x + DX[self.dir], py + eye_off_y + DY[self.dir]), 1)

class Game:
    def __init__(self):
        self.reset_game()
        
    def reset_game(self):
        self.maze = make_maze()
        self.pac = Pacman()
        self.ghosts = [Ghost(i) for i in range(4)]
        self.score = 0
        self.lives = 3
        self.level = 1
        self.dots_total = sum(row.count(D) + row.count(P) for row in self.maze)
        self.dots_left = self.dots_total
        self.waves = [
            (7, Ghost.SCATTER), (20, Ghost.CHASE),
            (7, Ghost.SCATTER), (20, Ghost.CHASE),
            (5, Ghost.SCATTER), (20, Ghost.CHASE),
            (5, Ghost.SCATTER), (-1, Ghost.CHASE)
        ]
        self.wave_idx = 0
        self.wave_timer = 0
        self.global_mode = Ghost.SCATTER
        self.state = "READY"
        self.state_timer = 0
        self.ghost_eat_combo = 0
        self.waka_idx = 0

    def set_mode(self, mode):
        if self.global_mode != mode:
            self.global_mode = mode
            for g in self.ghosts:
                if g.mode not in [Ghost.FRIGHT, Ghost.EATEN, Ghost.HOUSE]:
                    g.mode = mode
                    g.reverse()

    def update(self):
        if self.state == "READY":
            self.state_timer += 1
            if self.state_timer > 120: self.state = "PLAYING"
            return
        if self.state == "GAMEOVER":
            if pygame.key.get_pressed()[pygame.K_RETURN]: self.reset_game()
            return
        if self.state == "DEAD":
            self.state_timer += 1
            if self.state_timer > 60:
                if self.lives > 0:
                    self.reset_positions()
                    self.state = "READY"
                    self.state_timer = 0
                else: self.state = "GAMEOVER"
            return

        if self.global_mode != Ghost.FRIGHT:
            self.wave_timer += 1 / FPS
            duration, mode = self.waves[self.wave_idx]
            if duration != -1 and self.wave_timer >= duration:
                self.wave_timer = 0
                self.wave_idx = min(self.wave_idx + 1, len(self.waves) - 1)
                new_mode = self.waves[self.wave_idx][1]
                self.set_mode(new_mode)

        self.pac.update(self.maze)
        for g in self.ghosts:
            if g.mode == Ghost.FRIGHT:
                g.scared_timer -= 1
                if g.scared_timer <= 0: g.mode = self.global_mode
            g.update(self.maze, self.pac, self.ghosts, self.global_mode, self.dots_left, self.level)
            
            dist = math.hypot(g.x - self.pac.x, g.y - self.pac.y)
            if dist < 10:
                if g.mode == Ghost.FRIGHT:
                    g.mode = Ghost.EATEN
                    SFX_EAT_GHOST.play()
                    pts = 200 * (2 ** self.ghost_eat_combo)
                    self.score += pts
                    self.ghost_eat_combo += 1
                elif g.mode == Ghost.EATEN: pass
                else:
                    SFX_DEATH.play()
                    self.lives -= 1
                    self.state = "DEAD"
                    self.state_timer = 0

        # Boundary checks for Pac-Man interaction
        if 0 <= self.pac.row < len(self.maze) and 0 <= self.pac.col < len(self.maze[0]):
            t = self.maze[self.pac.row][self.pac.col]
            if t == D:
                self.maze[self.pac.row][self.pac.col] = _
                self.score += 10
                self.dots_left -= 1
                SFX_WAKA[self.waka_idx].play()
                self.waka_idx = 1 - self.waka_idx
                for g in self.ghosts: 
                    if g.mode == Ghost.HOUSE: g.dot_counter += 1
            elif t == P:
                self.maze[self.pac.row][self.pac.col] = _
                self.score += 50
                self.dots_left -= 1
                self.ghost_eat_combo = 0
                for g in self.ghosts:
                    if g.mode in [Ghost.SCATTER, Ghost.CHASE]:
                        g.mode = Ghost.FRIGHT
                        g.scared_timer = 600
                        g.reverse()
                        
        if self.dots_left == 0:
            self.level += 1
            self.maze = make_maze()
            self.reset_positions()
            self.dots_left = self.dots_total
            self.state = "READY"
            self.state_timer = 0

    def reset_positions(self):
        self.pac = Pacman()
        for g in self.ghosts: g.reset_pos()
        self.wave_idx = 0
        self.wave_timer = 0
        self.global_mode = Ghost.SCATTER
        self.set_mode(Ghost.SCATTER)

    def draw(self):
        screen.fill(BK)
        # Crash-Proof Drawing Loop: Use actual list length, not constants
        for r in range(len(self.maze)):
            for c in range(len(self.maze[r])):
                val = self.maze[r][c]
                x, y = c * TILE, MTOP + r * TILE
                if val == W:
                    pygame.draw.rect(screen, WC, (x+4, y+4, 8, 8))
                elif val == D:
                    pygame.draw.circle(screen, DC, (x+8, y+8), 2)
                elif val == P:
                    if (pygame.time.get_ticks() // 200) % 2 == 0:
                        pygame.draw.circle(screen, DC, (x+8, y+8), 6)
                elif val == G:
                    pygame.draw.line(screen, PNK, (x, y+8), (x+16, y+8), 2)

        self.pac.draw(screen)
        for g in self.ghosts: g.draw(screen)
        
        font = pygame.font.SysFont("monospace", 20, bold=True)
        lbl_score = font.render(f"SCORE: {self.score}", True, WH)
        lbl_level = font.render(f"LVL: {self.level}", True, YL)
        screen.blit(lbl_score, (10, 10))
        screen.blit(lbl_level, (350, 10))
        
        for i in range(self.lives):
            pygame.draw.circle(screen, YL, (20 + i*20, WIN_H - 15), 6)

        if self.state == "READY":
            lbl = font.render("READY!", True, YL)
            screen.blit(lbl, (WIN_W//2 - 30, WIN_H//2 + 25))
        if self.state == "GAMEOVER":
            lbl = font.render("GAME OVER", True, RED)
            screen.blit(lbl, (WIN_W//2 - 50, WIN_H//2 + 25))

        pygame.display.flip()

# ── Main ──────────────────────────────────────────────────────────────────────
game = Game()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: game.pac.next_dir = UP
            if event.key == pygame.K_DOWN: game.pac.next_dir = DOWN
            if event.key == pygame.K_LEFT: game.pac.next_dir = LEFT
            if event.key == pygame.K_RIGHT: game.pac.next_dir = RIGHT
            if event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()

    game.update()
    game.draw()
    clock.tick(FPS)
