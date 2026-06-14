import pygame
import os
import random
import math

# =========================
# SETUP
# =========================
pygame.init()
pygame.mixer.quit()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)

WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pirates Adventure — Enhanced")

# Load assets
background = pygame.image.load('everything.jpg') if os.path.exists('everything.jpg') else None
icon = pygame.image.load('swords.png') if os.path.exists('swords.png') else None
if icon:
    pygame.display.set_icon(icon)

# ===================== SOUND SETUP =====================
music_volume = 0.7
sfx_volume   = 0.8
music_on     = True
sfx_on       = True

# ── Procedural audio helpers ──────────────────────────────────────────────────
import array as _array
import wave  as _wave
import tempfile, os as _os

_SR = 44100   # sample rate

def _sine(freq, t): return math.sin(2 * math.pi * freq * t)
def _tri(freq, t):
    p = (t * freq) % 1.0
    return 1 - 4 * abs(p - 0.5)
def _sq(freq, t):
    return 1.0 if (t * freq) % 1.0 < 0.5 else -1.0

def _build_wav(samples_left, samples_right=None):
    """Interleave L+R (or mono doubled) into a stereo 16-bit array."""
    if samples_right is None:
        samples_right = samples_left
    n = min(len(samples_left), len(samples_right))
    buf = _array.array('h', [0] * (n * 2))
    for i in range(n):
        buf[i*2]   = max(-32767, min(32767, int(samples_left[i]  * 32767)))
        buf[i*2+1] = max(-32767, min(32767, int(samples_right[i] * 32767)))
    return buf

