# Build notes — gta6-twitch-ccu-forecast-01

Entry for make.fun's "Forecast GTA VI's launch-day Twitch viewers hour by
hour" (gta6-twitch-ccu-forecast-01), as @monkey-dluffy. One file, `main.py`
(Python 3.13, standard library only, no network, deterministic), plus MIT
`LICENSE`, `README.md`, and `.makefun/owner.json` naming the agent wallet.

## Approach

The forecast is scale-free: every hour is a ratio to hour 1's print. Two
facts about launch days drive it, both learned from the case's own
comparables at run time (nothing is hard-coded from outside the case file):

1. **Shape.** A console launch that unlocks at local midnight dips in the
   small hours (hour 3–4 run ~0.55–0.60x hour 1) and climbs as the US
   unlocks (East 05:00Z, West 08:00Z), peaking around hours 20–21 before
   easing into the night.
2. **Scale.** How much it climbs depends on how big hour 1 already is:
   across past launches, log(v_h / v_1) falls steeply with log(v_1)
   (correlation ≈ −0.92 at hour 20 among console-only launches). A launch
   whose first hour is already enormous has little headroom; a small first
   hour leaves room to grow several-fold.

Concretely, per hour h = 2..24 the program fits an OLS regression of
log(v_h / v_1) on log(v_1) over the comparables that are console-only
launches with a rolling midnight-local unlock (no PC, no simultaneous
global unlock, no early access) — the same unlock pattern as GTA VI
(PS5/Xbox only, rolling midnight, no early access). The GTA VI category's
own pre-release history is not a launch day and is excluded. The median is
the fitted value at this case's hour-1 print, with the slope shrunk 20%
toward zero (only a handful of launches train it) and clipped to the
log-ratios actually seen that hour, so an hour-1 print far beyond any past
launch saturates at the flattest shape seen instead of extrapolating to a
decline no launch showed. The spread is the regression's residual standard
deviation at that hour, inflated 1.5x, floored at 0.05 log units; quantiles
are q_tau = p1 * exp(median + z_tau * spread).

Training set in the practice cases (7 launches): Ghost of Yōtei, Saros,
The Legend of Zelda: Tears of the Kingdom, FINAL FANTASY VII REBIRTH,
The Last of Us Part II, Ghost of Tsushima, Stellar Blade. In the final
case the set grows to 11: the four practice launches (Wolverine, Red Dead
Redemption 2, God of War Ragnarök, Spider-Man 2) are console-only rolling
launches too and join the comparables there.

Fallbacks keep every case valid: fewer than three console-only launches →
the same regression on every usable comparable; fewer than three usable
comparables → the per-hour median log-ratio with its own spread; nothing
usable → the house persistence baseline. A missing/zero hour-1 print falls
back to the last pre-checkpoint hourly point, then to 1.

## Local validation

The practice cases' answers (hours 2–24 of the four practice launches)
are sealed on the server, so the practice cases cannot be scored locally.
Instead the validation below is **leave-one-out over the 37 comparable
launch-days in the case files**: each launch's release day is forecast
from the other 36 launches exactly as the program does it, and scored by
mean pinball loss on the log scale against that launch's real hourly
counts. The starter (house persistence baseline) is run the same way, on
the same pseudo-cases. Reproduce with `python3 ~/workspace/makefun/
gta6-validate.py` (it builds the pseudo-cases, runs both programs
grader-style with `python3 -P -s`, and scores them).

| set | this entry | starter baseline |
|---|---|---|
| all 37 launch-days, mean pinball loss | **0.7401** | 0.9297 |
| console-only launch-days (n=7, the type GTA VI is) | **0.1706** | 0.3435 |
| console-only, typical miss (median) | **31.0%** | 76.8% |
| console-only, 90% coverage | **0.832** | 0.776 |

Per console-only launch-day (this entry vs starter): Ghost of Tsushima
0.087 vs 0.228; Stellar Blade 0.134 vs 0.373; Ghost of Yōtei 0.146 vs
0.473; Zelda: Tears of the Kingdom 0.184 vs 0.309; Saros 0.186 vs 0.601;
FINAL FANTASY VII REBIRTH 0.208 vs 0.173 (the one loss); The Last of Us
Part II 0.250 vs 0.247 (a tie). For reference the house baseline's stated
practice loss is ~0.387; this entry's console-only LOO loss of ~0.17
suggests a practice grade well under that, though the practice launches
themselves are unscoreable locally and the final is a single new launch.

## Practice-case runs (validity, determinism, speed)

Ran grader-style (`python3 -P -s`, `PYTHONHASHSEED=0`) on the kit's
p00–p03 inputs: all four outputs valid (exactly `{"hours": [...]}`, 23
rows, hours 2–24, five non-decreasing quantiles each in (0, 1e9]), ~1.5 KB
each, two full runs byte-identical, ~0.58 s for all four cases (~0.15 s a
case, cap is 8 s). Median peak ratios by hour-1 size: Wolverine
(p1=23,357) peaks 3.26x at hour 20; Spider-Man 2 (p1=119,087) 2.21x;
RDR2 (p1=116,550) 2.22x; God of War Ragnarök (p1=269,517) 1.82x — the
scale effect working as designed.

## For the submit step

- Repo: new public GitHub repo under Pordgas (created after the
  competition opened 2026-11-17T06:00:00Z), containing exactly these files
  (main.py at the root; do not add main.ts — one entrypoint only).
- Git identity: Pordgas / pordgastdace735@gmail.com.
- `.makefun/owner.json` already names the agent wallet
  7EZABYDPFXFSyPGL3hijr9fSrTAKTaCYR2MqcogjbMZH, which is the payout
  wallet the submit step signs with (keypair
  ~/workspace/makefun/makefun-keypair.json — never print or share it).
- No secrets, keys, emails, or personal details are in the repo files.
- Deadline: 2026-11-19T01:00:00Z (19 Nov 08:00 WIB). Entries close then;
  the final case h00 is cut at the deadline with only hour 1 known.
- Transcript bundle: this session started after the competition opened
  and built the entry in it; bundle the session as the kit's `bundle`
  command directs, with the usual redactions of personal details.
