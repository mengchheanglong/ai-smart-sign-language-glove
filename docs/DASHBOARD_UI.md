# Dashboard UI — design record

The telemetry console (`dashboard/app.py`) is styled as a measurement instrument for a
research setting, not a presentation page. This note records the system, the decisions and
the limits, so a later change does not silently undo them.

## What was wrong before

| Problem | Evidence |
|---|---|
| Presentation styling, not instrument styling | Gradient headline text, `backdrop-filter: blur` glass cards, animated pulse dot |
| Emoji as interface vocabulary | `🖐️ 5-Finger Flex Sensors`, `🧭`, `🎛️`, `🔴 Bent (90°)`, `🖕` as the ring-finger icon |
| Five ad-hoc chart palettes | Probabilities used a gradient colourscale; acceleration and rate each used three unrelated hues |
| Box-on-box hierarchy | Header card + hero card + five finger cards + ticker + panel cards, all bordered and shadowed |
| Invented content | Sentence ticker initialised to `["HELLO"]`, so a translation appeared before any gesture was made |
| A control that did nothing | The "Debounce Window" slider set `predictor.smoothing_window`, but the rolling `deque` kept its original `maxlen` |
| Unlabelled measurement | Axes hidden on the probability chart; units and scale unstated on the accelerometer charts |
| Remote font dependency | `@import` of Plus Jakarta Sans from Google, which fails offline in a lab demo |

## Structure

One page, four sections plus a diagnostics drawer. Section headers use a single pattern:
title on the left, machine-readable meta on the right, one hairline rule underneath.

1. **Header** — project identity, then session meta (source, session clock, frames/s, gate)
   and one status chip. Status is a word plus a dot; colour never carries meaning alone.
2. **Current recognition** — the class, its identifier, its gloss, and four readouts
   (confidence, margin to gate, frames held, best-class probability) beside class
   probabilities with the gate drawn as a dotted vertical line on the chart. The chip
   distinguishes *Recognised* from *Sustained · below gate*: the majority window can hold a
   class while the current frame sits under the gate, and saying so is more honest than
   calling that frame recognised. A note under the chart states that the bars are this
   frame's probabilities while the reported class is the window's majority.
3. **Flex channels** — a measurement table (`Channel · Pin · ADC · Volts · Bend · State`)
   instead of five decorated cards. State is a dot *shape* (open, half, filled) plus a word.
4. **Orientation and motion** — derived pitch/roll/resultant/posture in a four-cell strip,
   then per-axis acceleration and angular rate on fixed, labelled ranges.
5. **Session log** — the committed gloss line, then the last eight commits with the
   confidence that committed them, and a truthful empty state.
6. **Measurement notes** — "What this shows" beside "What it does not show", equal weight.
7. **Diagnostics** — collapsed: raw packet JSON, frame counts, model artifact and classes.

## Tokens

Single source of truth is the `T` dict at the top of `app.py`; the CSS is generated from it
with `string.Template`, and every Plotly trace reads the same values.

| Token | Value | Role |
|---|---|---|
| `bg` | `#FFFFFF` | Canvas |
| `surface` / `surface-2` | `#FAFAFA` / `#F4F4F5` | Sidebar, gloss line, hover |
| `surface-3` | `#EBEBEE` | Meter tracks |
| `line` / `line-strong` | `rgba(24,24,27,0.10)` / `0.18` | Hairlines, input borders |
| `text` / `text-2` / `text-3` | `#18181B` / `#52525B` / `#6B6B74` | Primary, secondary, meta |
| `accent` | `#1B62D6` | Interaction, and the top class bar only |
| `ok` / `warn` / `danger` | `#12633F` / `#8A5A00` / `#B42318` | Real status states only |
| `bar` / `bar_neutral` | `rgba(24,24,27,0.72)` / `0.18` | Measurement bars / non-top classes |

Computed ratios (WCAG 2.2 AA needs 4.5:1 for text, 3:1 for large text and UI parts):

| Pair | Ratio |
|---|---|
| `text` on `bg` | 17.72:1 |
| `text-2` on `bg` | 7.73:1 |
| `text-3` on `bg` | 5.28:1 |
| `text-3` on sidebar `surface` | 5.05:1 |
| `accent` on `bg` | 5.58:1 |
| `ok` on `bg` | 7.29:1 |
| `warn` on `bg` | 5.93:1 |
| `danger` on `bg` | 6.57:1 |
| `ok` on its chip fill | 6.80:1 |
| `warn` on its chip fill | 5.54:1 |
| `danger` on its chip fill | 6.01:1 |

Typography: system sans stack for the interface, system mono for every measured value with
`font-variant-numeric: tabular-nums`, so columns of numbers align. No web fonts are loaded,
which keeps the console readable with no network. Scale: 10–11 meta, 12–13 secondary,
15–17 emphasis, 24 section identity, 31 the recognised class.

Shape: 999 px pills for status chips and meters, 10 px for the gloss line and notes block,
8 px for buttons, 4 px for meter tracks, square for the section grid and tables.

## Rejected alternatives

- **Dual light/dark themes with a runtime switch.** The CSS is themable, but Streamlit's own
  widget chrome comes from `.streamlit/config.toml`, which is static per process. A runtime
  switch would leave sliders and selectboxes in the old theme. Shipped one calibrated light
  theme instead; a dark theme needs the config changed and a second contrast pass.
- **Card-per-metric tiles.** Rejected because five bordered cards for five symmetric
  channels imply five separate objects; a table states the same thing in one comparison.
- **Gradient bars and multi-hue charts.** Removed: in this console colour marks state and
  the selected class, and bar length already encodes the measurement.
- **Keeping emoji as icons.** Rejected for rendering consistency across operating systems
  and because a symbol set that includes `🖕` cannot sit in an academic submission.

## Verification performed

- `python -m py_compile` on the dashboard and the predictor.
- `pytest tests/` for the shared backend modules.
- Contrast pairs computed with the ui-ux-design skill's `contrast.py`.
- App started with Streamlit and loaded in a browser; all sections rendered, the browser
  console was empty, and the server log carried no tracebacks after the final edit.
- Sidebar placement and widget behaviour checked in the browser: source radio, routine
  selectbox, gate and window sliders, and the live-refresh switch all sit in the sidebar.
- Empty state checked with a fresh session: the log starts empty (no invented tokens), the
  translation line explains how to add a word, and *Clear session* is disabled until there
  is something to clear.
- Server log is free of `use_container_width` deprecation output after switching to the
  `width="stretch"` API; `requirements.txt` records the floor that API needs.
- Backend test suite: `34 passed`.

Not verified: real ESP32 serial input, screen-reader traversal, and any participant testing
of the new layout. Colour choices assume an sRGB desktop display.
