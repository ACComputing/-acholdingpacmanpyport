import pygame
import sys
import math
import random
import struct

# ==============================================================================
# ACHOLDING PACMAN 1.0 — EXACT FAMICOM / ARCADE EDITION
# No External Files | Procedural Famicom Audio | 1:1 Ghost AI Target Logic @ 60 FPS
# ==============================================================================

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()
pygame.display.set_caption("PAC-MAN - Famicom 60 FPS Exact Edition")

# ------------------------------------------------------------------------------
# 0. FONTS & MENU CONSTANTS (added for menu)
# ------------------------------------------------------------------------------
FONT_LARGE = pygame.font.SysFont('courier', 36, bold=True)
FONT_MED = pygame.font.SysFont('courier', 24, bold=True)

# ------------------------------------------------------------------------------
# 1. AUDIO SYSTEM (Procedural APU Synthesis)
# ------------------------------------------------------------------------------
def _synth_wave(freq_start, freq_end, duration, vol, wave_type='square'):
    n_samples = max(1, int(44100 * duration))
    buf = bytearray()
    phase_acc = 0.0
    for i in range(n_samples):
        t = i / n_samples
        current_freq = freq_start * (1 - t) + freq_end * t
        phase_add = current_freq / 44100.0
        phase_acc += phase_add
        phase_acc -= int(phase_acc)
        env = 1.0 if t < 0.8 else (1.0 - (t - 0.8) * 5)
        val = 0.0
        if wave_type == 'square': val = 1.0 if phase_acc < 0.5 else -1.0
        elif wave_type == 'triangle': val = 2.0 * abs(0.5 - phase_acc) - 1.0
        elif wave_type == 'noise': val = random.uniform(-1.0, 1.0)
        sample = max(-32768, min(32767, int(val * vol * env * 32767)))
        buf.extend(struct.pack('h', sample))
    return pygame.mixer.Sound(buffer=buf)

def _synth_siren():
    n_samples = int(44100 * 0.3)
    buf = bytearray()
    phase_acc = 0.0
    for i in range(n_samples):
        f = 450 + 100 * math.sin(i / n_samples * math.pi * 2)
        phase_acc += f / 44100.0
        phase_acc -= int(phase_acc)
        val = 2.0 * abs(0.5 - phase_acc) - 1.0
        sample = max(-32768, min(32767, int(val * 0.08 * 32767)))
        buf.extend(struct.pack('h', sample))
    return pygame.mixer.Sound(buffer=buf)

try:
    SND_WAKA_1 = _synth_wave(450, 300, 0.1, 0.1, 'triangle')
    SND_WAKA_2 = _synth_wave(300, 450, 0.1, 0.1, 'triangle')
    SND_EAT_GHOST = _synth_wave(800, 1600, 0.4, 0.2, 'square')
    SND_DEATH = _synth_wave(300, 50, 1.5, 0.3, 'noise')
    SND_POWER = _synth_wave(600, 1000, 0.3, 0.15, 'square')
    SND_SIREN = _synth_siren()
    ch_siren = pygame.mixer.Channel(0)
    ch_waka = pygame.mixer.Channel(1)
except:
    pass

# ------------------------------------------------------------------------------
# 2. CONSTANTS & EXACT MAZE LAYOUT
# ------------------------------------------------------------------------------
TILE = 16
COLS = 28
ROWS = 31
TOP_PAD = 48
WIN_W = COLS * TILE
WIN_H = ROWS * TILE + TOP_PAD + 32
FPS = 60

BG = (0, 0, 0)
W = (255, 255, 255)
PAC_C = (255, 255, 0)
DOT_C = (255, 184, 174)
WALL_C = (33, 33, 222)
DOOR_C = (255, 184, 255)

G_RED    = (255, 0, 0)
G_PINK   = (255, 184, 255)
G_CYAN   = (0, 255, 255)
G_ORANGE = (255, 184, 82)
G_BLUE   = (33, 33, 255)

