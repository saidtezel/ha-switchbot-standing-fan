# Standing Fan Oscillation Angle Selects — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the SwitchBot Standing Fan's horizontal and vertical oscillation angle (30° / 60° / 90°) as two Home Assistant `select` entities, driven by pySwitchbot's native angle methods.

**Architecture:** Replace the dead `_send_combined_angles` workaround in `select.py` with two clean `SelectEntity` classes that call `set_horizontal_oscillation_angle()` / `set_vertical_oscillation_angle()` using the library's angle enums. `current_option` reads the pySwitchbot getter with a raw-byte→option map, falling back to the last set value. Register both in `async_setup_entry`; fix the stale wiring comment; update the README.

**Tech Stack:** Home Assistant custom integration (Python 3), pySwitchbot (`switchbot`), HACS packaging. No test harness in this repo — static checks (`python -m py_compile`) plus a deferred on-device verification checklist.

---

## Testing note

This repo is a HACS shadow of `home-assistant/core`'s `switchbot` integration and carries **no test suite** (no `tests/` dir, `ruff` not installed locally). Full import-time validation needs HA + `switchbot` installed, which is not available in the dev environment. Each code task therefore verifies with `python3 -m py_compile` (catches syntax/indentation errors) and defers behavioral verification to the on-device checklist in Task 6. This is a deliberate, spec-sanctioned deviation from the usual pytest TDD loop.

## File structure

- **Modify** `custom_components/switchbot/select.py` — swap dead angle code for two clean select classes; register them; add `HorizontalOscillationAngle` import.
- **Modify** `custom_components/switchbot/__init__.py:95-100` — fix the stale `STANDING_FAN` platform comment.
- **Verify (no change expected)** `custom_components/switchbot/strings.json`, `custom_components/switchbot/translations/en.json` — angle translation keys already present.
- **Modify** `README.md` — remove the angle known-limitation bullet; add the two entities to the entity table.
- **Modify** `custom_components/switchbot/__init__.py` comment only (no logic).

---

### Task 1: Replace dead angle code in `select.py`

Removes the misdiagnosis (`_ensure_angle_cache`, `_send_combined_angles`, `_V_OPTION_TO_BYTE`, and the two old class bodies) and the now-unused constants, and adds the `HorizontalOscillationAngle` import. This task leaves `select.py` temporarily without the angle classes; Task 2 adds the clean replacements. (Split this way so each diff is small and compiles.)

**Files:**
- Modify: `custom_components/switchbot/select.py`

- [ ] **Step 1: Add `HorizontalOscillationAngle` to the switchbot import**

Replace the import block (currently lines 7-11):

```python
from switchbot import (
    NightLightState,
    SwitchbotOperationError,
    VerticalOscillationAngle,
)
```

with:

```python
from switchbot import (
    HorizontalOscillationAngle,
    NightLightState,
    SwitchbotOperationError,
    VerticalOscillationAngle,
)
```

- [ ] **Step 2: Delete the dead angle helpers and old class bodies**

Delete this entire block (currently lines 83-174 — from `HORIZONTAL_ANGLE_OPTIONS = ...` through the end of `class SwitchBotStandingFanVerticalAngleSelect`, i.e. everything between the `SwitchBotStandingFanNightLightSelect` class and the `class SwitchBotMeterProCO2TimeFormatSelect` class):

```python
HORIZONTAL_ANGLE_OPTIONS = ["30", "60", "90"]
VERTICAL_ANGLE_OPTIONS = ["30", "60", "90"]


_V_OPTION_TO_BYTE = {
    "30": VerticalOscillationAngle.ANGLE_30.value,
    "60": VerticalOscillationAngle.ANGLE_60.value,
    "90": VerticalOscillationAngle.ANGLE_90.value,  # 0x5F (95), not 90
}


def _ensure_angle_cache(coordinator: SwitchbotDataUpdateCoordinator) -> None:
    ...
```

through the end of `class SwitchBotStandingFanVerticalAngleSelect` (the `async_select_option` that ends with `self.async_write_ha_state()` just before `class SwitchBotMeterProCO2TimeFormatSelect`). Task 2 re-adds clean versions in that same location.

- [ ] **Step 3: Verify the file still compiles**

Run: `python3 -m py_compile custom_components/switchbot/select.py`
Expected: no output, exit code 0. (`VerticalOscillationAngle` is now imported but unused — acceptable transient state; Task 2 uses it.)

- [ ] **Step 4: Commit**

```bash
git add custom_components/switchbot/select.py
git commit -m "refactor: remove dead combined-command angle workaround

BLE captures confirm the Standing Fan uses pySwitchbot's native per-axis
angle format byte-for-byte; the _send_combined_angles workaround solved a
non-problem. Removing it before wiring the native-method selects."
```

---

### Task 2: Add clean angle select classes

**Files:**
- Modify: `custom_components/switchbot/select.py`

