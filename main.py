"""Shared drawing core for news-image-20261119 previews.

Stdlib-only software rasterizer + PNG encoder + text from the shipped
glyph atlas (fonts.bin, DejaVu OFL, ASCII 32-126 + bullet). Written
fresh in this session for the 19 Nov bounty; the winning layout will
be inlined into a single self-contained main.py for submission.
Deterministic, network-free.
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

"""Front-page engine for news-image-20261119, round 2 (v2 options).

Follows the top 1-5 leaderboard template, verified live 20 Nov 07:48-07:52
WIB: cream newspaper front page, serif date masthead, red subheadline,
region bar + numbers strip, 3 illustrated heroes, numbered grid, world
map + ALSO list, DATE CHECK box, sources footer. Three style variants:
A Classic (top-1), B Atlas (top-5 navy/gold), C Airy (top-4, 19 stories).
Written fresh in this session; scenes re-typed and adapted from the
v11 layout (same contest family), with new 19 Nov content throughout.
All 42 stories verified in news_19nov_verified.md; GTA VI unlock and
the ICJ 9-6 vote verified separately 20 Nov (Reuters/BBC).
"""



MAPSEA = LIGHTBLUE  # v11's map sea colour

W, H = 1024, 1024
MX = 20

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

REGION_BAR = [  # (label, count, bar colour, label colour) — 42 stories
    ("EUROPE", 5, (30, 90, 180), WHITE),
    ("MIDDLE EAST", 5, RED, WHITE),
    ("ASIA", 8, (200, 160, 0), INK),
    ("AFRICA", 6, (150, 90, 30), WHITE),
    ("AMERICAS", 7, (34, 139, 34), WHITE),
    ("OCEANIA", 2, (0, 140, 140), WHITE),
    ("WORLD", 9, (120, 60, 160), WHITE),
]
FIELD_BAR = [
    ("War & security", 10), ("Politics & diplomacy", 11),
    ("Economy & labour", 7), ("Society & culture", 3),
    ("Disasters & weather", 2), ("Tech", 3),
    ("Climate & space", 2), ("Justice", 4),
]
NUMBERS = [
    ("3", " leaders at one table"),
    ("9-6", " ICJ genocide vote"),
    ("$120bn", " aid goal cut"),
    ("$81bn", " Anthropic's record IPO"),
    ("109-0", " Danish vote on Arctic pact"),
    ("95%", " chance of a Dec Fed hike"),
]
DATE_CHECK = ("Left out on purpose because they were first reported "
              "on Wednesday 18 Nov, not today: the Iranian drone "
              "interceptions over Kuwait and Bahrain; the EU's "
              "45bn euro Ukraine loan plan; the first COP31 draft "
              "(Monday); Akvan formed 16 Nov. Voyager crossed one "
              "light-day on Wednesday; NASA confirmed it today.")

# --- stories: (cat label, region, scene kind, headline, dek) ------------
HERO_A = [
    ("ASIA  \u2022  SUMMIT", "asia", "summit19",
     "Trump, Xi and Putin hold first three-way summit",
     "The three leaders meet at Kylin Villa in Shenzhen; no "
     "concrete deals. \u2014 Reuters"),
    ("THE HAGUE  \u2022  JUSTICE", "global", "icj19",
     "World Court: Myanmar committed genocide",
     "By 9 votes to 6 the ICJ finds Myanmar guilty of the 2017 "
     "Rohingya genocide. \u2014 Reuters"),
    ("ANTALYA  \u2022  CLIMATE", "global", "cop19",
     "COP31 draft drops fossil fuels and $120bn aid goal",
     "The slimmer text has no fossil-fuel exit; talks end "
     "Friday. \u2014 Reuters \u00b7 AFP"),
]
GRID_A = [
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
    ("NEW YORK  \u2022  MARKETS", "global", "ant19",
     "Anthropic starts trading on Nasdaq",
     "Its record $81bn share sale was priced at $83. \u2014 AP"),
    ("WORLDWIDE  \u2022  GAMES", "global", "gta",
     "GTA VI unlocks worldwide",
     "Midnight launch rolls out by time zone, NZ first. \u2014 Reuters"),
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

# Option C (airy, 19 stories): heroes summit / gta / anthropic.
HERO_C = [
    ("ASIA  \u2022  SUMMIT", "asia", "summit19",
     "Trump, Xi and Putin hold first three-way summit",
     "The three leaders meet at Kylin Villa in Shenzhen; no "
     "concrete deals. \u2014 Reuters"),
    ("WORLDWIDE  \u2022  GAMES", "global", "gta19",
     "GTA VI unlocks worldwide",
     "Rockstar's sequel goes live at midnight in each region, "
     "New Zealand first. \u2014 Reuters"),
    ("NEW YORK  \u2022  MARKETS", "global", "ant19h",
     "Anthropic starts trading on Nasdaq",
     "Its record $81bn share sale was priced at $83; shares "
     "jump 17% on day one. \u2014 AP"),
]
GRID_C = [
    ("THE HAGUE  \u2022  JUSTICE", "global", "icj19s",
     "World Court: Myanmar committed genocide",
     "By 9 votes to 6 the ICJ finds Myanmar guilty. \u2014 Reuters"),
    ("RIYADH  \u2022  WAR", "middle_east", "pif19",
     "Missile hits Riyadh PIF Tower",
     "Windows blown out on 7-8 floors; no one hurt. \u2014 Reuters"),
    ("KYIV  \u2022  WAR", "europe", "pylon",
     "Kyiv drone raid hits cathedral",
     "One killed, five hurt; two embassies hit. \u2014 AFP"),
    ("GAZA  \u2022  WAR", "middle_east", "gaza19",
     "Israel ends Gaza tank raid",
     "Truce frays as Board of Peace warns it may collapse. \u2014 Reuters"),
    ("ANTALYA  \u2022  CLIMATE", "global", "cop19s",
     "COP31 draft drops fossil fuels",
     "Slimmer text has no fossil-fuel exit. \u2014 Reuters"),
    ("ODISHA  \u2022  STORM", "asia", "bengal",
     "Cyclone Akvan nears India's coast",
     "Landfall due Friday noon; districts on alert. \u2014 IMD"),
    ("WASHINGTON  \u2022  ECONOMY", "americas", "fed19",
     "Fed: December hike likely",
     "Markets price a rise at about 95%. \u2014 Reuters"),
    ("DHAKA  \u2022  POLITICS", "asia", "bangla19",
     "Bangladesh shuts down",
     "Lockdown called; two killed, Yunus home torched. \u2014 Reuters"),
]
ALSO_C = [  # 8 briefs, numbers 12-19
    "Badme: Ethiopia, Eritrea mass troops on border",
    "Copenhagen: Denmark backs Greenland deal 109-0",
    "Space: Voyager 1, one light-day away",
    "Brasilia: central bank sells $1bn as real slides",
    "Washington: Trump weighs new Iran strikes",
    "Mogadishu: Somalia expels UAE ambassador",
    "India: Nicholls ton rescues New Zealand",
    "Manila: Trump unveils $17bn Asia deals",
]

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

# Map pins for the 13 cards (map box 460x190).
DOTS_A = {
    1: (400, 75), 2: (215, 45), 3: (285, 68), 4: (295, 90),
    5: (265, 50), 6: (300, 98), 7: (365, 82), 8: (258, 105),
    9: (60, 85), 10: (445, 165), 11: (368, 100), 12: (70, 70),
    13: (30, 150),
}
# Map dots for the 29 briefs (number -> (x, y, region)).
DOTS_SMALL_A = {
    14: (330, 85, "middle_east"), 15: (240, 48, "europe"),
    16: (224, 56, "europe"), 17: (232, 40, "europe"),
    18: (306, 100, "middle_east"), 19: (250, 90, "africa"),
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
# Option C map: 3 hero pins + 8 grid pins + 7 brief dots.
DOTS_C = {
    1: (400, 75), 2: (445, 165), 3: (60, 85), 4: (215, 45),
    5: (295, 90), 6: (265, 50), 7: (300, 98), 8: (285, 68),
    9: (368, 100), 10: (70, 70), 11: (365, 82),
}
DOTS_SMALL_C = {
    12: (258, 105, "africa"), 13: (232, 40, "europe"),
    14: (30, 150, "global"), 15: (100, 95, "americas"),
    16: (318, 102, "middle_east"), 17: (306, 100, "middle_east"),
    18: (415, 150, "oceania"), 19: (390, 86, "asia"),
}


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


def scene(cv, kind, x, y, w, h):
    """Paint one illustrated scene inside (x, y, x+w, y+h)."""
    if kind == "summit19":
        # Three leaders at a summit table (top-1 style), 318x110.
        cv.rect(x, y, x + w, y + h, fill=(232, 238, 244))
        cv.rect(x, y + 78, x + w, y + h, fill=(250, 224, 190))
        cv.rect(x, y, x + w, y + 15, fill=NAVY)
        SANS_B(cv, 9, x + 20, y + 3, "APEC 2026  \u2022  SHENZHEN", WHITE)
        _t = "FIRST US-CHINA-RUSSIA SUMMIT"
        SANS_B(cv, 9, x + w - 8 - text_width("sans_bold", 9, _t), y + 3,
               _t, GOLD)
        # Desk flags behind the figures.
        _flag_us(cv, x + 28, y + 22, 22, 13)
        _flag_cn(cv, x + 148, y + 22, 22, 13)
        _flag_ru(cv, x + 268, y + 22, 22, 13)
        # The three leaders.
        figure(cv, x + 62, y + 34, 20, (232, 190, 150), (30, 30, 40))
        figure(cv, x + 159, y + 34, 20, (240, 200, 160), (40, 45, 70))
        figure(cv, x + 256, y + 34, 20, (225, 185, 145), (60, 60, 70))
        # Table front with name plates.
        cv.rect(x, y + 66, x + w, y + h, fill=(150, 110, 70))
        cv.rect(x, y + 66, x + w, y + 70, fill=(190, 150, 100))
        for _cx, _name in ((62, "TRUMP"), (159, "XI"), (256, "PUTIN")):
            _pw = text_width("sans_bold", 9, _name) + 12
            cv.rect(x + _cx - _pw // 2, y + 78, x + _cx + _pw // 2,
                    y + 92, fill=WHITE, outline=INK, width=1)
            SANS_B(cv, 9, x + _cx - text_width("sans_bold", 9, _name) // 2,
                   y + 81, _name, INK)
    elif kind == "icj19":
        # World Court in The Hague + scales + red 9-6 box, 318x110.
        cv.rect(x, y, x + w, y + h, fill=(232, 240, 244))
        cv.rect(x, y + 96, x + w, y + h, fill=(200, 210, 200))
        cv.polygon([(x + 28, y + 38), (x + 105, y + 12), (x + 182, y + 38)],
                   fill=(220, 215, 200))
        cv.rect(x + 32, y + 38, x + 178, y + 96, fill=(240, 238, 225))
        for _cx in (46, 76, 106, 136, 166):
            cv.rect(x + _cx, y + 44, x + _cx + 8, y + 92, fill=WHITE)
        cv.rect(x + 28, y + 92, x + 182, y + 96, fill=(200, 195, 180))
        cv.rect(x + 20, y + 96, x + 190, y + 100, fill=(180, 175, 160))
        cv.rect(x + 14, y + 100, x + 196, y + 104, fill=(160, 155, 140))
        # Scales of justice, right.
        cv.line(x + 250, y + 26, x + 250, y + 92, fill=GOLD, width=3)
        cv.line(x + 222, y + 34, x + 278, y + 34, fill=GOLD, width=3)
        cv.ellipse(x + 246, y + 22, x + 254, y + 30, fill=GOLD)
        for _px in (222, 278):
            cv.line(x + _px, y + 34, x + _px, y + 52, fill=GOLD, width=1)
            cv.polygon([(x + _px - 12, y + 52), (x + _px + 12, y + 52),
                        (x + _px, y + 66)], fill=GOLD)
        cv.ellipse(x + 244, y + 92, x + 256, y + 96, fill=GOLD)
        # Red 9-6 box, top right.
        cv.rect(x + 276, y + 4, x + 312, y + 28, fill=RED)
        _t = "9-6"
        SANS_B(cv, 16, x + 294 - text_width("sans_bold", 16, _t) // 2,
               y + 8, _t, WHITE)
    elif kind == "cop19":
        # COP31: globe, crossed-out FOSSIL FUELS, CUT stamp, 318x110.
        cv.rect(x, y, x + w, y + h, fill=(232, 240, 244))
        cv.ellipse(x + 28, y + 14, x + 104, y + 90, fill=NAVY)
        cv.ellipse(x + 30, y + 16, x + 102, y + 88, fill=(90, 170, 220))
        cv.ellipse(x + 42, y + 26, x + 62, y + 42, fill=(80, 170, 90))
        cv.ellipse(x + 66, y + 52, x + 88, y + 72, fill=(80, 170, 90))
        cv.ellipse(x + 50, y + 62, x + 64, y + 76, fill=(80, 170, 90))
        cv.arc(x + 36, y + 30, x + 96, y + 66, 200, 340, fill=WHITE,
               width=1)
        # Thermometer, far right.
        cv.rect(x + 296, y + 14, x + 306, y + 78, fill=WHITE,
                outline=INK, width=1)
        cv.rect(x + 299, y + 46, x + 303, y + 76, fill=RED)
        cv.ellipse(x + 292, y + 74, x + 310, y + 92, fill=RED)
        cv.ellipse(x + 296, y + 78, x + 306, y + 88, fill=(255, 120, 120))
        # Crossed-out FOSSIL FUELS + aid line.
        _t = "FOSSIL FUELS"
        SANS_B(cv, 15, x + 122, y + 16, _t, INK)
        _fw = text_width("sans_bold", 15, _t)
        cv.line(x + 120, y + 24, x + 122 + _fw, y + 24, fill=RED, width=3)
        SANS_B(cv, 11, x + 122, y + 34, "$120BN ADAPTATION AID", RED)
        # Draft document with red stamp ring.
        cv.rect(x + 122, y + 52, x + 216, y + 92, fill=WHITE,
                outline=NAVY, width=1)
        for _ly in (60, 67, 74):
            cv.line(x + 130, y + _ly, x + 208, y + _ly, fill=GREY, width=1)
        cv.ellipse(x + 192, y + 76, x + 208, y + 90, fill=RED)
        cv.ellipse(x + 195, y + 79, x + 205, y + 87, fill=WHITE)
        # CUT stamp.
        cv.rect(x + 228, y + 62, x + 288, y + 90, fill=None, outline=RED,
                width=2)
        SANS_B(cv, 16, x + 258 - text_width("sans_bold", 16, "CUT") // 2,
               y + 70, "CUT", RED)
    elif kind == "gta19":
        # GTA VI: Vice City sunset skyline, 318x110.
        cv.gradient(x, y, w, h, (255, 190, 100), (150, 60, 130))
        cv.ellipse(x + 232, y + 8, x + 276, y + 52, fill=(255, 220, 120))
        SANS_B(cv, 22, x + 12, y + 8, "VICE CITY", (60, 20, 60))
        SANS_B(cv, 22, x + 10, y + 6, "VICE CITY", WHITE)
        for (_bx, _bw, _bh) in ((0, 34, 42), (38, 26, 58), (68, 30, 36),
                                (102, 22, 64), (128, 36, 44),
                                (168, 24, 58), (196, 30, 38),
                                (230, 26, 52), (260, 34, 40),
                                (298, 20, 56)):
            cv.rect(x + _bx, y + 110 - _bh, x + _bx + _bw, y + 110,
                    fill=(40, 30, 60))
            cv.rect(x + _bx + 5, y + 110 - _bh + 6, x + _bx + 9,
                    y + 110 - _bh + 10, fill=(255, 214, 100))
            cv.rect(x + _bx + _bw - 10, y + 110 - _bh + 14,
                    x + _bx + _bw - 6, y + 110 - _bh + 18,
                    fill=(255, 214, 100))
        # Palms at both edges.
        for _px in (14, 306):
            cv.line(x + _px, y + 78, x + _px, y + 104, fill=(30, 20, 40),
                    width=2)
            for _dx, _dy in ((-10, -6), (10, -6), (-8, -12), (8, -12)):
                cv.line(x + _px, y + 78, x + _px + _dx, y + 78 + _dy,
                        fill=(30, 20, 40), width=2)
    elif kind == "ant19h":
        # Anthropic on Nasdaq: dark panel, rising chart, ANT $83.
        cv.rect(x, y, x + w, y + h, fill=(16, 32, 64))
        cv.line(x + 8, y + 96, x + w - 8, y + 96, fill=WHITE, width=1)
        cv.line(x + 8, y + 12, x + 8, y + 96, fill=WHITE, width=1)
        _bars = [(16, 62, 76), (34, 56, 70), (52, 66, 82), (70, 50, 66),
                 (88, 58, 74), (106, 44, 60), (124, 50, 68),
                 (142, 36, 54), (160, 42, 60), (178, 28, 46),
                 (196, 34, 52), (214, 20, 38), (232, 26, 44),
                 (250, 14, 30)]
        for _bx, _lo, _hi in _bars:
            _col = (60, 200, 120) if _hi < _lo + 4 else (220, 60, 60)
            cv.rect(x + _bx, y + _hi, x + _bx + 12, y + _lo, fill=_col)
        cv.polyline([(x + 20, y + 70), (x + 70, y + 58), (x + 120, y + 48),
                     (x + 170, y + 36), (x + 220, y + 24), (x + 270, y + 14)],
                    fill=(60, 220, 130), width=3)
        SANS_B(cv, 26, x + 12, y + 8, "ANT  $83", WHITE)
        SANS_B(cv, 10, x + 12, y + 38, "NASDAQ  \u2022  +17% DAY ONE",
               (150, 200, 230))
        cv.polygon([(x + 288, y + 8), (x + 306, y + 8), (x + 297, y + 24)],
                   fill=(60, 220, 130))
    elif kind == "pif19":
        # PIF Tower in Riyadh at night, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(30, 45, 70))
        cv.ellipse(x + 8, y + 4, x + 20, y + 16, fill=(220, 220, 200))
        cv.rect(x + 82, y + 2, x + 104, y + 38, fill=(60, 70, 90))
        cv.polygon([(x + 82, y + 2), (x + 93, y - 4), (x + 104, y + 2)],
                   fill=(60, 70, 90))
        for _wy in (8, 14, 20, 26, 32):
            for _wx in (86, 94):
                cv.rect(x + _wx, y + _wy, x + _wx + 4, y + _wy + 3,
                        fill=(255, 214, 100))
        # Broken patch + smoke.
        cv.polygon([(x + 84, y + 10), (x + 92, y + 6), (x + 98, y + 12),
                    (x + 90, y + 16), (x + 84, y + 14)], fill=(20, 25, 40))
        for (_sx, _sy, _sr) in ((96, 2, 4), (104, -2, 5), (112, 2, 4)):
            cv.ellipse(x + _sx - _sr, y + _sy, x + _sx + _sr,
                       y + _sy + _sr, fill=(180, 180, 170))
        cv.rect(x + 30, y + 28, x + 60, y + 38, fill=(45, 55, 70))
        cv.rect(x + 130, y + 24, x + 160, y + 38, fill=(45, 55, 70))
        for _wx in (34, 44, 134, 146):
            cv.rect(x + _wx, y + 30, x + _wx + 4, y + 33,
                    fill=(255, 214, 100))
    elif kind == "gaza19":
        # Gaza: tank beside ruined buildings, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(232, 214, 170))
        cv.polygon([(x, y + 20), (x + 33, y + 9), (x + 67, y + 20),
                    (x + 105, y + 10), (x + 146, y + 19), (x + 185, y + 11),
                    (x + 185, y + 37), (x, y + 37)], fill=(137, 165, 112))
        cv.polygon([(x + 118, y + 8), (x + 130, y + 4), (x + 142, y + 8),
                    (x + 138, y + 30), (x + 118, y + 30)], fill=(160, 155, 140))
        cv.polygon([(x + 146, y + 12), (x + 158, y + 6), (x + 172, y + 12),
                    (x + 168, y + 30), (x + 146, y + 30)], fill=(140, 135, 120))
        cv.rect(x, y + 32, x + 185, y + 37, fill=(166, 158, 119))
        cv.rounded_rect(x + 52, y + 28, x + 106, y + 35, radius=3,
                        fill=(48, 62, 45))
        cv.polygon([(x + 54, y + 21), (x + 92, y + 21), (x + 104, y + 28),
                    (x + 100, y + 31), (x + 51, y + 31)], fill=(103, 124, 75))
        cv.rect(x + 66, y + 15, x + 86, y + 23, fill=(86, 108, 66))
        cv.line(x + 84, y + 18, x + 112, y + 17, fill=(65, 85, 52), width=3)
        figure(cv, x + 24, y + 22, 8, (173, 132, 92), (88, 111, 67))
        figure(cv, x + 140, y + 24, 7, (190, 150, 110), (120, 90, 70))
    elif kind == "bangla19":
        # Dhaka lockdown: crowd, police van, a torched shop, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(214, 226, 230))
        cv.rect(x + 3, y + 8, x + 47, y + 28, fill=(166, 174, 173))
        cv.rect(x + 49, y + 13, x + 99, y + 28, fill=(186, 187, 177))
        flame(cv, x + 22, y + 16, 0.25)
        cv.rect(x, y + 28, x + 185, y + 37, fill=(153, 149, 136))
        cv.ellipse(x + 132, y + 27, x + 143, y + 37, fill=(39, 49, 58))
        cv.ellipse(x + 169, y + 27, x + 180, y + 37, fill=(39, 49, 58))
        cv.rounded_rect(x + 125, y + 12, x + 183, y + 32, radius=3,
                        fill=(246, 246, 233))
        cv.rect(x + 132, y + 16, x + 151, y + 22, fill=(67, 107, 133))
        cv.rect(x + 126, y + 25, x + 182, y + 29, fill=(43, 99, 153))
        for (fx, fy, fs, skin, suit) in (
                (15, 21, 6, (190, 137, 98), (48, 103, 150)),
                (43, 19, 6, (222, 172, 126), (237, 235, 219)),
                (72, 21, 6, (190, 137, 98), (48, 103, 150)),
                (99, 19, 6, (222, 172, 126), (237, 235, 219))):
            figure(cv, x + fx, y + fy, fs, skin, suit)
        figure(cv, x + 57, y + 25, 8, (216, 164, 120), (41, 87, 133))
        cv.polygon([(x + 49, y + 21), (x + 53, y + 15), (x + 60, y + 14),
                    (x + 65, y + 20), (x + 64, y + 32), (x + 59, y + 29),
                    (x + 60, y + 21), (x + 55, y + 19), (x + 53, y + 25)],
                   fill=(240, 237, 220))
    elif kind == "ant19":
        # Anthropic IPO, small chart, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(16, 32, 64))
        SANS_B(cv, 9, x + 20, y + 3, "ANT", WHITE)
        SANS_B(cv, 9, x + w - 6 - text_width("sans_bold", 9, "$83"),
               y + 3, "$83", (60, 220, 130))
        cv.polyline([(x + 8, y + 32), (x + 40, y + 28), (x + 70, y + 24),
                     (x + 100, y + 18), (x + 130, y + 14), (x + 160, y + 8),
                     (x + 178, y + 5)], fill=(60, 220, 130), width=2)
        for (_bx, _bh) in ((14, 6), (44, 9), (74, 7), (104, 12), (134, 9),
                           (164, 14)):
            cv.rect(x + _bx, y + 34 - _bh, x + _bx + 10, y + 34,
                    fill=(60, 200, 120))
        cv.polygon([(x + 172, y + 2), (x + 180, y + 2), (x + 176, y + 10)],
                   fill=(60, 220, 130))
    elif kind == "fed19":
        # Central bank facade + big rising arrow, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(233, 233, 219))
        cv.rect(x + 9, y + 14, x + 94, y + 33, fill=(187, 190, 179))
        cv.polygon([(x + 5, y + 14), (x + 51, y + 3), (x + 98, y + 14)],
                   fill=(245, 243, 228), outline=(156, 165, 158))
        for cx in (14, 35, 56, 77):
            cv.rect(x + cx, y + 18, x + cx + 9, y + 32, fill=(247, 246, 231))
        cv.polygon([(x + 83, y + 35), (x + 103, y + 24), (x + 116, y + 26),
                    (x + 140, y + 8), (x + 135, y + 3), (x + 158, y + 3),
                    (x + 154, y + 23), (x + 149, y + 16), (x + 119, y + 35),
                    (x + 106, y + 32), (x + 92, y + 37)],
                   fill=(178, 34, 34))
        SANS_B(cv, 10, x + 122, y + 24, "95%", INK)
    elif kind == "icj19s":
        # World Court, small, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(232, 240, 244))
        cv.polygon([(x + 20, y + 14), (x + 70, y + 4), (x + 120, y + 14)],
                   fill=(220, 215, 200))
        cv.rect(x + 24, y + 14, x + 116, y + 32, fill=(240, 238, 225))
        for _cx in (32, 52, 72, 92):
            cv.rect(x + _cx, y + 18, x + _cx + 7, y + 32, fill=WHITE)
        cv.line(x + 152, y + 8, x + 152, y + 32, fill=GOLD, width=2)
        cv.line(x + 138, y + 12, x + 166, y + 12, fill=GOLD, width=2)
        for _px in (138, 166):
            cv.polygon([(x + _px - 7, y + 16), (x + _px + 7, y + 16),
                        (x + _px, y + 24)], fill=GOLD)
        cv.rect(x + 168, y + 4, x + 184, y + 18, fill=RED)
        SANS_B(cv, 9, x + 172, y + 7, "9-6", WHITE)
    elif kind == "cop19s":
        # COP31, small: globe + document + stamp, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(232, 240, 244))
        cv.ellipse(x + 10, y + 2, x + 42, y + 34, fill=NAVY)
        cv.ellipse(x + 11, y + 3, x + 41, y + 33, fill=(90, 170, 220))
        cv.ellipse(x + 17, y + 8, x + 27, y + 16, fill=(80, 170, 90))
        cv.ellipse(x + 28, y + 20, x + 38, y + 28, fill=(80, 170, 90))
        cv.rect(x + 58, y + 6, x + 138, y + 32, fill=WHITE,
                outline=NAVY, width=1)
        for _ly in (12, 18, 24):
            cv.line(x + 64, y + _ly, x + 132, y + _ly, fill=GREY, width=1)
        cv.ellipse(x + 122, y + 22, x + 134, y + 32, fill=RED)
        cv.ellipse(x + 125, y + 25, x + 131, y + 29, fill=WHITE)
        SANS_B(cv, 10, x + 146, y + 12, "CUT", RED)
        cv.line(x + 144, y + 24, x + 182, y + 24, fill=RED, width=2)
    elif kind == "pylon":
        # Night in Ukraine: the grid under attack, homes lit, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(22, 35, 66))
        cv.ellipse(x + 91, y + 4, x + 101, y + 14, fill=(155, 67, 59))
        cv.ellipse(x + 95, y + 2, x + 104, y + 11, fill=(22, 35, 66))
        cv.polygon([(x + 72, y + 32), (x + 72, y + 25), (x + 91, y + 25),
                    (x + 91, y + 21), (x + 106, y + 21), (x + 106, y + 27),
                    (x + 120, y + 27), (x + 120, y + 37), (x + 72, y + 37)],
                   fill=(35, 46, 65))
        cv.polygon([(x + 115, y + 15), (x + 143, y + 15), (x + 143, y + 11),
                    (x + 179, y + 11), (x + 179, y + 37), (x + 115, y + 37)],
                   fill=(48, 57, 70))
        for (wx, wy) in ((123, 21), (137, 20), (153, 17), (168, 17),
                         (153, 29)):
            cv.rect(x + wx, y + wy, x + wx + 4, y + wy + 6,
                    fill=(232, 204, 108))
        cv.line(x + 25, y + 35, x + 40, y + 4, fill=(11, 20, 35), width=2)
        cv.line(x + 55, y + 35, x + 40, y + 4, fill=(11, 20, 35), width=2)
        cv.line(x + 19, y + 11, x + 61, y + 11, fill=(11, 20, 35), width=2)
        cv.line(x + 24, y + 19, x + 56, y + 19, fill=(11, 20, 35), width=2)
        cv.polyline([(x + 2, y + 14), (x + 20, y + 16), (x + 40, y + 11),
                     (x + 65, y + 16), (x + 85, y + 14)], fill=(11, 20, 35),
                    width=1)
        cv.rect(x, y + 36, x + 185, y + 37, fill=(16, 25, 39))
    elif kind == "bengal":
        # Cyclone Akvan: flattened storm with a clear eye, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(116, 169, 196))
        cv.polygon([(x, y), (x + 39, y), (x + 35, y + 9), (x + 46, y + 17),
                    (x + 41, y + 24), (x + 53, y + 31), (x + 49, y + 37),
                    (x, y + 37)], fill=(210, 198, 153))
        cv.polyline([(x + 40, y + 2), (x + 36, y + 9), (x + 48, y + 17),
                     (x + 43, y + 24), (x + 55, y + 31), (x + 51, y + 36)],
                    fill=(164, 201, 207), width=3)
        cv.ellipse(x + 56, y + 2, x + 181, y + 36, fill=(59, 116, 160))
        cv.polyline([(x + 65, y + 27), (x + 62, y + 20), (x + 67, y + 12),
                     (x + 80, y + 6), (x + 99, y + 4), (x + 120, y + 6),
                     (x + 137, y + 12), (x + 143, y + 19), (x + 138, y + 26),
                     (x + 125, y + 30)], fill=(224, 237, 231), width=5)
        cv.polyline([(x + 173, y + 11), (x + 177, y + 19), (x + 170, y + 27),
                     (x + 156, y + 32), (x + 137, y + 34), (x + 116, y + 31),
                     (x + 103, y + 25), (x + 101, y + 18), (x + 107, y + 12),
                     (x + 119, y + 10)], fill=(224, 237, 231), width=5)
        cv.polyline([(x + 91, y + 11), (x + 102, y + 7), (x + 118, y + 8),
                     (x + 132, y + 13), (x + 136, y + 19), (x + 132, y + 25),
                     (x + 122, y + 28), (x + 112, y + 25), (x + 108, y + 20),
                     (x + 112, y + 16), (x + 119, y + 15), (x + 125, y + 18)],
                    fill=(247, 247, 232), width=3)
        cv.ellipse(x + 116, y + 16, x + 124, y + 24, fill=(54, 112, 156))
        cv.ellipse(x + 118, y + 18, x + 122, y + 22, fill=(151, 198, 212))
    elif kind == "space":
        # Voyager 1: the big white dish, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(10, 18, 43))
        for sx, sy in ((9, 7), (31, 25), (49, 5), (72, 30), (88, 9),
                       (157, 30), (179, 7)):
            cv.ellipse(x + sx, y + sy, x + sx + 2, y + sy + 2,
                       fill=(226, 233, 236))
        cv.ellipse(x + 10, y + 23, x + 21, y + 34, fill=(62, 119, 174))
        cv.polygon([(x + 12, y + 25), (x + 17, y + 24), (x + 18, y + 27),
                    (x + 15, y + 29), (x + 16, y + 32), (x + 12, y + 30)],
                   fill=(104, 151, 107))
        for (sx, sy, ex, ey) in ((137, 13, 144, 10), (149, 8, 156, 6),
                                 (162, 5, 169, 4), (175, 4, 182, 4)):
            cv.line(x + sx, y + sy, x + ex, y + ey, fill=(211, 225, 235),
                    width=1)
        cv.line(x + 110, y + 29, x + 83, y + 35, fill=(176, 155, 91),
                width=2)
        cv.polygon([(x + 104, y + 26), (x + 117, y + 24), (x + 125, y + 30),
                    (x + 112, y + 35), (x + 102, y + 32)], fill=(209, 168, 58))
        cv.line(x + 113, y + 28, x + 108, y + 13, fill=(167, 178, 186),
                width=1)
        cv.line(x + 113, y + 28, x + 134, y + 24, fill=(167, 178, 186),
                width=1)
        cv.polygon([(x + 98, y + 4), (x + 106, y + 3), (x + 117, y + 7),
                    (x + 129, y + 15), (x + 140, y + 25), (x + 141, y + 29),
                    (x + 133, y + 30), (x + 121, y + 25), (x + 109, y + 17),
                    (x + 100, y + 9)], fill=(244, 244, 230))
        cv.polygon([(x + 100, y + 9), (x + 109, y + 17), (x + 121, y + 25),
                    (x + 133, y + 30), (x + 141, y + 29), (x + 135, y + 33),
                    (x + 123, y + 29), (x + 110, y + 22), (x + 102, y + 14)],
                   fill=(185, 198, 205))
        cv.line(x + 119, y + 17, x + 130, y + 8, fill=(154, 166, 176),
                width=1)
        cv.ellipse(x + 128, y + 6, x + 132, y + 10, fill=(219, 187, 83))
    elif kind == "ethiopia":
        # Two armies face each other across the desert border, 186x38.
        cv.rect(x, y, x + w, y + h, fill=(189, 216, 226))
        cv.polygon([(x, y + 18), (x + 28, y + 9), (x + 58, y + 18),
                    (x + 89, y + 12), (x + 123, y + 19), (x + 155, y + 10),
                    (x + 185, y + 17), (x + 185, y + 25), (x, y + 25)],
                   fill=(173, 164, 128))
        cv.rect(x, y + 21, x + 185, y + 37, fill=(220, 194, 143))
        for by in (21, 27, 33):
            cv.line(x + 93, y + by, x + 93, y + by + 3, fill=(135, 112, 79),
                    width=1)
        cv.rounded_rect(x + 12, y + 27, x + 63, y + 34, radius=3,
                        fill=(66, 70, 49))
        cv.rounded_rect(x + 123, y + 27, x + 174, y + 34, radius=3,
                        fill=(66, 70, 49))
        cv.polygon([(x + 15, y + 22), (x + 54, y + 22), (x + 63, y + 28),
                    (x + 12, y + 28)], fill=(110, 120, 72))
        cv.polygon([(x + 132, y + 22), (x + 171, y + 22), (x + 174, y + 28),
                    (x + 123, y + 28)], fill=(110, 120, 72))
        cv.rect(x + 28, y + 16, x + 48, y + 23, fill=(88, 104, 63))
        cv.rect(x + 138, y + 16, x + 158, y + 23, fill=(88, 104, 63))
        cv.line(x + 47, y + 19, x + 76, y + 19, fill=(67, 84, 51), width=3)
        cv.line(x + 139, y + 19, x + 110, y + 19, fill=(67, 84, 51), width=3)
        figure(cv, x + 25, y + 26, 6, (143, 104, 73), (91, 109, 65))
        figure(cv, x + 160, y + 26, 6, (143, 104, 73), (91, 109, 65))
        cv.ellipse(x + 20, y + 21, x + 30, y + 25, fill=(64, 83, 50))
        cv.ellipse(x + 155, y + 21, x + 165, y + 25, fill=(64, 83, 50))
    else:  # gta — GTA VI launch: the shop, the controller, midnight.
        cv.rect(x, y, x + w, y + h, fill=(27, 67, 72))
        cv.rect(x + 75, y + 13, x + 181, y + 36, fill=(208, 199, 165))
        cv.rect(x + 82, y + 22, x + 107, y + 35, fill=(83, 125, 132))
        cv.rect(x + 113, y + 22, x + 139, y + 35, fill=(83, 125, 132))
        cv.rect(x + 145, y + 22, x + 160, y + 36, fill=(61, 97, 105))
        cv.polygon([(x + 70, y + 11), (x + 169, y + 11), (x + 177, y + 20),
                    (x + 75, y + 20)], fill=(180, 59, 58))
        cv.line(x + 75, y + 20, x + 176, y + 20, fill=(119, 43, 45),
                width=2)
        cv.polygon([(x + 14, y + 12), (x + 24, y + 7), (x + 83, y + 7),
                    (x + 94, y + 12), (x + 105, y + 30), (x + 102, y + 35),
                    (x + 91, y + 35), (x + 77, y + 26), (x + 36, y + 26),
                    (x + 22, y + 35), (x + 11, y + 35), (x + 7, y + 30)],
                   fill=(18, 28, 40))
        cv.rounded_rect(x + 20, y + 9, x + 91, y + 26, radius=7,
                        fill=(44, 60, 72))
        cv.rect(x + 28, y + 14, x + 33, y + 25, fill=(188, 198, 191))
        cv.rect(x + 25, y + 17, x + 36, y + 22, fill=(188, 198, 191))
        cv.ellipse(x + 43, y + 21, x + 52, y + 30, fill=(10, 20, 29))
        cv.ellipse(x + 65, y + 21, x + 74, y + 30, fill=(10, 20, 29))
        for (bx, by, col) in ((79, 12, (183, 63, 66)),
                              (85, 17, (79, 157, 112)),
                              (73, 17, (76, 135, 184)),
                              (79, 22, (216, 184, 76))):
            cv.ellipse(x + bx, y + by, x + bx + 5, y + by + 5, fill=col)
        cv.ellipse(x + 145, y + 2, x + 179, y + 36, fill=(20, 30, 39))
        cv.ellipse(x + 148, y + 5, x + 176, y + 33, fill=(247, 243, 225))
        for (tx, ty, ex, ey) in ((162, 7, 162, 10), (162, 28, 162, 31),
                                 (150, 19, 153, 19), (171, 19, 174, 19)):
            cv.line(x + tx, y + ty, x + ex, y + ey, fill=(28, 37, 43),
                    width=1)
        cv.line(x + 162, y + 19, x + 162, y + 9, fill=(28, 37, 43), width=2)
        cv.line(x + 162, y + 19, x + 161, y + 12, fill=(28, 37, 43),
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


def _region_bar(cv, y):
    bx = MX
    total = sum(c for _n, c, _col, _tc in REGION_BAR)
    widths = [(W - 2 * MX) * c // total
              for _n, c, _col, _tc in REGION_BAR]
    deficit = sum(max(0, 60 - wdt) for wdt in widths)
    donors = sorted(range(len(widths)), key=lambda i: -widths[i])[:2]
    dtot = sum(widths[i] for i in donors)
    for i in donors:
        widths[i] -= deficit * widths[i] // dtot
    widths = [60 if wdt < 60 else wdt for wdt in widths]
    for k, (name, count, col, tcol) in enumerate(REGION_BAR):
        seg = (W - MX - bx) if k == len(REGION_BAR) - 1 else widths[k]
        cv.rect(bx, y, bx + seg - 1, y + 16, fill=col)
        label = f"{name} {count}"
        size = 9 if text_width("sans_bold", 9, label) <= seg - 2 else 8
        lw = text_width("sans_bold", size, label)
        SANS_B(cv, size, bx + (seg - lw) // 2, y + 3, label, tcol)
        bx += seg


def _numbers_strip(cv, y):
    nx = MX
    SANS_B(cv, 9, nx, y, "THE DAY IN NUMBERS:  ", GREY)
    nx += text_width("sans_bold", 9, "THE DAY IN NUMBERS:  ")
    for j, (num, label) in enumerate(NUMBERS):
        SANS_B(cv, 9, nx, y, num, RED)
        nx += text_width("sans_bold", 9, num)
        SANS(cv, 9, nx, y, label, INK)
        nx += text_width("sans", 9, label)
        if j < len(NUMBERS) - 1:
            SANS(cv, 9, nx, y, "   \u2022   ", GREY)
            nx += text_width("sans", 9, "   \u2022   ")


def _hero_card(cv, i, x, y, hw, hg, cat, region, kind, title, dek):
    cv.rect(x + 3, y + 3, x + hw + 3, y + hg + 3, fill=(220, 214, 196))
    cv.rect(x, y, x + hw, y + hg, fill=WHITE,
            outline=(180, 172, 150), width=2)
    cv.rect(x, y, x + hw, y + 3, fill=RED)
    scene(cv, kind, x + 2, y + 5, hw - 4, 110)
    cv.rect(x + 2, y + 5, x + 16, y + 19, fill=RED)
    num = str(i + 1)
    nw = text_width("sans_bold", 10, num)
    SANS_B(cv, 10, x + 2 + (14 - nw) // 2, y + 7, num, WHITE)
    ctw = text_width("sans_bold", 9, cat)
    cv.rect(x + 10, y + 120, x + 10 + ctw + 14, y + 134,
            fill=CHIP[region])
    SANS_B(cv, 9, x + 17, y + 122, cat, INK if region == "asia" else WHITE)
    text_block(cv, "serif_bold", 19, x + 10, y + 138, title, INK,
               hw - 20, 22, max_lines=2)
    text_block(cv, "sans", 12, x + 10, y + 186, dek, GREY, hw - 20, 15,
               max_lines=2)


def _grid_card(cv, i, x, y, gw, gh, cat, region, kind, title, dek):
    cv.rect(x + 2, y + 2, x + gw + 2, y + gh + 2, fill=(220, 214, 196))
    cv.rect(x, y, x + gw, y + gh, fill=WHITE,
            outline=(180, 172, 150), width=2)
    cv.rect(x, y, x + gw, y + 3, fill=RED)
    scene(cv, kind, x + 2, y + 5, gw - 4, 38)
    cv.rect(x + 2, y + 5, x + 16, y + 19, fill=RED)
    num = str(i + 4)
    nw = text_width("sans_bold", 10, num)
    SANS_B(cv, 10, x + 2 + (14 - nw) // 2, y + 7, num, WHITE)
    ctw = text_width("sans_bold", 9, cat)
    cv.rect(x + 8, y + 46, x + 8 + ctw + 10, y + 59, fill=CHIP[region])
    SANS_B(cv, 9, x + 13, y + 48, cat, INK if region == "asia" else WHITE)
    text_block(cv, "serif_bold", 14, x + 8, y + 61, title, INK,
               gw - 16, 16, max_lines=2)
    text_block(cv, "sans", 11, x + 8, y + 95, dek, GREY, gw - 16, 12,
               max_lines=2)


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
    if dotted:
        cv.rect(mx, my, mx + 460, my + 190, fill=(16, 32, 64))
        for _py in range(4, 188, 7):
            for _px in range(4, 458, 7):
                for _poly in CONTINENTS:
                    if _inside(_px, _py, _poly):
                        cv.rect(mx + _px, my + _py, mx + _px + 2,
                                my + _py + 2, fill=(200, 210, 220))
                        break
    else:
        cv.rect(mx, my, mx + 460, my + 190, fill=MAPSEA)
        for poly in CONTINENTS:
            pts = [(mx + px, my + py) for px, py in poly]
            cv.polygon(pts, fill=LAND, outline=(90, 130, 90))
        _greenland = [(158, 14), (178, 6), (196, 10), (200, 20),
                      (188, 28), (168, 26), (156, 20)]
        cv.polygon([(mx + px, my + py) for px, py in _greenland],
                   fill=(225, 235, 220), outline=(150, 180, 160))
        _antarctica = [(140, 182), (230, 176), (320, 180), (420, 176),
                       (460, 182), (460, 190), (140, 190)]
        cv.polygon([(mx + px, my + py) for px, py in _antarctica],
                   fill=(235, 242, 244), outline=(190, 210, 220))
        _ocean = (70, 145, 185)
        _aw = text_width("sans_bold", 11, "ATLANTIC")
        SANS_B(cv, 11, mx + 178 - _aw // 2, my + 62, "ATLANTIC", _ocean)
        _ow = text_width("sans_bold", 11, "OCEAN")
        SANS_B(cv, 11, mx + 178 - _ow // 2, my + 74, "OCEAN", _ocean)
        SANS_B(cv, 10, mx + 6, my + 160, "PACIFIC", _ocean)
        SANS_B(cv, 10, mx + 6, my + 172, "OCEAN", _ocean)
        _iw = text_width("sans_bold", 11, "INDIAN")
        SANS_B(cv, 11, mx + 325 - _iw // 2, my + 138, "INDIAN", _ocean)
        _ow2 = text_width("sans_bold", 11, "OCEAN")
        SANS_B(cv, 11, mx + 325 - _ow2 // 2, my + 150, "OCEAN", _ocean)
        SANS_B(cv, 8, mx + 204, my + 14, "GREENLAND", (90, 140, 170))
        SANS_B(cv, 8, mx + 79, my + 24, "NORTH", (200, 110, 40))
        SANS_B(cv, 8, mx + 76, my + 34, "AMERICA", (200, 110, 40))
        SANS_B(cv, 8, mx + 111, my + 130, "SOUTH", (200, 110, 40))
        SANS_B(cv, 8, mx + 106, my + 140, "AMERICA", (200, 110, 40))
        SANS_B(cv, 9, mx + 228, my + 84, "AFRICA", (178, 34, 34))
        _ew = text_width("sans_bold", 9, "EURASIA")
        SANS_B(cv, 9, mx + 351 - _ew // 2, my + 38, "EURASIA",
               (150, 100, 0))
        SANS_B(cv, 7, mx + 388, my + 134, "AUSTRALIA", (14, 110, 120))
        _nw = text_width("sans_bold", 8, "ANTARCTICA")
        SANS_B(cv, 8, mx + 230 - _nw // 2, my + 181, "ANTARCTICA",
               (90, 140, 170))
        _whale = (72, 132, 172)
        cv.ellipse(mx + 62, my + 166, mx + 106, my + 180, fill=_whale)
        cv.polygon([(mx + 64, my + 170), (mx + 52, my + 164),
                    (mx + 54, my + 178)], fill=_whale)
        cv.ellipse(mx + 96, my + 171, mx + 99, my + 174, fill=INK)
        cv.ellipse(mx + 185, my + 162, mx + 225, my + 174, fill=_whale)
        cv.polygon([(mx + 185, my + 167), (mx + 175, my + 162),
                    (mx + 176, my + 173)], fill=_whale)
        cv.ellipse(mx + 217, my + 166, mx + 220, my + 169, fill=INK)
        cv.polygon([(mx + 160, my + 112), (mx + 196, my + 112),
                    (mx + 190, my + 120), (mx + 166, my + 120)],
                   fill=(120, 70, 40))
        cv.line(mx + 178, my + 112, mx + 178, my + 98, fill=INK, width=2)
        cv.polygon([(mx + 180, my + 100), (mx + 180, my + 110),
                    (mx + 194, my + 110)], fill=WHITE)
        cv.ellipse(mx + 432, my + 4, mx + 448, my + 18, fill=(230, 120, 60))
        cv.rect(mx + 438, my + 20, mx + 444, my + 25, fill=(120, 70, 40))
        for _px, _py in ((170, 13), (184, 15)):
            cv.ellipse(mx + _px - 3, my + _py - 3, mx + _px + 3,
                       my + _py + 4, fill=INK)
            cv.ellipse(mx + _px - 2, my + _py, mx + _px + 2, my + _py + 4,
                       fill=WHITE)
        for _px in (165, 350):
            cv.ellipse(mx + _px - 3, my + 181, mx + _px + 3, my + 188,
                       fill=INK)
            cv.ellipse(mx + _px - 2, my + 183, mx + _px + 2, my + 188,
                       fill=WHITE)
    for _num, (px, py, reg) in dots_small.items():
        cx, cy = mx + px, my + py
        cv.ellipse(cx - 3, cy - 3, cx + 3, cy + 3, fill=REGION[reg])
    for num, (px, py) in dots.items():
        cx, cy = mx + px, my + py
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
        cv.ellipse(lx - 4, my + 194, lx + 4, my + 202, fill=col)
        SANS(cv, 11, lx + 7, my + 192, name, _lcol)
        lx += 7 + text_width("sans", 11, name) + 14
    SANS(cv, 11, mx, my + 208, "Pins = cards  \u2022  dots = briefs", _lcol)


def _also_panel(cv, by, ph, also, title, cols, col_w, wrap_w, size,
                leading, start_num):
    ax = MX + 508
    cv.rect(ax, by, W - MX, by + ph, fill=WHITE,
            outline=(180, 172, 150), width=2)
    SANS_B(cv, 14, ax + 12, by + 8, title, INK)
    per = (len(also) + cols - 1) // cols
    for col_i in range(cols):
        cx = ax + 12 + col_i * col_w
        yy = by + 34
        for i, item in enumerate(
                also[col_i * per:(col_i + 1) * per],
                start=col_i * per + start_num):
            SANS_B(cv, 10, cx, yy, f"{i}", RED)
            lines = wrap("sans", size, item, wrap_w)
            text_block(cv, "sans", size, cx + 20, yy, item, INK, wrap_w,
                       leading, max_lines=3)
            yy += leading * max(1, min(3, len(lines)))


def _date_check(cv, y, h, fill):
    cv.rect(MX, y, W - MX, y + h, fill=fill, outline=RED, width=2)
    cv.rect(MX, y, MX + 6, y + h, fill=RED)
    SANS_B(cv, 11, MX + 16, y + 6, "DATE CHECK:  ", RED)
    text_block(cv, "sans", 11, MX + 16 + text_width("sans_bold", 11,
               "DATE CHECK:  "), y + 6, DATE_CHECK, INK,
               W - 2 * MX - 16 - text_width("sans_bold", 11,
               "DATE CHECK:  "), 15, max_lines=2)


def _footer(cv, y):
    SANS(cv, 10, MX, y,
         "Every story here happened or was first reported on "
         "Thursday, 19 November 2026. Contested claims are "
         "attributed. Sources: Reuters, AP, AFP, Al Jazeera, "
         "Bloomberg. Original drawings.", GREY)


def front_page(style, heroes, grid, also, dots, dots_small, subhead,
              kicker_l, kicker_r, title, also_title):
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
        hero_y, grid_y = 92, 374
        cv.rect(MX, 330, W - MX, 366, fill=NAVY)
        _stats = [("$81.3bn", "raised by Anthropic, the largest IPO ever"),
                  ("$83", "ANT's debut price, above its range"),
                  ("109-0", "Danish vote on the Arctic pact"),
                  ("16bn miles", "Voyager 1 away from Earth"),
                  ("95%", "chance of a Dec Fed hike")]
        _sx = MX + 10
        _colw = (W - 2 * MX - 20) // 5
        for _num, _lab in _stats:
            SANS_B(cv, 18, _sx, 334, _num, GOLD)
            SANS(cv, 8, _sx, 354, _lab, WHITE)
            _sx += _colw
        map_y, map_h, dc_y, dc_h, ft_y = 630, 280, 918, 48, 974
    else:
        SANS_B(cv, 10, MX, 8, kicker_l, RED if style == "airy" else INK)
        SANS_B(cv, 10, W - MX - text_width("sans_bold", 10, kicker_r), 8,
               kicker_r, RED)
        SERIF_B(cv, 52, MX, 22, title, INK)
        SERIF(cv, 15, MX, 80, subhead, RED)
        if style == "classic":
            _region_bar(cv, 100)
            cv.rect(MX, 119, W - MX, 134, fill=INK)
            _ft = "BY FIELD:  " + "   \u2022   ".join(
                f"{name} {count}" for name, count in FIELD_BAR)
            SANS(cv, 10, MX + 8, 122, _ft, WHITE)
            _numbers_strip(cv, 138)
            hero_y, grid_y = 158, 396
            map_y, map_h, dc_y, dc_h, ft_y = 652, 260, 920, 48, 974
        else:  # airy
            _numbers_strip(cv, 100)
            hero_y, grid_y = 122, 360
            map_y, map_h, dc_y, dc_h, ft_y = 672, 250, 930, 48, 986
    hw, hg, gap = 322, 230, 8
    for i, (cat, region, kind, t, dek) in enumerate(heroes):
        _hero_card(cv, i, MX + i * (hw + gap), hero_y, hw, hg, cat,
                   region, kind, t, dek)
    if style == "airy":
        gw, gh, cols = 240, 148, 4
    else:
        gw, gh, cols = 190, 120, 5
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
    if style == "airy":
        _also_panel(cv, map_y, map_h, also, also_title, 2, 220, 190, 10,
                    13, n_cards + 1)
    else:
        _also_panel(cv, map_y, map_h, also, also_title, 3, 156, 128, 8,
                    10, n_cards + 1)
    _date_check(cv, dc_y, dc_h,
                (250, 225, 225) if style == "airy" else None)
    _footer(cv, ft_y)
    return cv

# --- entry point: option 2A, Front Page Classic (top-1 template) --------
init_fonts(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fonts.bin"))
cv = front_page(
    "classic", HERO_A, GRID_A, ALSO_A, DOTS_A, DOTS_SMALL_A,
    "Trump, Xi and Putin share one table \u00b7 The World Court finds "
    "genocide in Myanmar \u00b7 COP31's draft drops fossil fuels",
    "THE WORLD IN ONE DAY",
    "42 STORIES  \u2022  EVERY CONTINENT  \u2022  ALL FROM THIS ONE DAY",
    "Thursday 19 November 2026",
    "ALSO ON THURSDAY 19 NOVEMBER 2026")
save(cv, "entry.png")
