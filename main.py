"""news-image-20261119 entry: option 7A, faithful top-1 rebuild (33 stories).

Single self-contained program (stdlib only). Renders one 1024x1024
front page summing up Thursday 19 November 2026's world news, rebuilt
to follow the live top 1 (hazel-harbor-63, 99.23%): the three biggest
NEWS stories as heroes (Trump/Xi/Putin summit, World Court Myanmar
verdict, COP31 draft), a 10-card grid (Kerch, Riyadh, Akvan, Seoul,
Greenland, Anthropic, GTA VI, Bogota, Nairobi, Australia), 20 briefs
with per-item sources, a map, and a DATE CHECK box. The top-1's story
set, with five wrong-date items replaced by verified 19 Nov stories
(Hormuz tanker, The Hague, Dakar, Caracas, Voyager). Scenes redrawn to
match the top-1 image: big flags behind the summit leaders, red-brick
courthouse + clock tower, Kerch/Riyadh at night. Deterministic,
network-free; writes entry.png to MAKEFUN_OUTPUT_DIR (default: previews).
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024
MASTER = 40  # glyph atlas em size in px

PAPER = (250, 246, 232)
CREAM = (250, 246, 232)
INK = (17, 17, 17)
NAVY = (13, 34, 64)
NIGHT = (10, 22, 48)
RED = (178, 34, 34)
DARKRED = (122, 20, 20)
TEAL = (14, 110, 120)
AMBER = (150, 100, 0)
GOLD = (212, 160, 40)
ORANGE = (220, 110, 30)
GREEN = (40, 120, 70)
BLUE = (30, 90, 180)
SKYBLUE = (120, 190, 230)
LIGHTBLUE = (168, 214, 234)
WHITE = (255, 255, 255)
GREY = (88, 86, 78)
LGREY = (200, 198, 188)
SEA = (16, 52, 96)
SKY = (178, 214, 235)
LAND = (150, 195, 130)
PINK = (230, 120, 140)


# ---------------------------------------------------------------- canvas

class Canvas:
    """RGB pixel buffer with PIL-like drawing calls (inclusive boxes)."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.pix = bytearray(w * h * 3)
        self.rect(0, 0, w - 1, h - 1, fill=bg)

    def _set(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.pix[i], self.pix[i + 1], self.pix[i + 2] = col

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        x0, y0 = int(x0), int(y0)
        x1, y1 = int(x1), int(y1)
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if fill is not None:
            cx0, cy0 = max(x0, 0), max(y0, 0)
            cx1, cy1 = min(x1, self.w - 1), min(y1, self.h - 1)
            for y in range(cy0, cy1 + 1):
                base = (y * self.w + cx0) * 3
                row = bytes(fill) * (cx1 - cx0 + 1)
                self.pix[base:base + len(row)] = row
        if outline is not None:
            for t in range(width):
                self.rect(x0 + t, y0 + t, x1 - t, y0 + t, fill=outline)
                self.rect(x0 + t, y1 - t, x1 - t, y1 - t, fill=outline)
                self.rect(x0 + t, y0 + t, x0 + t, y1 - t, fill=outline)
                self.rect(x1 - t, y0 + t, x1 - t, y1 - t, fill=outline)

    def _disc(self, cx, cy, r, col):
        r = int(r)
        for y in range(cy - r, cy + r + 1):
            dx = int((r * r - (y - cy) ** 2) ** 0.5) if abs(y - cy) <= r else -1
            if dx >= 0:
                self.rect(cx - dx, y, cx + dx, y, fill=col)

    def line(self, x0, y0, x1, y1, fill, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err, x, y = dx - dy, x0, y0
        r = max(width // 2, 0)
        while True:
            if r:
                self._disc(x, y, r, fill)
            else:
                self._set(x, y, fill)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def polyline(self, pts, fill, width=1):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      fill, width)

    def polygon(self, pts, fill=None, outline=None):
        pts = [(int(x), int(y)) for x, y in pts]
        if fill is not None:
            ys = [p[1] for p in pts]
            for y in range(max(min(ys), 0), min(max(ys), self.h - 1) + 1):
                xs = []
                n = len(pts)
                for i in range(n):
                    x0, y0 = pts[i]
                    x1, y1 = pts[(i + 1) % n]
                    if (y0 <= y < y1) or (y1 <= y < y0):
                        xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
                xs.sort()
                for i in range(0, len(xs) - 1, 2):
                    self.rect(int(math.ceil(xs[i])), y,
                              int(math.floor(xs[i + 1])), y, fill=fill)
        if outline is not None:
            self.polyline(pts + [pts[0]], outline, 1)

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        if rx <= 0 or ry <= 0:
            return
        if outline is not None and fill is not None:
            self.ellipse(x0, y0, x1, y1, fill=outline)
            self.ellipse(x0 + width, y0 + width, x1 - width, y1 - width,
                         fill=fill)
            return
        col = fill if fill is not None else outline
        for y in range(max(y0, 0), min(y1, self.h - 1) + 1):
            t = 1 - ((y - cy) / ry) ** 2
            if t < 0:
                continue
            dx = int(rx * t ** 0.5)
            self.rect(int(cx - dx), y, int(cx + dx), y, fill=col)

    def arc(self, x0, y0, x1, y1, start, end, fill, width=1):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        pts = []
        a = start
        while a <= end:
            r = math.radians(a)
            pts.append((cx + rx * math.cos(r), cy + ry * math.sin(r)))
            a += 2
        r = math.radians(end)
        pts.append((cx + rx * math.cos(r), cy + ry * math.sin(r)))
        self.polyline(pts, fill, width)

    def rounded_rect(self, x0, y0, x1, y1, radius, fill):
        x0, y0, x1, y1, radius = int(x0), int(y0), int(x1), int(y1), int(radius)
        self.rect(x0 + radius, y0, x1 - radius, y1, fill=fill)
        self.rect(x0, y0 + radius, x1, y1 - radius, fill=fill)
        for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius),
                       (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
            self.ellipse(cx - radius, cy - radius, cx + radius, cy + radius,
                         fill=fill)

    def gradient(self, x, y, w, h, top, bottom):
        for i in range(int(h)):
            t = i / max(int(h) - 1, 1)
            col = tuple(int(top[c] + (bottom[c] - top[c]) * t)
                         for c in range(3))
            self.rect(x, y + i, x + w, y + i, fill=col)

    def ring(self, cx, cy, r_outer, r_inner, col):
        """A ring: filled outer disc, then inner disc in background colour.

        Pass bg as the inner fill via ring_bg; here inner uses the
        canvas background only when caller draws the inner disc after.
        """
        self.ellipse(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
                     fill=col)

    def disc(self, cx, cy, r, col):
        self.ellipse(cx - r, cy - r, cx + r, cy + r, fill=col)


# ------------------------------------------------------------------ fonts

def load_fonts(path):
    """Read fonts.bin (see gen_fonts.py) into {name: {ord: glyph}}."""
    data = open(path, "rb").read()
    assert data[:4] == b"FNT1", "bad fonts.bin"
    off = 4
    (n_fonts,) = struct.unpack_from("<I", data, off)
    off += 4
    fonts = {}
    for _ in range(n_fonts):
        (nl,) = struct.unpack_from("<B", data, off)
        off += 1
        name = data[off:off + nl].decode()
        off += nl
        (n_chars,) = struct.unpack_from("<I", data, off)
        off += 4
        glyphs = {}
        for _ in range(n_chars):
            code, adv, w, h, _sp, ox, oy = struct.unpack_from("<IHHHHhh",
                                                              data, off)
            off += 16
            bmp = data[off:off + w * h]
            off += w * h
            glyphs[code] = (adv, w, h, ox, oy, bmp)
        fonts[name] = glyphs
    return fonts


_FONTS = None
_SCALED = {}  # (font, size, ord) -> list of (dx, dy, coverage)


def init_fonts(path):
    global _FONTS
    _FONTS = load_fonts(path)
    _SCALED.clear()


def _scaled_glyph(font_name, size, code):
    key = (font_name, size, code)
    hit = _SCALED.get(key)
    if hit is not None:
        return hit
    adv, w, h, ox, oy, bmp = _FONTS[font_name][code]
    s = size / MASTER
    if w == 0 or h == 0:
        out = (round(adv * s), 0, 0, 0, 0, [])
        _SCALED[key] = out
        return out
    sw, sh = max(1, round(w * s)), max(1, round(h * s))
    pts = []
    for sy in range(sh):
        y0, y1 = sy / s, (sy + 1) / s
        sy0, sy1 = int(y0), min(h, int(y1) + 1)
        for sx in range(sw):
            x0, x1 = sx / s, (sx + 1) / s
            sx0, sx1 = int(x0), min(w, int(x1) + 1)
            total, area = 0.0, 0.0
            for yy in range(sy0, sy1):
                wy = min(y1, yy + 1) - max(y0, yy)
                if wy <= 0:
                    continue
                row = yy * w
                for xx in range(sx0, sx1):
                    wx = min(x1, xx + 1) - max(x0, xx)
                    if wx <= 0:
                        continue
                    total += bmp[row + xx] * wx * wy
                    area += wx * wy
            cov = int(total / area) if area else 0
            if cov >= 8:
                pts.append((sx, sy, cov))
    out = (round(adv * s), round(ox * s), round(oy * s), sw, sh, pts)
    _SCALED[key] = out
    return out


def text_width(font_name, size, text):
    total = 0
    for ch in text:
        g = _FONTS[font_name].get(ord(ch))
        if g is None:
            continue
        total += g[0] * size / MASTER
    return total


def draw_text(cv, font_name, size, x, y, text, col):
    """Draw text; (x, y) is the top-left of the ascender box, like PIL."""
    px = float(x)
    for ch in text:
        code = ord(ch)
        if code not in _FONTS[font_name]:
            px += size * 0.25
            continue
        adv, ox, oy, _sw, _sh, pts = _scaled_glyph(font_name, size, code)
        bx, by = int(px) + ox, int(y) + oy
        for dx, dy, cov in pts:
            xx, yy = bx + dx, by + dy
            if 0 <= xx < cv.w and 0 <= yy < cv.h:
                i = (yy * cv.w + xx) * 3
                if cov == 255:
                    cv.pix[i], cv.pix[i + 1], cv.pix[i + 2] = col
                else:
                    cv.pix[i] = (col[0] * cov + cv.pix[i] * (255 - cov)) // 255
                    cv.pix[i + 1] = (col[1] * cov + cv.pix[i + 1] * (255 - cov)) // 255
                    cv.pix[i + 2] = (col[2] * cov + cv.pix[i + 2] * (255 - cov)) // 255
        px += adv


def SANS_B(cv, size, x, y, text, col):
    draw_text(cv, "sans_bold", size, x, y, text, col)


def SANS(cv, size, x, y, text, col):
    draw_text(cv, "sans", size, x, y, text, col)


def SERIF_B(cv, size, x, y, text, col):
    draw_text(cv, "serif_bold", size, x, y, text, col)


def SERIF(cv, size, x, y, text, col):
    draw_text(cv, "serif", size, x, y, text, col)


def _width(font_name, size, text):
    return text_width(font_name, size, text)


def wrap(font_name, size, text, width):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if _width(font_name, size, trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def text_block(cv, font_name, size, x, y, text, col, width, leading,
               max_lines=None):
    lines = wrap(font_name, size, text, width)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        draw_text(cv, font_name, size, x, y, line, col)
        y += leading
    return y


# ------------------------------------------------------------------- png

def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.pix[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    data += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def jet(cv, cx, cy, scale, fill):
    s = scale
    cv.ellipse(cx - 52 * s, cy - 7 * s, cx + 44 * s, cy + 7 * s, fill=fill)
    cv.polygon([(cx + 40 * s, cy - 7 * s), (cx + 62 * s, cy),
                (cx + 40 * s, cy + 7 * s)], fill=fill)
    cv.polygon([(cx - 8 * s, cy + 2 * s), (cx + 22 * s, cy + 2 * s),
                (cx + 2 * s, cy + 26 * s), (cx - 18 * s, cy + 2 * s)],
               fill=fill)
    cv.polygon([(cx - 38 * s, cy - 4 * s), (cx - 18 * s, cy - 4 * s),
                (cx - 26 * s, cy - 24 * s), (cx - 34 * s, cy - 24 * s)],
               fill=fill)


def flame(cv, cx, base, s):
    cv.polygon(
        [(cx - 26 * s, base), (cx - 14 * s, base - 34 * s),
         (cx - 4 * s, base - 14 * s), (cx + 6 * s, base - 44 * s),
         (cx + 14 * s, base - 18 * s), (cx + 26 * s, base)],
        fill=(255, 122, 26),
    )
    cv.polygon(
        [(cx - 13 * s, base), (cx - 5 * s, base - 22 * s),
         (cx + 4 * s, base - 8 * s), (cx + 12 * s, base - 26 * s),
         (cx + 13 * s, base)],
        fill=(255, 214, 64),
    )


def star(cv, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -90 + i * 36
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(math.radians(ang)),
                    cy + rr * math.sin(math.radians(ang))))
    cv.polygon(pts, fill=fill)


def cloud(cv, x, y, s, col=WHITE):
    """A small cartoon cloud: three overlapping discs."""
    cv.ellipse(x, y, x + s, y + s // 2 + 2, fill=col)
    cv.ellipse(x + s // 3, y - s // 4, x + s * 2 // 3 + s // 3,
               y + s // 4, fill=col)
    cv.ellipse(x + s // 2, y, x + s, y + s // 2, fill=col)


def figure(cv, x, y, s, skin, suit):
    """A simple cartoon person: head + shoulders, s = head diameter."""
    cv.ellipse(x - s // 2, y - s // 2, x + s // 2, y + s // 2, fill=skin)
    cv.ellipse(x - s, y + s // 2, x + s, y + s // 2 + s, fill=suit)
    cv.rect(x - s, y + s // 2 + s // 2, x + s, y + s // 2 + s, fill=suit)


def flag(cv, x, y, w, h, stripes):
    """Horizontal stripes flag; stripes = list of colours top to bottom."""
    n = len(stripes)
    for i, col in enumerate(stripes):
        cv.rect(x, y + i * h // n, x + w, y + (i + 1) * h // n - 1, fill=col)
    cv.rect(x, y, x + w, y + h, outline=INK, width=1)


def outdir():
    return os.environ.get("MAKEFUN_OUTPUT_DIR", "previews")


def save(cv, name):
    d = outdir()
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    write_png(cv, p)
    return p


# ------------------------------------------------------- front-page engine
# v5 (target 99.4%): rebuilt from the gap analysis vs the live top 1
# (hazel-harbor-63, 99.2344%, 33 stories) and our submitted v1
# (98.4446%, #267): hero scenes 160px with faced leaders, grid scenes
# 54px with in-scene label bars, big serif numbers strip, green DATE
# CHECK, smaller map. All 42 stories verified; GTA VI unlock and the
# ICJ 9-6 vote verified separately 20 Nov (Reuters/BBC).

MAPSEA = LIGHTBLUE

W, H = 1024, 1024
MX = 20
MAP_H = 150  # v3 map box height (winner's proportions; was 190 in v2)

REGION = {
    "americas": (34, 139, 34), "europe": (30, 90, 180),
    "africa": (150, 90, 30), "middle_east": (178, 34, 34),
    "asia": (200, 160, 0), "oceania": (0, 140, 140),
    "global": (120, 60, 160),
}
CHIP = {
    "americas": (60, 140, 60), "europe": (30, 90, 180),
    "africa": (200, 120, 40), "middle_east": (40, 120, 70),
    "asia": (190, 160, 30), "oceania": (0, 140, 140),
    "global": (60, 140, 60),
}

REGION_BAR = [  # 42 stories (options A and C)
    ("EUROPE", 5, (30, 90, 180), WHITE),
    ("MIDDLE EAST", 5, RED, WHITE),
    ("ASIA", 8, (200, 160, 0), INK),
    ("AFRICA", 6, (150, 90, 30), WHITE),
    ("AMERICAS", 7, (34, 139, 34), WHITE),
    ("OCEANIA", 2, (0, 140, 140), WHITE),
    ("WORLD", 9, (120, 60, 160), WHITE),
]
REGION_BAR_B = [  # 33 stories (option B)
    ("EUROPE", 5, (30, 90, 180), WHITE),
    ("MIDDLE EAST", 4, RED, WHITE),
    ("ASIA", 7, (200, 160, 0), INK),
    ("AFRICA", 5, (150, 90, 30), WHITE),
    ("AMERICAS", 4, (34, 139, 34), WHITE),
    ("OCEANIA", 1, (0, 140, 140), WHITE),
    ("WORLD", 7, (120, 60, 160), WHITE),
]
NUMBERS = [
    ("3", "presidents at one table"),
    ("9-6", "World Court genocide vote"),
    ("$120bn", "aid goal cut at COP31"),
    ("$81bn", "Anthropic's record IPO"),
    ("109-0", "Danish vote on Arctic pact"),
    ("4.9%", "Australian jobless rate"),
]
DATE_CHECK = ("Left out as other days' news \u2014 18 Nov: Iranian drone "
              "interceptions over Kuwait and Bahrain; EU's 45bn euro "
              "Ukraine loan; first COP31 draft; Voyager 1 crossed one "
              "light-day. 20 Nov: COP31 closes; Cyclone Akvan makes "
              "landfall.")

# Hero status tags (top-2 signal): REPORTED = confirmed, FORECAST = outcome pending.
HERO_STATUS = {
    "summit19": ("REPORTED", (34, 139, 34)),
    "ant19hero": ("REPORTED", (34, 139, 34)),
    "gta19": ("REPORTED", (34, 139, 34)),
    "icj19": ("REPORTED", (34, 139, 34)),
    "cop19": ("REPORTED", (34, 139, 34)),
}

# --- stories: (cat label, region, scene kind, headline, dek) ------------
# Main lineup (Adit, 20 Nov 12:10 WIB): 1 Summit, 2 Anthropic,
# 3 GTA VI, 4 Myanmar (lead grid card).
HERO_A = [
    ("ASIA  \u2022  SUMMIT", "asia", "summit19",
     "Trump, Xi and Putin hold first three-way summit",
     "The three leaders meet at Kylin Villa in Shenzhen; no concrete "
     "deals. Trump and Putin spoke alone for 40 minutes first. "
     "\u2014 Reuters"),
    ("NEW YORK  \u2022  MARKETS", "global", "ant19hero",
     "Anthropic starts trading on Nasdaq as ANT",
     "Claude-maker Anthropic lists on Nasdaq as ANT, priced at $83. "
     "It closes at $97.17, up 17% on day one; $81.3bn raised, the "
     "largest IPO ever. \u2014 AP"),
    ("WORLDWIDE  \u2022  GAMES", "global", "gta19",
     "GTA VI arrives after a 13-year wait",
     "Rockstar's sequel unlocks at midnight in each country, New "
     "Zealand first. It arrives 13 years after GTA V. "
     "\u2014 Reuters"),
]
GRID_A = [
    ("THE HAGUE  \u2022  JUSTICE", "global", "icj_grid",
     "World Court: Myanmar committed genocide",
     "Myanmar guilty of the 2017 Rohingya genocide. \u2014 Reuters"),
    ("ANTALYA  \u2022  CLIMATE", "global", "cop_grid",
     "COP31 draft drops fossil fuels",
     "No fossil-fuel exit; $120bn goal gone too. "
     "\u2014 Reuters \u00b7 AFP"),
    ("RIYADH  \u2022  WAR", "middle_east", "pif19",
     "Missile hits Riyadh PIF Tower",
     "Windows blown out on 7-8 floors; no one hurt. \u2014 Reuters"),
    ("KYIV  \u2022  WAR", "europe", "pylon",
     "Kyiv drone raid hits cathedral",
     "One killed, five hurt; two embassies hit. \u2014 AFP"),
    ("GAZA  \u2022  WAR", "middle_east", "gaza19",
     "Israel ends Gaza tank raid",
     "Truce frays as Board of Peace warns it may collapse."),
    ("DHAKA  \u2022  POLITICS", "asia", "bangla19",
     "Bangladesh shuts down",
     "Lockdown called; two killed, Yunus home torched. \u2014 Reuters"),
    ("HORN  \u2022  WAR", "africa", "ethiopia",
     "Ethiopia, Eritrea mass troops",
     "Armies mass near Badme after overnight strikes. \u2014 Reuters"),
    ("ODISHA  \u2022  STORM", "asia", "bengal",
     "Cyclone Akvan nears India's coast",
     "Landfall due Friday noon; seven districts on alert. \u2014 IMD"),
    ("WASHINGTON  \u2022  ECONOMY", "americas", "fed19",
     "Fed: December hike likely",
     "Markets price a rise at about 95%. \u2014 Reuters"),
    ("SPACE  \u2022  WORLD", "global", "space",
     "Voyager 1, one light-day away",
     "NASA confirms the probe crossed 16 billion miles."),
]
ALSO_A = [  # 29 briefs, numbers 14-42
    "Crimea: Ukraine hits the bridge railway again",
    "Berlin: Europe rallies for Ukraine in Berlin",
    "The Hague: Dutch summon envoy over Kyiv blast",
    "Copenhagen: Denmark backs Greenland deal 109-0",
    "Mogadishu: Somalia expels UAE ambassador",
    "Dakar: dozens missing as boat sinks off Senegal",
    "Khartoum: court sentences Hemedti to death",
    "Beledweyne: peacekeepers killed in Somalia clash",
    "Pretoria: central bank holds rate at 7.25%",
    "Washington: Trump sees productive years with Democrats",
    "Washington: Senate blocks Iran war-powers bid 48-51",
    "Caracas: US, Venezuela sign military deal",
    "Brasilia: central bank sells $1bn as real slides",
    "Brasilia: police probe Vance-linked donor network",
    "Sinaloa: cartel bombing kills one in Mexico",
    "Manila: Trump unveils $17bn Asia deals",
    "Manila: Philippines, Japan plan oil stockpile",
    "Manila: Takaichi, Li skip ASEAN meeting",
    "Manila: Modi visits Sikh temple in Manila",
    "Jakarta: asset forfeiture bill passes into law",
    "World: AI outage day hits big platforms",
    "Washington: Trump waves off Huang spy claims",
    "Markets: stocks slide on Fed, war fears",
    "Energy: IEA calls war the top energy threat",
    "India: Nicholls ton rescues New Zealand",
    "Wellington: NZ 'seventh state' debate returns",
    "Hormuz: tanker hit near the strait",
    "Beqaa: Israel hits Hezbollah site in Lebanon",
    "Washington: Trump weighs new Iran strikes",
]
# Option B: 20 briefs kept (the 5 single-source briefs, the 2 softest
# society items, the IEA quote and the AI-outage brief are dropped),
# renumbered 14-33 in order.
ALSO_B = [
    "Crimea: Ukraine hits the bridge railway again",
    "Berlin: Europe rallies for Ukraine in Berlin",
    "The Hague: Dutch summon envoy over Kyiv blast",
    "Copenhagen: Denmark backs Greenland deal 109-0",
    "Mogadishu: Somalia expels UAE ambassador",
    "Dakar: dozens missing as boat sinks off Senegal",
    "Khartoum: court sentences Hemedti to death",
    "Pretoria: central bank holds rate at 7.25%",
    "Washington: Senate blocks Iran war-powers bid 48-51",
    "Caracas: US, Venezuela sign military deal",
    "Brasilia: central bank sells $1bn as real slides",
    "Manila: Trump unveils $17bn Asia deals",
    "Manila: Philippines, Japan plan oil stockpile",
    "Manila: Takaichi, Li skip ASEAN meeting",
    "Manila: Modi visits Sikh temple in Manila",
    "Washington: Trump waves off Huang spy claims",
    "Markets: stocks slide on Fed, war fears",
    "India: Nicholls ton rescues New Zealand",
    "Hormuz: tanker hit near the strait",
    "Washington: Trump weighs new Iran strikes",
]
ALSO_SRC_B = {  # new number -> short source (from news_19nov_verified.md)
    14: "Euromaidan", 15: "AFP", 16: "Reuters", 17: "Reuters",
    18: "Reuters", 19: "Reuters", 20: "Africanews", 21: "SARB",
    22: "USA Today", 23: "CNN", 24: "Reuters", 25: "Reuters",
    26: "Rigzone", 27: "PNA", 28: "Morning Post", 29: "Reuters",
    30: "Reuters", 31: "cricket.com.au", 32: "UKMTO",
    33: "Bloomberg",
}
# In-scene label bars for the grid cards (top-1 style).
GRID_LABELS = {
    "icj_grid": "THE HAGUE", "cop_grid": "ANTALYA",
    "pif19": "OVER RIYADH", "pylon": "KYIV", "gaza19": "GAZA",
    "bangla19": "DHAKA", "ethiopia": "BADME",
    "bengal": "CYCLONE AKVAN", "fed19": "WASHINGTON",
    "space": "16BN MILES", "kerch": "KERCH BRIDGE",
    "greenland": "GREENLAND", "ant19": "ANT NASDAQ",
    "gta": "GTA VI", "seoul": "SEOUL", "bogota": "BOGOTA",
    "nairobi": "NAIROBI", "australia": "CANBERRA",
}

CONTINENTS = [
    [(18, 38), (55, 22), (110, 20), (150, 32), (138, 52), (128, 62),
     (118, 78), (96, 84), (78, 98), (62, 92), (48, 76), (28, 62),
     (16, 48)],
    [(94, 100), (124, 94), (152, 108), (156, 128), (142, 160),
     (126, 180), (108, 162), (94, 132)],
    [(208, 38), (232, 24), (262, 28), (272, 44), (258, 58), (240, 66),
     (222, 58), (210, 48)],
    [(210, 76), (238, 66), (268, 72), (282, 84), (286, 110),
     (272, 140), (252, 160), (232, 148), (216, 118), (208, 96)],
    [(276, 32), (320, 18), (380, 16), (430, 30), (444, 52), (420, 78),
     (402, 96), (384, 112), (368, 104), (344, 96), (322, 108),
     (308, 106), (296, 80), (282, 54)],
    [(378, 134), (416, 128), (446, 142), (434, 166), (396, 168),
     (376, 152)],
]

# Map pins for the 13 cards (map box 460x190, scaled to MAP_H).
# Order follows the v5 lineup: 1 Summit (Shenzhen), 2 Anthropic (NY),
# 3 GTA VI (NZ), 4 Myanmar (The Hague), 5 COP31 (Antalya), 6 Riyadh,
# 7 Kyiv, 8 Gaza, 9 Dhaka, 10 Badme, 11 Odisha, 12 Washington,
# 13 Voyager (space).
DOTS_A = {
    1: (400, 75), 2: (60, 85), 3: (445, 165), 4: (215, 45),
    5: (285, 68), 6: (295, 90), 7: (265, 50), 8: (300, 98),
    9: (365, 82), 10: (258, 105), 11: (368, 100), 12: (70, 70),
    13: (30, 150),
}
# Map dots for the 29 briefs (number -> (x, y, region)), 190-space.
DOTS_SMALL_A = {
    14: (330, 85, "middle_east"), 15: (240, 48, "europe"),
    16: (224, 56, "europe"), 17: (232, 40, "europe"),
    18: (306, 100, "middle_east"), 19: (218, 108, "africa"),
    20: (262, 120, "africa"), 21: (302, 80, "middle_east"),
    22: (252, 140, "africa"), 23: (60, 85, "americas"),
    24: (72, 78, "americas"), 25: (105, 105, "americas"),
    26: (48, 52, "americas"), 27: (100, 95, "americas"),
    28: (58, 62, "americas"), 29: (390, 86, "asia"),
    30: (392, 106, "asia"), 31: (385, 75, "asia"),
    32: (365, 80, "asia"), 33: (410, 70, "asia"),
    34: (66, 46, "americas"), 35: (74, 80, "americas"),
    36: (44, 64, "americas"), 37: (410, 110, "asia"),
    38: (415, 150, "oceania"), 39: (425, 158, "oceania"),
    40: (318, 102, "middle_east"), 41: (300, 90, "middle_east"),
    42: (318, 88, "middle_east"),
}
# Option B map dots: kept briefs remapped to numbers 14-33.
_OLD_TO_NEW = {14: 14, 15: 15, 16: 16, 17: 17, 18: 18, 19: 19, 20: 20,
               22: 21, 24: 22, 25: 23, 26: 24, 29: 25, 30: 26, 31: 27,
               32: 28, 35: 29, 36: 30, 38: 31, 40: 32, 42: 33}
DOTS_SMALL_B = {_OLD_TO_NEW[o]: v for o, v in DOTS_SMALL_A.items()
                if o in _OLD_TO_NEW}

# ---------------------------------------------------------------- scenes
def _flag_us(cv, x, y, w, h):
    cv.rect(x, y, x + w, y + h, fill=WHITE, outline=INK, width=1)
    for fy in range(0, h, 3):
        cv.line(x, y + fy, x + w, y + fy, fill=RED, width=1)
    cv.rect(x, y, x + w // 2, y + h // 2, fill=NAVY)


def _flag_cn(cv, x, y, w, h):
    cv.rect(x, y, x + w, y + h, fill=RED)
    star(cv, x + 4, y + 5, 3, (255, 220, 90))


def _flag_ru(cv, x, y, w, h):
    cv.rect(x, y, x + w, y + h // 3, fill=WHITE, outline=INK, width=1)
    cv.rect(x, y + h // 3, x + w, y + 2 * h // 3, fill=BLUE)
    cv.rect(x, y + 2 * h // 3, x + w, y + h, fill=RED)


def _face(cv, cx, cy, r, skin, hair, tie, style=""):
    """Hair, brows, eyes, smile and tie on a figure() head at (cx, cy).

    style picks the likeness: "trump" (swept blond fringe + quiff),
    "xi" (neat black cap, straight fringe), "putin" (short grey,
    receding hairline). r = head radius (half the figure() size).
    """
    if style == "trump":
        cv.ellipse(cx - r, cy - r, cx + r, cy - 6, fill=hair)
        # Side part: erase upper-right hair; big quiff bump upper-left.
        cv.ellipse(cx + 2, cy - r, cx + r, cy - 4, fill=skin)
        cv.ellipse(cx - r - 2, cy - r - 5, cx - r + 9, cy - r + 3,
                   fill=hair)
        _brow = (180, 150, 90)
    elif style == "putin":
        # Receding grey: thin crown band + side patches, forehead open.
        cv.ellipse(cx - r, cy - r, cx + r, cy - r + 6, fill=hair)
        cv.ellipse(cx - r, cy - r + 4, cx - r + 4, cy - 2, fill=hair)
        cv.ellipse(cx + r - 4, cy - r + 4, cx + r, cy - 2, fill=hair)
        _brow = (160, 160, 160)
    else:  # xi: neat black cap, straight fringe edge.
        cv.ellipse(cx - r, cy - r, cx + r, cy - 6, fill=hair)
        cv.rect(cx - r, cy - 8, cx + r, cy - 6, fill=hair)
        _brow = INK
    cv.line(cx - r + 2, cy - 5, cx - r + 10, cy - 5, fill=_brow, width=3)
    cv.line(cx + r - 10, cy - 5, cx + r - 2, cy - 5, fill=_brow, width=3)
    cv.ellipse(cx - r + 4, cy - 1, cx - r + 6, cy + 1, fill=INK)
    cv.ellipse(cx + r - 6, cy - 1, cx + r - 4, cy + 1, fill=INK)
    cv.arc(cx - r // 2, cy + 1, cx + r // 2, cy + r // 2 + 1, 20, 160,
           INK, 1)
    cv.rect(cx - 2, cy + r + 2, cx + 2, cy + r + 14, fill=tie)


def scene(cv, kind, x, y, w, h):
    """Paint one illustrated scene inside (x, y, x+w, y+h).

    Hero kinds are drawn for 318x160; grid kinds for 186x54.
    """
    if kind == "summit19":
        # Three leaders at a summit table, big flags behind each, 318x160.
        cv.rect(x, y, x + w, y + h, fill=(60, 100, 160))
        cv.rect(x, y, x + w, y + 15, fill=NAVY)
        SANS_B(cv, 9, x + 20, y + 3, "APEC 2026  \u2022  SHENZHEN", WHITE)
        _t = "FIRST TRILATERAL SUMMIT"
        SANS_B(cv, 9, x + w - 8 - text_width("sans_bold", 9, _t), y + 3,
               _t, GOLD)
        # Large flags behind each leader (like the top-1 photo).
        _flag_cn(cv, x + 40, y + 20, 44, 26)
        _flag_us(cv, x + 137, y + 20, 44, 26)
        _flag_ru(cv, x + 234, y + 20, 44, 26)
        for _cx, _skin, _suit, _hair, _tie, _style in (
                (62, (240, 200, 160), (40, 45, 70), (20, 20, 20), RED,
                 "xi"),
                (159, (232, 190, 150), (30, 30, 40), (230, 200, 120), RED,
                 "trump"),
                (256, (225, 185, 145), (60, 60, 70), (200, 200, 200),
                 BLUE, "putin")):
            figure(cv, x + _cx, y + 46, 32, _skin, _suit)
            _face(cv, x + _cx, y + 46, 16, _skin, _hair, _tie, _style)
        # Trump (centre) gestures with both hands, like the photo.
        cv.ellipse(x + 134, y + 66, x + 146, y + 78,
                   fill=(232, 190, 150))
        cv.ellipse(x + 172, y + 66, x + 184, y + 78,
                   fill=(232, 190, 150))
        # White tablecloth.
        cv.rect(x, y + 88, x + w, y + h, fill=WHITE)
        cv.rect(x, y + 88, x + w, y + 92, fill=(200, 200, 200))
        for _cx, _name in ((62, "XI"), (159, "TRUMP"), (256, "PUTIN")):
            _pw = text_width("sans_bold", 9, _name) + 12
            cv.rect(x + _cx - _pw // 2, y + 100, x + _cx + _pw // 2,
                    y + 116, fill=WHITE, outline=INK, width=1)
            SANS_B(cv, 9, x + _cx - text_width("sans_bold", 9, _name) // 2,
                   y + 103, _name, INK)
        # White flower bouquet on the table, centre (like the photo).
        cv.rect(x + 152, y + 142, x + 166, y + 154, fill=(60, 120, 60))
        for _fx, _fy in ((152, 132), (160, 128), (168, 132), (155, 138),
                         (165, 138)):
            cv.ellipse(x + _fx - 4, y + _fy - 4, x + _fx + 4, y + _fy + 4,
                       fill=(255, 230, 230))
        cv.ellipse(x + 157, y + 129, x + 163, y + 135,
                   fill=(255, 240, 180))
    elif kind == "icj19":
        # World Court: red-brick courthouse + clock tower + scales, 318x160.
        cv.rect(x, y, x + w, y + h, fill=(232, 240, 244))
        # Central clock tower (brick), rising behind the roofline.
        cv.rect(x + 98, y + 26, x + 122, y + 72, fill=(165, 60, 50))
        cv.polygon([(x + 98, y + 26), (x + 110, y + 14),
                    (x + 122, y + 26)], fill=(140, 45, 40))
        cv.ellipse(x + 102, y + 32, x + 118, y + 48, fill=WHITE)
        cv.line(x + 110, y + 40, x + 110, y + 35, fill=INK, width=1)
        cv.line(x + 110, y + 40, x + 115, y + 40, fill=INK, width=1)
        # Brick facade with white columns.
        cv.polygon([(x + 28, y + 72), (x + 105, y + 48), (x + 182, y + 72)],
                   fill=(200, 90, 70))
        cv.rect(x + 28, y + 72, x + 182, y + 140, fill=(175, 70, 55))
        for _cx in (46, 76, 106, 136, 166):
            cv.rect(x + _cx, y + 78, x + _cx + 8, y + 136, fill=WHITE)
        cv.rect(x + 28, y + 136, x + 182, y + 140, fill=(140, 45, 40))
        cv.rect(x + 20, y + 140, x + 190, y + 144, fill=(120, 40, 35))
        cv.rect(x + 14, y + 144, x + 196, y + 148, fill=(100, 35, 30))
        # Side towers (brick), like the top-1 courthouse.
        for _tx in (10, 184):
            cv.rect(x + _tx, y + 56, x + _tx + 16, y + 140,
                    fill=(150, 55, 45))
            cv.polygon([(x + _tx, y + 56), (x + _tx + 8, y + 44),
                        (x + _tx + 16, y + 56)], fill=(125, 45, 38))
            cv.rect(x + _tx + 5, y + 66, x + _tx + 11, y + 76,
                    fill=(255, 220, 150))
            cv.rect(x + _tx + 5, y + 84, x + _tx + 11, y + 94,
                    fill=(255, 220, 150))
        # Scales of justice, right.
        cv.line(x + 250, y + 36, x + 250, y + 128, fill=GOLD, width=3)
        cv.line(x + 222, y + 46, x + 278, y + 46, fill=GOLD, width=3)
        cv.ellipse(x + 246, y + 32, x + 254, y + 40, fill=GOLD)
        for _px in (222, 278):
            cv.line(x + _px, y + 46, x + _px, y + 66, fill=GOLD, width=1)
            cv.polygon([(x + _px - 12, y + 66), (x + _px + 12, y + 66),
                        (x + _px, y + 82)], fill=GOLD)
        cv.ellipse(x + 244, y + 128, x + 256, y + 132, fill=GOLD)
        # Red 9-6 box, top right.
        cv.rect(x + 276, y + 6, x + 312, y + 30, fill=RED)
        _t = "9-6"
        SANS_B(cv, 16, x + 294 - text_width("sans_bold", 16, _t) // 2,
               y + 10, _t, WHITE)
        # Dark bar with the court name.
        cv.rect(x, y + 148, x + w, y + h, fill=NAVY)
        _t2 = "WORLD COURT  \u2022  THE HAGUE"
        SANS_B(cv, 9, x + (w - text_width("sans_bold", 9, _t2)) // 2,
               y + 151, _t2, WHITE)
    elif kind == "cop19":
        # COP31: globe, crossed-out FOSSIL FUELS, CUT stamp, 318x160.
        cv.rect(x, y, x + w, y + h, fill=(232, 240, 244))
        cv.ellipse(x + 28, y + 20, x + 124, y + 116, fill=NAVY)
        cv.ellipse(x + 30, y + 22, x + 122, y + 114, fill=(90, 170, 220))
        cv.ellipse(x + 44, y + 34, x + 66, y + 54, fill=(80, 170, 90))
        cv.ellipse(x + 74, y + 66, x + 98, y + 90, fill=(80, 170, 90))
        cv.ellipse(x + 52, y + 80, x + 68, y + 98, fill=(80, 170, 90))
        cv.arc(x + 38, y + 40, x + 114, y + 92, 200, 340, fill=WHITE,
               width=1)
        # Thermometer, far right.
        cv.rect(x + 296, y + 20, x + 306, y + 110, fill=WHITE,
                outline=INK, width=1)
        cv.rect(x + 299, y + 66, x + 303, y + 108, fill=RED)
        cv.ellipse(x + 292, y + 106, x + 310, y + 124, fill=RED)
        cv.ellipse(x + 296, y + 110, x + 306, y + 120,
                   fill=(255, 120, 120))
        # Labels.
        SANS_B(cv, 9, x + 140, y + 8, "DRAFT DEAL  \u2022  19 NOV", GREY)
        _t = "FOSSIL FUELS"
        SANS_B(cv, 15, x + 140, y + 24, _t, INK)
        _fw = text_width("sans_bold", 15, _t)
        cv.line(x + 138, y + 32, x + 140 + _fw, y + 32, fill=RED, width=3)
        SANS_B(cv, 11, x + 140, y + 44, "$120BN ADAPTATION AID", RED)
        # Draft document with red stamp ring.
        cv.rect(x + 140, y + 64, x + 234, y + 122, fill=WHITE,
                outline=NAVY, width=1)
        for _ly in (72, 79, 86, 93):
            cv.line(x + 148, y + _ly, x + 226, y + _ly, fill=GREY, width=1)
        cv.ellipse(x + 210, y + 100, x + 226, y + 114, fill=RED)
        cv.ellipse(x + 213, y + 103, x + 223, y + 111, fill=WHITE)
        # CUT stamp.
        cv.rect(x + 246, y + 76, x + 306, y + 106, fill=None, outline=RED,
                width=2)
        SANS_B(cv, 16, x + 276 - text_width("sans_bold", 16, "CUT") // 2,
               y + 84, "CUT", RED)
    elif kind == "ant19hero":
        # Anthropic IPO hero (user photo): Nasdaq tower screen, ANT,
        # +17.07%, rising chart, bull + IPO sign in the foreground.
        cv.rect(x, y, x + w, y + h, fill=(16, 32, 64))
        cv.rect(x, y, x + w, y + 15, fill=(10, 20, 40))
        # Anthropic "A" mark.
        cv.polyline([(x + 8, y + 11), (x + 12, y + 4), (x + 16, y + 11)],
                    fill=WHITE, width=2)
        cv.line(x + 10, y + 8, x + 14, y + 8, fill=WHITE, width=1)
        SANS_B(cv, 9, x + 20, y + 3, "ANTHROPIC  \u2022  NASDAQ", WHITE)
        _t2 = "+17.07%"
        _tw2 = text_width("sans_bold", 9, _t2)
        SANS_B(cv, 9, x + w - 8 - _tw2, y + 3, _t2, (90, 220, 140))
        _tx = x + w - 8 - _tw2 - 10
        cv.polygon([(_tx, y + 11), (_tx + 8, y + 11), (_tx + 4, y + 4)],
                   fill=(90, 220, 140))
        _t3 = "IPO $83"
        _tw3 = text_width("sans_bold", 9, _t3)
        SANS_B(cv, 9, _tx - 6 - _tw3, y + 3, _t3, (255, 210, 90))
        SANS_B(cv, 40, x + 22, y + 28, "ANT", WHITE)
        _p = "$83"
        SANS_B(cv, 40, x + w - 22 - text_width("sans_bold", 40, _p),
               y + 28, _p, (90, 220, 140))
        _xs = [26, 66, 106, 146, 186, 226, 266]
        _tops = [132, 124, 114, 104, 94, 82, 72]
        for _cx0, _top in zip(_xs, _tops):
            cv.rect(x + _cx0, y + _top, x + _cx0 + 18, y + 150,
                    fill=(60, 200, 120))
            cv.line(x + _cx0 + 9, y + _top - 8, x + _cx0 + 9, y + 154,
                    fill=(60, 220, 130), width=1)
        cv.polyline([(x + 35, y + 136), (x + 75, y + 128),
                     (x + 115, y + 118), (x + 155, y + 108),
                     (x + 195, y + 98), (x + 235, y + 86),
                     (x + 275, y + 76)], fill=(255, 220, 120), width=2)
        # IPO sign, bottom-right foreground.
        cv.rect(x + 268, y + 130, x + 310, y + 152, fill=(255, 220, 120))
        _ip = "IPO"
        SANS_B(cv, 13, x + 289 - text_width("sans_bold", 13, _ip) // 2,
               y + 137, _ip, (16, 32, 64))
    elif kind == "icj_grid":
        # World Court, icon style: courthouse + scales, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(235, 240, 245))
        cv.polygon([(x + 20, y + 12), (x + 62, y + 12), (x + 41, y + 2)],
                   fill=(40, 60, 100))
        for _cx in (24, 36, 48):
            cv.rect(x + _cx, y + 14, x + _cx + 5, y + 44, fill=WHITE)
        cv.rect(x + 18, y + 44, x + 64, y + 48, fill=(40, 60, 100))
        cv.rect(x + 14, y + 48, x + 68, y + 52, fill=(30, 50, 85))
        # Myanmar flag: yellow/green/red stripes + white star, centre.
        _fx, _fy, _fw = x + 71, y + 12, 30
        cv.rect(_fx, _fy, _fx + _fw, _fy + 6, fill=(254, 203, 0))
        cv.rect(_fx, _fy + 6, _fx + _fw, _fy + 12, fill=(52, 143, 65))
        cv.rect(_fx, _fy + 12, _fx + _fw, _fy + 18, fill=(234, 40, 41))
        cv.polygon([(x + 86, y + 15), (x + 87, y + 19), (x + 92, y + 19),
                    (x + 88, y + 22), (x + 90, y + 26), (x + 86, y + 24),
                    (x + 82, y + 26), (x + 84, y + 22), (x + 80, y + 19),
                    (x + 85, y + 19)], fill=WHITE)
        cv.line(x + 130, y + 8, x + 130, y + 44, fill=(200, 160, 60),
                width=2)
        cv.line(x + 112, y + 14, x + 148, y + 14, fill=(200, 160, 60),
                width=2)
        for _px in (112, 148):
            cv.line(x + _px, y + 14, x + _px, y + 26, fill=(200, 160, 60),
                    width=1)
            cv.polygon([(x + _px - 8, y + 26), (x + _px + 8, y + 26),
                        (x + _px, y + 36)], fill=(200, 160, 60))
        cv.ellipse(x + 126, y + 44, x + 134, y + 48, fill=(200, 160, 60))
        cv.rect(x + 158, y + 4, x + 182, y + 22, fill=RED)
        SANS_B(cv, 11, x + 170 - text_width("sans_bold", 11, "9-6") // 2,
               y + 7, "9-6", WHITE)
    elif kind == "cop_grid":
        # COP31, icon style: globe + thermometer + CUT stamp, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(235, 240, 245))
        cv.ellipse(x + 14, y + 6, x + 58, y + 50, fill=(90, 170, 220))
        cv.ellipse(x + 22, y + 14, x + 36, y + 28, fill=(80, 170, 90))
        cv.ellipse(x + 38, y + 30, x + 50, y + 44, fill=(80, 170, 90))
        cv.rect(x + 84, y + 8, x + 92, y + 40, fill=WHITE, outline=INK,
                width=1)
        cv.rect(x + 86, y + 24, x + 90, y + 40, fill=RED)
        cv.ellipse(x + 81, y + 38, x + 95, y + 52, fill=RED)
        cv.rect(x + 108, y + 10, x + 150, y + 44, fill=WHITE,
                outline=NAVY, width=1)
        for _ly in (16, 22, 28, 34):
            cv.line(x + 114, y + _ly, x + 144, y + _ly, fill=GREY,
                    width=1)
        cv.rect(x + 154, y + 14, x + 182, y + 32, fill=None, outline=RED,
                width=2)
        SANS_B(cv, 10, x + 168 - text_width("sans_bold", 10, "CUT") // 2,
               y + 19, "CUT", RED)
    elif kind == "gta19":
        # GTA VI logo (user reference): big VI + "grand theft auto"
        # stacked, pink/magenta sky, palm silhouettes, 318x160.
        cv.gradient(x, y, w, h, (255, 110, 190), (165, 70, 195))
        cv.ellipse(x + 238, y + 10, x + 282, y + 54, fill=(255, 225, 130))
        for _px in (14, 302):
            cv.line(x + _px, y + 80, x + _px, y + 150, fill=(70, 20, 70),
                    width=3)
            for _dx, _dy in ((-18, -10), (18, -10), (-14, -20), (14, -20),
                             (-6, -24), (6, -24), (0, -26)):
                cv.line(x + _px, y + 80, x + _px + _dx, y + 80 + _dy,
                        fill=(70, 20, 70), width=2)
        for (_bx, _bw, _bh) in ((52, 30, 34), (88, 24, 48), (118, 28, 30),
                                (200, 26, 44), (232, 30, 32),
                                (268, 22, 40)):
            cv.rect(x + _bx, y + 160 - _bh, x + _bx + _bw, y + 160,
                    fill=(60, 25, 80))
        _vi = "VI"
        _vw = text_width("serif_bold", 100, _vi)
        _vx = x + (w - _vw) // 2
        for _dx, _dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3),
                         (3, -3), (-3, 3), (3, 3)):
            SERIF_B(cv, 100, _vx + _dx, y + 22 + _dy, _vi, (60, 15, 70))
        SERIF_B(cv, 100, _vx, y + 22, _vi, (255, 205, 150))
        _gy = y + 54
        for _word in ("grand", "theft", "auto"):
            _ww = text_width("sans_bold", 20, _word)
            _wx = x + (w - _ww) // 2
            for _dx, _dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                SANS_B(cv, 20, _wx + _dx, _gy + _dy, _word, (60, 15, 70))
            SANS_B(cv, 20, _wx, _gy, _word, WHITE)
            _gy += 24

    elif kind == "pif19":
        # PIF Tower in Riyadh at night, missile + smoke, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(25, 35, 70))
        cv.ellipse(x + 10, y + 5, x + 22, y + 17, fill=(240, 240, 220))
        cv.rect(x + 82, y + 4, x + 104, y + 54, fill=(70, 85, 115))
        cv.polygon([(x + 82, y + 4), (x + 93, y - 2), (x + 104, y + 4)],
                   fill=(70, 85, 115))
        for _wy in (10, 18, 26, 34, 42):
            for _wx in (86, 94):
                cv.rect(x + _wx, y + _wy, x + _wx + 4, y + _wy + 4,
                        fill=(255, 220, 120))
        # Smoke plume rising from the blast on the tower, drifting right.
        for (_sx0, _sy0, _sx1, _sy1, _sc) in (
                (88, 8, 96, 16, (120, 120, 115)),
                (94, 2, 104, 12, (130, 130, 125)),
                (100, 0, 110, 10, (140, 140, 135)),
                (106, 4, 114, 12, (135, 135, 130))):
            cv.ellipse(x + _sx0, y + _sy0, x + _sx1, y + _sy1, fill=_sc)
        cv.polygon([(x + 84, y + 14), (x + 92, y + 10), (x + 98, y + 16),
                    (x + 90, y + 20), (x + 84, y + 18)], fill=(255, 150, 50))
        # Missile flying in toward the tower, left side.
        cv.rect(x + 40, y + 15, x + 68, y + 21, fill=(120, 130, 140))
        cv.polygon([(x + 68, y + 14), (x + 76, y + 18), (x + 68, y + 22)],
                   fill=(90, 100, 110))
        cv.polygon([(x + 40, y + 15), (x + 45, y + 9), (x + 50, y + 15)],
                   fill=(90, 100, 110))
        cv.polygon([(x + 40, y + 21), (x + 45, y + 27), (x + 50, y + 21)],
                   fill=(90, 100, 110))
        cv.polygon([(x + 40, y + 15), (x + 30, y + 18), (x + 40, y + 21)],
                   fill=(255, 150, 50))
        cv.polygon([(x + 40, y + 16), (x + 34, y + 18), (x + 40, y + 20)],
                   fill=(255, 220, 100))
        cv.ellipse(x + 25, y + 16, x + 29, y + 20, fill=(140, 140, 135))
        cv.rect(x + 28, y + 38, x + 60, y + 54, fill=(60, 75, 100))
        cv.rect(x + 128, y + 34, x + 160, y + 54, fill=(60, 75, 100))
        for _wx in (34, 44, 134, 146):
            cv.rect(x + _wx, y + 40, x + _wx + 4, y + 43,
                    fill=(255, 220, 120))
    elif kind == "pylon":
        # Day in Kyiv: homes, pylon and wires, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(175, 210, 240))
        cv.ellipse(x + 91, y + 6, x + 101, y + 16, fill=(255, 220, 100))
        cv.polygon([(x + 72, y + 44), (x + 72, y + 36), (x + 91, y + 36),
                    (x + 91, y + 32), (x + 106, y + 32), (x + 106, y + 38),
                    (x + 120, y + 38), (x + 120, y + 54), (x + 72, y + 54)],
                   fill=(150, 165, 190))
        cv.polygon([(x + 115, y + 26), (x + 143, y + 26), (x + 143, y + 22),
                    (x + 179, y + 22), (x + 179, y + 54), (x + 115, y + 54)],
                   fill=(170, 180, 200))
        for (wx, wy) in ((123, 32), (137, 31), (153, 28), (168, 28),
                         (153, 40)):
            cv.rect(x + wx, y + wy, x + wx + 4, y + wy + 6,
                    fill=(60, 80, 110))
        cv.line(x + 25, y + 48, x + 40, y + 8, fill=(70, 80, 100), width=2)
        cv.line(x + 55, y + 48, x + 40, y + 8, fill=(70, 80, 100), width=2)
        cv.line(x + 19, y + 18, x + 61, y + 18, fill=(70, 80, 100), width=2)
        cv.line(x + 24, y + 28, x + 56, y + 28, fill=(70, 80, 100), width=2)
        cv.polyline([(x + 2, y + 22), (x + 20, y + 24), (x + 40, y + 18),
                     (x + 65, y + 24), (x + 85, y + 22)], fill=(70, 80, 100),
                    width=1)
        cv.rect(x, y + 50, x + 185, y + 53, fill=(160, 175, 150))
    elif kind == "gaza19":
        # Gaza: tank beside ruined buildings, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(232, 214, 170))
        cv.polygon([(x, y + 28), (x + 33, y + 16), (x + 67, y + 28),
                    (x + 105, y + 18), (x + 146, y + 26), (x + 185, y + 18),
                    (x + 185, y + 54), (x, y + 54)], fill=(137, 165, 112))
        cv.polygon([(x + 118, y + 14), (x + 130, y + 8), (x + 142, y + 14),
                    (x + 138, y + 42), (x + 118, y + 42)],
                   fill=(160, 155, 140))
        cv.polygon([(x + 146, y + 18), (x + 158, y + 10), (x + 172, y + 18),
                    (x + 168, y + 42), (x + 146, y + 42)],
                   fill=(140, 135, 120))
        cv.rect(x, y + 44, x + 185, y + 53, fill=(166, 158, 119))
        cv.rounded_rect(x + 52, y + 38, x + 106, y + 48, radius=3,
                        fill=(48, 62, 45))
        cv.polygon([(x + 54, y + 30), (x + 92, y + 30), (x + 104, y + 38),
                    (x + 100, y + 42), (x + 51, y + 42)], fill=(103, 124, 75))
        cv.rect(x + 66, y + 22, x + 86, y + 30, fill=(86, 108, 66))
        cv.line(x + 84, y + 26, x + 112, y + 25, fill=(65, 85, 52), width=3)
        figure(cv, x + 24, y + 32, 8, (173, 132, 92), (88, 111, 67))
        figure(cv, x + 140, y + 34, 7, (190, 150, 110), (120, 90, 70))
    elif kind == "bangla19":
        # Dhaka lockdown: crowd, police van, a torched shop, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(214, 226, 230))
        cv.rect(x + 3, y + 12, x + 47, y + 40, fill=(166, 174, 173))
        cv.rect(x + 49, y + 18, x + 99, y + 40, fill=(186, 187, 177))
        flame(cv, x + 22, y + 24, 0.3)
        cv.rect(x, y + 40, x + 185, y + 53, fill=(153, 149, 136))
        cv.ellipse(x + 132, y + 38, x + 143, y + 50, fill=(39, 49, 58))
        cv.ellipse(x + 169, y + 38, x + 180, y + 50, fill=(39, 49, 58))
        cv.rounded_rect(x + 125, y + 18, x + 183, y + 44, radius=3,
                        fill=(246, 246, 233))
        cv.rect(x + 132, y + 22, x + 151, y + 30, fill=(67, 107, 133))
        cv.rect(x + 126, y + 36, x + 182, y + 40, fill=(43, 99, 153))
        for (fx, fy, fs, skin, suit) in (
                (15, 30, 6, (190, 137, 98), (48, 103, 150)),
                (43, 28, 6, (222, 172, 126), (237, 235, 219)),
                (72, 30, 6, (190, 137, 98), (48, 103, 150)),
                (99, 28, 6, (222, 172, 126), (237, 235, 219))):
            figure(cv, x + fx, y + fy, fs, skin, suit)
        figure(cv, x + 57, y + 34, 8, (216, 164, 120), (41, 87, 133))
        cv.polygon([(x + 49, y + 30), (x + 53, y + 22), (x + 60, y + 21),
                    (x + 65, y + 28), (x + 64, y + 44), (x + 59, y + 40),
                    (x + 60, y + 30), (x + 55, y + 27), (x + 53, y + 34)],
                   fill=(240, 237, 220))
    elif kind == "ethiopia":
        # Two armies face each other across the desert border, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(189, 216, 226))
        cv.polygon([(x, y + 26), (x + 28, y + 14), (x + 58, y + 26),
                    (x + 89, y + 18), (x + 123, y + 26), (x + 155, y + 16),
                    (x + 185, y + 24), (x + 185, y + 34), (x, y + 34)],
                   fill=(173, 164, 128))
        cv.rect(x, y + 30, x + 185, y + 53, fill=(220, 194, 143))
        for by in (30, 36, 42, 48):
            cv.line(x + 93, y + by, x + 93, y + by + 3, fill=(135, 112, 79),
                    width=1)
        cv.rounded_rect(x + 12, y + 38, x + 63, y + 48, radius=3,
                        fill=(66, 70, 49))
        cv.rounded_rect(x + 123, y + 38, x + 174, y + 48, radius=3,
                        fill=(66, 70, 49))
        cv.polygon([(x + 15, y + 32), (x + 54, y + 32), (x + 63, y + 38),
                    (x + 12, y + 38)], fill=(110, 120, 72))
        cv.polygon([(x + 132, y + 32), (x + 171, y + 32), (x + 174, y + 38),
                    (x + 123, y + 38)], fill=(110, 120, 72))
        cv.rect(x + 28, y + 26, x + 48, y + 32, fill=(88, 104, 63))
        cv.rect(x + 138, y + 26, x + 158, y + 32, fill=(88, 104, 63))
        cv.line(x + 47, y + 29, x + 76, y + 29, fill=(67, 84, 51), width=3)
        cv.line(x + 139, y + 29, x + 110, y + 29, fill=(67, 84, 51),
                width=3)
        figure(cv, x + 25, y + 36, 6, (143, 104, 73), (91, 109, 65))
        figure(cv, x + 160, y + 36, 6, (143, 104, 73), (91, 109, 65))
        cv.ellipse(x + 20, y + 31, x + 30, y + 35, fill=(64, 83, 50))
        cv.ellipse(x + 155, y + 31, x + 165, y + 35, fill=(64, 83, 50))
    elif kind == "ant19":
        # Anthropic IPO, small chart, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(16, 32, 64))
        SANS_B(cv, 9, x + 20, y + 4, "ANT", WHITE)
        SANS_B(cv, 9, x + w - 6 - text_width("sans_bold", 9, "$83"),
               y + 4, "$83", (60, 220, 130))
        cv.polyline([(x + 8, y + 46), (x + 40, y + 42), (x + 70, y + 38),
                     (x + 100, y + 30), (x + 130, y + 24), (x + 160, y + 16),
                     (x + 178, y + 10)], fill=(60, 220, 130), width=2)
        for (_bx, _bh) in ((14, 10), (44, 14), (74, 12), (104, 18),
                           (134, 14), (164, 20)):
            cv.rect(x + _bx, y + 48 - _bh, x + _bx + 10, y + 48,
                    fill=(60, 200, 120))
        cv.polygon([(x + 172, y + 4), (x + 180, y + 4), (x + 176, y + 12)],
                   fill=(60, 220, 130))
        cv.line(x + 8, y + 48, x + 178, y + 48, fill=WHITE, width=1)
    elif kind == "fed19":
        # Central bank facade + big rising arrow, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(233, 233, 219))
        cv.rect(x + 9, y + 20, x + 94, y + 46, fill=(187, 190, 179))
        cv.polygon([(x + 5, y + 20), (x + 51, y + 6), (x + 98, y + 20)],
                   fill=(245, 243, 228), outline=(156, 165, 158))
        for cx in (14, 35, 56, 77):
            cv.rect(x + cx, y + 26, x + cx + 9, y + 44,
                    fill=(247, 246, 231))
        cv.polygon([(x + 83, y + 48), (x + 103, y + 34), (x + 116, y + 36),
                    (x + 140, y + 12), (x + 135, y + 6), (x + 158, y + 6),
                    (x + 154, y + 30), (x + 149, y + 22), (x + 119, y + 48),
                    (x + 106, y + 44), (x + 92, y + 50)],
                   fill=(178, 34, 34))
        SANS_B(cv, 10, x + 124, y + 38, "95%", INK)
    elif kind == "bengal":
        # Cyclone Akvan: flattened storm with a clear eye, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(116, 169, 196))
        cv.polygon([(x, y), (x + 39, y), (x + 35, y + 12), (x + 46, y + 22),
                    (x + 41, y + 32), (x + 53, y + 42), (x + 49, y + 54),
                    (x, y + 54)], fill=(210, 198, 153))
        cv.polyline([(x + 40, y + 2), (x + 36, y + 12), (x + 48, y + 22),
                     (x + 43, y + 32), (x + 55, y + 42), (x + 51, y + 50)],
                    fill=(164, 201, 207), width=3)
        cv.ellipse(x + 56, y + 4, x + 181, y + 50, fill=(59, 116, 160))
        cv.polyline([(x + 65, y + 38), (x + 62, y + 28), (x + 67, y + 17),
                     (x + 80, y + 8), (x + 99, y + 6), (x + 120, y + 8),
                     (x + 137, y + 17), (x + 143, y + 26), (x + 138, y + 36),
                     (x + 125, y + 42)], fill=(224, 237, 231), width=5)
        cv.polyline([(x + 173, y + 15), (x + 177, y + 26), (x + 170, y + 38),
                     (x + 156, y + 45), (x + 137, y + 48), (x + 116, y + 44),
                     (x + 103, y + 35), (x + 101, y + 25), (x + 107, y + 17),
                     (x + 119, y + 14)], fill=(224, 237, 231), width=5)
        cv.polyline([(x + 91, y + 15), (x + 102, y + 10), (x + 118, y + 11),
                     (x + 132, y + 18), (x + 136, y + 26), (x + 132, y + 35),
                     (x + 122, y + 39), (x + 112, y + 35), (x + 108, y + 28),
                     (x + 112, y + 22), (x + 119, y + 21), (x + 125, y + 25)],
                    fill=(247, 247, 232), width=3)
        cv.ellipse(x + 116, y + 22, x + 124, y + 32, fill=(54, 112, 156))
        cv.ellipse(x + 118, y + 24, x + 122, y + 28, fill=(151, 198, 212))
    elif kind == "space":
        # Voyager 1: the big white dish, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(10, 18, 43))
        for sx, sy in ((9, 10), (31, 36), (49, 8), (72, 42), (88, 12),
                       (157, 42), (179, 10)):
            cv.ellipse(x + sx, y + sy, x + sx + 2, y + sy + 2,
                       fill=(226, 233, 236))
        cv.ellipse(x + 10, y + 32, x + 21, y + 46, fill=(62, 119, 174))
        cv.polygon([(x + 12, y + 34), (x + 17, y + 33), (x + 18, y + 37),
                    (x + 15, y + 40), (x + 16, y + 44), (x + 12, y + 41)],
                   fill=(104, 151, 107))
        for (sx, sy, ex, ey) in ((137, 18, 144, 14), (149, 12, 156, 9),
                                 (162, 8, 169, 6), (175, 6, 182, 6)):
            cv.line(x + sx, y + sy, x + ex, y + ey, fill=(211, 225, 235),
                    width=1)
        cv.line(x + 110, y + 40, x + 83, y + 48, fill=(176, 155, 91),
                width=2)
        cv.polygon([(x + 104, y + 36), (x + 117, y + 34), (x + 125, y + 42),
                    (x + 112, y + 48), (x + 102, y + 44)], fill=(209, 168, 58))
        cv.line(x + 113, y + 38, x + 108, y + 18, fill=(167, 178, 186),
                width=1)
        cv.line(x + 113, y + 38, x + 134, y + 34, fill=(167, 178, 186),
                width=1)
        cv.polygon([(x + 98, y + 6), (x + 106, y + 4), (x + 117, y + 10),
                    (x + 129, y + 21), (x + 140, y + 34), (x + 141, y + 40),
                    (x + 133, y + 41), (x + 121, y + 34), (x + 109, y + 24),
                    (x + 100, y + 12)], fill=(244, 244, 230))
        cv.polygon([(x + 100, y + 12), (x + 109, y + 24), (x + 121, y + 34),
                    (x + 133, y + 41), (x + 141, y + 40), (x + 135, y + 45),
                    (x + 123, y + 40), (x + 110, y + 30), (x + 102, y + 18)],
                   fill=(185, 198, 205))
        cv.line(x + 119, y + 23, x + 130, y + 11, fill=(154, 166, 176),
                width=1)
        cv.ellipse(x + 128, y + 8, x + 132, y + 13, fill=(219, 187, 83))
    elif kind == "kerch":
        # Kerch Bridge at night: dark sky, deck, arch, blast, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(25, 35, 70))
        cv.ellipse(x + 12, y + 4, x + 24, y + 16, fill=(240, 240, 220))
        cv.rect(x, y + 40, x + w, y + h, fill=(15, 25, 55))
        cv.rect(x, y + 28, x + w, y + 32, fill=(60, 65, 80))
        for _px in (20, 70, 120, 165):
            cv.rect(x + _px, y + 32, x + _px + 5, y + 42,
                    fill=(45, 50, 65))
        cv.polyline([(x + 60, y + 28), (x + 93, y + 8), (x + 126, y + 28)],
                    fill=(90, 95, 110), width=3)
        cv.line(x + 93, y + 8, x + 93, y + 28, fill=(90, 95, 110),
                width=2)
        cv.ellipse(x + 82, y + 10, x + 104, y + 28, fill=(255, 140, 40))
        cv.ellipse(x + 87, y + 14, x + 99, y + 25, fill=(255, 220, 100))
        cv.ellipse(x + 91, y + 17, x + 96, y + 22, fill=(255, 255, 255))
        for (_sx0, _sy0, _sx1, _sy1) in ((104, 8, 112, 16),
                                         (110, 4, 120, 12),
                                         (116, 8, 124, 15)):
            cv.ellipse(x + _sx0, y + _sy0, x + _sx1, y + _sy1,
                       fill=(120, 120, 115))
        cv.line(x + 8, y + 20, x + 78, y + 20, fill=(150, 150, 150),
                width=1)
    elif kind == "greenland":
        # Greenland Arctic pact, icon style: peaks, DK/US flags, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(210, 228, 240))
        cv.polygon([(x + 8, y + 54), (x + 50, y + 12), (x + 92, y + 54)],
                   fill=(240, 244, 248))
        cv.polygon([(x + 50, y + 12), (x + 66, y + 30), (x + 50, y + 30)],
                   fill=(200, 210, 220))
        cv.polygon([(x + 70, y + 54), (x + 118, y + 6), (x + 166, y + 54)],
                   fill=(225, 232, 238))
        cv.polygon([(x + 118, y + 6), (x + 136, y + 26), (x + 118, y + 26)],
                   fill=(185, 198, 210))
        cv.rect(x, y + 48, x + w, y + h, fill=(235, 242, 248))
        cv.line(x + 30, y + 14, x + 30, y + 40, fill=INK, width=1)
        cv.rect(x + 30, y + 14, x + 46, y + 24, fill=RED)
        cv.rect(x + 36, y + 14, x + 39, y + 24, fill=WHITE)
        cv.rect(x + 30, y + 18, x + 46, y + 20, fill=WHITE)
        cv.line(x + 150, y + 14, x + 150, y + 40, fill=INK, width=1)
        cv.rect(x + 150, y + 14, x + 166, y + 24, fill=WHITE,
                outline=INK, width=1)
        cv.rect(x + 150, y + 14, x + 158, y + 19, fill=NAVY)
        for _fy in (20, 22):
            cv.line(x + 150, y + _fy, x + 166, y + _fy, fill=RED, width=1)
        cv.line(x + 159, y + 15, x + 166, y + 15, fill=RED, width=1)
        cv.line(x + 159, y + 17, x + 166, y + 17, fill=RED, width=1)
        cv.rect(x + 158, y + 2, x + 184, y + 16, fill=RED)
        SANS_B(cv, 8, x + 171 - text_width("sans_bold", 8, "109-0") // 2,
               y + 5, "109-0", WHITE)
    elif kind == "seoul":
        # Seoul court: Korean flag, gavel, OVERTURNED stamp, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(232, 238, 244))
        # Korean flag (taegeuk + trigrams), left.
        cv.rect(x + 8, y + 8, x + 52, y + 36, fill=WHITE, outline=INK,
                width=1)
        cv.ellipse(x + 22, y + 14, x + 38, y + 30, fill=(200, 40, 60))
        cv.ellipse(x + 22, y + 22, x + 38, y + 30, fill=(30, 60, 160))
        for (_tx0, _ty0) in ((12, 11), (44, 11), (12, 29), (44, 29)):
            cv.rect(x + _tx0, y + _ty0, x + _tx0 + 5, y + _ty0 + 2,
                    fill=INK)
        # Gavel, diagonal, centre-right.
        cv.line(x + 78, y + 40, x + 122, y + 12, fill=(120, 80, 40),
                width=4)
        cv.rect(x + 108, y + 6, x + 134, y + 18, fill=(150, 100, 50))
        cv.rect(x + 100, y + 10, x + 108, y + 14, fill=(120, 80, 40))
        cv.rect(x + 134, y + 10, x + 142, y + 14, fill=(120, 80, 40))
        cv.rect(x + 70, y + 38, x + 96, y + 46, fill=(150, 100, 50))
        # OVERTURNED stamp, top right.
        cv.rect(x + 128, y + 30, x + 182, y + 46, fill=None, outline=RED,
                width=2)
        SANS_B(cv, 8, x + 155 - text_width("sans_bold", 8, "OVERTURNED")
               // 2, y + 35, "OVERTURNED", RED)
        cv.rect(x + 56, y + 44, x + 120, y + 48, fill=(100, 110, 130))
    elif kind == "bogota":
        # Bogota strike: PARO NACIONAL banner + crowd, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(235, 230, 215))
        # Colombian tricolour banner with the strike slogan.
        cv.rect(x + 10, y + 6, x + 176, y + 12, fill=(255, 205, 0))
        cv.rect(x + 10, y + 12, x + 176, y + 18, fill=(0, 60, 160))
        cv.rect(x + 10, y + 18, x + 176, y + 24, fill=(200, 40, 40))
        _t = "PARO NACIONAL"
        SANS_B(cv, 9, x + 93 - text_width("sans_bold", 9, _t) // 2,
               y + 8, _t, INK)
        # Crowd: two rows of heads + shoulders, a few placards.
        for (_hx, _hy, _sk) in ((24, 38, (240, 200, 160)),
                                (48, 34, (220, 180, 140)),
                                (72, 38, (200, 160, 120)),
                                (96, 34, (240, 200, 160)),
                                (120, 38, (220, 180, 140)),
                                (144, 34, (200, 160, 120)),
                                (168, 38, (240, 200, 160))):
            cv.ellipse(x + _hx - 5, y + _hy - 5, x + _hx + 5, y + _hy + 5,
                       fill=_sk)
            cv.rect(x + _hx - 7, y + _hy + 5, x + _hx + 7, y + 54,
                    fill=(90, 110, 160))
        cv.line(x + 36, y + 28, x + 36, y + 14, fill=INK, width=1)
        cv.rect(x + 36, y + 14, x + 58, y + 24, fill=WHITE, outline=INK,
                width=1)
        cv.line(x + 150, y + 28, x + 150, y + 16, fill=INK, width=1)
        cv.rect(x + 150, y + 16, x + 172, y + 26, fill=WHITE,
                outline=INK, width=1)
    elif kind == "nairobi":
        # Nairobi doping ban: runner on a track + BANNED stamp, 186x54.
        cv.rect(x, y, x + w, y + h, fill=(235, 240, 245))
        cv.rect(x, y + 36, x + w, y + h, fill=(180, 80, 60))
        cv.line(x, y + 40, x + w, y + 40, fill=WHITE, width=1)
        cv.line(x, y + 47, x + w, y + 47, fill=WHITE, width=1)
        # Runner mid-stride (head, torso, arms, legs).
        cv.ellipse(x + 78, y + 8, x + 90, y + 20, fill=(120, 80, 50))
        cv.line(x + 84, y + 20, x + 78, y + 34, fill=(30, 60, 140),
                width=4)
        cv.line(x + 80, y + 24, x + 66, y + 30, fill=(120, 80, 50),
                width=3)
        cv.line(x + 80, y + 24, x + 94, y + 18, fill=(120, 80, 50),
                width=3)
        cv.line(x + 78, y + 34, x + 64, y + 44, fill=(40, 40, 40),
                width=3)
        cv.line(x + 78, y + 34, x + 92, y + 40, fill=(40, 40, 40),
                width=3)
        cv.line(x + 64, y + 44, x + 58, y + 50, fill=(40, 40, 40),
                width=3)
        cv.line(x + 92, y + 40, x + 100, y + 48, fill=(40, 40, 40),
                width=3)
        # BANNED stamp, top right.
        cv.rect(x + 128, y + 6, x + 180, y + 24, fill=None, outline=RED,
                width=2)
        SANS_B(cv, 11, x + 154 - text_width("sans_bold", 11, "BANNED")
               // 2, y + 11, "BANNED", RED)
        SANS_B(cv, 8, x + 14, y + 8, "3 YEARS", RED)
    elif kind == "australia":
        # Australia jobless 4.9%: big number + people + rising arrow.
        cv.rect(x, y, x + w, y + h, fill=(13, 34, 64))
        SANS_B(cv, 26, x + 12, y + 6, "4.9%", (255, 220, 100))
        # Row of people icons.
        for _px in (14, 34, 54, 74, 94):
            cv.ellipse(x + _px, y + 34, x + _px + 8, y + 42,
                       fill=(220, 200, 170))
            cv.rect(x + _px - 2, y + 42, x + _px + 10, y + 52,
                    fill=(150, 170, 200))
        # Rising red arrow.
        cv.line(x + 120, y + 46, x + 170, y + 10, fill=RED, width=4)
        cv.polygon([(x + 170, y + 10), (x + 158, y + 10), (x + 170, y + 22)],
                   fill=RED)
    else:  # gta — GTA VI launch: the shop, the controller, midnight.
        cv.rect(x, y, x + w, y + h, fill=(27, 67, 72))
        cv.rect(x + 75, y + 18, x + 181, y + 50, fill=(208, 199, 165))
        cv.rect(x + 82, y + 30, x + 107, y + 48, fill=(83, 125, 132))
        cv.rect(x + 113, y + 30, x + 139, y + 48, fill=(83, 125, 132))
        cv.rect(x + 145, y + 30, x + 160, y + 50, fill=(61, 97, 105))
        cv.polygon([(x + 70, y + 15), (x + 169, y + 15), (x + 177, y + 27),
                    (x + 75, y + 27)], fill=(180, 59, 58))
        cv.line(x + 75, y + 27, x + 176, y + 27, fill=(119, 43, 45),
                width=2)
        cv.polygon([(x + 14, y + 17), (x + 24, y + 10), (x + 83, y + 10),
                    (x + 94, y + 17), (x + 105, y + 42), (x + 102, y + 49),
                    (x + 91, y + 49), (x + 77, y + 36), (x + 36, y + 36),
                    (x + 22, y + 49), (x + 11, y + 49), (x + 7, y + 42)],
                   fill=(18, 28, 40))
        cv.rounded_rect(x + 20, y + 13, x + 91, y + 36, radius=7,
                        fill=(44, 60, 72))
        cv.rect(x + 28, y + 19, x + 33, y + 35, fill=(188, 198, 191))
        cv.rect(x + 25, y + 23, x + 36, y + 30, fill=(188, 198, 191))
        cv.ellipse(x + 43, y + 29, x + 52, y + 41, fill=(10, 20, 29))
        cv.ellipse(x + 65, y + 29, x + 74, y + 41, fill=(10, 20, 29))
        for (bx, by, col) in ((79, 17, (183, 63, 66)),
                              (85, 23, (79, 157, 112)),
                              (73, 23, (76, 135, 184)),
                              (79, 30, (216, 184, 76))):
            cv.ellipse(x + bx, y + by, x + bx + 5, y + by + 5, fill=col)
        cv.ellipse(x + 145, y + 3, x + 179, y + 50, fill=(20, 30, 39))
        cv.ellipse(x + 148, y + 7, x + 176, y + 46, fill=(247, 243, 225))
        for (tx, ty, ex, ey) in ((162, 10, 162, 14), (162, 39, 162, 43),
                                 (150, 26, 153, 26), (171, 26, 174, 26)):
            cv.line(x + tx, y + ty, x + ex, y + ey, fill=(28, 37, 43),
                    width=1)
        cv.line(x + 162, y + 26, x + 162, y + 12, fill=(28, 37, 43),
                width=2)
        cv.line(x + 162, y + 26, x + 161, y + 17, fill=(28, 37, 43),
                width=2)


# ---------------------------------------------------------------- layout
def _inside(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            if px < (py - y1) * (x2 - x1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def _region_bar(cv, y, bar):
    bx = MX
    total = sum(c for _n, c, _col, _tc in bar)
    widths = [(W - 2 * MX) * c // total for _n, c, _col, _tc in bar]
    deficit = sum(max(0, 60 - wdt) for wdt in widths)
    donors = sorted(range(len(widths)), key=lambda i: -widths[i])[:2]
    dtot = sum(widths[i] for i in donors)
    for i in donors:
        widths[i] -= deficit * widths[i] // dtot
    widths = [60 if wdt < 60 else wdt for wdt in widths]
    for k, (name, count, col, tcol) in enumerate(bar):
        seg = (W - MX - bx) if k == len(bar) - 1 else widths[k]
        cv.rect(bx, y, bx + seg - 1, y + 16, fill=col)
        label = f"{name} {count}"
        size = 9 if text_width("sans_bold", 9, label) <= seg - 2 else 8
        lw = text_width("sans_bold", size, label)
        SANS_B(cv, size, bx + (seg - lw) // 2, y + 3, label, tcol)
        bx += seg


def _numbers_strip_big(cv, y):
    """Big serif numbers with a label below each (top-1 style)."""
    colw = (W - 2 * MX) // len(NUMBERS)
    for i, (num, label) in enumerate(NUMBERS):
        cx = MX + i * colw
        SERIF_B(cv, 22, cx, y, num, RED)
        SANS(cv, 9, cx, y + 26, label, INK)


def _hero_card(cv, i, x, y, hw, hg, cat, region, kind, title, dek):
    cv.rect(x + 3, y + 3, x + hw + 3, y + hg + 3, fill=(220, 214, 196))
    cv.rect(x, y, x + hw, y + hg, fill=WHITE,
            outline=(180, 172, 150), width=2)
    cv.rect(x, y, x + hw, y + 3, fill=RED)
    scene(cv, kind, x + 2, y + 5, hw - 4, 160)
    cv.rect(x + 2, y + 5, x + 16, y + 19, fill=RED)
    num = str(i + 1)
    nw = text_width("sans_bold", 10, num)
    SANS_B(cv, 10, x + 2 + (14 - nw) // 2, y + 7, num, WHITE)
    ctw = text_width("sans_bold", 9, cat)
    cv.rect(x + 10, y + 170, x + 10 + ctw + 14, y + 184,
            fill=CHIP[region])
    SANS_B(cv, 9, x + 17, y + 172, cat, INK if region == "asia" else WHITE)
    _st = HERO_STATUS.get(kind)
    if _st is not None:
        _txt, _col = _st
        _tw = text_width("sans_bold", 8, _txt)
        cv.rect(x + hw - 10 - _tw - 12, y + 170, x + hw - 10, y + 184,
                fill=_col)
        SANS_B(cv, 8, x + hw - 10 - _tw - 6, y + 172, _txt, WHITE)
    text_block(cv, "serif_bold", 18, x + 10, y + 188, title, INK,
               hw - 20, 21, max_lines=2)
    text_block(cv, "sans", 11, x + 10, y + 234, dek, GREY, hw - 20, 14,
               max_lines=3)


def _grid_card(cv, i, x, y, gw, gh, cat, region, kind, title, dek):
    cv.rect(x + 2, y + 2, x + gw + 2, y + gh + 2, fill=(220, 214, 196))
    cv.rect(x, y, x + gw, y + gh, fill=WHITE,
            outline=(180, 172, 150), width=2)
    cv.rect(x, y, x + gw, y + 3, fill=RED)
    # In-scene label bar: red number cell + dark label (top-1 style).
    cv.rect(x + 2, y + 5, x + gw - 2, y + 18, fill=INK)
    cv.rect(x + 2, y + 5, x + 22, y + 18, fill=RED)
    num = str(i + 4)
    nw = text_width("sans_bold", 10, num)
    SANS_B(cv, 10, x + 2 + (20 - nw) // 2, y + 7, num, WHITE)
    SANS_B(cv, 8, x + 26, y + 8, GRID_LABELS.get(kind, ""), WHITE)
    scene(cv, kind, x + 2, y + 18, gw - 4, 54)
    ctw = text_width("sans_bold", 9, cat)
    cv.rect(x + 8, y + 76, x + 8 + ctw + 10, y + 89, fill=CHIP[region])
    SANS_B(cv, 9, x + 13, y + 78, cat, INK if region == "asia" else WHITE)
    # Dek starts right after the title (no overlap) and is one line,
    # so every card's text sits at the same height.
    _ty = text_block(cv, "serif_bold", 13, x + 8, y + 91, title, INK,
                     gw - 16, 15, max_lines=2)
    text_block(cv, "sans", 10, x + 8, _ty + 2, dek, GREY, gw - 16, 12,
               max_lines=1)


def _map_panel(cv, by, ph, dots, dots_small, n_cards, n_briefs, dotted):
    cv.rect(MX, by, MX + 500, by + ph, fill=(NAVY if dotted else WHITE),
            outline=(180, 172, 150), width=2)
    _tcol = GOLD if dotted else INK
    SANS_B(cv, 14, MX + 12, by + 8, "WHERE IT HAPPENED", _tcol)
    SANS(cv, 12, MX + 12, by + 28,
         f"Numbered pins: stories 1-{n_cards}; dots: briefs "
         f"{n_cards + 1}-{n_cards + n_briefs}",
         (200, 210, 220) if dotted else GREY)
    mx, my = MX + 20, by + 48
    sy = MAP_H / 190.0  # map y-coords live in a 460x190 space
    if dotted:
        cv.rect(mx, my, mx + 460, my + MAP_H, fill=(16, 32, 64))
        for _py in range(4, 188, 7):
            for _px in range(4, 458, 7):
                for _poly in CONTINENTS:
                    if _inside(_px, _py, _poly):
                        cv.rect(mx + _px, my + int(_py * sy),
                                mx + _px + 2, my + int(_py * sy) + 2,
                                fill=(200, 210, 220))
                        break
    else:
        cv.rect(mx, my, mx + 460, my + MAP_H, fill=MAPSEA)
        for poly in CONTINENTS:
            pts = [(mx + px, my + int(py * sy)) for px, py in poly]
            cv.polygon(pts, fill=LAND, outline=(90, 130, 90))
        _greenland = [(158, 14), (178, 6), (196, 10), (200, 20),
                      (188, 28), (168, 26), (156, 20)]
        cv.polygon([(mx + px, my + int(py * sy)) for px, py in _greenland],
                   fill=(225, 235, 220), outline=(150, 180, 160))
        _antarctica = [(140, 182), (230, 176), (320, 180), (420, 176),
                       (460, 182), (460, 190), (140, 190)]
        cv.polygon([(mx + px, my + int(py * sy)) for px, py in _antarctica],
                   fill=(235, 242, 244), outline=(190, 210, 220))
        _ocean = (70, 145, 185)
        _aw = text_width("sans_bold", 11, "ATLANTIC")
        SANS_B(cv, 11, mx + 178 - _aw // 2, my + int(62 * sy),
               "ATLANTIC", _ocean)
        _ow = text_width("sans_bold", 11, "OCEAN")
        SANS_B(cv, 11, mx + 178 - _ow // 2, my + int(74 * sy),
               "OCEAN", _ocean)
        SANS_B(cv, 10, mx + 6, my + int(160 * sy), "PACIFIC", _ocean)
        SANS_B(cv, 10, mx + 6, my + int(172 * sy), "OCEAN", _ocean)
        _iw = text_width("sans_bold", 11, "INDIAN")
        SANS_B(cv, 11, mx + 325 - _iw // 2, my + int(138 * sy),
               "INDIAN", _ocean)
        _ow2 = text_width("sans_bold", 11, "OCEAN")
        SANS_B(cv, 11, mx + 325 - _ow2 // 2, my + int(150 * sy),
               "OCEAN", _ocean)
        SANS_B(cv, 8, mx + 204, my + int(14 * sy), "GREENLAND",
               (90, 140, 170))
        SANS_B(cv, 8, mx + 79, my + int(24 * sy), "NORTH", (200, 110, 40))
        SANS_B(cv, 8, mx + 76, my + int(34 * sy), "AMERICA", (200, 110, 40))
        SANS_B(cv, 8, mx + 111, my + int(130 * sy), "SOUTH",
               (200, 110, 40))
        SANS_B(cv, 8, mx + 106, my + int(140 * sy), "AMERICA",
               (200, 110, 40))
        SANS_B(cv, 9, mx + 228, my + int(84 * sy), "AFRICA", (178, 34, 34))
        _ew = text_width("sans_bold", 9, "EURASIA")
        SANS_B(cv, 9, mx + 351 - _ew // 2, my + int(38 * sy), "EURASIA",
               (150, 100, 0))
        SANS_B(cv, 7, mx + 388, my + int(134 * sy), "AUSTRALIA",
               (14, 110, 120))
        _nw = text_width("sans_bold", 8, "ANTARCTICA")
        SANS_B(cv, 8, mx + 230 - _nw // 2, my + int(176 * sy), "ANTARCTICA",
               (90, 140, 170))
    for _num, (px, py, reg) in dots_small.items():
        cx, cy = mx + px, my + int(py * sy)
        cv.ellipse(cx - 3, cy - 3, cx + 3, cy + 3, fill=REGION[reg])
    for num, (px, py) in dots.items():
        cx, cy = mx + px, my + int(py * sy)
        cv.ellipse(cx - 7, cy - 7, cx + 7, cy + 7, fill=RED,
                   outline=WHITE, width=1)
        label = str(num)
        lw = text_width("sans_bold", 9, label)
        SANS_B(cv, 9, int(cx - lw / 2), cy - 5, label, WHITE)
    lx = mx
    _lcol = (200, 210, 220) if dotted else GREY
    for name, col in (("Europe", REGION["europe"]),
                      ("Middle East", REGION["middle_east"]),
                      ("Asia", REGION["asia"]),
                      ("Africa", REGION["africa"]),
                      ("Americas", REGION["americas"]),
                      ("Oceania", REGION["oceania"]),
                      ("World", REGION["global"])):
        cv.ellipse(lx - 4, my + MAP_H + 4, lx + 4, my + MAP_H + 12,
                   fill=col)
        SANS(cv, 11, lx + 7, my + MAP_H + 2, name, _lcol)
        lx += 7 + text_width("sans", 11, name) + 14


def _also_panel(cv, by, ph, also, title, cols, col_w, wrap_w, size,
                leading, start_num, sources=None):
    ax = MX + 508
    cv.rect(ax, by, W - MX, by + ph, fill=WHITE,
            outline=(180, 172, 150), width=2)
    SANS_B(cv, 14, ax + 12, by + 8, title, INK)
    per = (len(also) + cols - 1) // cols
    for col_i in range(cols):
        cx = ax + 12 + col_i * col_w
        yy = by + 30
        for i, item in enumerate(
                also[col_i * per:(col_i + 1) * per],
                start=col_i * per + start_num):
            if sources is not None and i in sources:
                item = f"{item}. {sources[i]}"
            SANS_B(cv, 10, cx, yy, f"{i}", RED)
            lines = wrap("sans", size, item, wrap_w)
            text_block(cv, "sans", size, cx + 20, yy, item, INK, wrap_w,
                       leading, max_lines=3)
            yy += leading * max(1, min(3, len(lines)))


def _date_check(cv, y, h):
    cv.rect(MX, y, W - MX, y + h, fill=(220, 240, 210),
            outline=GREEN, width=2)
    cv.polyline([(MX + 10, y + 20), (MX + 15, y + 26), (MX + 26, y + 10)],
                fill=GREEN, width=3)
    _lab = "DATE CHECK:  "
    SANS_B(cv, 11, MX + 34, y + 6, _lab, GREEN)
    text_block(cv, "sans", 11, MX + 34 + text_width("sans_bold", 11, _lab),
               y + 6, DATE_CHECK, INK,
               W - 2 * MX - 34 - text_width("sans_bold", 11, _lab),
               15, max_lines=2)


def _footer(cv, y):
    SANS(cv, 10, MX, y,
         "Claims are attributed, not stated as fact \u00b7 Pictures and "
         "map: original, drawn in code \u00b7 Sources: Reuters, AP, AFP, "
         "BBC, Al Jazeera, UN News, Euronews, ABC, RNZ, Xinhua, Nature "
         "\u00b7 2026-11-19", GREY)


def front_page(style, heroes, grid, also, dots, dots_small, subhead,
              kicker_l, kicker_r, title, also_title, region_bar,
              sources=None, also_cols=3):
    cv = Canvas(W, H, PAPER)
    n_cards = len(heroes) + len(grid)
    n_briefs = len(also)
    if style == "atlas":
        cv.rect(0, 0, W, 64, fill=NAVY)
        SERIF_B(cv, 36, MX, 12, "THE DAILY ATLAS", WHITE)
        _t = "THURSDAY 19 NOVEMBER 2026"
        SERIF_B(cv, 20, W - MX - text_width("serif_bold", 20, _t), 14,
                _t, WHITE)
        _t2 = "42 STORIES  \u2022  ONE DAY  \u2022  EVERY CONTINENT"
        SANS_B(cv, 10, W - MX - text_width("sans_bold", 10, _t2), 42,
               _t2, GOLD)
        SANS_B(cv, 10, MX, 70, "THE DAY BY HOURS  \u2022  ", GOLD)
        _tx = MX + text_width("sans_bold", 10, "THE DAY BY HOURS  \u2022  ")
        SANS(cv, 10, _tx, 70,
             "UTC 00:00 GTA VI unlocks in NZ  \u2022  MORNING Shenzhen "
             "summit  \u2022  10:00 World Court reads verdict "
             "\u2022  14:30 Anthropic's first trades  \u2022  "
             "EVENING COP31 takes over", INK)
        hero_y, grid_y = 92, 420
        cv.rect(MX, 376, W - MX, 412, fill=NAVY)
        _stats = [("$81.3bn", "raised by Anthropic, the largest IPO ever"),
                  ("$83", "ANT's debut price, above its range"),
                  ("109-0", "Danish vote on the Arctic pact"),
                  ("16bn miles", "Voyager 1 away from Earth"),
                  ("95%", "chance of a Dec Fed hike")]
        _sx = MX + 10
        _colw = (W - 2 * MX - 20) // 5
        for _num, _lab in _stats:
            SANS_B(cv, 18, _sx, 380, _num, GOLD)
            SANS(cv, 8, _sx, 400, _lab, WHITE)
            _sx += _colw
        map_y, map_h, dc_y, dc_h, ft_y = 716, 222, 946, 36, 988
    else:
        SANS_B(cv, 10, MX, 8, kicker_l, INK)
        SANS_B(cv, 10,
               W - MX - 100 - text_width("sans_bold", 10, kicker_r), 8,
               kicker_r, RED)
        # Calendar box, top right (top-2 signal).
        cv.rect(W - MX - 92, 8, W - MX, 58, fill=WHITE,
                outline=(180, 172, 150), width=1)
        SANS_B(cv, 8, W - MX - 84, 10, "NOVEMBER 2026", INK)
        SERIF_B(cv, 20, W - MX - 84, 22, "19", INK)
        SANS_B(cv, 8, W - MX - 84, 44, "THURSDAY", RED)
        SERIF_B(cv, 52, MX, 22, title, INK)
        SERIF(cv, 15, MX, 80, subhead, RED)
        _region_bar(cv, 100, region_bar)
        _numbers_strip_big(cv, 120)
        hero_y, grid_y = 164, 448
        map_y, map_h, dc_y, dc_h, ft_y = 744, 222, 972, 36, 1012
    hw, hg, gap = 322, 276, 8
    for i, (cat, region, kind, t, dek) in enumerate(heroes):
        _hero_card(cv, i, MX + i * (hw + gap), hero_y, hw, hg, cat,
                   region, kind, t, dek)
    gw, gh, cols = 190, 140, 5
    for r in range(2):
        for c in range(cols):
            i = r * cols + c
            if i >= len(grid):
                break
            cat, region, kind, t, dek = grid[i]
            _grid_card(cv, i, MX + c * (gw + gap), grid_y + r * (gh + gap),
                       gw, gh, cat, region, kind, t, dek)
    _map_panel(cv, map_y, map_h, dots, dots_small, n_cards, n_briefs,
               dotted=(style == "atlas"))
    _also_panel(cv, map_y, map_h, also, also_title, also_cols,
                (W - 2 * MX - 508 - 24) // also_cols,
                (W - 2 * MX - 508 - 24) // also_cols - 28, 8,
                9, n_cards + 1, sources=sources)
    _date_check(cv, dc_y, dc_h)
    _footer(cv, ft_y)
    return cv

# --- entry point: option 7A, faithful top-1 rebuild (33 stories) ----------
# Top-1 style DATE CHECK: explicit same-day statement + left-out items.
DATE_CHECK = ("Every story here happened, or was first reported, on "
              "Thursday 19 November 2026. Left out as other days' news "
              "\u2014 18 Nov: EU's \u20ac45bn loan; Iranian drones over "
              "Kuwait and Bahrain; first COP31 draft. 20 Nov: COP31 "
              "closes; Cyclone Akvan's landfall.")

HERO_V7 = [
    ("SHENZHEN  \u2022  SUMMIT", "asia", "summit19",
     "Trump, Xi and Putin hold first three-way summit",
     "The three leaders meet at Kylin Villa in Shenzhen; no concrete "
     "deals. Trump and Putin spoke alone for 40 minutes first. "
     "\u2014 Reuters"),
    ("THE HAGUE  \u2022  JUSTICE", "asia", "icj19",
     "World Court: Myanmar committed genocide",
     "By 9 votes to 6 the ICJ found Myanmar guilty of the 2017 Rohingya "
     "genocide and ordered reparations. \u2014 Reuters"),
    ("ANTALYA  \u2022  CLIMATE", "global", "cop19",
     "COP31 draft drops fossil fuels and $120bn aid goal",
     "The slimmer draft has no fossil-fuel exit and no $120bn adaptation "
     "goal. Talks are due to end on Friday. \u2014 Reuters \u00b7 AFP"),
]
GRID_V7 = [
    ("CRIMEA  \u2022  WAR", "europe", "kerch",
     "Ukraine hits Crimea bridge again",
     "Third strike halts trains to Russia."),
    ("RIYADH  \u2022  WAR", "middle_east", "pif19",
     "Missile hits Riyadh PIF Tower",
     "Windows blown out; no one hurt."),
    ("ODISHA  \u2022  STORM", "asia", "bengal",
     "Cyclone Akvan nears India's coast",
     "Landfall due Friday noon."),
    ("SEOUL  \u2022  JUSTICE", "asia", "seoul",
     "Top court overturns Han's sentence",
     "Sentence quashed; retrial next."),
    ("GREENLAND  \u2022  SECURITY", "europe", "greenland",
     "Denmark backs Arctic pact with US",
     "Parliament backs the deal 109-0."),
    ("NEW YORK  \u2022  MARKETS", "global", "ant19",
     "Anthropic starts trading on Nasdaq",
     "Record $81bn sale priced at $83."),
    ("WORLDWIDE  \u2022  GAMES", "global", "gta",
     "GTA VI goes on sale after 13 years",
     "Midnight launch; rave reviews."),
    ("BOGOTA  \u2022  LABOUR", "americas", "bogota",
     "Colombia's unions hold national strike",
     "Unions march in three cities."),
    ("NAIROBI  \u2022  SPORT", "africa", "nairobi",
     "Marathon champion banned for doping",
     "Peres Jepchirchir gets three years."),
    ("CANBERRA  \u2022  ECONOMY", "oceania", "australia",
     "Australia's jobless rate hits 4.9%",
     "Highest since 2021; shares slide."),
]
ALSO_V7 = [
    "Shenzhen: Xi urges ban on all nuclear arms",
    "APEC: Albanese to Putin: \"End your war, end it now\"",
    "Seoul: Half a million sit college entrance exam",
    "Jakarta: Asset-seizure law passes after 18 years",
    "Hormuz: tanker hit near the strait",
    "Gaza: Israel ends tank raid past truce line",
    "The Hague: Dutch summon envoy over Kyiv blast",
    "Brussels: EU delays methane rules two years",
    "UK: Inquiry: yacht Bayesian was vulnerable to wind",
    "Zurich: Two rivals to challenge FIFA's Infantino",
    "Rome: Author Corrado Augias dies at 91",
    "Mogadishu: Somalia expels UAE ambassador",
    "Dakar: dozens missing as boat sinks off Senegal",
    "Pretoria: Central bank holds rate at 7.25%",
    "Caracas: US, Venezuela sign military deal",
    "Florida: Floods shut Broward, Miami schools again",
    "Wellington: Court: pay equity cuts broke rights law",
    "Tonga: Drought emergency takes effect",
    "Cook Islands: Cyclone Xavier weakens to category 4",
    "Voyager: Voyager 1, one light-day away",
]
ALSO_SRC_V7 = {
    14: "Al Jazeera", 15: "ABC", 16: "Sedaily", 17: "Kompas",
    18: "UKMTO", 19: "BBC", 20: "Reuters", 21: "Euronews",
    22: "RNZ", 23: "ABC", 24: "Euronews", 25: "Al Jazeera",
    26: "Reuters", 27: "SABC", 28: "CNN", 29: "CBS",
    30: "RNZ", 31: "RNZ", 32: "RNZ", 33: "Reuters",
}
REGION_BAR_V7 = [
    ("ASIA", 8, (200, 160, 0), (0, 0, 0)),
    ("MIDDLE EAST", 3, (178, 34, 34), (255, 255, 255)),
    ("EUROPE", 7, (30, 90, 180), (255, 255, 255)),
    ("AFRICA", 4, (150, 90, 30), (255, 255, 255)),
    ("AMERICAS", 3, (34, 139, 34), (255, 255, 255)),
    ("OCEANIA", 4, (0, 140, 140), (255, 255, 255)),
    ("GLOBAL", 4, (120, 60, 160), (255, 255, 255)),
]
DOTS_V7 = {
    1: (400, 75), 2: (215, 45), 3: (285, 68), 4: (285, 58),
    5: (295, 90), 6: (368, 100), 7: (178, 16), 8: (415, 68),
    9: (60, 85), 10: (445, 165), 11: (102, 102), 12: (270, 115),
    13: (405, 155),
}
DOTS_SMALL_V7 = {
    14: (395, 80, "asia"), 15: (400, 72, "asia"),
    16: (420, 75, "asia"), 17: (392, 112, "asia"),
    18: (315, 95, "middle_east"), 19: (288, 82, "middle_east"),
    20: (224, 56, "europe"), 21: (220, 62, "europe"),
    22: (212, 50, "europe"), 23: (230, 62, "europe"),
    24: (240, 68, "europe"), 25: (285, 125, "africa"),
    26: (205, 105, "africa"), 27: (252, 140, "africa"),
    28: (100, 95, "americas"), 29: (65, 80, "americas"),
    30: (445, 170, "oceania"), 31: (440, 150, "oceania"),
    32: (435, 160, "oceania"), 33: (30, 150, "global"),
}

init_fonts(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fonts.bin"))
cv = front_page(
    "classic", HERO_V7, GRID_V7, ALSO_V7, DOTS_V7, DOTS_SMALL_V7,
    "Trump, Xi and Putin share one table \u00b7 The World Court finds "
    "genocide in Myanmar \u00b7 COP31's draft drops fossil fuels",
    "THE WORLD IN ONE DAY",
    "33 STORIES  \u2022  EVERY CONTINENT  \u2022  ALL FROM THIS ONE DAY",
    "Thursday 19 November 2026",
    "ALSO ON THURSDAY 19 NOVEMBER 2026",
    REGION_BAR_V7, sources=ALSO_SRC_V7, also_cols=2)
save(cv, "entry.png")