screen = pygame.display.set_mode((WIN_W, WIN_H))
clock = pygame.time.Clock()

# EXACT 244 Dot Arcade Layout (1:Wall, 2:Dot, 3:Power, =:Door, 0:Empty)
FULL_MAZE = [
    "1111111111111111111111111111",
    "1222222222222112222222222221",
    "1211112111112112111112111121",
    "1311112111112112111112111131",
    "1211112111112112111112111121",
    "1222222222222222222222222221",
    "1211112112111111112112111121",
    "1211112112111111112112111121",
    "1222222112222112222112222221",
    "1111112111110110111112111111",
    "0000012111110110111112100000",
    "0000012110000000000112100000",
    "0000012110111==1110112100000",
    "1111112110100000010112111111",
    "0000002000100000010002000000", 
    "1111112110100000010112111111",
    "0000012110111111110112100000",
    "0000012110000000000112100000",
    "0000012110111111110112100000",
    "1111112110111111110112111111",
    "1222222222222112222222222221",
    "1211112111112112111112111121",
    "1211112111112112111112111121",
    "1322112222222002222222112231",
    "1112112112111111112112112111",
    "1112112112111111112112112111",
    "1222222112222112222112222221",
    "1211111111112112111111111121",
    "1211111111112112111111111121",
    "1222222222222222222222222221",
    "1111111111111111111111111111"
]

