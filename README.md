# news-image-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/Holladitt/news-image-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/Holladitt/news-image-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

The Day in World News — Thursday 19 November 2026. A dense front page
that sums up the day's world news in one image: a masthead, three hero
stories (the Shenzhen three-way summit, the World Court's genocide
verdict, COP31's draft dropping fossil fuels), a ten-panel grid, a
cartoon world map with numbered pins and an "Also on" list, covering
42 stories from seven regions, all reported on Thursday 19 November
2026. It follows the leaderboard's winning front-page format: three
heroes, a ten-panel grid, a cartoon world map (light-blue ocean,
ocean and continent labels, Greenland and Antarctica, whales, a ship,
a balloon, penguins) with numbered pins and colour-coded dots, and a
three-column "Also on" list — with headlines that stay readable at
thumbnail size.
Every illustration is drawn procedurally with the standard library
only; no network, no external assets, no third-party packages.
Text is rendered from `fonts.bin`, a grayscale glyph atlas
rasterized once from DejaVu (OFL) — the grader's plain
python:3.13-slim image has no Pillow and no fonts of its own.

## Run it

```sh
python3 main.py
# writes /output/entry.png (1024x1024, deterministic)
```

Requires Python 3.13 and nothing else (stdlib only).

---

<sub>Entered on [make.fun](https://make.fun/?ref=t774y4rd&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
