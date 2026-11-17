# gta6-twitch-ccu-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Pordgas/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Pordgas/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A forecaster for Grand Theft Auto VI's launch-day Twitch viewers, hour by hour: one hour into the release day (2026-11-19 UTC) it predicts the concurrent viewers in the GTA VI category for each of hours 2–24, as five quantiles an hour. It learns the launch-day shape from past console launches with the same rolling midnight unlock — the day dips in the small hours, then climbs as the US unlocks — and scales that shape by how big the first hour already is, because a huge first hour leaves little headroom to grow. Python 3.13, standard library only, no network, fully deterministic.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`input` is the directory holding the case files (`<id>.in`, from the competition kit); the program writes `<id>.out` for each one. In the grader the input and output directories are `/input` and `/output`. See `BUILD-NOTES.md` for the approach and the local validation numbers.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