- [ ] **Step 1: Insert the two select classes**

In the location vacated by Task 1 (between `SwitchBotStandingFanNightLightSelect` and `SwitchBotMeterProCO2TimeFormatSelect`), add:

```python
HORIZONTAL_ANGLE_OPTIONS = ["30", "60", "90"]
VERTICAL_ANGLE_OPTIONS = ["30", "60", "90"]

# Option string -> pySwitchbot angle enum. Passing the enum lets the library
# emit the correct byte (horizontal 90 -> 0x5A, vertical 90 -> 0x5F/95).
_H_OPTION_TO_ENUM = {
    "30": HorizontalOscillationAngle.ANGLE_30,
    "60": HorizontalOscillationAngle.ANGLE_60,
    "90": HorizontalOscillationAngle.ANGLE_90,
}
_V_OPTION_TO_ENUM = {
    "30": VerticalOscillationAngle.ANGLE_30,
    "60": VerticalOscillationAngle.ANGLE_60,
    "90": VerticalOscillationAngle.ANGLE_90,  # enum value 95 -> byte 0x5F
}
# Raw device byte -> option string. Vertical 90° reads back as 95.
_H_BYTE_TO_OPTION = {30: "30", 60: "60", 90: "90"}
_V_BYTE_TO_OPTION = {30: "30", 60: "60", 95: "90"}


class SwitchBotStandingFanHorizontalAngleSelect(SwitchbotEntity, SelectEntity):
    """Horizontal oscillation angle for SwitchBot Standing Fan."""

    _device: switchbot.SwitchbotStandingFan
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "horizontal_oscillation_angle"
    _attr_options = HORIZONTAL_ANGLE_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_h_angle"
        self._last_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current horizontal angle (device truth, then last-set)."""
        byte = self._device.get_horizontal_oscillation_angle()
        if byte is None:
            return self._last_option
        return _H_BYTE_TO_OPTION.get(byte, self._last_option)

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set the horizontal oscillation angle."""
        await self._device.set_horizontal_oscillation_angle(_H_OPTION_TO_ENUM[option])
        self._last_option = option
        self.async_write_ha_state()


class SwitchBotStandingFanVerticalAngleSelect(SwitchbotEntity, SelectEntity):
    """Vertical oscillation angle for SwitchBot Standing Fan.

    90° maps to device byte 95 (0x5F); the VerticalOscillationAngle enum
    encodes this, and the getter reports 95 for 90°.
    """

    _device: switchbot.SwitchbotStandingFan
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "vertical_oscillation_angle"
    _attr_options = VERTICAL_ANGLE_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_v_angle"
        self._last_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current vertical angle (device truth, then last-set)."""
        byte = self._device.get_vertical_oscillation_angle()
        if byte is None:
            return self._last_option
        return _V_BYTE_TO_OPTION.get(byte, self._last_option)

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set the vertical oscillation angle."""
        await self._device.set_vertical_oscillation_angle(_V_OPTION_TO_ENUM[option])
        self._last_option = option
        self.async_write_ha_state()
```

- [ ] **Step 2: Verify the file compiles**

Run: `python3 -m py_compile custom_components/switchbot/select.py`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add custom_components/switchbot/select.py
git commit -m "feat: add Standing Fan oscillation angle selects (native API)"
```

---

### Task 3: Register the angle selects

**Files:**
- Modify: `custom_components/switchbot/select.py` (`async_setup_entry`, currently lines 40-41)

- [ ] **Step 1: Add both selects to the Standing Fan branch**

Replace:

```python
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities([SwitchBotStandingFanNightLightSelect(coordinator)])
```

with:

```python
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities(
            [
                SwitchBotStandingFanNightLightSelect(coordinator),
                SwitchBotStandingFanHorizontalAngleSelect(coordinator),
                SwitchBotStandingFanVerticalAngleSelect(coordinator),
            ]
        )
```

- [ ] **Step 2: Verify the file compiles**

Run: `python3 -m py_compile custom_components/switchbot/select.py`
Expected: no output, exit code 0.

- [ ] **Step 3: Verify no stale references remain**

Run: `grep -nE "_send_combined_angles|_ensure_angle_cache|_V_OPTION_TO_BYTE|_sf_h_option|_sf_v_option" custom_components/switchbot/`
Expected: no matches (empty output).

- [ ] **Step 4: Commit**

```bash
git add custom_components/switchbot/select.py
git commit -m "feat: register Standing Fan horizontal/vertical angle selects"
```

---

### Task 4: Fix the stale platform comment in `__init__.py`

**Files:**
- Modify: `custom_components/switchbot/__init__.py:95-100`

- [ ] **Step 1: Update the comment**

Replace:

```python
    SupportedModels.STANDING_FAN.value: [
        Platform.FAN,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],  # SELECT = night-light only (angles removed — firmware ignores commands)