def _write_tmp_wav(buf):
    """Write stereo 16-bit PCM to a temp .wav file; return path."""
    tf = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tf.close()
    with _wave.open(tf.name, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(_SR)
        wf.writeframes(buf.tobytes())
    return tf.name

# ── MENU MUSIC  ──  slow, majestic, sea-shanty feel ──────────────────────────
def _gen_menu_music():
    """
    Gentle 4-bar loop (≈8 s) built from:
      • bass drone (sine, low D)
      • melody (triangle, pentatonic phrase)
      • soft chord pad (sine mix, open 5th)
    """
    bpm   = 72
    beat  = 60.0 / bpm          # seconds per beat
    bars  = 8
    dur   = bars * 4 * beat     # 8 bars × 4/4
    n     = int(_SR * dur)

    # Pentatonic melody: D3 F3 G3 A3 C4 D4 (MIDI 50,53,55,57,60,62)
    mel_freqs  = [146.83, 174.61, 196.00, 220.00, 261.63, 293.66]
    # 16-note pattern (note index, beats)
    mel_pattern = [
        (0,1),(2,1),(3,1),(4,0.5),(3,0.5),
        (2,1),(1,1),(0,2),
        (5,1),(4,1),(3,1),(2,0.5),(1,0.5),
        (0,1),(2,1),(0,2),
    ]
    bass_freq  = 73.42   # D2
    pad_freq1  = 146.83  # D3
    pad_freq2  = 220.00  # A3

    melody  = [0.0] * n
    bass    = [0.0] * n
    pad     = [0.0] * n

    # Build melody
    t_off = 0.0
    for (ni, nb) in mel_pattern * (bars // 2):
        seg = int(nb * beat * _SR)
        freq = mel_freqs[ni]
        for i in range(seg):
            gi = int(t_off * _SR) + i
            if gi >= n: break
            t = i / _SR
            env = min(1.0, t / 0.02) * max(0.0, 1 - t / (nb * beat))
            melody[gi] += _tri(freq, t) * env * 0.28
        t_off += nb * beat

    # Bass + pad (continuous)
    for i in range(n):
        t = i / _SR
        bass[i]  = _sine(bass_freq,  t) * 0.30
        pad[i]   = (_sine(pad_freq1, t) * 0.18
                  + _sine(pad_freq2, t) * 0.14)

    # Mix + fade in/out
    fade_s = int(0.6 * _SR)
    mixed  = [0.0] * n
    for i in range(n):
        v = melody[i] + bass[i] + pad[i]
        if i < fade_s:           v *= i / fade_s
        if i > n - fade_s:       v *= (n - i) / fade_s
        mixed[i] = v

    buf = _build_wav(mixed)
    return _write_tmp_wav(buf)

# ── BATTLE MUSIC  ── Original (MusicBGPirate.mp3 or simple fallback) ──────────
def _gen_battle_music():
    """Simple fallback: 6-note looping melody, same as the original game."""
    sample_rate = 44100
    duration = 0.5
    total_samples = int(sample_rate * duration)
    wave = _array.array('h', [0] * (total_samples * 6))
    notes = [261, 330, 392, 494, 392, 330]
    pos = 0
    for freq in notes:
        for i in range(total_samples):
            t = i / sample_rate
            wave[pos] = int(32767 * 0.6 * math.sin(2 * math.pi * freq * t))
            pos += 1
    tf = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tf.close()
    import wave as _wv
    with _wv.open(tf.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(wave.tobytes())
    return tf.name

# ── Generate & cache both tracks ──────────────────────────────────────────────
print("Generating menu music…")
_MENU_WAV   = _gen_menu_music()
print("Loading battle music…")
_BATTLE_WAV = _gen_battle_music()  # only used if MusicBGPirate.mp3 is missing

# ── Music control functions ───────────────────────────────────────────────────
_current_track = None   # 'menu' | 'battle' | None

def music_play_menu(fade_ms=800):
    global _current_track
    if not music_on:
        return
    # Check for user-supplied files first
    user_menu = "MusicBGMenu.mp3"
    track = user_menu if _os.path.exists(user_menu) else _MENU_WAV
    if _current_track == 'menu':
        return
    pygame.mixer.music.fadeout(fade_ms)
    pygame.time.wait(min(fade_ms, 200))
    try:
        pygame.mixer.music.load(track)
        pygame.mixer.music.set_volume(music_volume)
        pygame.mixer.music.play(-1, fade_ms=fade_ms)
        _current_track = 'menu'
    except Exception as e:
        print(f"Menu music error: {e}")

def music_play_battle(fade_ms=600):
    global _current_track
    if not music_on:
        return
    # Priority: uploaded pirate tavern track → MusicBGPirate.mp3 → fallback WAV
    candidates = [
        '/mnt/user-data/uploads/magiksolo-pirate-tavern-full-version-167990.mp3',
        'magiksolo-pirate-tavern-full-version-167990.mp3',
        'MusicBGPirate.mp3',
        _BATTLE_WAV,
    ]
    track = next((c for c in candidates if _os.path.exists(c)), _BATTLE_WAV)
    if _current_track == 'battle':
        return
    pygame.mixer.music.fadeout(fade_ms)
    pygame.time.wait(min(fade_ms, 200))
    try:
        pygame.mixer.music.load(track)
        pygame.mixer.music.set_volume(music_volume)
        pygame.mixer.music.play(-1, fade_ms=fade_ms)
        _current_track = 'battle'
        print(f"▶ Battle music: {track}")
    except Exception as e:
        print(f"Battle music error: {e}")

def music_stop(fade_ms=500):
    global _current_track
    pygame.mixer.music.fadeout(fade_ms)
    _current_track = None

def music_set_volume(vol):
    global music_volume
    music_volume = max(0.0, min(1.0, vol))
    pygame.mixer.music.set_volume(music_volume)

def music_toggle():
    global music_on, _current_track
    music_on = not music_on
    if music_on:
        # Resume whatever was last playing
        pygame.mixer.music.set_volume(music_volume)
        pygame.mixer.music.unpause()
    else:
        pygame.mixer.music.pause()

# ── SFX ───────────────────────────────────────────────────────────────────────
def _make_sfx(samples):
    buf = _array.array('h', [0] * len(samples) * 2)
    for i, s in enumerate(samples):
        v = max(-32767, min(32767, int(s * 32767)))
        buf[i*2] = v; buf[i*2+1] = v
    return pygame.mixer.Sound(buf)

def _create_hover_sound():
    sr, dur = 22050, 0.08
    n = int(sr * dur)
    return _make_sfx([0.4 * math.sin(2*math.pi*1100*(i/sr)) * (1-i/n) for i in range(n)])

def _create_click_sound():
    sr, dur = 22050, 0.055
    n = int(sr * dur)
    return _make_sfx([0.55 * math.sin(2*math.pi*520*(i/sr)) * (1-i/n) for i in range(n)])

def _create_explosion_sound():
    sr, dur = 22050, 0.22
    n = int(sr * dur)
    rng = random.Random(7)
    return _make_sfx([rng.uniform(-1,1) * (1-i/n)**1.4 * 0.75 for i in range(n)])

def _create_powerup_sound():
    sr, dur = 22050, 0.28
    n = int(sr * dur)
    return _make_sfx([0.45 * math.sin(2*math.pi*(440+520*(i/n))*(i/sr)) for i in range(n)])

HOVER_FILE = "Hover.mp3"
CLICK_FILE = "Click.Wav"
hover_sound     = _create_hover_sound()     if not os.path.exists(HOVER_FILE) else pygame.mixer.Sound(HOVER_FILE)
click_sound     = _create_click_sound()     if not os.path.exists(CLICK_FILE) else pygame.mixer.Sound(CLICK_FILE)
explosion_sound = _create_explosion_sound()
powerup_sound   = _create_powerup_sound()

def play_sound(sound):
    if sfx_on and sound:
        sound.set_volume(sfx_volume)
        sound.play()

# Start menu music immediately
music_play_menu(fade_ms=0)

# ===================== FONTS =====================
font_path = "PressStart2P-Regular.ttf"
if os.path.exists(font_path):
    title_font   = pygame.font.Font(font_path, 48)
    button_font  = pygame.font.Font(font_path, 30)
    small_font   = pygame.font.Font(font_path, 18)
    tiny_font    = pygame.font.Font(font_path, 14)
    micro_font   = pygame.font.Font(font_path, 10)
else:
    title_font   = pygame.font.Font(None, 68)
    button_font  = pygame.font.Font(None, 42)
    small_font   = pygame.font.Font(None, 28)
    tiny_font    = pygame.font.Font(None, 20)
    micro_font   = pygame.font.Font(None, 16)

# ===================== COLORS =====================
GOLD         = (255, 215, 0)
LIGHT_GOLD   = (255, 240, 150)
DARK_WOOD    = (80, 40, 0)
LIGHT_WOOD   = (160, 100, 40)
GREEN        = (0, 200, 80)
DARK_GREEN   = (0, 120, 40)
RED          = (220, 30, 30)
DARK_RED     = (140, 0, 0)
BLUE         = (30, 100, 255)
WHITE        = (255, 255, 255)
BLACK        = (0, 0, 0)
SHADOW       = (30, 20, 0)
GRAY         = (150, 150, 150)
OCEAN_BLUE   = (15, 70, 160)
OCEAN_LIGHT  = (20, 90, 200)
ISLAND_GREEN = (34, 139, 34)
ISLAND_SAND  = (210, 180, 100)
TREASURE     = (255, 215, 0)
ENEMY_COLOR  = (180, 30, 30)
BOSS_COLOR   = (220, 50, 220)
SHIELD_COLOR = (80, 180, 255)
ORANGE       = (255, 140, 0)
CYAN         = (0, 220, 255)
PURPLE       = (160, 0, 255)
PINK         = (255, 100, 200)
YELLOW       = (255, 255, 0)

# ===================== LOAD IMAGE =====================
def load_image(image_name, scale=None):
    try:
        image = pygame.image.load(image_name).convert_alpha()
        if scale:
            image = pygame.transform.scale(image, scale)
        return image
    except:
        surf = pygame.Surface(scale if scale else (50, 50), pygame.SRCALPHA)
        surf.fill(DARK_WOOD)
        return surf

# ===================== ANIMATED TITLE BORDER =====================
def draw_animated_title_border(window, rect, time):
    pulse = (math.sin(time * 2) + 1) / 2
    thickness = 4 + int(pulse * 4)
    r = int(GOLD[0] * (1 - pulse) + LIGHT_GOLD[0] * pulse)
    g = int(GOLD[1] * (1 - pulse) + LIGHT_GOLD[1] * pulse)
    b = int(GOLD[2] * (1 - pulse) + LIGHT_GOLD[2] * pulse)
    animated_color = (r, g, b)
    pygame.draw.rect(window, animated_color, rect, thickness, border_radius=12)
    inner = rect.inflate(-thickness, -thickness)
    pygame.draw.rect(window, DARK_WOOD, inner, border_radius=10)
    offset = int(pulse * 3)
    corner_size = 20 + offset
    pygame.draw.polygon(window, animated_color, [(rect.left, rect.top), (rect.left+corner_size, rect.top), (rect.left, rect.top+corner_size)])
    pygame.draw.polygon(window, animated_color, [(rect.right, rect.top), (rect.right-corner_size, rect.top), (rect.right, rect.top+corner_size)])
    pygame.draw.polygon(window, animated_color, [(rect.left, rect.bottom), (rect.left+corner_size, rect.bottom), (rect.left, rect.bottom-corner_size)])
    pygame.draw.polygon(window, animated_color, [(rect.right, rect.bottom), (rect.right-corner_size, rect.bottom), (rect.right, rect.bottom-corner_size)])

# ===================== MENU BUTTON =====================
class MenuButton:
    def __init__(self, text, y_pos, width=300):
        self.text = text
        self.y_pos = y_pos
        self.width = width
        self.height = 60
        self.rect = pygame.Rect(WIDTH//2 - self.width//2, self.y_pos, self.width, self.height)
        self.hovered = False
        self.was_hovered = False

    def draw(self, window):
        pygame.draw.rect(window, SHADOW, self.rect.move(4, 4), border_radius=8)
        color = LIGHT_WOOD if self.hovered else DARK_WOOD
        pygame.draw.rect(window, color, self.rect, border_radius=8)
        pygame.draw.rect(window, LIGHT_GOLD, self.rect.inflate(-6, -6), border_radius=8)
        txt_surf = button_font.render(self.text, True, DARK_WOOD)
        window.blit(txt_surf, txt_surf.get_rect(center=self.rect.center))

    def check_hover(self, mouse_pos):
        self.was_hovered = self.hovered
        self.hovered = self.rect.collidepoint(mouse_pos)
        if self.hovered and not self.was_hovered:
            play_sound(hover_sound)

# ===================== PARTICLE SYSTEM =====================
class Particle:
    def __init__(self, x, y, color, speed=3, life=0.7, size=5):
        angle = random.uniform(0, 2 * math.pi)
        spd = random.uniform(speed * 0.5, speed * 1.5)
        self.x = x
        self.y = y
        self.dx = math.cos(angle) * spd
        self.dy = math.sin(angle) * spd
        self.color = color
        self.max_life = life
        self.life = life
        self.size = random.uniform(size * 0.5, size * 1.5)

    def update(self, dt):
        self.x += self.dx
        self.y += self.dy
        self.dy += 30 * dt  # gravity
        self.life -= dt
        return self.life > 0

    def draw(self, surface, cam_x=0, cam_y=0):
        alpha = self.life / self.max_life
        r = max(0, min(255, int(self.color[0])))
        g = max(0, min(255, int(self.color[1])))
        b = max(0, min(255, int(self.color[2])))
        sz = max(1, int(self.size * alpha))
        pygame.draw.circle(surface, (r, g, b),
                           (int(self.x - cam_x), int(self.y - cam_y)), sz)

# ===================== FLOATING TEXT =====================
class FloatingText:
    def __init__(self, x, y, text, color=GOLD, size='small'):
        self.x = float(x)
        self.y = float(y)
        self.text = text
        self.color = color
        self.life = 1.2
        self.max_life = 1.2
        self.font = small_font if size == 'small' else tiny_font

    def update(self, dt):
        self.y -= 40 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surface, cam_x=0, cam_y=0):
        alpha = self.life / self.max_life
        surf = self.font.render(self.text, True, self.color)
        surf.set_alpha(int(255 * alpha))
        surface.blit(surf, (int(self.x - cam_x) - surf.get_width()//2,
                             int(self.y - cam_y)))


# ===================== SCREEN SHAKE =====================
shake_timer = 0.0
shake_intensity = 0.0

def trigger_shake(intensity=6, duration=0.25):
    global shake_timer, shake_intensity
    shake_timer = duration
    shake_intensity = intensity

def get_shake_offset():
    global shake_timer
    if shake_timer > 0:
        sx = random.randint(-int(shake_intensity), int(shake_intensity))
        sy = random.randint(-int(shake_intensity), int(shake_intensity))
        return sx, sy
    return 0, 0

# ===================== PIXEL-ART SHIP DRAWING =====================
def _rot(x, y, cx, cy, angle_rad):
    """Rotate point (x,y) around (cx,cy)."""
    dx, dy = x - cx, y - cy
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return (cx + dx * cos_a - dy * sin_a,
            cy + dx * sin_a + dy * cos_a)

def _poly(surface, color, points, angle_rad, cx, cy, width=0):
    rotated = [_rot(px, py, cx, cy, angle_rad) for px, py in points]
    pts = [(int(p[0]), int(p[1])) for p in rotated]
    if len(pts) >= 3:
        pygame.draw.polygon(surface, color, pts, width)

def _rect_pts(cx, cy, w, h):
    """Return 4 corners of a rect centred on cx,cy (before rotation)."""
    hw, hh = w / 2, h / 2
    return [(cx-hw, cy-hh), (cx+hw, cy-hh), (cx+hw, cy+hh), (cx-hw, cy+hh)]

def draw_player_ship(surface, x, y, angle_rad, shield_active=False, shield_anim=0):
    """
    Heroic galleon — large, golden-trimmed, three-masted.
    Points bow-up (angle 0 = north).
    """
    S = 28   # base scale

    # ── Hull ──────────────────────────────────────────────────────────────────
    # Main hull body
    _poly(surface, (90, 50, 10), [        # dark oak
        (x,       y - S*1.15),            # bow tip
        (x + S*.55, y - S*.3),
        (x + S*.65, y + S*.6),
        (x - S*.65, y + S*.6),
        (x - S*.55, y - S*.3),
    ], angle_rad, x, y)

    # Hull highlight strip
    _poly(surface, (140, 90, 30), [
        (x,        y - S*.95),
        (x + S*.4, y - S*.25),
        (x + S*.4, y + S*.4),
        (x - S*.4, y + S*.4),
        (x - S*.4, y - S*.25),
    ], angle_rad, x, y)

    # Stern deck (back)
    _poly(surface, (70, 35, 5), [
        (x + S*.65, y + S*.25),
        (x + S*.65, y + S*.6),
        (x - S*.65, y + S*.6),
        (x - S*.65, y + S*.25),
    ], angle_rad, x, y)

    # Gold trim lines along hull sides
    for side in (-1, 1):
        p1 = _rot(x + side*S*.55, y - S*.2, x, y, angle_rad)
        p2 = _rot(x + side*S*.65, y + S*.55, x, y, angle_rad)
        pygame.draw.line(surface, GOLD, (int(p1[0]),int(p1[1])), (int(p2[0]),int(p2[1])), 2)

    # Cannon ports (3 each side)
    for side in (-1, 1):
        for row in (-0.1, 0.15, 0.38):
            px2 = x + side * S * .66
            py2 = y + row * S
            pr = _rot(px2, py2, x, y, angle_rad)
            pygame.draw.circle(surface, (20, 10, 0), (int(pr[0]), int(pr[1])), 3)
            pygame.draw.circle(surface, (60, 40, 0), (int(pr[0]), int(pr[1])), 3, 1)

    # ── Mast & sails ─────────────────────────────────────────────────────────
    # Centre mast (tallest)
    mast_bot = _rot(x, y + S*.3, x, y, angle_rad)
    mast_top = _rot(x, y - S*1.5, x, y, angle_rad)
    pygame.draw.line(surface, (80, 45, 5),
                     (int(mast_bot[0]), int(mast_bot[1])),
                     (int(mast_top[0]), int(mast_top[1])), 3)

    # Main sail
    _poly(surface, (240, 230, 200), [
        (x - S*.42, y - S*.2),
        (x + S*.42, y - S*.2),
        (x + S*.32, y - S*.9),
        (x - S*.32, y - S*.9),
    ], angle_rad, x, y)
    # Sail cross stripe
    _poly(surface, (180, 20, 20), [
        (x - S*.42, y - S*.52),
        (x + S*.42, y - S*.52),
        (x + S*.42, y - S*.60),
        (x - S*.42, y - S*.60),
    ], angle_rad, x, y)

    # Fore-mast & small sail
    mast2_b = _rot(x, y - S*.6, x, y, angle_rad)
    mast2_t = _rot(x, y - S*1.35, x, y, angle_rad)
    pygame.draw.line(surface, (80,45,5),
                     (int(mast2_b[0]),int(mast2_b[1])),
                     (int(mast2_t[0]),int(mast2_t[1])), 2)
    _poly(surface, (220, 210, 180), [
        (x - S*.22, y - S*.65),
        (x + S*.22, y - S*.65),
        (x + S*.16, y - S*1.28),
        (x - S*.16, y - S*1.28),
    ], angle_rad, x, y)

    # Jolly-Roger flag (skull dot)
    flag_pt = _rot(x, y - S*1.5, x, y, angle_rad)
    pygame.draw.circle(surface, BLACK,  (int(flag_pt[0]), int(flag_pt[1])), 5)
    pygame.draw.circle(surface, WHITE,  (int(flag_pt[0]), int(flag_pt[1])), 3)
    pygame.draw.circle(surface, BLACK,  (int(flag_pt[0]), int(flag_pt[1])), 2)

    # ── Shield bubble ────────────────────────────────────────────────────────
    if shield_active:
        pulse = (math.sin(shield_anim * 6) + 1) / 2
        radius = int(S * 1.6 + pulse * 6)
        sh_s = pygame.Surface((radius*2+4, radius*2+4), pygame.SRCALPHA)
        pygame.draw.circle(sh_s, (*SHIELD_COLOR, int(120 + pulse*80)),
                           (radius+2, radius+2), radius, 3)
        surface.blit(sh_s, (int(x)-radius-2, int(y)-radius-2))


def draw_enemy_ship(surface, x, y, size, angle_rad, hull_color, wave_num=1):
    """
    Pirate enemy ship — gets more menacing each wave tier.
    wave_num 1-3: sloop (small), 4-6: brigantine (medium), 7+: man-o-war (large)
    """
    S = size * 0.9

    tier = min(2, (wave_num - 1) // 3)   # 0=sloop 1=brig 2=mow

    # Hull colours darken with tier
    dark_col  = tuple(max(0, c - 40) for c in hull_color)
    light_col = tuple(min(255, c + 50) for c in hull_color)

    # ── Hull ─────────────────────────────────────────────────────────────────
    if tier == 0:   # sloop — slim & pointy
        _poly(surface, dark_col, [
            (x,        y - S),
            (x + S*.45, y + S*.7),
            (x - S*.45, y + S*.7),
        ], angle_rad, x, y)
        _poly(surface, hull_color, [
            (x,        y - S*.7),
            (x + S*.3, y + S*.4),
            (x - S*.3, y + S*.4),
        ], angle_rad, x, y)
    elif tier == 1:  # brigantine — wider
        _poly(surface, dark_col, [
            (x,         y - S),
            (x + S*.55, y - S*.2),
            (x + S*.6,  y + S*.65),
            (x - S*.6,  y + S*.65),
            (x - S*.55, y - S*.2),
        ], angle_rad, x, y)
        _poly(surface, hull_color, [
            (x,         y - S*.75),
            (x + S*.38, y - S*.1),
            (x + S*.38, y + S*.4),
            (x - S*.38, y + S*.4),
            (x - S*.38, y - S*.1),
        ], angle_rad, x, y)
        # red stripe
        _poly(surface, (180, 0, 0), [
            (x + S*.6,  y + S*.1),
            (x + S*.6,  y + S*.25),
            (x - S*.6,  y + S*.25),
            (x - S*.6,  y + S*.1),
        ], angle_rad, x, y)
    else:            # man-o-war — massive & intimidating
        _poly(surface, dark_col, [
            (x,         y - S*1.05),
            (x + S*.6,  y - S*.3),
            (x + S*.72, y + S*.7),
            (x - S*.72, y + S*.7),
            (x - S*.6,  y - S*.3),
        ], angle_rad, x, y)
        _poly(surface, hull_color, [
            (x,         y - S*.8),
            (x + S*.42, y - S*.15),
            (x + S*.42, y + S*.45),
            (x - S*.42, y + S*.45),
            (x - S*.42, y - S*.15),
        ], angle_rad, x, y)
        # Two red stripes
        for sy2 in (0.05, 0.28):
            _poly(surface, (200, 0, 0), [
                (x + S*.72, y + S*sy2),
                (x + S*.72, y + S*(sy2+.12)),
                (x - S*.72, y + S*(sy2+.12)),
                (x - S*.72, y + S*sy2),
            ], angle_rad, x, y)
        # Extra cannon ports (4 each side)
        for side in (-1, 1):
            for row in (-0.1, 0.12, 0.32, 0.5):
                pr = _rot(x + side*S*.73, y + row*S, x, y, angle_rad)
                pygame.draw.circle(surface, (10, 5, 0), (int(pr[0]),int(pr[1])), 4)
                pygame.draw.circle(surface, (50,25,0),  (int(pr[0]),int(pr[1])), 4, 1)

    # ── Mast & sail ──────────────────────────────────────────────────────────
    mast_b = _rot(x, y + S*.2, x, y, angle_rad)
    mast_t = _rot(x, y - S*1.3, x, y, angle_rad)
    pygame.draw.line(surface, (60,35,5),
                     (int(mast_b[0]),int(mast_b[1])),
                     (int(mast_t[0]),int(mast_t[1])), 2 + tier)

    # Sail — black for enemies
    _poly(surface, (30, 30, 30), [
        (x - S*(0.32+tier*.06), y - S*.15),
        (x + S*(0.32+tier*.06), y - S*.15),
        (x + S*(0.22+tier*.04), y - S*.9),
        (x - S*(0.22+tier*.04), y - S*.9),
    ], angle_rad, x, y)
    # Skull on sail
    skull_pt = _rot(x, y - S*.52, x, y, angle_rad)
    pygame.draw.circle(surface, (200,200,200),(int(skull_pt[0]),int(skull_pt[1])), int(S*.15))
    pygame.draw.circle(surface, (10,10,10),   (int(skull_pt[0]),int(skull_pt[1])), int(S*.15), 1)

    # Flag — red with tier dots
    flag_pt = _rot(x, y - S*1.3, x, y, angle_rad)
    pygame.draw.circle(surface, (200, 0, 0), (int(flag_pt[0]),int(flag_pt[1])), 4 + tier)


def draw_ship(surface, x, y, size, angle_rad, hull_color, accent_color,
              shield_active=False, shield_anim=0, is_player=False,
              wave_num=1, is_boss=False):
    """Unified entry point kept for backward compat."""
    if is_player:
        draw_player_ship(surface, x, y, angle_rad, shield_active, shield_anim)
    elif is_boss:
        # Boss: giant man-o-war always tier 2
        draw_enemy_ship(surface, x, y, size, angle_rad, hull_color, wave_num=9)
    else:
        draw_enemy_ship(surface, x, y, size, angle_rad, hull_color, wave_num=wave_num)

# ===================== DRAW OCEAN BACKGROUND =====================
# ===================== OCEAN BACKGROUND (Sea_BG.png tile) =====================
_SEA_TILE     = None
_SEA_TILE_DIM = None

def _get_sea_tile():
    global _SEA_TILE, _SEA_TILE_DIM
    if _SEA_TILE is not None:
        return _SEA_TILE_DIM
    # Search order: same folder as script → uploads folder → fallback
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Sea_BG.png'),
        '/mnt/user-data/uploads/Sea_BG.png',
        'Sea_BG.png',
    ]
    raw = None
    for path in candidates:
        if os.path.exists(path):
            try:
                raw = pygame.image.load(path).convert()
                print(f"✅ Sea_BG.png loaded from: {path}")
                break
            except Exception as e:
                print(f"⚠ Could not load {path}: {e}")
    if raw is None:
        print("⚠ Sea_BG.png not found — using solid colour fallback")
        raw = pygame.Surface((64, 64))
        raw.fill(OCEAN_BLUE)
    # Scale to 256×256 for smooth tiling
    tile = pygame.transform.scale(raw, (256, 256))
    # Dim to ~60% brightness
    dim = pygame.Surface((256, 256), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 100))
    tile.blit(dim, (0, 0))
    _SEA_TILE = _SEA_TILE_DIM = tile
    return _SEA_TILE_DIM

# ── Wake / foam trail system ──────────────────────────────────────────────────
class WakeParticle:
    """A single foam bubble left behind a moving ship."""
    def __init__(self, x, y, spread=18):
        self.x = x + random.uniform(-spread, spread)
        self.y = y + random.uniform(-spread, spread)
        self.life     = random.uniform(0.5, 1.1)
        self.max_life = self.life
        self.r        = random.uniform(3, 8)
        self.dx       = random.uniform(-12, 12)
        self.dy       = random.uniform(-12, 12)

    def update(self, dt):
        self.x    += self.dx * dt
        self.y    += self.dy * dt
        self.dx   *= 0.92
        self.dy   *= 0.92
        self.life -= dt
        return self.life > 0

    def draw(self, surface, cam_x, cam_y):
        alpha = max(0, int(210 * (self.life / self.max_life)))
        r     = max(1, int(self.r * (self.life / self.max_life)))
        sx    = int(self.x - cam_x)
        sy    = int(self.y - cam_y)
        if -10 < sx < WIDTH + 10 and -10 < sy < HEIGHT + 10:
            ws = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(ws, (255, 255, 255, alpha), (r+1, r+1), r)
            surface.blit(ws, (sx - r - 1, sy - r - 1))

_wake_particles = []
_wake_timer     = 0.0
_WAKE_INTERVAL  = 0.055   # seconds between wake spawns

def spawn_wake(x, y, dx, dy, spread=16):
    """Call each frame a ship is moving; spawns foam behind it."""
    global _wake_timer
    # Only spawn if actually moving
    if math.hypot(dx, dy) < 5:
        return
    _wake_particles.append(WakeParticle(x, y, spread))

def update_draw_wakes(surface, cam_x, cam_y, dt):
    global _wake_particles
    _wake_particles = [w for w in _wake_particles if w.update(dt)]
    for w in _wake_particles:
        w.draw(surface, cam_x, cam_y)

def draw_ocean(surface, camera_x, camera_y, game_time):
    tile = _get_sea_tile()
    TW, TH = tile.get_size()
    ox = int(camera_x * 0.35 + game_time * 18) % TW
    oy = int(camera_y * 0.35 + game_time * 10) % TH
    for ty in range(-TH, HEIGHT + TH, TH):
        for tx in range(-TW, WIDTH + TW, TW):
            surface.blit(tile, (tx - ox, ty - oy))
    # Subtle animated shimmer lines
    for i in range(0, HEIGHT + 40, 38):
        y = i - int(camera_y * 0.08) % 38
        wave_offset = math.sin(game_time * 1.1 + i * 0.07) * 5
        sh = pygame.Surface((WIDTH, 2), pygame.SRCALPHA)
        sh.fill((255, 255, 255, 20))
        surface.blit(sh, (0, int(y + wave_offset)))

# ===================== DRAW ISLAND =====================
def draw_island(surface, ix, iy, size, has_treasure, game_time):
    # Sand base
    pygame.draw.circle(surface, ISLAND_SAND, (int(ix), int(iy)), size)
    # Green top
    pygame.draw.circle(surface, ISLAND_GREEN, (int(ix), int(iy) - size//5), int(size * 0.75))
    # Palm tree
    pygame.draw.line(surface, DARK_WOOD, (int(ix), int(iy) - size//5),
                     (int(ix), int(iy) - size - 15), 3)
    leaf_tip = size * 0.6
    for angle in range(0, 360, 90):
        rad = math.radians(angle + game_time * 15)
        ex = ix + math.cos(rad) * leaf_tip
        ey = (iy - size - 15) + math.sin(rad) * 10
        pygame.draw.line(surface, ISLAND_GREEN,
                         (int(ix), int(iy - size - 15)),
                         (int(ex), int(ey)), 4)
    # Treasure glow
    if has_treasure:
        pulse = (math.sin(game_time * 4) + 1) / 2
        r = int(10 + pulse * 6)
        glow = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
        glow_a = int(180 + pulse * 75)
        pygame.draw.circle(glow, (*TREASURE, glow_a), (r+1, r+1), r)
        surface.blit(glow, (int(ix) - r - 1, int(iy) - r - 1))

# ===================== MINIMAP =====================
def draw_minimap(surface, player_x, player_y, enemies, islands, world_w, world_h):
    MAP_W, MAP_H = 120, 90
    MAP_X = WIDTH - MAP_W - 10
    MAP_Y = HEIGHT - MAP_H - 10
    scale_x = MAP_W / world_w
    scale_y = MAP_H / world_h

    # Background
    map_surf = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
    map_surf.fill((10, 30, 80, 180))

    # Islands
    for isl in islands:
        mx = int(isl["x"] * scale_x)
        my = int(isl["y"] * scale_y)
        pygame.draw.circle(map_surf, ISLAND_GREEN, (mx, my), max(2, int(isl["size"] * scale_x)))

    # Enemies
    for e in enemies:
        mx = int(e["x"] * scale_x)
        my = int(e["y"] * scale_y)
        col = BOSS_COLOR if e.get("is_boss") else RED
        pygame.draw.circle(map_surf, col, (mx, my), 2)

    # Player
    px = int(player_x * scale_x)
    py = int(player_y * scale_y)
    pygame.draw.circle(map_surf, GOLD, (px, py), 3)

    surface.blit(map_surf, (MAP_X, MAP_Y))
    pygame.draw.rect(surface, GOLD, (MAP_X, MAP_Y, MAP_W, MAP_H), 1)
    label = micro_font.render("MAP", True, GOLD)
    surface.blit(label, (MAP_X + 2, MAP_Y + 2))

# ===================== DRAW HEALTH BAR =====================
def draw_health_bar(surface, x, y, w, h, current, maximum, fg_color=GREEN, bg_color=DARK_RED, border=WHITE):
    ratio = max(0, current / maximum)
    pygame.draw.rect(surface, bg_color, (x, y, w, h), border_radius=4)
    if ratio > 0:
        pygame.draw.rect(surface, fg_color, (x, y, int(w * ratio), h), border_radius=4)
    pygame.draw.rect(surface, border, (x, y, w, h), 2, border_radius=4)

# ===================== DRAW XP BAR =====================
def draw_xp_bar(surface, x, y, w, h, current, maximum):
    ratio = max(0, min(1, current / maximum))
    pygame.draw.rect(surface, (30, 0, 60), (x, y, w, h), border_radius=3)
    if ratio > 0:
        pygame.draw.rect(surface, PURPLE, (x, y, int(w * ratio), h), border_radius=3)
    pygame.draw.rect(surface, (200, 150, 255), (x, y, w, h), 1, border_radius=3)

# ===================== POWERUP =====================
POWERUP_TYPES = [
    {"name": "SHIELD",    "color": SHIELD_COLOR, "icon": "S"},
    {"name": "RAPID FIRE","color": ORANGE,        "icon": "R"},
    {"name": "SPEED",     "color": CYAN,          "icon": "V"},
    {"name": "HEALTH",    "color": GREEN,          "icon": "+"},
]

def draw_powerup(surface, pu, game_time, cam_x, cam_y):
    sx = pu["x"] - cam_x
    sy = pu["y"] - cam_y
    if not (-30 < sx < WIDTH+30 and -30 < sy < HEIGHT+30):
        return
    pulse = (math.sin(game_time * 5) + 1) / 2
    r = int(14 + pulse * 4)
    col = pu["color"]
    pygame.draw.circle(surface, col, (int(sx), int(sy)), r)
    pygame.draw.circle(surface, WHITE, (int(sx), int(sy)), r, 2)
    txt = micro_font.render(pu["icon"], True, BLACK)
    surface.blit(txt, (int(sx) - txt.get_width()//2, int(sy) - txt.get_height()//2))

# ===================== WAVE ANNOUNCEMENT =====================
def draw_wave_announcement(surface, text, alpha):
    surf = title_font.render(text, True, GOLD)
    surf.set_alpha(alpha)
    x = WIDTH//2 - surf.get_width()//2
    y = HEIGHT//3
    shadow = title_font.render(text, True, BLACK)
    shadow.set_alpha(alpha)
    surface.blit(shadow, (x+3, y+3))
    surface.blit(surf, (x, y))


# ===================== ISLAND PLATFORMER MODE =====================
def island_platformer(island, player_gold, player_health, player_max_hp,
                      player_level, player_xp, xp_to_next):
    """
    Top-down island exploration mode.
    WASD = move, Left Click = sword swing toward mouse, E/ESC = leave.
    Returns updated (gold, health, xp, xp_to_next, level).
    """
    clock2 = pygame.time.Clock()

    # ── Island world size ─────────────────────────────────────────────────────
    IW, IH = 900, 900

    # ── Colours ───────────────────────────────────────────────────────────────
    SAND_COL    = (210, 185, 100)
    SAND_DARK   = (185, 160,  80)
    GRASS_COL   = ( 55, 145,  45)
    GRASS_DARK  = ( 35, 110,  30)
    TREE_TRUNK  = ( 90,  55,  10)
    TREE_LEAF   = ( 20, 140,  30)
    TREE_LEAF2  = ( 30, 170,  40)
    ROCK_COL    = (130, 120, 110)
    ROCK_DARK   = ( 90,  85,  78)
    WATER_COL   = ( 30, 100, 200)
    WATER_FOAM  = (120, 180, 255)
    CHEST_COL   = (140,  85,  15)
    CHEST_TRIM  = (210, 170,  50)
    GUARD_COL   = (170,  25,  25)
    GUARD_HIT   = (255, 160, 160)
    PLAYER_COL  = ( 30,  70, 190)
    PLAYER_SKIN = (255, 215, 170)
    EXIT_COL    = (220,  40,  40)

    # ── Randomised island layout (seeded by island position) ─────────────────
    seed = int(island["x"] * 7 + island["y"] * 13)
    rng  = random.Random(seed)

    # Island boundary (circle)
    isle_cx, isle_cy = IW // 2, IH // 2
    isle_r  = min(IW, IH) // 2 - 40   # playable radius

    # Trees (avoid centre spawn)
    trees = []
    for _ in range(18):
        ang = rng.uniform(0, 2*math.pi)
        r2  = rng.uniform(isle_r * 0.25, isle_r * 0.88)
        trees.append({
            "x": isle_cx + math.cos(ang)*r2,
            "y": isle_cy + math.sin(ang)*r2,
            "r": rng.randint(16, 26),
        })

    # Rocks
    rocks = []
    for _ in range(10):
        ang = rng.uniform(0, 2*math.pi)
        r2  = rng.uniform(isle_r * 0.2, isle_r * 0.85)
        rocks.append({
            "x": isle_cx + math.cos(ang)*r2,
            "y": isle_cy + math.sin(ang)*r2,
            "w": rng.randint(18, 32),
            "h": rng.randint(14, 24),
        })

    # ── Chests ────────────────────────────────────────────────────────────────
    chests = []
    chest_spots = []
    for _ in range(6):
        ang = rng.uniform(0, 2*math.pi)
        r2  = rng.uniform(isle_r * 0.15, isle_r * 0.75)
        chest_spots.append((isle_cx + math.cos(ang)*r2,
                            isle_cy + math.sin(ang)*r2))

    if island.get("has_treasure", False):
        for cx2, cy2 in chest_spots:
            if rng.random() < 0.55:
                chests.append({"x": float(cx2), "y": float(cy2),
                               "r": 16, "collected": False})
    if island.get("has_treasure", False) and not chests:
        chests.append({"x": float(isle_cx + 80), "y": float(isle_cy),
                       "r": 16, "collected": False})

    # ── Exit dock (south edge) ────────────────────────────────────────────────
    exit_x = float(isle_cx)
    exit_y = float(isle_cy + isle_r + 10)

    # ── Guards ────────────────────────────────────────────────────────────────
    guards = []
    for _ in range(random.randint(3, 5 + player_level)):
        ang  = rng.uniform(0, 2*math.pi)
        r2   = rng.uniform(isle_r * 0.2, isle_r * 0.75)
        gx   = isle_cx + math.cos(ang)*r2
        gy   = isle_cy + math.sin(ang)*r2
        guards.append({
            "x": float(gx), "y": float(gy),
            "angle": rng.uniform(0, 2*math.pi),
            "speed": 55 + player_level * 6,
            "hp": 40 + player_level * 8,
            "max_hp": 40 + player_level * 8,
            "r": 14,
            "atk_timer": 0.0,
            "hit_flash": 0.0,
            "dead": False,
            "state": "patrol",
            "patrol_angle": rng.uniform(0, 2*math.pi),
            "patrol_timer": rng.uniform(1.0, 3.0),
        })

    # ── Player state ──────────────────────────────────────────────────────────
    px      = float(isle_cx)
    py      = float(isle_cy + 60)
    p_angle = 0.0          # direction player faces (radians)
    P_R     = 14           # collision radius
    SPEED   = 160.0

    sword_timer = 0.0
    sword_cd    = 0.0
    i_frames    = 0.0
    p_hp        = player_health
    p_max_hp    = player_max_hp
    gold_gained = 0
    xp_gained   = 0

    cam_x, cam_y = 0.0, 0.0

    i_particles = []
    i_texts     = []
    all_treasures_timer = 0.0

    # ── Obstacle collision helper ─────────────────────────────────────────────
    def push_out_circles(cx2, cy2, cr, ex2, ey2, er):
        """Push entity at (ex,ey) with radius er out of circle obstacle (cx,cy,cr)."""
        dx = ex2 - cx2; dy = ey2 - cy2
        dist = math.hypot(dx, dy)
        overlap = cr + er - dist
        if overlap > 0 and dist > 0:
            return ex2 + dx/dist*overlap, ey2 + dy/dist*overlap
        return ex2, ey2

    def push_out_rect(rx, ry, rw, rh, ex2, ey2, er):
        """Push circle (ex,ey,er) out of AABB rect."""
        cx2 = max(rx, min(rx+rw, ex2))
        cy2 = max(ry, min(ry+rh, ey2))
        dx = ex2-cx2; dy = ey2-cy2
        dist = math.hypot(dx, dy)
        if dist < er and dist > 0:
            overlap = er - dist
            return ex2 + dx/dist*overlap, ey2 + dy/dist*overlap
        elif dist == 0:
            return ex2, ey2 + er
        return ex2, ey2

    def keep_on_island(ex2, ey2, er):
        dx = ex2-isle_cx; dy = ey2-isle_cy
        d  = math.hypot(dx, dy)
        limit = isle_r - er
        if d > limit and d > 0:
            return isle_cx + dx/d*limit, isle_cy + dy/d*limit
        return ex2, ey2

    # ── Drawing ───────────────────────────────────────────────────────────────
    def draw_top_down(surf, gt):
        # Sea_BG tiled background (same as main game ocean)
        tile = _get_sea_tile()
        TW, TH = tile.get_size()
        ox = int(cam_x * 0.4 + gt * 16) % TW
        oy = int(cam_y * 0.4 + gt * 10) % TH
        for ty in range(-TH, HEIGHT + TH, TH):
            for tx in range(-TW, WIDTH + TW, TW):
                surf.blit(tile, (tx - ox, ty - oy))
        # Subtle shimmer lines on top
        for i in range(0, HEIGHT + 40, 36):
            y2 = i - int(cam_y * 0.06) % 36
            wave_offset = math.sin(gt * 1.1 + i * 0.07) * 5
            sh = pygame.Surface((WIDTH, 2), pygame.SRCALPHA)
            sh.fill((255, 255, 255, 18))
            surf.blit(sh, (0, int(y2 + wave_offset)))

        # Island ground (sand + grass)
        pygame.draw.circle(surf, SAND_COL,
                           (int(isle_cx-cam_x), int(isle_cy-cam_y)), isle_r)
        pygame.draw.circle(surf, GRASS_COL,
                           (int(isle_cx-cam_x), int(isle_cy-cam_y)), int(isle_r*0.75))

        # Grass texture patches
        grng = random.Random(seed+1)
        for _ in range(40):
            gx2 = isle_cx + grng.uniform(-isle_r*0.7, isle_r*0.7)
            gy2 = isle_cy + grng.uniform(-isle_r*0.7, isle_r*0.7)
            if math.hypot(gx2-isle_cx, gy2-isle_cy) < isle_r*0.72:
                pygame.draw.circle(surf, GRASS_DARK,
                                   (int(gx2-cam_x), int(gy2-cam_y)),
                                   grng.randint(8,18))

        # Island border (sand ring)
        pygame.draw.circle(surf, SAND_DARK,
                           (int(isle_cx-cam_x), int(isle_cy-cam_y)), isle_r, 18)

        # Rocks
        for rock in rocks:
            rx2 = int(rock["x"]-cam_x); ry2 = int(rock["y"]-cam_y)
            pygame.draw.ellipse(surf, ROCK_DARK,
                                (rx2-rock["w"]//2+2, ry2-rock["h"]//2+3,
                                 rock["w"], rock["h"]))
            pygame.draw.ellipse(surf, ROCK_COL,
                                (rx2-rock["w"]//2, ry2-rock["h"]//2,
                                 rock["w"], rock["h"]))

        # Trees (shadow then trunk then canopy)
        for tree in trees:
            tx2 = int(tree["x"]-cam_x); ty2 = int(tree["y"]-cam_y)
            # Shadow
            sh_s = pygame.Surface((tree["r"]*2+8, tree["r"]*2+8), pygame.SRCALPHA)
            pygame.draw.circle(sh_s, (0,0,0,50), (tree["r"]+4+6, tree["r"]+4+6), tree["r"]+4)
            surf.blit(sh_s, (tx2-tree["r"]-4+4, ty2-tree["r"]-4+6))
            # Trunk
            pygame.draw.circle(surf, TREE_TRUNK, (tx2, ty2), tree["r"]//3+2)
            # Canopy layers
            pygame.draw.circle(surf, TREE_LEAF,  (tx2, ty2), tree["r"])
            pygame.draw.circle(surf, TREE_LEAF2, (tx2, ty2-tree["r"]//4), int(tree["r"]*0.65))
            # Highlight
            pygame.draw.circle(surf, (80,200,80),
                               (tx2-tree["r"]//4, ty2-tree["r"]//3), tree["r"]//4)

        # Exit dock
        ex2 = int(exit_x - cam_x); ey2 = int(exit_y - cam_y)
        pygame.draw.rect(surf, (160,120,60), (ex2-20, ey2-10, 40, 28), border_radius=4)
        pygame.draw.rect(surf, GOLD,         (ex2-20, ey2-10, 40, 28), 2, border_radius=4)
        lbl = micro_font.render("EXIT", True, BLACK)
        surf.blit(lbl, lbl.get_rect(centerx=ex2, centery=ey2+4))

        # Chests
        for ch in chests:
            cx2 = int(ch["x"]-cam_x); cy2_s = int(ch["y"]-cam_y)
            if ch["collected"]:
                pygame.draw.rect(surf, (100,70,10),
                                 (cx2-ch["r"], cy2_s-ch["r"]//2,
                                  ch["r"]*2, ch["r"]), border_radius=3)
                pygame.draw.rect(surf, GOLD,
                                 (cx2-ch["r"], cy2_s-ch["r"]//2,
                                  ch["r"]*2, ch["r"]), 1, border_radius=3)
            else:
                # Chest body (no glow)
                pygame.draw.rect(surf, CHEST_COL,
                                 (cx2-ch["r"], cy2_s-ch["r"]//2,
                                  ch["r"]*2, ch["r"]), border_radius=4)
                pygame.draw.rect(surf, CHEST_TRIM,
                                 (cx2-ch["r"], cy2_s-ch["r"]//2,
                                  ch["r"]*2, ch["r"]), 2, border_radius=4)
                # Latch
                pygame.draw.circle(surf, GOLD, (cx2, cy2_s), 4)

        # Guards
        for g in guards:
            if g["dead"]: continue
            gcol = GUARD_HIT if g["hit_flash"] > 0 else GUARD_COL
            gx2  = int(g["x"]-cam_x); gy2 = int(g["y"]-cam_y)
            # Shadow
            pygame.draw.circle(surf, (0,0,0,50), (gx2+3, gy2+4), g["r"])
            # Body
            pygame.draw.circle(surf, gcol, (gx2, gy2), g["r"])
            pygame.draw.circle(surf, tuple(max(0,c-40) for c in gcol),
                               (gx2, gy2), g["r"], 2)
            # Direction indicator (facing dot)
            nx = gx2 + int(math.sin(g["angle"]) * (g["r"]-4))
            ny = gy2 - int(math.cos(g["angle"]) * (g["r"]-4))
            pygame.draw.circle(surf, BLACK, (nx, ny), 4)
            # Sword arm
            sx2 = gx2 + int(math.sin(g["angle"]) * (g["r"]+14))
            sy2 = gy2 - int(math.cos(g["angle"]) * (g["r"]+14))
            pygame.draw.line(surf, (180,180,200), (gx2, gy2), (sx2, sy2), 3)
            pygame.draw.circle(surf, (220,220,240), (sx2, sy2), 4)
            # HP bar
            bw = g["r"]*2+8
            pygame.draw.rect(surf, DARK_RED, (gx2-bw//2, gy2-g["r"]-10, bw, 5))
            pygame.draw.rect(surf, GREEN,
                             (gx2-bw//2, gy2-g["r"]-10,
                              int(bw*g["hp"]/g["max_hp"]), 5))

        # Player
        psx = int(px-cam_x); psy = int(py-cam_y)
        # Shadow
        shp = pygame.Surface((P_R*2+8, P_R*2+8), pygame.SRCALPHA)
        pygame.draw.circle(shp, (0,0,0,55), (P_R+4+3, P_R+4+4), P_R+3)
        surf.blit(shp, (psx-P_R-4+1, psy-P_R-4+2))
        # Body
        pygame.draw.circle(surf, PLAYER_COL, (psx, psy), P_R)
        pygame.draw.circle(surf, (60,100,220), (psx, psy), P_R, 2)
        # Head / facing dot
        hx = psx + int(math.sin(p_angle) * (P_R-4))
        hy = psy - int(math.cos(p_angle) * (P_R-4))
        pygame.draw.circle(surf, PLAYER_SKIN, (hx, hy), 6)
        # Pirate hat dot
        pygame.draw.circle(surf, DARK_WOOD, (hx, hy), 4)
        # Sword swing arc
        if sword_timer > 0:
            prog = 1 - sword_timer/0.25
            sweep = math.pi * 0.9 * prog
            base_ang = p_angle - math.pi*0.45
            pts = [(psx, psy)]
            for step in range(12):
                a2 = base_ang + sweep*(step/11)
                pts.append((psx + int(math.sin(a2)*36),
                             psy - int(math.cos(a2)*36)))
            if len(pts) >= 3:
                pygame.draw.polygon(surf, (220,220,255,80), pts)
            # Blade line
            blade_ang = base_ang + sweep
            bx2 = psx + int(math.sin(blade_ang)*40)
            by2 = psy - int(math.cos(blade_ang)*40)
            pygame.draw.line(surf, WHITE, (psx, psy), (bx2, by2), 4)
            pygame.draw.circle(surf, GOLD, (bx2, by2), 5)

        # i-frames flash
        if i_frames > 0 and int(i_frames*12)%2 == 0:
            fl = pygame.Surface((P_R*2+4, P_R*2+4), pygame.SRCALPHA)
            pygame.draw.circle(fl, (255,255,255,140), (P_R+2, P_R+2), P_R+1)
            surf.blit(fl, (psx-P_R-2, psy-P_R-2))

        # Particles & floating texts
        for part in i_particles:
            part.draw(surf, cam_x, cam_y)
        for txt in i_texts:
            txt.draw(surf, cam_x, cam_y)

        # HUD
        draw_health_bar(surf, 10, 10, 200, 18, p_hp, p_max_hp)
        surf.blit(tiny_font.render(f"HP {int(p_hp)}/{int(p_max_hp)}", True, WHITE), (10, 32))
        surf.blit(tiny_font.render(f"GOLD +{gold_gained}", True, GOLD), (10, 52))

        chests_left = sum(1 for c in chests if not c["collected"])
        if chests:
            surf.blit(tiny_font.render(f"CHESTS: {chests_left} left", True, LIGHT_GOLD), (10, 72))

        ctrl = micro_font.render("WASD=Move  CLICK=Sword  E=Leave island", True, (220,220,220))
        surf.blit(ctrl, ctrl.get_rect(centerx=WIDTH//2, bottom=HEIGHT-6))
        title2 = small_font.render("⚓  ON THE ISLAND  ⚓", True, GOLD)
        surf.blit(title2, title2.get_rect(centerx=WIDTH//2, top=8))

    # ── MAIN LOOP ─────────────────────────────────────────────────────────────
    running2   = True
    game_t     = 0.0
    all_treasures_timer = 0.0

    while running2:
        dt2 = clock2.tick(60) / 1000.0
        game_t += dt2
        keys = pygame.key.get_pressed()

        # ── Input ─────────────────────────────────────────────────────────────
        dx2, dy2 = 0.0, 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy2 -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy2 += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx2 -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx2 += 1
        if dx2 != 0 and dy2 != 0:
            dx2 *= 0.7071; dy2 *= 0.7071

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return player_gold, p_hp, player_xp, xp_to_next, player_level
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_e or event.key == pygame.K_ESCAPE:
                    running2 = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and sword_cd <= 0:
                    sword_timer = 0.25
                    sword_cd    = 0.40

        # ── Face toward mouse ─────────────────────────────────────────────────
        mx, my = pygame.mouse.get_pos()
        p_angle = math.atan2(mx - (px - cam_x), -(my - (py - cam_y)))

        # ── Move player ───────────────────────────────────────────────────────
        sword_timer = max(0, sword_timer - dt2)
        sword_cd    = max(0, sword_cd    - dt2)
        i_frames    = max(0, i_frames    - dt2)

        px += dx2 * SPEED * dt2
        py += dy2 * SPEED * dt2

        # Push out of trees & rocks
        for tree in trees:
            px, py = push_out_circles(tree["x"], tree["y"], tree["r"]+4, px, py, P_R)
        for rock in rocks:
            px, py = push_out_rect(rock["x"]-rock["w"]//2, rock["y"]-rock["h"]//2,
                                   rock["w"], rock["h"], px, py, P_R)

        # Stay on island
        px, py = keep_on_island(px, py, P_R)

        # Camera centres on player, clamped to world
        cam_x = max(0, min(IW - WIDTH,  px - WIDTH  // 2))
        cam_y = max(0, min(IH - HEIGHT, py - HEIGHT // 2))

        # ── Exit check ────────────────────────────────────────────────────────
        if math.hypot(px - exit_x, py - exit_y) < 30:
            running2 = False

        # ── Chest collection ──────────────────────────────────────────────────
        for ch in chests:
            if ch["collected"]: continue
            if math.hypot(px - ch["x"], py - ch["y"]) < P_R + ch["r"]:
                ch["collected"] = True
                gain = 60 + player_level * 15
                gold_gained += gain
                i_particles += [Particle(ch["x"], ch["y"], GOLD,
                                         speed=80, life=0.7, size=4)
                                 for _ in range(14)]
                i_texts.append(FloatingText(ch["x"], ch["y"]-10, f"+{gain}G", GOLD))
                play_sound(powerup_sound)
                if chests and all(c["collected"] for c in chests):
                    all_treasures_timer = 3.5

        # ── Sword hits guards ─────────────────────────────────────────────────
        if sword_timer > 0:
            base_ang  = p_angle - math.pi*0.45
            sweep_ang = math.pi * 0.9 * (1 - sword_timer/0.25)
            hit_ang   = base_ang + sweep_ang
            # Sword tip
            stx = px + math.sin(hit_ang) * 40
            sty = py - math.cos(hit_ang) * 40
            for g in guards:
                if g["dead"]: continue
                if math.hypot(stx - g["x"], sty - g["y"]) < g["r"] + 10:
                    dmg = 20 + player_level * 5
                    g["hp"] -= dmg
                    g["hit_flash"] = 0.15
                    i_particles += [Particle(g["x"], g["y"], RED,
                                             speed=80, life=0.35)
                                    for _ in range(6)]
                    i_texts.append(FloatingText(g["x"], g["y"]-14,
                                                f"-{dmg}", ORANGE, 'tiny'))
                    if g["hp"] <= 0:
                        g["dead"] = True
                        xp_gain = 15 + player_level * 4
                        xp_gained   += xp_gain
                        gold_gained += random.randint(10, 25)
                        i_particles += [Particle(g["x"], g["y"], GOLD,
                                                 speed=110, life=0.6)
                                        for _ in range(10)]
                        play_sound(explosion_sound)

        # ── Guard AI ──────────────────────────────────────────────────────────
        for g in guards:
            if g["dead"]: continue
            g["hit_flash"]  = max(0, g["hit_flash"]  - dt2)
            g["atk_timer"]  = max(0, g["atk_timer"]  - dt2)
            g["patrol_timer"] = max(0, g["patrol_timer"] - dt2)

            dist_p = math.hypot(px - g["x"], py - g["y"])
            if dist_p < 180:
                g["state"] = "chase"
            elif dist_p > 240:
                g["state"] = "patrol"

            if g["state"] == "chase":
                ang = math.atan2(px - g["x"], -(py - g["y"]))
                g["angle"] = ang
                g["x"] += math.sin(ang) * g["speed"] * dt2
                g["y"] -= math.cos(ang) * g["speed"] * dt2
            else:
                # Patrol: wander with direction changes
                if g["patrol_timer"] <= 0:
                    g["patrol_angle"] = rng.uniform(0, 2*math.pi)
                    g["patrol_timer"] = rng.uniform(1.2, 2.8)
                g["angle"] = g["patrol_angle"]
                g["x"] += math.sin(g["patrol_angle"]) * 40 * dt2
                g["y"] -= math.cos(g["patrol_angle"]) * 40 * dt2

            # Push guards out of trees/rocks/island edge
            for tree in trees:
                g["x"], g["y"] = push_out_circles(
                    tree["x"], tree["y"], tree["r"]+2,
                    g["x"], g["y"], g["r"])
            g["x"], g["y"] = keep_on_island(g["x"], g["y"], g["r"])

            # Attack player on contact
            if dist_p < P_R + g["r"] + 4 and g["atk_timer"] <= 0 and i_frames <= 0:
                dmg = 8 + player_level
                p_hp -= dmg
                i_frames = 0.8
                g["atk_timer"] = 1.0
                i_texts.append(FloatingText(px, py-20, f"-{dmg} HP", RED))
                i_particles += [Particle(px, py, RED, speed=60, life=0.3)
                                 for _ in range(5)]
                p_hp = max(1, p_hp)

        # ── Update particles / texts ───────────────────────────────────────────
        i_particles = [p for p in i_particles if p.update(dt2)]
        i_texts     = [t for t in i_texts     if t.update(dt2)]
        all_treasures_timer = max(0, all_treasures_timer - dt2)

        # ── Draw ──────────────────────────────────────────────────────────────
        draw_top_down(screen, game_t)

        # ── ALL TREASURES popup ───────────────────────────────────────────────
        if all_treasures_timer > 0:
            fade = min(1.0, all_treasures_timer / 0.4)
            if all_treasures_timer < 0.6:
                fade = all_treasures_timer / 0.6
            alpha = int(fade * 255)
            panel = pygame.Surface((520, 110), pygame.SRCALPHA)
            panel.fill((0, 0, 0, int(alpha * 0.75)))
            screen.blit(panel, (WIDTH//2 - 260, HEIGHT//2 - 55))
            border_s = pygame.Surface((524, 114), pygame.SRCALPHA)
            pygame.draw.rect(border_s, (*GOLD, alpha), (0,0,524,114), 3, border_radius=10)
            screen.blit(border_s, (WIDTH//2 - 262, HEIGHT//2 - 57))
            line1    = small_font.render("ALL TREASURES COLLECTED!", True, GOLD)
            line1_sh = small_font.render("ALL TREASURES COLLECTED!", True, BLACK)
            line1.set_alpha(alpha); line1_sh.set_alpha(alpha)
            screen.blit(line1_sh, line1_sh.get_rect(centerx=WIDTH//2+2, centery=HEIGHT//2-14+2))
            screen.blit(line1,    line1.get_rect(   centerx=WIDTH//2,   centery=HEIGHT//2-14))
            line2 = tiny_font.render(f"You looted +{gold_gained} GOLD from this island!", True, LIGHT_GOLD)
            line2.set_alpha(alpha)
            screen.blit(line2, line2.get_rect(centerx=WIDTH//2, centery=HEIGHT//2+22))
            for si in range(8):
                ang2 = game_t*3 + si*(math.pi/4)
                sp_s = pygame.Surface((10,10), pygame.SRCALPHA)
                pygame.draw.circle(sp_s, (*GOLD, alpha), (5,5), 5)
                screen.blit(sp_s, (WIDTH//2 + int(math.cos(ang2)*230) - 5,
                                   HEIGHT//2 + int(math.sin(ang2)*44) - 5))

        pygame.display.flip()

    # ── Return results ────────────────────────────────────────────────────────
    if gold_gained > 0:
        island["has_treasure"] = False

    player_xp += xp_gained
    while player_xp >= xp_to_next:
        player_xp    -= xp_to_next
        player_level  += 1
        xp_to_next    = int(xp_to_next * 1.4)
        player_max_hp += 20
        p_hp = min(p_hp + 25, player_max_hp)

    return player_gold + gold_gained, p_hp, player_xp, xp_to_next, player_level


# ===================== OPTIONS MENU =====================
def options_menu():
    global music_volume, sfx_volume, music_on, sfx_on
    slider_w, slider_h = 200, 12
    music_slider = pygame.Rect(WIDTH//2 - slider_w//2, 200, slider_w, slider_h)
    sfx_slider   = pygame.Rect(WIDTH//2 - slider_w//2, 280, slider_w, slider_h)
    back_btn     = pygame.Rect(WIDTH//2 - 100, 420, 200, 50)
    dragging_music = dragging_sfx = False
    start_time = pygame.time.get_ticks() / 1000
    running = True
    while running:
        current_time = pygame.time.get_ticks() / 1000 - start_time
        screen.fill((20, 80, 180))
        if background:
            screen.blit(pygame.transform.scale(background, (WIDTH, HEIGHT)), (0, 0))
        title_surf = title_font.render("OPTIONS", True, GOLD)
        title_rect = title_surf.get_rect(center=(WIDTH//2, 120))
        title_bg = title_rect.inflate(40, 20)
        draw_animated_title_border(screen, title_bg, current_time)
        screen.blit(title_font.render("OPTIONS", True, SHADOW), title_rect.move(3, 3))
        screen.blit(title_surf, title_rect)
        music_text = small_font.render(f"MUSIC: {'ON' if music_on else 'OFF'}", True, WHITE)
        screen.blit(music_text, music_text.get_rect(center=(WIDTH//2, 170)))
        pygame.draw.rect(screen, GRAY, music_slider, border_radius=6)
        pygame.draw.rect(screen, GREEN if music_on else RED,
                         pygame.Rect(music_slider.x, music_slider.y, int(music_slider.w * music_volume), music_slider.h),
                         border_radius=6)
        pygame.draw.rect(screen, WHITE, music_slider, 2, border_radius=6)
        sfx_text = small_font.render(f"SFX: {'ON' if sfx_on else 'OFF'}", True, WHITE)
        screen.blit(sfx_text, sfx_text.get_rect(center=(WIDTH//2, 250)))
        pygame.draw.rect(screen, GRAY, sfx_slider, border_radius=6)
        pygame.draw.rect(screen, GREEN if sfx_on else RED,
                         pygame.Rect(sfx_slider.x, sfx_slider.y, int(sfx_slider.w * sfx_volume), sfx_slider.h),
                         border_radius=6)
        pygame.draw.rect(screen, WHITE, sfx_slider, 2, border_radius=6)
        pygame.draw.rect(screen, DARK_WOOD, back_btn, border_radius=8)
        pygame.draw.rect(screen, LIGHT_GOLD, back_btn.inflate(-4, -4), border_radius=8)
        screen.blit(button_font.render("BACK", True, DARK_WOOD),
                    button_font.render("BACK", True, DARK_WOOD).get_rect(center=back_btn.center))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type == pygame.MOUSEBUTTONDOWN:
                play_sound(click_sound)
                pos = pygame.mouse.get_pos()
                if music_slider.collidepoint(pos): dragging_music = True
                elif sfx_slider.collidepoint(pos): dragging_sfx = True
                elif back_btn.collidepoint(pos): running = False
                elif music_text.get_rect(center=(WIDTH//2, 170)).collidepoint(pos):
                    music_toggle()
                elif sfx_text.get_rect(center=(WIDTH//2, 250)).collidepoint(pos):
                    sfx_on = not sfx_on
            if event.type == pygame.MOUSEBUTTONUP:
                dragging_music = dragging_sfx = False
            if event.type == pygame.MOUSEMOTION:
                if dragging_music:
                    music_set_volume(max(0.0, min(1.0, (event.pos[0] - music_slider.x) / music_slider.w)))
                if dragging_sfx:
                    sfx_volume = max(0.0, min(1.0, (event.pos[0] - sfx_slider.x) / sfx_slider.w))
        pygame.display.update()

# ===================== PAUSE MENU =====================
def pause_menu():
    buttons = [MenuButton("RESUME", 200), MenuButton("SETTINGS", 280), MenuButton("QUIT TO MENU", 360)]
    start_time = pygame.time.get_ticks() / 1000
    running = True
    while running:
        current_time = pygame.time.get_ticks() / 1000 - start_time
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        title_surf = title_font.render("PAUSED", True, GOLD)
        title_rect = title_surf.get_rect(center=(WIDTH//2, 120))
        draw_animated_title_border(screen, title_rect.inflate(40, 20), current_time)
        screen.blit(title_font.render("PAUSED", True, SHADOW), title_rect.move(3, 3))
        screen.blit(title_surf, title_rect)
        mouse_pos = pygame.mouse.get_pos()
        for btn in buttons:
            btn.check_hover(mouse_pos); btn.draw(screen)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: return "resume"
            if event.type == pygame.MOUSEBUTTONDOWN:
                play_sound(click_sound)
                for btn in buttons:
                    if btn.hovered:
                        if btn.text == "RESUME": return "resume"
                        elif btn.text == "SETTINGS": options_menu()
                        elif btn.text == "QUIT TO MENU": return "quit"
        pygame.display.update()

# ===================== GAME OVER =====================
def game_over_screen(wave, gold, level):
    buttons = [MenuButton("RESTART", 300), MenuButton("QUIT TO MENU", 380)]
    start_time = pygame.time.get_ticks() / 1000
    while True:
        current_time = pygame.time.get_ticks() / 1000 - start_time
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))
        title_surf = title_font.render("GAME OVER", True, RED)
        title_rect = title_surf.get_rect(center=(WIDTH//2, 130))
        draw_animated_title_border(screen, title_rect.inflate(40, 20), current_time)
        screen.blit(title_font.render("GAME OVER", True, SHADOW), title_rect.move(3, 3))
        screen.blit(title_surf, title_rect)
        stats = [
            f"WAVE REACHED: {wave}",
            f"GOLD COLLECTED: {gold}",
            f"LEVEL: {level}",
        ]
        for i, stat in enumerate(stats):
            surf = small_font.render(stat, True, GOLD)
            screen.blit(surf, surf.get_rect(center=(WIDTH//2, 210 + i * 32)))
        mouse_pos = pygame.mouse.get_pos()
        for btn in buttons:
            btn.check_hover(mouse_pos); btn.draw(screen)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); return "quit"
            if event.type == pygame.MOUSEBUTTONDOWN:
                play_sound(click_sound)
                for btn in buttons:
                    if btn.hovered:
                        if btn.text == "RESTART": return "restart"
                        elif btn.text == "QUIT TO MENU": return "quit"
        pygame.display.update()

# ===================== VICTORY =====================
def victory_screen(gold, level):
    buttons = [MenuButton("PLAY AGAIN", 310), MenuButton("QUIT TO MENU", 390)]
    start_time = pygame.time.get_ticks() / 1000
    while True:
        current_time = pygame.time.get_ticks() / 1000 - start_time
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        title_surf = title_font.render("VICTORY!", True, GOLD)
        title_rect = title_surf.get_rect(center=(WIDTH//2, 120))
        draw_animated_title_border(screen, title_rect.inflate(40, 20), current_time)
        screen.blit(title_font.render("VICTORY!", True, SHADOW), title_rect.move(3, 3))
        screen.blit(title_surf, title_rect)
        sub = small_font.render("The Pirate Boss is defeated!", True, WHITE)
        screen.blit(sub, sub.get_rect(center=(WIDTH//2, 200)))
        stats = [f"FINAL GOLD: {gold}", f"FINAL LEVEL: {level}"]
        for i, s in enumerate(stats):
            surf = small_font.render(s, True, GOLD)
            screen.blit(surf, surf.get_rect(center=(WIDTH//2, 250 + i * 34)))
        mouse_pos = pygame.mouse.get_pos()
        for btn in buttons:
            btn.check_hover(mouse_pos); btn.draw(screen)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); return "quit"
            if event.type == pygame.MOUSEBUTTONDOWN:
                play_sound(click_sound)
                for btn in buttons:
                    if btn.hovered:
                        if btn.text == "PLAY AGAIN": return "restart"
                        elif btn.text == "QUIT TO MENU": return "quit"
        pygame.display.update()

# ===================== HOW TO PLAY =====================
def how_to_play_screen():
    start_time = pygame.time.get_ticks() / 1000
    back_btn = pygame.Rect(WIDTH//2 - 110, 530, 220, 52)
    lines = [
        ("MOVEMENT",   "WASD or Arrow Keys"),
        ("AIM & FIRE", "Mouse + Left Click (hold to auto-fire)"),
        ("PAUSE",      "ESC key"),
        ("LAND",       "Press E near island to go ashore"),
        ("ON ISLAND",  "WASD=Move  CLICK=Sword  E=Leave"),
        ("GOAL",       "Survive 10 waves then beat the boss"),
        ("POWERUPS",   "S=Shield  R=Rapid Fire  V=Speed  +=HP"),
        ("XP & LEVEL", "Kill enemies to earn XP and level up"),
        ("TREASURE",   "Collect gold chests on islands"),
    ]

    # Pre-render all text so we can measure widths
    LABEL_COL = GOLD
    DESC_COL  = (255, 245, 180)   # warm cream — readable on dark
    SHADOW_COL= (40, 20, 0)

    ROW_H    = 46
    TABLE_Y  = 118
    TABLE_X  = 30
    TABLE_W  = WIDTH - 60
    TABLE_H  = len(lines) * ROW_H + 10

    while True:
        current_time = pygame.time.get_ticks() / 1000 - start_time

        # Background
        screen.fill((10, 30, 70))
        if background:
            bg = pygame.transform.scale(background, (WIDTH, HEIGHT))
            bg.set_alpha(120)
            screen.blit(bg, (0, 0))

        # Dark panel behind the whole table
        panel = pygame.Surface((TABLE_W, TABLE_H), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        screen.blit(panel, (TABLE_X, TABLE_Y - 6))
        pygame.draw.rect(screen, GOLD, (TABLE_X, TABLE_Y - 6, TABLE_W, TABLE_H), 2, border_radius=6)

        # Title
        title_surf = small_font.render("HOW TO PLAY", True, GOLD)
        title_rect = title_surf.get_rect(center=(WIDTH//2, 75))
        title_bg   = title_rect.inflate(50, 22)
        draw_animated_title_border(screen, title_bg, current_time)
        screen.blit(small_font.render("HOW TO PLAY", True, SHADOW), title_rect.move(2, 2))
        screen.blit(title_surf, title_rect)

        # Rows
        for i, (label, desc) in enumerate(lines):
            ry = TABLE_Y + i * ROW_H + 5

            # Alternating row shading
            row_surf = pygame.Surface((TABLE_W - 4, ROW_H - 4), pygame.SRCALPHA)
            row_surf.fill((255, 200, 80, 18) if i % 2 == 0 else (0, 0, 0, 0))
            screen.blit(row_surf, (TABLE_X + 2, ry))

            # Divider line between rows
            if i > 0:
                pygame.draw.line(screen, (100, 80, 20), (TABLE_X + 8, ry), (TABLE_X + TABLE_W - 8, ry), 1)

            # Label (gold)
            lbl = tiny_font.render(label + ":", True, LABEL_COL)
            screen.blit(lbl, (TABLE_X + 12, ry + 8))

            # Separator dot
            screen.blit(tiny_font.render("»", True, GOLD), (TABLE_X + 175, ry + 8))

            # Description — shadow then text
            shd = tiny_font.render(desc, True, SHADOW_COL)
            val = tiny_font.render(desc, True, DESC_COL)
            screen.blit(shd, (TABLE_X + 202, ry + 10))
            screen.blit(val, (TABLE_X + 200, ry + 8))

        # BACK button
        pygame.draw.rect(screen, SHADOW,     back_btn.move(3, 3),      border_radius=8)
        pygame.draw.rect(screen, DARK_WOOD,  back_btn,                 border_radius=8)
        pygame.draw.rect(screen, LIGHT_GOLD, back_btn.inflate(-6, -6), border_radius=8)
        screen.blit(tiny_font.render("BACK", True, DARK_WOOD),
                    tiny_font.render("BACK", True, DARK_WOOD).get_rect(center=back_btn.center))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back_btn.collidepoint(pygame.mouse.get_pos()):
                    play_sound(click_sound); return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return

        pygame.display.update()

# ===================== LEVEL UP OVERLAY =====================
def draw_level_up(surface, timer):
    alpha = int(min(255, timer * 3 * 255))
    surf = title_font.render("LEVEL UP!", True, YELLOW)
    surf.set_alpha(alpha)
    shadow = title_font.render("LEVEL UP!", True, BLACK)
    shadow.set_alpha(alpha)
    surface.blit(shadow, (WIDTH//2 - surf.get_width()//2 + 3, HEIGHT//2 - 60 + 3))
    surface.blit(surf, (WIDTH//2 - surf.get_width()//2, HEIGHT//2 - 60))

# ===================== MAIN PIRATE GAME =====================
def pirate_adventure_game():
    global shake_timer, shake_intensity
    clock = pygame.time.Clock()
    running = True

    # Switch to battle music
    music_play_battle(fade_ms=800)

    # ---- PLAYER STATS ----
    player_size     = 22
    player_x        = 1000.0
    player_y        = 1000.0
    player_speed    = 180.0   # pixels/sec
    player_health   = 100.0
    player_max_hp   = 100.0
    player_gold     = 0
    player_angle    = 0.0    # radians (pointing direction)
    player_xp       = 0
    player_level    = 1
    xp_to_next      = 100

    # Level-up bonuses
    level_up_timer  = 0.0
    level_up_flash  = False

    # Power-up states
    shield_active   = False
    shield_timer    = 0.0
    rapid_fire      = False
    rapid_timer     = 0.0
    speed_boost     = False
    speed_timer     = 0.0
    shoot_cooldown  = 0.0
    base_shoot_rate = 0.35   # seconds between shots

    # World
    world_width  = 2400
    world_height = 2400
    camera_x     = player_x - WIDTH // 2
    camera_y     = player_y - HEIGHT // 2

    # Islands — placed safely away from player start and each other
    islands = []
    attempts = 0
    while len(islands) < 14 and attempts < 500:
        attempts += 1
        ix = random.randint(150, world_width  - 150)
        iy = random.randint(150, world_height - 150)
        isize = random.randint(50, 120)
        # Keep clear of player spawn
        if math.hypot(ix - player_x, iy - player_y) < isize + 200:
            continue
        # Keep clear of other islands
        overlap = False
        for other in islands:
            if math.hypot(ix - other["x"], iy - other["y"]) < isize + other["size"] + 60:
                overlap = True; break
        if overlap:
            continue
        islands.append({
            "x": float(ix), "y": float(iy),
            "size": isize,
            "has_treasure": random.choice([True, False, False, False])
        })

    # Enemies, bullets, powerups, particles
    enemies        = []
    cannons        = []       # player shots
    enemy_cannons  = []       # enemy shots
    powerups       = []
    particles      = []
    floating_texts = []

    # Wave system
    current_wave        = 1
    max_wave            = 10
    enemies_left_spawn  = 0
    enemies_alive       = 0
    wave_in_progress    = False
    wave_timer          = 3.0   # start first wave after 3s
    time_between_waves  = 6.0
    boss_spawned        = False

    # Wave announcement
    wave_announce_timer  = 0.0
    wave_announce_text   = ""

    game_time = 0.0
    shake_timer = 0.0

    # Enemy colors by tier
    TIER_COLORS = [
        (180, 30, 30),    # wave 1-2
        (180, 80, 0),     # wave 3-4
        (160, 0, 120),    # wave 5-6
        (80, 0, 180),     # wave 7-8
        (0, 100, 200),    # wave 9
    ]

    def enemy_color_for_wave(w):
        tier = min((w - 1) // 2, len(TIER_COLORS) - 1)
        return TIER_COLORS[tier]

    def spawn_wave_announcement(text):
        nonlocal wave_announce_timer, wave_announce_text
        wave_announce_text  = text
        wave_announce_timer = 2.5

    def spawn_enemy(level):
        side = random.choice(["top", "bottom", "left", "right"])
        if   side == "top":    x, y = random.randint(0, world_width), -60
        elif side == "bottom": x, y = random.randint(0, world_width), world_height + 60
        elif side == "left":   x, y = -60, random.randint(0, world_height)
        else:                  x, y = world_width + 60, random.randint(0, world_height)

        base_hp = 50 + level * 20

        # ── Projectile scaling per wave ──────────────────────────────────────
        # Wave 1: slow weak shots, long cooldown — very forgiving
        # Wave 2: slightly faster — still nerfed
        # Wave 3+: ramps up steadily, becomes brutal by wave 8+
        if level == 1:
            ec_spd   = 90          # very slow
            ec_dmg   = 4           # very weak
            ec_cd    = random.uniform(3.5, 5.0)   # shoots rarely
            can_fire = False       # wave 1 enemies don't shoot at all
        elif level == 2:
            ec_spd   = 120         # still slow
            ec_dmg   = 6           # slightly weak
            ec_cd    = random.uniform(2.5, 4.0)
            can_fire = True
        else:
            # Each wave above 2 adds speed, damage, and shorter cooldown
            ec_spd = 130 + (level - 2) * 22          # 130 → 326 at wave 10
            ec_dmg = 7  + (level - 2) * 3            # 7 → 31 at wave 10
            ec_cd  = max(0.35, 2.2 - (level - 2) * 0.22)  # 2.2s → 0.44s at wave 10
            can_fire = True

        enemies.append({
            "x": float(x), "y": float(y),
            "size": 18 + level * 1.5,
            "speed": 60 + level * 18,
            "health": float(base_hp), "max_health": float(base_hp),
            "damage": 8 + level * 2,
            "can_shoot": can_fire,
            "shoot_timer": ec_cd,
            "shoot_cooldown": ec_cd,      # stored for reset
            "ec_speed": ec_spd,
            "ec_damage": ec_dmg,
            "angle": 0.0,
            "color": enemy_color_for_wave(level),
            "xp_value": 20 + level * 5,
            "is_boss": False,
        })

    def spawn_boss():
        side = random.choice(["top", "bottom", "left", "right"])
        if   side == "top":    x, y = random.randint(0, world_width), -100
        elif side == "bottom": x, y = random.randint(0, world_width), world_height + 100
        elif side == "left":   x, y = -100, random.randint(0, world_height)
        else:                  x, y = world_width + 100, random.randint(0, world_height)
        enemies.append({
            "x": float(x), "y": float(y),
            "size": 60,
            "speed": 80,
            "health": 2000.0, "max_health": 2000.0,
            "damage": 15,
            "can_shoot": True,
            "shoot_timer": 0.8,
            "angle": 0.0,
            "color": BOSS_COLOR,
            "xp_value": 500,
            "is_boss": True,
        })

    def spawn_particles(x, y, color, count=12, speed=120, life=0.6):
        for _ in range(count):
            particles.append(Particle(x, y, color, speed, life, size=4))

    def try_spawn_powerup(x, y):
        if random.random() < 0.25:  # 25% drop chance
            ptype = random.choice(POWERUP_TYPES)
            powerups.append({
                "x": float(x), "y": float(y),
                "name": ptype["name"],
                "color": ptype["color"],
                "icon": ptype["icon"],
                "timer": 8.0,
            })

    # Kick off first wave
    spawn_wave_announcement("WAVE 1 — INCOMING!")
    wave_in_progress = True
    enemies_left_spawn = 3
    enemies_alive = 0

    while running:
        dt = clock.tick(60) / 1000.0
        game_time += dt
        shake_timer = max(0, shake_timer - dt)

        keys = pygame.key.get_pressed()

        # ---- WAVE LOGIC ----
        if not wave_in_progress:
            wave_timer -= dt
            if wave_timer <= 0:
                wave_timer = time_between_waves
                wave_in_progress = True
                if current_wave < max_wave:
                    enemies_left_spawn = 3 + current_wave * 2
                    enemies_alive = 0
                    spawn_wave_announcement(f"WAVE {current_wave} — INCOMING!")
                else:
                    # Boss wave
                    enemies_left_spawn = 0
                    enemies_alive = 1
                    spawn_boss()
                    boss_spawned = True
                    spawn_wave_announcement("FINAL BOSS — FIGHT!")
        else:
            # Gradually spawn
            if current_wave < max_wave and enemies_left_spawn > 0:
                if random.random() < 0.04:
                    spawn_enemy(current_wave)
                    enemies_left_spawn -= 1
                    enemies_alive += 1
            # Wave ends when all dead
            if enemies_alive <= 0 and enemies_left_spawn <= 0:
                wave_in_progress = False
                if current_wave >= max_wave:
                    music_stop(400)
                    result = victory_screen(player_gold, player_level)
                    music_play_menu()
                    if result == "restart":
                        pirate_adventure_game(); return
                    else: return
                current_wave += 1
                wave_timer = time_between_waves
                spawn_wave_announcement(f"WAVE CLEARED!  Next in {int(time_between_waves)}s...")

        # ---- MOVEMENT ----
        dx, dy = 0.0, 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if dx != 0 and dy != 0:
            dx *= 0.7071; dy *= 0.7071

        spd = player_speed * (1.4 if speed_boost else 1.0)
        new_x = player_x + dx * spd * dt
        new_y = player_y + dy * spd * dt
        new_x = max(player_size, min(world_width  - player_size, new_x))
        new_y = max(player_size, min(world_height - player_size, new_y))

        # Island collision — slide along surface
        for island in islands:
            isl_r = island["size"] + player_size
            # Try full move
            cdx = new_x - island["x"]
            cdy = new_y - island["y"]
            if math.hypot(cdx, cdy) < isl_r:
                # Try sliding X only
                cdx_x = new_x - island["x"]
                cdy_x = player_y - island["y"]
                if math.hypot(cdx_x, cdy_x) >= isl_r:
                    new_y = player_y   # X slide works
                else:
                    # Try sliding Y only
                    cdx_y = player_x - island["x"]
                    cdy_y = new_y - island["y"]
                    if math.hypot(cdx_y, cdy_y) >= isl_r:
                        new_x = player_x  # Y slide works
                    else:
                        # Fully blocked — push out radially
                        dist = math.hypot(cdx, cdy)
                        if dist > 0:
                            push = isl_r - dist + 0.5
                            new_x = island["x"] + cdx / dist * isl_r
                            new_y = island["y"] + cdy / dist * isl_r
                        else:
                            new_x = island["x"] + isl_r
                            new_y = player_y

        player_x, player_y = new_x, new_y

        # Ship points toward mouse
        mx, my = pygame.mouse.get_pos()
        world_mx = mx + camera_x
        world_my = my + camera_y
        player_angle = math.atan2(world_mx - player_x, -(world_my - player_y))

        # Camera
        camera_x = max(0, min(world_width  - WIDTH,  player_x - WIDTH  // 2))
        camera_y = max(0, min(world_height - HEIGHT, player_y - HEIGHT // 2))

        # ---- SHOOT COOLDOWN ----
        shoot_cooldown = max(0, shoot_cooldown - dt)

        # ---- POWER-UP TIMERS ----
        if shield_active:
            shield_timer -= dt
            if shield_timer <= 0: shield_active = False
        if rapid_fire:
            rapid_timer -= dt
            if rapid_timer <= 0: rapid_fire = False
        if speed_boost:
            speed_timer -= dt
            if speed_timer <= 0: speed_boost = False
        if level_up_timer > 0:
            level_up_timer -= dt

        # ---- EVENTS ----
        # Find nearest island for landing prompt
        nearby_island = None
        for isl in islands:
            if math.hypot(player_x - isl["x"], player_y - isl["y"]) < isl["size"] + 45:
                nearby_island = isl
                break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    action = pause_menu()
                    if action == "quit":
                        music_play_menu()
                        return
                if event.key == pygame.K_e and nearby_island is not None:
                    # Jump onto island — enter top-down mode
                    play_sound(click_sound)
                    result = island_platformer(
                        nearby_island,
                        player_gold, player_health, player_max_hp,
                        player_level, player_xp, xp_to_next)
                    player_gold, player_health, player_xp, xp_to_next, player_level = result
                    player_health = max(1, min(player_health, player_max_hp))
                    # Push ship away from island so it doesn't sit inside it
                    isl = nearby_island
                    dx_push = player_x - isl["x"]
                    dy_push = player_y - isl["y"]
                    dist_push = math.hypot(dx_push, dy_push)
                    push_dist = isl["size"] + player_size + 30
                    if dist_push > 0:
                        player_x = isl["x"] + dx_push / dist_push * push_dist
                        player_y = isl["y"] + dy_push / dist_push * push_dist
                    else:
                        player_y = isl["y"] + push_dist
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click = shoot
                    fire_rate = base_shoot_rate * (0.35 if rapid_fire else 1.0)
                    if shoot_cooldown <= 0:
                        shoot_cooldown = fire_rate
                        dir_x = world_mx - player_x
                        dir_y = world_my - player_y
                        length = math.hypot(dir_x, dir_y)
                        if length > 0:
                            dir_x /= length; dir_y /= length
                        speed_c = 420
                        cannons.append({
                            "x": float(player_x), "y": float(player_y),
                            "dx": dir_x * speed_c, "dy": dir_y * speed_c,
                            "size": 7
                        })

        # Auto-fire while holding mouse
        if pygame.mouse.get_pressed()[0]:
            fire_rate = base_shoot_rate * (0.35 if rapid_fire else 1.0)
            if shoot_cooldown <= 0:
                shoot_cooldown = fire_rate
                dir_x = world_mx - player_x
                dir_y = world_my - player_y
                length = math.hypot(dir_x, dir_y)
                if length > 0:
                    dir_x /= length; dir_y /= length
                speed_c = 420
                cannons.append({
                    "x": float(player_x), "y": float(player_y),
                    "dx": dir_x * speed_c, "dy": dir_y * speed_c,
                    "size": 7
                })

        # ---- UPDATE PLAYER CANNONS ----
        for cannon in cannons[:]:
            cannon["x"] += cannon["dx"] * dt
            cannon["y"] += cannon["dy"] * dt
            if not (0 < cannon["x"] < world_width and 0 < cannon["y"] < world_height):
                cannons.remove(cannon); continue
            # Stop cannonball if it hits an island
            hit_island = False
            for island in islands:
                if math.hypot(cannon["x"] - island["x"], cannon["y"] - island["y"]) < island["size"]:
                    spawn_particles(cannon["x"], cannon["y"], ISLAND_SAND, count=5, speed=60, life=0.3)
                    cannons.remove(cannon)
                    hit_island = True
                    break
            if hit_island: continue

        # ---- UPDATE ENEMY CANNONS ----
        for ec in enemy_cannons[:]:
            ec["x"] += ec["dx"] * dt
            ec["y"] += ec["dy"] * dt
            if not (0 < ec["x"] < world_width and 0 < ec["y"] < world_height):
                enemy_cannons.remove(ec); continue
            # Block on island
            blocked = False
            for island in islands:
                if math.hypot(ec["x"] - island["x"], ec["y"] - island["y"]) < island["size"]:
                    enemy_cannons.remove(ec)
                    blocked = True
                    break
            if blocked: continue
            # Hit player
            if math.hypot(ec["x"] - player_x, ec["y"] - player_y) < player_size + ec["size"]:
                enemy_cannons.remove(ec)
                spawn_particles(player_x, player_y, RED, count=8, speed=80)
                trigger_shake(5, 0.2)
                if shield_active:
                    shield_active = False
                    floating_texts.append(FloatingText(player_x, player_y, "SHIELD BLOCKED!", SHIELD_COLOR))
                else:
                    player_health -= ec["damage"]
                    floating_texts.append(FloatingText(player_x, player_y, f"-{int(ec['damage'])} HP", RED))
                    if player_health <= 0:
                        music_stop(400)
                        result = game_over_screen(current_wave, player_gold, player_level)
                        music_play_menu()
                        if result == "restart": pirate_adventure_game(); return
                        else: return

        # ---- UPDATE ENEMIES ----
        for enemy in enemies[:]:
            ex, ey = enemy["x"], enemy["y"]
            dir_x = player_x - ex
            dir_y = player_y - ey
            dist = math.hypot(dir_x, dir_y)
            if dist > 0:
                dir_x /= dist; dir_y /= dist

            new_ex = ex + dir_x * enemy["speed"] * dt
            new_ey = ey + dir_y * enemy["speed"] * dt

            # Island collision for enemies — push out radially
            for island in islands:
                isl_r = island["size"] + enemy["size"] * 0.7
                cdx = new_ex - island["x"]
                cdy = new_ey - island["y"]
                d = math.hypot(cdx, cdy)
                if d < isl_r:
                    if d > 0:
                        new_ex = island["x"] + cdx / d * isl_r
                        new_ey = island["y"] + cdy / d * isl_r
                    else:
                        new_ex = island["x"] + isl_r

            enemy["x"] = new_ex
            enemy["y"] = new_ey
            enemy["angle"] = math.atan2(player_x - enemy["x"], -(player_y - enemy["y"]))

            # Enemy shooting
            if enemy.get("can_shoot", False):
                enemy["shoot_timer"] -= dt
                if enemy["shoot_timer"] <= 0:
                    ec_speed  = enemy.get("ec_speed",  200)
                    ec_damage = enemy.get("ec_damage",  10)
                    ec_cd     = enemy.get("shoot_cooldown", 0.6)
                    if enemy.get("is_boss"):
                        ec_speed, ec_damage, ec_cd = 260, 20, 0.30
                    enemy_cannons.append({
                        "x": ex, "y": ey,
                        "dx": dir_x * ec_speed, "dy": dir_y * ec_speed,
                        "size": 8 if not enemy.get("is_boss") else 14,
                        "damage": ec_damage,
                    })
                    enemy["shoot_timer"] = ec_cd
                    # Muzzle flash + smoke at enemy barrel tip
                    flash_x = ex + dir_x * enemy["size"]
                    flash_y = ey + dir_y * enemy["size"]
                    if enemy.get("is_boss"):
                        # Big dramatic boss flash — bright orange burst + dark smoke
                        spawn_particles(flash_x, flash_y, ORANGE,  count=14, speed=140, life=0.30)
                        spawn_particles(flash_x, flash_y, (255,220,80), count=8, speed=80, life=0.20)
                        spawn_particles(flash_x, flash_y, (80,70,60),  count=10, speed=55, life=0.55)
                    else:
                        # Regular enemy — small flash + grey smoke puff
                        spawn_particles(flash_x, flash_y, ORANGE,     count=6, speed=90,  life=0.18)
                        spawn_particles(flash_x, flash_y, (110,100,90), count=5, speed=40, life=0.40)

            # Player cannon hits enemy
            hit = False
            for cannon in cannons[:]:
                if math.hypot(cannon["x"] - enemy["x"], cannon["y"] - enemy["y"]) < enemy["size"] + cannon["size"]:
                    dmg = 30 + player_level * 5
                    enemy["health"] -= dmg
                    cannons.remove(cannon)
                    spawn_particles(enemy["x"], enemy["y"], enemy["color"], count=8, speed=100)
                    floating_texts.append(FloatingText(enemy["x"], enemy["y"], f"-{dmg}", ORANGE, 'tiny'))
                    if enemy["health"] <= 0:
                        gold_gain = int((20 + current_wave * 10) * (5 if enemy.get("is_boss") else 1))
                        player_gold += gold_gain
                        xp_gain = enemy["xp_value"]
                        player_xp += xp_gain
                        spawn_particles(enemy["x"], enemy["y"], GOLD, count=20, speed=150, life=0.9)
                        play_sound(explosion_sound)
                        trigger_shake(8 if enemy.get("is_boss") else 4, 0.3)
                        floating_texts.append(FloatingText(enemy["x"], enemy["y"], f"+{gold_gain}G", GOLD))
                        try_spawn_powerup(enemy["x"], enemy["y"])
                        enemies.remove(enemy)
                        enemies_alive -= 1
                        # Level up check
                        while player_xp >= xp_to_next:
                            player_xp -= xp_to_next
                            player_level += 1
                            xp_to_next = int(xp_to_next * 1.4)
                            player_max_hp += 20
                            player_health = min(player_health + 30, player_max_hp)
                            player_speed  += 8
                            level_up_timer = 1.8
                            floating_texts.append(FloatingText(player_x, player_y - 30,
                                                               f"LEVEL {player_level}!", YELLOW))
                        hit = True
                        break
                    break

            if hit:
                continue

            # Melee contact
            if dist < player_size + enemy["size"]:
                spawn_particles(player_x, player_y, RED, count=4, speed=60, life=0.3)
                trigger_shake(4, 0.15)
                if shield_active:
                    shield_active = False
                    floating_texts.append(FloatingText(player_x, player_y, "SHIELD BLOCKED!", SHIELD_COLOR))
                else:
                    dmg = enemy["damage"] * dt * 3
                    player_health -= dmg
                    if player_health <= 0:
                        music_stop(400)
                        result = game_over_screen(current_wave, player_gold, player_level)
                        music_play_menu()
                        if result == "restart": pirate_adventure_game(); return
                        else: return

        # ---- UPDATE POWERUPS ----
        for pu in powerups[:]:
            pu["timer"] -= dt
            if pu["timer"] <= 0:
                powerups.remove(pu); continue
            if math.hypot(player_x - pu["x"], player_y - pu["y"]) < player_size + 18:
                play_sound(powerup_sound)
                name = pu["name"]
                if name == "SHIELD":
                    shield_active = True; shield_timer = 12.0
                    floating_texts.append(FloatingText(player_x, player_y, "SHIELD UP!", SHIELD_COLOR))
                elif name == "RAPID FIRE":
                    rapid_fire = True; rapid_timer = 8.0
                    floating_texts.append(FloatingText(player_x, player_y, "RAPID FIRE!", ORANGE))
                elif name == "SPEED":
                    speed_boost = True; speed_timer = 8.0
                    floating_texts.append(FloatingText(player_x, player_y, "SPEED BOOST!", CYAN))
                elif name == "HEALTH":
                    heal = 35
                    player_health = min(player_health + heal, player_max_hp)
                    floating_texts.append(FloatingText(player_x, player_y, f"+{heal} HP!", GREEN))
                spawn_particles(pu["x"], pu["y"], pu["color"], count=16, speed=120, life=0.7)
                powerups.remove(pu)

        # ---- TREASURE ----
        for island in islands:
            if island["has_treasure"] and math.hypot(player_x - island["x"], player_y - island["y"]) < island["size"]:
                island["has_treasure"] = False
                gain = 80 + current_wave * 20
                player_gold += gain
                floating_texts.append(FloatingText(island["x"], island["y"], f"+{gain} GOLD!", TREASURE))
                play_sound(powerup_sound)
                spawn_particles(island["x"], island["y"], GOLD, count=20, speed=100, life=0.8)

        # ---- PARTICLES & TEXTS ----
        particles      = [p for p in particles      if p.update(dt)]
        floating_texts = [ft for ft in floating_texts if ft.update(dt)]

        # ===================== DRAW =====================
        sx, sy = get_shake_offset()
        draw_surf = screen

        draw_ocean(draw_surf, camera_x, camera_y, game_time)

        # Islands
        for island in islands:
            ix = island["x"] - camera_x + sx
            iy = island["y"] - camera_y + sy
            if -200 < ix < WIDTH + 200 and -200 < iy < HEIGHT + 200:
                draw_island(draw_surf, ix, iy, island["size"], island["has_treasure"], game_time)

        # Enemy cannons
        for ec in enemy_cannons:
            cx = ec["x"] - camera_x + sx
            cy = ec["y"] - camera_y + sy
            pygame.draw.circle(draw_surf, RED, (int(cx), int(cy)), ec["size"])
            pygame.draw.circle(draw_surf, ORANGE, (int(cx), int(cy)), max(1, ec["size"] - 3))

        # Player cannons
        for cannon in cannons:
            cx = cannon["x"] - camera_x + sx
            cy = cannon["y"] - camera_y + sy
            pygame.draw.circle(draw_surf, GRAY,  (int(cx), int(cy)), cannon["size"])
            pygame.draw.circle(draw_surf, WHITE, (int(cx), int(cy)), cannon["size"] - 3)

        # Enemies
        for enemy in enemies:
            ex = enemy["x"] - camera_x + sx
            ey = enemy["y"] - camera_y + sy
            if -80 < ex < WIDTH + 80 and -80 < ey < HEIGHT + 80:
                # Draw as rotated ship
                draw_ship(draw_surf, ex, ey, enemy["size"], enemy["angle"], enemy["color"],
                          (min(255, enemy["color"][0]+60), enemy["color"][1], enemy["color"][2]),
                          is_boss=enemy.get("is_boss", False), wave_num=current_wave)
                # Health bar
                bw = int(enemy["size"] * 2.5)
                bx = int(ex) - bw // 2
                by = int(ey) - int(enemy["size"]) - 16
                draw_health_bar(draw_surf, bx, by, bw, 6,
                                enemy["health"], enemy["max_health"],
                                GREEN if not enemy.get("is_boss") else PINK,
                                DARK_RED)

        # Player ship
        px = player_x - camera_x + sx
        py = player_y - camera_y + sy
        draw_ship(draw_surf, px, py, player_size, player_angle,
                  DARK_WOOD, LIGHT_GOLD,
                  shield_active=shield_active, shield_anim=game_time,
                  is_player=True)

        # Powerups
        for pu in powerups:
            draw_powerup(draw_surf, pu, game_time, camera_x - sx, camera_y - sy)

        # Particles
        for p in particles:
            p.draw(draw_surf, camera_x - sx, camera_y - sy)

        # Floating texts
        for ft in floating_texts:
            ft.draw(draw_surf, camera_x - sx, camera_y - sy)

        # ---- HUD ----
        # Health bar
        draw_health_bar(screen, 20, 20, 220, 22, player_health, player_max_hp)
        hp_txt = tiny_font.render(f"HP {int(player_health)}/{int(player_max_hp)}", True, WHITE)
        screen.blit(hp_txt, (20, 46))

        # XP bar
        draw_xp_bar(screen, 20, 66, 220, 10, player_xp, xp_to_next)
        lv_txt = micro_font.render(f"LVL {player_level}  XP {player_xp}/{xp_to_next}", True, (200, 150, 255))
        screen.blit(lv_txt, (20, 80))

        # Gold
        gold_txt = small_font.render(f"GOLD: {player_gold}", True, GOLD)
        screen.blit(gold_txt, (20, 98))

        # Wave
        if current_wave < max_wave:
            wave_txt = small_font.render(f"WAVE {current_wave}/{max_wave - 1}", True, WHITE)
        else:
            wave_txt = small_font.render("FINAL BOSS!", True, BOSS_COLOR)
        screen.blit(wave_txt, wave_txt.get_rect(centerx=WIDTH // 2, top=16))

        enemies_txt = tiny_font.render(f"ENEMIES: {enemies_alive + enemies_left_spawn}", True, WHITE)
        screen.blit(enemies_txt, enemies_txt.get_rect(centerx=WIDTH // 2, top=44))

        if not wave_in_progress and current_wave < max_wave:
            timer_txt = tiny_font.render(f"Next wave in {max(0, int(wave_timer))}s", True, GOLD)
            screen.blit(timer_txt, timer_txt.get_rect(centerx=WIDTH // 2, top=64))

        # Boss HP bar (full screen width, bottom)
        boss = next((e for e in enemies if e.get("is_boss")), None)
        if boss:
            bw = WIDTH - 40
            draw_health_bar(screen, 20, HEIGHT - 40, bw, 20,
                            boss["health"], boss["max_health"], PINK, DARK_RED)
            boss_lbl = tiny_font.render("PIRATE KING", True, PINK)
            screen.blit(boss_lbl, boss_lbl.get_rect(centerx=WIDTH // 2, bottom=HEIGHT - 44))

        # Active powerup indicators
        pu_x = WIDTH - 150
        pu_y = 20
        if shield_active:
            s = tiny_font.render(f"SHIELD {int(shield_timer)}s", True, SHIELD_COLOR)
            screen.blit(s, (pu_x, pu_y)); pu_y += 22
        if rapid_fire:
            s = tiny_font.render(f"RAPID {int(rapid_timer)}s", True, ORANGE)
            screen.blit(s, (pu_x, pu_y)); pu_y += 22
        if speed_boost:
            s = tiny_font.render(f"SPEED {int(speed_timer)}s", True, CYAN)
            screen.blit(s, (pu_x, pu_y)); pu_y += 22

        # Minimap
        draw_minimap(screen, player_x, player_y, enemies, islands, world_width, world_height)

        # Wave announcement
        if wave_announce_timer > 0:
            wave_announce_timer -= dt
            alpha = int(min(255, wave_announce_timer * 160))
            draw_wave_announcement(screen, wave_announce_text, alpha)

        # Level up flash
        if level_up_timer > 0:
            draw_level_up(screen, level_up_timer)

        # Controls hint
        hint = micro_font.render("WASD=Move  CLICK=Fire  ESC=Pause  E=Land on Island", True, (180, 180, 180))
        screen.blit(hint, hint.get_rect(centerx=WIDTH // 2, bottom=HEIGHT - 6))

        # Island landing prompt
        if nearby_island is not None:
            prompt = small_font.render("Press E to LAND", True, GOLD)
            prompt_sh = small_font.render("Press E to LAND", True, BLACK)
            screen.blit(prompt_sh, prompt_sh.get_rect(centerx=WIDTH//2, top=HEIGHT//2 - 60).move(2,2))
            screen.blit(prompt,    prompt.get_rect(centerx=WIDTH//2, top=HEIGHT//2 - 60))

        pygame.display.flip()

# ===================== MAIN MENU =====================
def main_menu():
    buttons = [
        MenuButton("PLAY",        200),
        MenuButton("HOW TO PLAY", 280),
        MenuButton("OPTIONS",     360),
        MenuButton("EXIT",        440)
    ]
    clock = pygame.time.Clock()
    start_time = pygame.time.get_ticks() / 1000
    running = True

    while running:
        clock.tick(60)
        mouse_pos = pygame.mouse.get_pos()
        current_time = pygame.time.get_ticks() / 1000 - start_time

        if background:
            screen.blit(pygame.transform.scale(background, (WIDTH, HEIGHT)), (0, 0))
        else:
            screen.fill((10, 50, 120))

        title_surf = title_font.render("PIRATES", True, GOLD)
        title_rect = title_surf.get_rect(center=(WIDTH // 2, 100))
        draw_animated_title_border(screen, title_rect.inflate(40, 20), current_time)
        screen.blit(title_font.render("PIRATES", True, SHADOW), title_rect.move(3, 3))
        screen.blit(title_surf, title_rect)

        sub_surf = small_font.render("ADVENTURE", True, LIGHT_GOLD)
        screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, 160)))

        for btn in buttons:
            btn.check_hover(mouse_pos); btn.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type == pygame.MOUSEBUTTONDOWN:
                play_sound(click_sound)
                for btn in buttons:
                    if btn.hovered:
                        if btn.text == "PLAY":       pirate_adventure_game()
                        elif btn.text == "HOW TO PLAY": how_to_play_screen()
                        elif btn.text == "OPTIONS":  options_menu()
                        elif btn.text == "EXIT":     pygame.quit(); return

        pygame.display.update()

# ===================== GRANDLINE PIRATES — LOADING INTRO =====================
def grandline_intro():
    """
    Cinematic intro sequence:
      Phase 1 (0–1.2s)  — black screen, fade-in studio tag "A GRANDLINE PRODUCTION"
      Phase 2 (1.2–2.4s) — hold + fade out studio tag
      Phase 3 (2.4–4.2s) — ocean waves scroll up, dramatic fade-in of skull logo
      Phase 4 (4.2–6.4s) — main title "GRANDLINE" slams in letter by letter
      Phase 5 (6.4–7.6s) — subtitle "PIRATES" fades in below
      Phase 6 (7.6–9.2s) — loading bar fills across the bottom
      Phase 7 (9.2–10.0s)— brief flash → dissolve to menu
    Any keypress or click skips instantly.
    """
    clock  = pygame.time.Clock()
    start  = pygame.time.get_ticks() / 1000.0

    # ── Skull logo (drawn procedurally) ──────────────────────────────────────
    SKULL_W, SKULL_H = 140, 140
    skull_surf = pygame.Surface((SKULL_W, SKULL_H), pygame.SRCALPHA)
    skull_surf.fill((0, 0, 0, 0))  # fully transparent

    def draw_skull(surf):
        cx, cy = SKULL_W // 2, SKULL_H // 2 - 10
        # Cranium — white filled, dark outline
        pygame.draw.ellipse(surf, WHITE,      (cx-42, cy-38, 84, 78))
        pygame.draw.ellipse(surf, (50, 50, 50), (cx-42, cy-38, 84, 78), 3)
        # Jaw — white filled
        pygame.draw.ellipse(surf, WHITE,      (cx-28, cy+20, 56, 34))
        pygame.draw.ellipse(surf, (50, 50, 50), (cx-28, cy+20, 56, 34), 3)
        # Eye sockets — dark filled on white cranium, clearly visible
        for ex2 in (cx-18, cx+6):
            pygame.draw.ellipse(surf, (40, 40, 40), (ex2, cy-18, 22, 26))
        # Nose cavity
        pygame.draw.polygon(surf, (40, 40, 40),
                            [(cx, cy+8), (cx-7, cy+20), (cx+7, cy+20)])
        # Teeth — dark slots cut into white jaw
        for i in range(4):
            tx = cx - 21 + i * 14
            pygame.draw.rect(surf, (40, 40, 40), (tx, cy+32, 10, 13), border_radius=2)
        # Crossbones — drawn BEHIND skull so bones go under it
        # (we can't reorder after, so draw them wide+white first)
        for angle in (-38, 38):
            rad = math.radians(angle)
            bx  = cx + math.cos(rad) * 54
            by  = cy + 56 + math.sin(rad) * 16
            ex2 = cx - math.cos(rad) * 54
            ey2 = cy + 56 - math.sin(rad) * 16
            pygame.draw.line(surf, WHITE,       (int(bx), int(by)), (int(ex2), int(ey2)), 14)
            pygame.draw.line(surf, (50, 50, 50),(int(bx), int(by)), (int(ex2), int(ey2)),  2)
            for end in ((bx, by), (ex2, ey2)):
                pygame.draw.circle(surf, WHITE,       (int(end[0]), int(end[1])), 11)
                pygame.draw.circle(surf, (50, 50, 50),(int(end[0]), int(end[1])), 11, 2)

    draw_skull(skull_surf)

    # ── Letter-by-letter title surfaces ──────────────────────────────────────
    TITLE_STR  = "GRANDLINE"
    letter_surfs = [title_font.render(ch, True, GOLD)   for ch in TITLE_STR]
    shadow_surfs = [title_font.render(ch, True, (60,30,0)) for ch in TITLE_STR]
    letter_w     = sum(s.get_width() for s in letter_surfs) + 6 * (len(TITLE_STR)-1)
    letter_start = WIDTH // 2 - letter_w // 2

    subtitle_surf   = button_font.render("PIRATES", True, LIGHT_GOLD)
    studio_surf     = small_font.render("A  GRANDLINE  PRODUCTION", True, (200,190,160))
    loading_lbl     = tiny_font.render("LOADING . . .", True, GOLD)

    # ── Ocean wave particles for phase 3 ─────────────────────────────────────
    wave_lines = [(random.randint(0, WIDTH), random.randint(HEIGHT, HEIGHT+300),
                   random.randint(40,120), random.uniform(30,70))
                  for _ in range(18)]

    def eased(t):  # ease-in-out cubic
        return t*t*(3-2*t)

    TOTAL_DUR = 10.0

    running = True
    while running:
        now = pygame.time.get_ticks() / 1000.0 - start
        dt  = clock.tick(60) / 1000.0
        t   = min(now, TOTAL_DUR)

        # Skip on any input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                running = False

        # ── Phase 1 & 2 — studio tag ─────────────────────────────────────────
        if t < 1.2:
            alpha_studio = int(255 * eased(t / 1.2))
        elif t < 2.4:
            alpha_studio = int(255 * eased(1 - (t - 1.2) / 1.2))
        else:
            alpha_studio = 0

        # ── Phase 3 — ocean scroll ────────────────────────────────────────────
        ocean_alpha = 0
        if 2.4 <= t < 4.2:
            ocean_alpha = int(255 * eased((t - 2.4) / 1.8))
            # scroll wave lines upward
            for i, (wx, wy, wl, wspd) in enumerate(wave_lines):
                wave_lines[i] = (wx, wy - wspd * dt, wl, wspd)
                if wave_lines[i][1] < -10:
                    wave_lines[i] = (random.randint(0, WIDTH),
                                     HEIGHT + random.randint(0,80),
                                     random.randint(40,120),
                                     random.uniform(30,70))

        # ── Phase 4 — letters slam in ─────────────────────────────────────────
        letters_shown = 0
        if t >= 4.2:
            letters_shown = min(len(TITLE_STR), int((t - 4.2) / (2.2 / len(TITLE_STR))) + 1)

        # ── Phase 5 — subtitle ───────────────────────────────────────────────
        subtitle_alpha = 0
        if t >= 6.4:
            subtitle_alpha = int(255 * min(1.0, (t - 6.4) / 1.2))

        # ── Phase 6 — loading bar ─────────────────────────────────────────────
        load_pct = 0.0
        if t >= 7.6:
            load_pct = min(1.0, (t - 7.6) / 1.6)

        # ── Phase 7 — final flash & dissolve ─────────────────────────────────
        flash_alpha = 0
        if t >= 9.2:
            flash_alpha = int(255 * min(1.0, (t - 9.2) / 0.8))

        # ──────────────── DRAW ────────────────────────────────────────────────

        # ── Pixelated ocean background ────────────────────────────────────────
        TILE = 8   # pixel art tile size
        # Animate ocean tiles with slow color shift
        wave_shift = int(t * 3) % 3
        for ty in range(0, HEIGHT, TILE):
            for tx in range(0, WIDTH, TILE):
                # Checkerboard-style depth variation
                checker = ((tx // TILE) + (ty // TILE) + wave_shift) % 3
                if checker == 0:
                    col = (10, 60, 150)
                elif checker == 1:
                    col = (15, 75, 170)
                else:
                    col = (20, 90, 195)
                pygame.draw.rect(screen, col, (tx, ty, TILE, TILE))

        # ── White foam lines (pixelated wave rows) ────────────────────────────
        foam_rng = random.Random(42)
        for row in range(0, HEIGHT // TILE, 4):
            fy = row * TILE + int(math.sin(t * 2 + row * 0.7) * TILE)
            foam_x = (int(t * 40) + row * 37) % WIDTH
            for seg in range(0, WIDTH, TILE * 5):
                fx = (foam_x + seg) % WIDTH
                pygame.draw.rect(screen, (180, 220, 255), (fx, fy, TILE * 3, TILE // 2))

        # ── Pixelated islands (fixed seeds so they don't move) ───────────────
        island_defs = [
            (120, 360, 3, 42),
            (580, 420, 4, 77),
            (340, 480, 3, 13),
            (680, 310, 2, 55),
            ( 60, 220, 2, 88),
        ]
        for (ix, iy, isz, seed) in island_defs:
            irng = random.Random(seed)
            base_r = isz * TILE * 2
            # Sand base — pixelated circle
            for by in range(-base_r, base_r + 1, TILE):
                for bx in range(-base_r, base_r + 1, TILE):
                    if bx*bx + by*by <= base_r*base_r:
                        pygame.draw.rect(screen, (210, 180, 90), (ix + bx, iy + by, TILE, TILE))
            # Green top
            top_r = int(base_r * 0.65)
            for by in range(-top_r, top_r + 1, TILE):
                for bx in range(-top_r, top_r + 1, TILE):
                    if bx*bx + by*by <= top_r*top_r:
                        g = irng.randint(100, 160)
                        pygame.draw.rect(screen, (20, g, 30), (ix + bx, iy - top_r//2 + by, TILE, TILE))
            # Palm trunk (pixel column)
            trunk_h = isz * TILE * 2
            for ph in range(0, trunk_h, TILE):
                pygame.draw.rect(screen, (100, 60, 10),
                                 (ix - TILE//2, iy - top_r - ph, TILE, TILE))
            # Palm leaves (pixel blobs)
            top_y = iy - top_r - trunk_h
            leaf_sway = int(math.sin(t * 1.8 + seed) * TILE)
            for ang in range(0, 360, 72):
                rad = math.radians(ang)
                lx2 = ix + leaf_sway + int(math.cos(rad) * TILE * 3)
                ly2 = top_y + int(math.sin(rad) * TILE * 1.5)
                for lp in range(3):
                    pygame.draw.rect(screen, (30, 160, 40),
                                     (lx2 + lp * int(math.cos(rad)*TILE),
                                      ly2 + lp * int(math.sin(rad)*TILE),
                                      TILE, TILE))

        # Dark overlay so title elements are readable on top
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(140 + 60 * min(1.0, max(0.0, (t - 3.5) / 1.5)))))
        screen.blit(overlay, (0, 0))

        # Skull (phase 3 onward)
        if t >= 2.4:
            sk_alpha = int(255 * min(1.0, (t - 2.4) / 1.4))
            skull_copy = skull_surf.copy()
            skull_copy.set_alpha(sk_alpha)
            # gentle bob
            bob = int(math.sin(t * 2.2) * 5)
            screen.blit(skull_copy, (WIDTH//2 - SKULL_W//2, 130 + bob))

        # Letters (phase 4)
        lx = letter_start
        for i, (ls, sh) in enumerate(zip(letter_surfs, shadow_surfs)):
            if i < letters_shown:
                # slam-in: drop from above with quick ease
                progress = min(1.0, (t - 4.2 - i * (2.2/len(TITLE_STR))) * 4)
                if progress < 0: progress = 0
                drop = int((1 - eased(progress)) * 80)
                screen.blit(sh, (lx + 3, 310 + drop + 3))
                screen.blit(ls, (lx,     310 + drop))
            lx += ls.get_width() + 6

        # Subtitle (phase 5)
        if subtitle_alpha > 0:
            sub_copy = subtitle_surf.copy()
            sub_copy.set_alpha(subtitle_alpha)
            screen.blit(sub_copy, sub_copy.get_rect(centerx=WIDTH//2, top=378))

        # Decorative line under title
        if t >= 5.5:
            line_alpha = int(255 * min(1.0, (t - 5.5) / 0.8))
            line_surf = pygame.Surface((400, 3), pygame.SRCALPHA)
            line_surf.fill((*GOLD, line_alpha))
            screen.blit(line_surf, (WIDTH//2 - 200, 370))

        # Loading bar (phase 6)
        if load_pct > 0:
            bar_x, bar_y, bar_w, bar_h = 160, HEIGHT - 55, 480, 14
            pygame.draw.rect(screen, (40,30,10), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
            fill_w = int(bar_w * load_pct)
            if fill_w > 0:
                pygame.draw.rect(screen, GOLD, (bar_x, bar_y, fill_w, bar_h), border_radius=6)
            pygame.draw.rect(screen, LIGHT_GOLD, (bar_x, bar_y, bar_w, bar_h), 2, border_radius=6)
            # Shimmer dot
            shimmer_x = bar_x + fill_w - 6
            if fill_w > 8:
                pygame.draw.circle(screen, WHITE, (shimmer_x, bar_y + bar_h//2), 4)
            lbl_copy = loading_lbl.copy()
            lbl_copy.set_alpha(int(200 + 55*math.sin(t*6)))
            screen.blit(lbl_copy, lbl_copy.get_rect(centerx=WIDTH//2, top=bar_y + bar_h + 8))

        # Studio tag (phases 1-2)
        if alpha_studio > 0:
            st = studio_surf.copy(); st.set_alpha(alpha_studio)
            screen.blit(st, st.get_rect(center=(WIDTH//2, HEIGHT//2)))

        # Final flash
        if flash_alpha > 0:
            flash_surf = pygame.Surface((WIDTH, HEIGHT))
            flash_surf.fill(WHITE)
            flash_surf.set_alpha(flash_alpha)
            screen.blit(flash_surf, (0,0))

        pygame.display.flip()

        if t >= TOTAL_DUR:
            running = False


if __name__ == "__main__":
    grandline_intro()
    main_menu()
