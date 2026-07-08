# Standing Fan oscillation angle selects — design

**Date:** 2026-07-08
**Component:** `custom_components/switchbot/` (Standing Circulator Fan support)
**Goal:** Expose the Standing Fan's horizontal and vertical oscillation angle
settings (30° / 60° / 90°) — available in pySwitchbot — as Home Assistant
entities.

## Background

The Standing Fan firmware supports per-axis oscillation angle, proven by the
official SwitchBot iOS app. An earlier attempt in this repo wired up angle
selects but pulled them back, concluding "firmware ignores commands" and adding
a `_send_combined_angles` workaround (dead code in `select.py`). The README
lists angle setters as a known limitation.

BLE captures from the iOS app (PacketLogger, HCI trace) settle the question.
Header `570f410202` = set-oscillation-params; the four data bytes carry the
angle in the axis's slot and `0xFF` elsewhere:

| Axis | Wire bytes (after `570f410202`) | 30 | 60 | 90 |
|---|---|---|---|---|
| Horizontal | `[a] FF FF FF` | `1E` | `3C` | `5A` (90) |
| Vertical | `FF FF [a] FF` | `1E` | `3C` | `5F` (95) |

This is **byte-for-byte identical to pySwitchbot's native
`set_horizontal_oscillation_angle()` / `set_vertical_oscillation_angle()`**,
including the horizontal-90 = `0x5A` vs vertical-90 = `0x5F` asymmetry that the
library encodes via separate enums. Conclusions:

- The app pads the unchanged axis with `0xFF` and it works — the "firmware
  ignores `0xFF`-padded per-axis commands" theory is **wrong**.
- The `_send_combined_angles` workaround solved a non-problem and is removed.
- v1 calls the native library methods: cleanest *and* provably correct.

## pySwitchbot API (verified against source)

```python
async def set_horizontal_oscillation_angle(self, angle: HorizontalOscillationAngle | int) -> bool
async def set_vertical_oscillation_angle(self, angle: VerticalOscillationAngle | int) -> bool
def get_horizontal_oscillation_angle(self) -> int | None   # raw byte; 30/60/90
def get_vertical_oscillation_angle(self) -> int | None     # raw byte; 90° reads as 95

class HorizontalOscillationAngle(Enum): ANGLE_30 = 30; ANGLE_60 = 60; ANGLE_90 = 90
class VerticalOscillationAngle(Enum):   ANGLE_30 = 30; ANGLE_60 = 60; ANGLE_90 = 95
```

Passing the **enum** (not a raw int) makes the library emit the correct byte —
we never hand-roll hex. `VerticalOscillationAngle` is already imported in
`select.py`; `HorizontalOscillationAngle` will be added to the same import.

## Entities

Two `SelectEntity`s for the Standing Fan, mirroring the existing night-light
select:

| Entity | Options | Category |
|---|---|---|
| `select.<name>_horizontal_oscillation_angle` | `30` / `60` / `90` | CONFIG |
| `select.<name>_vertical_oscillation_angle` | `30` / `60` / `90` | CONFIG |

Registered in `select.py` `async_setup_entry` for the `SwitchbotStandingFan`
branch, alongside `SwitchBotStandingFanNightLightSelect`. The SELECT platform is
already wired for `STANDING_FAN` in `__init__.py`.

Unique IDs (unchanged from the existing dead classes): `{base}_h_angle`,
`{base}_v_angle`.

## Command path (the version swap-point)

`async_select_option(option)`:

1. Map the option string to the axis enum member:
   - Horizontal: `{"30": ANGLE_30, "60": ANGLE_60, "90": ANGLE_90}` (H enum)
   - Vertical: same keys → V enum members (V `ANGLE_90` has value 95)
2. `await self._device.set_horizontal_oscillation_angle(member)` (or vertical).
3. On success, remember the option as the optimistic fallback and
   `async_write_ha_state()`.

Wrapped in the existing `@exception_handler`. This method body is the **only**
place the wire behavior lives — a future version format change is a
one-function edit, entity structure untouched.

## State reflection (`current_option`)

Property, matching the night-light select's live-getter pattern:

- Read `get_horizontal_oscillation_angle()` / `get_vertical_oscillation_angle()`.
- Map the raw byte back to an option string. Vertical `95` → `"90"`; otherwise
  `str(byte)`.
- If the getter returns `None`, fall back to the last successfully-set option so
  the UI isn't stuck on "unknown."

## Cleanup

- Remove `_send_combined_angles`, `_ensure_angle_cache`, `_V_OPTION_TO_BYTE`,
  and all `coordinator._sf_*` monkey-patch state.
- Rewrite the two existing dead select classes clean per the above.
- Fix the stale `__init__.py` comment (`SELECT = night-light only (angles
  removed — firmware ignores commands)`) to reflect angle selects being present.

## Translations & docs

- Add translation keys `entity.select.horizontal_oscillation_angle.name` and
  `entity.select.vertical_oscillation_angle.name` to `strings.json` and
  `translations/en.json`.
- README: remove the "oscillation angle setters not exposed" known-limitation
  bullet; add the two entities to the entity table.

## Verification (deferred to hardware)

No live fan this session. v1 ships; the maintainer tests:

1. Set horizontal angle 30 / 60 / 90 — confirm the head's horizontal sweep width
   changes on each.
2. Set vertical angle 30 / 60 / 90 — confirm vertical sweep width changes; 90°
   in particular (byte `0x5F`) must sweep, not halt.
3. Confirm each select's `current_option` reflects the set value.

This is the checkpoint for a possible v2.

## Known risks

- **Getter population unverified.** Whether this fan advertises
  `oscillating_horizontal_angle` / `oscillating_vertical_angle` is unconfirmed.
  If they stay `None`, the selects rely on the optimistic fallback — still
  correct for HA-initiated changes, but won't reflect angle changes made from
  the SwitchBot app. Addressed in a later version only if it proves to matter.

## Out of scope

- 9-hour sleep timer (not in pySwitchbot).
- RGB night-light colour (not in pySwitchbot).
- Automated tests — this repo is a HACS shadow of core without core's test
  harness; verification is on-device.