def build_maze_surf():
    surf = pygame.Surface((WIN_W, WIN_H))
    surf.fill(BG)
    for r in range(ROWS):
        for c in range(COLS):
            char = FULL_MAZE[r][c]
            x, y = c * TILE, r * TILE + TOP_PAD
            if char == '1':
                # Retro Famicom Double-Line Visuals
                pygame.draw.rect(surf, WALL_C, (x, y, TILE, TILE))
                pygame.draw.rect(surf, BG, (x+3, y+3, TILE-6, TILE-6))
            elif char == '=':
                pygame.draw.rect(surf, DOOR_C, (x, y+TILE//2-2, TILE, 4))
    return surf
MAZE_SURF = build_maze_surf()

def is_wall(c, r, allow_door=False):
    if r == 14 and (c < 0 or c >= COLS): return False # Tunnels
    if c < 0 or c >= COLS or r < 0 or r >= ROWS: return True
    char = FULL_MAZE[r][c]
    if char == '1': return True
    if char == '=' and not allow_door: return True
    return False

# ------------------------------------------------------------------------------
# 3. CORE ENTITIES
# ------------------------------------------------------------------------------
class Pacman:
    def __init__(self):
        self.score = 0
        self.lives = 3
        self.reset()
        
    def reset(self):
        self.col, self.row = 13, 23
        self.x = self.col * TILE + TILE / 2.0
        self.y = self.row * TILE + TOP_PAD + TILE / 2.0
        self.dir = (-1, 0)
        self.next_dir = (-1, 0)
        self.speed = 1.6
        self.anim_frame = 0
        self.freeze_frames = 0
        
    def update(self, is_frightened):
        if self.freeze_frames > 0:
            self.freeze_frames -= 1
            return
            
        self.speed = 1.8 if is_frightened else 1.6
        old_x, old_y = self.x, self.y
        
        # Famicom Instant Reverse
        if self.next_dir == (-self.dir[0], -self.dir[1]) and self.dir != (0,0):
            self.dir = self.next_dir
            self.next_dir = (0,0)
            
        # Move
        self.x += self.dir[0] * self.speed
        self.y += self.dir[1] * self.speed
        self.anim_frame += self.speed
        
        # Tunnels Wrap
        if self.x < -8: self.x = WIN_W + 8
        if self.x > WIN_W + 8: self.x = -8

        cx = self.col * TILE + TILE / 2.0
        cy = self.row * TILE + TOP_PAD + TILE / 2.0

        # Sub-Pixel Intersection Crossing Logic
        passed = False
        if self.dir[0] > 0 and old_x <= cx and self.x > cx: passed = True
        elif self.dir[0] < 0 and old_x >= cx and self.x < cx: passed = True
        elif self.dir[1] > 0 and old_y <= cy and self.y > cy: passed = True
        elif self.dir[1] < 0 and old_y >= cy and self.y < cy: passed = True

        if passed:
            rem_dist = abs(self.x - cx) + abs(self.y - cy)
            self.x, self.y = cx, cy # Snap to precise grid center
            
            # Corner Buffering Execution
            if self.next_dir != (0,0) and not is_wall(self.col + self.next_dir[0], self.row + self.next_dir[1]):
                self.dir = self.next_dir
                self.next_dir = (0,0)
                
            # Stop if hitting wall
            if is_wall(self.col + self.dir[0], self.row + self.dir[1]):
                self.dir = (0,0)
                rem_dist = 0
                
            self.x += self.dir[0] * rem_dist
            self.y += self.dir[1] * rem_dist

        # Start from standstill
        if self.dir == (0,0) and self.next_dir != (0,0):
            if not is_wall(self.col + self.next_dir[0], self.row + self.next_dir[1]):
                self.dir = self.next_dir
                self.next_dir = (0,0)

        self.col = int(self.x // TILE)
        self.row = int((self.y - TOP_PAD) // TILE)

    def draw(self, surf, death_progress=None):
        pos = (int(self.x), int(self.y))
        
        if death_progress is not None: # Fold inwards animation
            mouth = death_progress * 180
            if mouth < 180:
                pygame.draw.circle(surf, PAC_C, pos, 12)
                p2 = (pos[0] + math.cos(math.radians(270 + mouth)) * 14, pos[1] - math.sin(math.radians(270 + mouth)) * 14)
                p3 = (pos[0] + math.cos(math.radians(270 - mouth)) * 14, pos[1] - math.sin(math.radians(270 - mouth)) * 14)
                pygame.draw.polygon(surf, BG, [pos, p2, p3])
            return

        angle = 0
        if self.dir == (1, 0): angle = 0
        elif self.dir == (-1, 0): angle = 180
        elif self.dir == (0, -1): angle = 90
        elif self.dir == (0, 1): angle = 270
        
        mouth = (self.anim_frame % 20) / 20 * 60
        if mouth > 30: mouth = 60 - mouth
        if self.dir == (0,0): mouth = 20
        
        pygame.draw.circle(surf, PAC_C, pos, 12)
        if mouth > 2:
            p2 = (pos[0] + int(math.cos(math.radians(angle + mouth)) * 14), pos[1] - int(math.sin(math.radians(angle + mouth)) * 14))
            p3 = (pos[0] + int(math.cos(math.radians(angle - mouth)) * 14), pos[1] - int(math.sin(math.radians(angle - mouth)) * 14))
            pygame.draw.polygon(surf, BG, [pos, p2, p3])


class Ghost:
    def __init__(self, type_id, color):
        self.type = type_id # 0=Red, 1=Pink, 2=Cyan, 3=Orange
        self.color = color
        self.reset()
        
    def reset(self):
        self.dir = (0,0)
        self.speed = 1.4
        self.in_house = True
        
        if self.type == 0:   # Blinky starts outside
            self.x = 13.5 * TILE + TILE/2; self.y = 11 * TILE + TILE/2 + TOP_PAD
            self.in_house = False; self.dir = (-1,0)
        elif self.type == 1: # Pinky
            self.x = 13.5 * TILE + TILE/2; self.y = 14 * TILE + TILE/2 + TOP_PAD
        elif self.type == 2: # Inky
            self.x = 11.5 * TILE + TILE/2; self.y = 14 * TILE + TILE/2 + TOP_PAD
        elif self.type == 3: # Clyde
            self.x = 15.5 * TILE + TILE/2; self.y = 14 * TILE + TILE/2 + TOP_PAD
            
        self.col = int(self.x // TILE)
        self.row = int((self.y - TOP_PAD) // TILE)
        self.state = 'scatter'
        self.anim = 0

    def update(self, pac, blinky, global_state, dots_eaten):
        self.anim += 1

        # Ghost House Logic
        if self.in_house:
            release = False
            if self.type == 1: release = True
            elif self.type == 2 and dots_eaten >= 30: release = True
            elif self.type == 3 and dots_eaten >= 60: release = True
            
            if release:
                target_x = 13.5 * TILE + TILE/2
                if abs(self.x - target_x) > 1: self.x += 1 if self.x < target_x else -1
                else:
                    self.x = target_x; self.y -= 1
                    if self.y <= 11 * TILE + TILE/2 + TOP_PAD:
                        self.y = 11 * TILE + TILE/2 + TOP_PAD
                        self.in_house = False
                        self.state = global_state
                        self.dir = (-1, 0)
            else:
                self.y += 0.5 if (self.anim // 15) % 2 == 0 else -0.5
            return

        # Handle Arcade Speeds
        if self.state == 'eaten': self.speed = 3.5
        elif self.state == 'frightened': self.speed = 1.0
        elif self.row == 14 and (self.col < 5 or self.col > 22): self.speed = 0.8 # Tunnels
        else: self.speed = 1.4

        old_x, old_y = self.x, self.y
        self.x += self.dir[0] * self.speed
        self.y += self.dir[1] * self.speed

        if self.x < -8: self.x = WIN_W + 8
        if self.x > WIN_W + 8: self.x = -8

        cx = self.col * TILE + TILE/2.0
        cy = self.row * TILE + TILE/2.0 + TOP_PAD

        passed = False
        if self.dir[0] > 0 and old_x <= cx and self.x > cx: passed = True
        elif self.dir[0] < 0 and old_x >= cx and self.x < cx: passed = True
        elif self.dir[1] > 0 and old_y <= cy and self.y > cy: passed = True
        elif self.dir[1] < 0 and old_y >= cy and self.y < cy: passed = True

        if passed:
            rem_dist = abs(self.x - cx) + abs(self.y - cy)
            self.x, self.y = cx, cy # Snap to center

            if self.state == 'eaten' and self.col in (13, 14) and self.row == 11:
                self.dir = (0, 1)
                self.state = global_state
                self.in_house = True
                return
            
            valid = []
            # Arcade Priority Tiebreaker: UP, LEFT, DOWN, RIGHT
            for d in [(0,-1), (-1,0), (0,1), (1,0)]:
                if d == (-self.dir[0], -self.dir[1]) and self.dir != (0,0): continue # Cannot reverse
                
                # Historic No-Up Zones
                if d == (0,-1) and self.state in ('chase', 'scatter'):
                    if (self.col, self.row) in [(12,11), (15,11), (12,23), (15,23)]: continue
                        
                if not is_wall(self.col + d[0], self.row + d[1], self.state == 'eaten'):
                    valid.append(d)
                    
            if not valid:
                self.dir = (-self.dir[0], -self.dir[1])
            elif len(valid) == 1:
                self.dir = valid[0]
            elif self.state == 'frightened':
                self.dir = random.choice(valid) # Pseudo-random
            else:
                # 1:1 Target Finding
                if self.state == 'eaten': tx, ty = 13, 11 
                elif self.state == 'scatter':
                    targets = [(25, -3), (2, -3), (27, 34), (0, 34)]
                    tx, ty = targets[self.type]
                else: # CHASE
                    if self.type == 0: tx, ty = pac.col, pac.row
                    elif self.type == 1:
                        tx, ty = pac.col + pac.dir[0]*4, pac.row + pac.dir[1]*4
                        if pac.dir == (0,-1): tx -= 4 # Pinky Authentic Overflow Bug
                    elif self.type == 2:
                        px, py = pac.col + pac.dir[0]*2, pac.row + pac.dir[1]*2
                        if pac.dir == (0,-1): px -= 2 # Inky Authentic Overflow Bug
                        vx, vy = px - blinky.col, py - blinky.row
                        tx, ty = px + vx, py + vy
                    else:
                        dist_sq = (self.col - pac.col)**2 + (self.row - pac.row)**2
                        tx, ty = (pac.col, pac.row) if dist_sq > 64 else (0, 34) # Clyde Radius

                # Euclidean Shortest Path
                best_d = valid[0]
                min_dist = float('inf')
                for d in valid:
                    nc, nr = self.col + d[0], self.row + d[1]
                    dist = (nc - tx)**2 + (nr - ty)**2
                    if dist < min_dist:
                        min_dist = dist
                        best_d = d
                self.dir = best_d

            self.x += self.dir[0] * rem_dist
            self.y += self.dir[1] * rem_dist

        self.col = int(self.x // TILE)
        self.row = int((self.y - TOP_PAD) // TILE)

    def draw(self, surf, fright_timer):
        pos = (int(self.x), int(self.y))
        
        if self.state == 'eaten':
            dx, dy = self.dir
            pygame.draw.circle(surf, W, (pos[0]-4+dx*2, pos[1]-2+dy*2), 4)
            pygame.draw.circle(surf, W, (pos[0]+4+dx*2, pos[1]-2+dy*2), 4)
            pygame.draw.circle(surf, G_BLUE, (pos[0]-4+dx*4, pos[1]-2+dy*4), 2)
            pygame.draw.circle(surf, G_BLUE, (pos[0]+4+dx*4, pos[1]-2+dy*4), 2)
            return

        c = self.color
        if self.state == 'frightened':
            c = W if (fright_timer < 120 and (fright_timer // 15) % 2 == 0) else G_BLUE
            
        pygame.draw.circle(surf, c, (pos[0], pos[1]-2), 12)
        pygame.draw.rect(surf, c, (pos[0]-12, pos[1]-2, 24, 14))
        
        # Wiggle skirt
        f = (self.anim // 8) % 2
        if f:
            pygame.draw.polygon(surf, c, [(pos[0]-12, pos[1]+12), (pos[0]-6, pos[1]+16), (pos[0], pos[1]+12)])
            pygame.draw.polygon(surf, c, [(pos[0], pos[1]+12), (pos[0]+6, pos[1]+16), (pos[0]+12, pos[1]+12)])
        else:
            pygame.draw.polygon(surf, c, [(pos[0]-12, pos[1]+12), (pos[0]-8, pos[1]+16), (pos[0]-4, pos[1]+12)])
            pygame.draw.polygon(surf, c, [(pos[0]-4, pos[1]+12), (pos[0], pos[1]+16), (pos[0]+4, pos[1]+12)])
            pygame.draw.polygon(surf, c, [(pos[0]+4, pos[1]+12), (pos[0]+8, pos[1]+16), (pos[0]+12, pos[1]+12)])
            
        if self.state == 'frightened': # Scared Face
            pygame.draw.circle(surf, (255, 184, 174), (pos[0]-4, pos[1]-2), 2)
            pygame.draw.circle(surf, (255, 184, 174), (pos[0]+4, pos[1]-2), 2)
            for ox in [-6, -2, 2]:
                pygame.draw.line(surf, (255, 184, 174), (pos[0]+ox, pos[1]+4), (pos[0]+ox+2, pos[1]+2), 2)
                pygame.draw.line(surf, (255, 184, 174), (pos[0]+ox+2, pos[1]+2), (pos[0]+ox+4, pos[1]+4), 2)
        else: # Normal Eyes
            dx, dy = self.dir
            pygame.draw.circle(surf, W, (pos[0]-4+dx*2, pos[1]-4+dy*2), 4)
            pygame.draw.circle(surf, W, (pos[0]+4+dx*2, pos[1]-4+dy*2), 4)
            pygame.draw.circle(surf, (0,0,255), (pos[0]-4+dx*4, pos[1]-4+dy*4), 2)
            pygame.draw.circle(surf, (0,0,255), (pos[0]+4+dx*4, pos[1]-4+dy*4), 2)

# ------------------------------------------------------------------------------
# 4. GAME LOOP
# ------------------------------------------------------------------------------
fnt_sys = pygame.font.SysFont('courier', 20, bold=True)
fnt_small = pygame.font.SysFont('courier', 14, bold=True)

def parse_maze():
    dots, powers = [], []
    for r in range(ROWS):
        for c in range(COLS):
            if FULL_MAZE[r][c] == '2': dots.append(pygame.Rect(c*TILE+6, r*TILE+TOP_PAD+6, 4, 4))
            elif FULL_MAZE[r][c] == '3': powers.append(pygame.Rect(c*TILE+2, r*TILE+TOP_PAD+2, 12, 12))
    return dots, powers

def run_game():
    pac = Pacman()
    
    while pac.lives > 0:
        dots, powers = parse_maze()
        ghosts = [
            Ghost(0, G_RED), Ghost(1, G_PINK), Ghost(2, G_CYAN), Ghost(3, G_ORANGE)
        ]
        
        # Level 1 Accurate Timers @ 60 FPS: 7s, 20s, 7s, 20s, 5s, 20s, 5s, inf
        WAVES = [(420, 'scatter'), (1200, 'chase'), (420, 'scatter'), (1200, 'chase'), 
                 (300, 'scatter'), (1200, 'chase'), (300, 'scatter'), (999999, 'chase')]
        wave_idx = 0
        global_state, wave_timer = WAVES[wave_idx][1], WAVES[wave_idx][0]
        
        fright_timer = 0
        combo = 200
        dots_eaten = 0
        waka_toggle = False
        freeze_frames = 120 # Ready Delay
        pending_reset = False

        # Ready Screen
        screen.blit(MAZE_SURF, (0,0))
        pac.draw(screen)
        for g in ghosts: g.draw(screen, 0)
        rd = fnt_sys.render("READY!", True, PAC_C)
        screen.blit(rd, (14*TILE - rd.get_width()//2, 17*TILE + TOP_PAD + 4))
        pygame.display.flip()
        pygame.time.wait(2000)

        if 'ch_siren' in globals(): ch_siren.play(SND_SIREN, loops=-1)

        running = True
        while running:
            clock.tick(FPS)
            
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
                if ev.type == pygame.KEYDOWN and freeze_frames <= 0:
                    if ev.key in (pygame.K_LEFT, pygame.K_a):  pac.next_dir = (-1, 0)
                    if ev.key in (pygame.K_RIGHT, pygame.K_d): pac.next_dir = (1, 0)
                    if ev.key in (pygame.K_UP, pygame.K_w):    pac.next_dir = (0, -1)
                    if ev.key in (pygame.K_DOWN, pygame.K_s):  pac.next_dir = (0, 1)

            if freeze_frames > 0:
                freeze_frames -= 1
                if freeze_frames == 0 and pending_reset:
                    if pac.lives <= 0: return # Game Over Flow
                    pac.reset()
                    for g in ghosts: g.reset()
                    freeze_frames = 120
                    pending_reset = False
            else:
                # Timer Management
                if fright_timer > 0:
                    fright_timer -= 1
                    if fright_timer == 0:
                        if 'ch_siren' in globals(): ch_siren.play(SND_SIREN, loops=-1)
                        for g in ghosts:
                            if g.state == 'frightened': g.state = global_state
                else:
                    wave_timer -= 1
                    if wave_timer <= 0:
                        wave_idx += 1
                        global_state, wave_timer = WAVES[wave_idx][1], WAVES[wave_idx][0]
                        for g in ghosts:
                            if g.state in ('scatter', 'chase'):
                                g.state = global_state
                                if g.dir != (0,0) and not g.in_house: 
                                    g.dir = (-g.dir[0], -g.dir[1]) # Reverse direction on mode switch

                pac.update(fright_timer > 0)
                p_rect = pygame.Rect(pac.x-6, pac.y-6, 12, 12)
                eaten_this_frame = False

                for d in dots[:]:
                    if p_rect.colliderect(d):
                        dots.remove(d); pac.score += 10; dots_eaten += 1
                        pac.freeze_frames = 1 # 1 Frame Pause for accurate Waka Rhythm
                        eaten_this_frame = True
                
                for p in powers[:]:
                    if p_rect.colliderect(p):
                        powers.remove(p); pac.score += 50; dots_eaten += 1
                        pac.freeze_frames = 3
                        eaten_this_frame = True
                        fright_timer = 360 # 6 seconds Frightened
                        combo = 200
                        if 'SND_POWER' in globals(): SND_POWER.play()
                        if 'ch_siren' in globals(): ch_siren.pause()
                        for g in ghosts:
                            if g.state in ('scatter', 'chase') and not g.in_house:
                                g.state = 'frightened'
                                g.dir = (-g.dir[0], -g.dir[1])

                if eaten_this_frame and 'ch_waka' in globals() and not ch_waka.get_busy():
                    ch_waka.play(SND_WAKA_1 if waka_toggle else SND_WAKA_2)
                    waka_toggle = not waka_toggle

                for g in ghosts:
                    g.update(pac, ghosts[0], global_state, dots_eaten)
                    if abs(pac.x - g.x) < 14 and abs(pac.y - g.y) < 14:
                        if g.state in ('scatter', 'chase'): # DEATH
                            if 'ch_siren' in globals(): ch_siren.stop()
                            if 'SND_DEATH' in globals(): SND_DEATH.play()
                            freeze_frames = 90
                            pac.lives -= 1
                            pending_reset = True
                        elif g.state == 'frightened': # EAT GHOST
                            g.state = 'eaten'
                            pac.score += combo; combo *= 2
                            if 'SND_EAT_GHOST' in globals(): SND_EAT_GHOST.play()
                            freeze_frames = 45 # Freeze game for dramatic impact

                if not dots and not powers and not pending_reset:
                    if 'ch_siren' in globals(): ch_siren.stop()
                    pygame.time.wait(1500)
                    running = False # Win Level

            # Drawing Loop
            screen.blit(MAZE_SURF, (0,0))
            for d in dots: pygame.draw.rect(screen, DOT_C, d)
            for p in powers:
                if (pygame.time.get_ticks() // 200) % 2: pygame.draw.circle(screen, DOT_C, p.center, 6)

            if pending_reset and freeze_frames > 0:
                pac.draw(screen, (90 - freeze_frames) / 90.0) # Fold inwards animation
            else:
                pac.draw(screen)
                for g in ghosts: g.draw(screen, fright_timer)

            screen.blit(fnt_sys.render("1UP", True, W), (30, 5))
            screen.blit(fnt_sys.render(str(pac.score), True, W), (30, 25))
            screen.blit(fnt_sys.render("HIGH SCORE", True, W), (WIN_W//2 - 50, 5))
            screen.blit(fnt_sys.render("10000", True, W), (WIN_W//2 - 20, 25))

            for i in range(pac.lives):
                px, py = 30 + i*32, WIN_H - 16
                pygame.draw.circle(screen, PAC_C, (px, py), 10)
                pygame.draw.polygon(screen, BG, [(px, py), (px-12, py+8), (px-12, py-8)])

            pygame.display.flip()

# ------------------------------------------------------------------------------
# 5. MENU SYSTEM (EXACTLY AS REQUESTED)
# ------------------------------------------------------------------------------
def show_menu():
    """Display main menu and handle navigation."""
    options = ["Play Game", "About", "Help", "Controls", "Copyright", "Exit"]
    selected = 0
    clock = pygame.time.Clock()
    tick = 0

    while True:
        clock.tick(FPS)
        tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    # Handle selection
                    if options[selected] == "Play Game":
                        run_game()  # start the game
                        # After game ends, return to menu
                    elif options[selected] == "About":
                        show_info_screen("About", 
                            "AC Holdings' Pac-Man Game 1.0\n"
                            "Exact Famicom/Arcade Edition\n"
                            "60 FPS | Procedural Audio\n\n"
                            "[C] Bandai Namco 1980\n"
                            "[C] AC Holdings 1999-2026")
                    elif options[selected] == "Help":
                        show_info_screen("Help",
                            "Eat all dots to clear the level.\n"
                            "Avoid ghosts unless powered up.\n"
                            "Eat power pellets to turn the tables!\n"
                            "Get ready for authentic ghost AI.")
                    elif options[selected] == "Controls":
                        show_info_screen("Controls",
                            "Arrow keys / WASD: Move Pac-Man\n"
                            "Enter/Space: Select menu option\n"
                            "Pause: not implemented")
                    elif options[selected] == "Copyright":
                        show_info_screen("Copyright",
                            "PAC-MAN is a trademark of Bandai Namco.\n"
                            "This is a fan recreation for educational purposes.\n"
                            "All rights reserved by respective owners.\n\n"
                            "AC Holdings (c) 1999-2026")
                    elif options[selected] == "Exit":
                        pygame.quit()
                        sys.exit()

        screen.fill(BG)

        # Title
        title = FONT_LARGE.render("AC Holdings' Pac-Man Game 1.0", True, PAC_C)
        screen.blit(title, (WIN_W//2 - title.get_width()//2, 50))

        # Subtitle / copyright line
        sub = fnt_sys.render("[C] Bandai Namco 1980   [C] AC Holdings 1999-2026", True, W)
        screen.blit(sub, (WIN_W//2 - sub.get_width()//2, 100))

        # Draw options
        for i, opt in enumerate(options):
            color = PAC_C if i == selected else W
            if i == selected and (tick // 30) % 2:
                color = G_ORANGE  # blinking cursor
            text = fnt_sys.render(opt, True, color)
            screen.blit(text, (WIN_W//2 - text.get_width()//2, 200 + i * 30))

        # Footer hint
        hint = fnt_small.render("Use UP/DOWN arrows to select, ENTER to confirm", True, (150,150,150))
        screen.blit(hint, (WIN_W//2 - hint.get_width()//2, WIN_H - 40))

        pygame.display.flip()

def show_info_screen(title, content_lines):
    """Display an information screen with the given title and multiline content.
    Press any key to return to menu.
    """
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                waiting = False

        screen.fill(BG)

        # Title
        t_surf = FONT_MED.render(title, True, PAC_C)
        screen.blit(t_surf, (WIN_W//2 - t_surf.get_width()//2, 100))

        # Content (split by newline)
        y = 180
        for line in content_lines.split('\n'):
            if line.strip():
                line_surf = fnt_sys.render(line, True, W)
                screen.blit(line_surf, (WIN_W//2 - line_surf.get_width()//2, y))
                y += 30
            else:
                y += 15

        # Back hint
        hint = fnt_small.render("Press any key to return to menu", True, (150,150,150))
        screen.blit(hint, (WIN_W//2 - hint.get_width()//2, WIN_H - 60))

        pygame.display.flip()
        pygame.time.wait(100)  # small delay to avoid key repeat

# ------------------------------------------------------------------------------
# 6. MAIN ENTRY POINT
# ------------------------------------------------------------------------------
def main():
    show_menu()

if __name__ == "__main__":
    main()