```

with:

```python
    SupportedModels.STANDING_FAN.value: [
        Platform.FAN,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],  # SELECT = night-light + horizontal/vertical oscillation angle
```

- [ ] **Step 2: Verify the file compiles**

Run: `python3 -m py_compile custom_components/switchbot/__init__.py`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add custom_components/switchbot/__init__.py
git commit -m "docs: correct STANDING_FAN select platform comment"
```

---

### Task 5: Verify translations and update README

Translation keys `horizontal_oscillation_angle` / `vertical_oscillation_angle` already exist in both `strings.json` and `translations/en.json` (leftover from the earlier attempt) — this task confirms that and does the README edits.

**Files:**
- Verify: `custom_components/switchbot/strings.json`, `custom_components/switchbot/translations/en.json`
- Modify: `README.md`

- [ ] **Step 1: Confirm translation keys are present and JSON is valid**

Run:
```bash
python3 -c "import json; [json.load(open(f))['entity']['select']['horizontal_oscillation_angle'] and json.load(open(f))['entity']['select']['vertical_oscillation_angle'] for f in ('custom_components/switchbot/strings.json','custom_components/switchbot/translations/en.json')]; print('ok')"
```
Expected: prints `ok` (no `KeyError`, valid JSON). If it raises, add the keys mirroring the `night_light` block with `name` "Horizontal angle" / "Vertical angle" and states `30`/`60`/`90` → `30°`/`60°`/`90°`.

- [ ] **Step 2: Add the two entities to the README entity table**

In `README.md`, in the "What it adds" table, after the `select.<name>_night_light` row add:

```markdown
| `select.<name>_horizontal_oscillation_angle` | Horizontal sweep width (30° / 60° / 90°) |
| `select.<name>_vertical_oscillation_angle` | Vertical sweep width (30° / 60° / 90°) |
```

- [ ] **Step 3: Remove the angle known-limitation bullet**

In `README.md`, under "Known limitations", delete the bullet that begins:

```markdown
- **Oscillation angle setters (30° / 60° / 90°)** are **not exposed**. PySwitchbot's per-axis angle commands don't appear to land on this firmware variant — the device ignores them. Removed from the entity list to avoid confusing UX. Open to PRs that find a reliable command format.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document Standing Fan angle select entities"
```

---

### Task 6: On-device verification (maintainer, deferred)

No live fan in the dev environment; the maintainer runs this after deploying the build to Home Assistant. This is the iteration checkpoint — if any step fails, capture the behavior and open a v2 iteration on the `select.py` `async_select_option` command path (the single swap-point).

**Files:** none (manual verification)

- [ ] **Step 1: Deploy and restart**

Copy `custom_components/switchbot/` to the HA instance (or pull via HACS) and restart Home Assistant. Confirm the Standing Fan device now shows two new config entities: **Horizontal angle** and **Vertical angle**.

- [ ] **Step 2: Horizontal angle**

Set Horizontal angle to `30`, `60`, `90` in turn. Expected: the head's horizontal sweep width visibly narrows/widens on each change; no error toast; the select shows the chosen value.

- [ ] **Step 3: Vertical angle (incl. the 90°/0x5F case)**

Set Vertical angle to `30`, `60`, `90` in turn. Expected: vertical sweep width changes each time. Confirm `90°` **sweeps** rather than halting the axis (this is the byte `0x5F` case the old code worried about).

- [ ] **Step 4: State reflection**

After setting each axis, confirm `current_option` reflects the chosen value. Note whether it survives a HA restart / external change from the SwitchBot app (this exercises the getter vs. the last-set fallback). Record the result — if the getter never populates, that informs whether a v2 needs a different state strategy.

- [ ] **Step 5: No regressions**

Confirm power, speed, preset mode, night-light, and both oscillation on/off switches still work on the fan, and that other SwitchBot devices in the instance are unaffected.

---

## Self-review

- **Spec coverage:** Entities (Task 2/3) ✓; native-enum command path (Task 2) ✓; state reflection with fallback (Task 2) ✓; delete workaround + monkey-patch (Task 1, grep-checked in Task 3) ✓; `__init__.py` comment (Task 4) ✓; translations (Task 5, already present) ✓; README (Task 5) ✓; on-device verification (Task 6) ✓; known-risk getter behavior surfaced in Task 6 Step 4 ✓.
- **Placeholder scan:** none — all code shown in full, all commands concrete.
- **Type consistency:** `_H_OPTION_TO_ENUM`/`_V_OPTION_TO_ENUM`/`_H_BYTE_TO_OPTION`/`_V_BYTE_TO_OPTION`, `_last_option`, class names `SwitchBotStandingFanHorizontalAngleSelect`/`SwitchBotStandingFanVerticalAngleSelect`, unique-id suffixes `_h_angle`/`_v_angle`, and method names match across Tasks 1–3 and the registration in Task 3.
