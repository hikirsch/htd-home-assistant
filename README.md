# Home Theater Direct Integration for Home Assistant

![HTD](logo-htd.png)

This integration adds support for the Home Theater Direct line of Whole House Audio to Home Assistant.

## Supported Models

| Model | Zones | Sources | Kind |
|---|---|---|---|
| MC/MCA-66 | 6 | 6 | MCA |
| Lync 6 | 6 | 12 | Lync |
| Lync 12 | 12 | 19 | Lync |

Model is auto-detected at connection time. No manual configuration of device type is required.

## Features

- Auto-discovery via DHCP (MAC prefix `A44F29*` / `A64F29*`)
- Per-zone power, volume, mute, and source selection
- Zone and source names read automatically from the controller on connect
- Customize zone and source names during setup or at any time via the integration's settings
- Hide unused zones so only the zones you care about appear in Home Assistant
- Per-zone source filtering — restrict which sources are selectable per zone
- Per-zone **Bass** and **Treble** sliders (enabled by default) and a **Balance** slider (hidden by default)
- Per-zone **DND (Do Not Disturb)** switch — controls party mode / all-zones-on exclusion (Lync only)
- Device rename via the integration's settings — no need to delete and re-add
- Serial (USB) or network connection

## Customizing Zone and Source Names

Zone and source names can be customized during initial setup or at any time via the integration's settings (reconfigure).

- **Zone names** default to the names stored on your HTD controller. You can override them per-zone in the integration UI.
- **Source names** default to the names stored on your HTD controller (Lync) or generic labels (MCA). You can override them per-source in the integration UI.

Both are optional — leave fields blank to keep the controller's names.

### Referencing sources in automations

The `source` attribute always shows a source's **current display name**, so renaming a source changes it — and any automation, script, or dashboard template comparing it to a literal name silently stops matching.

Every zone's `media_player` entity also exposes a `source_id` attribute that does **not** change when you rename a source. It holds the source's fixed position on the controller, as `"Source N"`:

```yaml
- condition: template
  value_template: "{{ state_attr('media_player.kitchen', 'source_id') == 'Source 3' }}"
```

Because `media_player.select_source` also accepts `"Source N"`, you can read it from one zone and act on it directly in another, with no lookup in between:

```yaml
- service: media_player.select_source
  target:
    entity_id: media_player.den
  data:
    source: "{{ state_attr('media_player.kitchen', 'source_id') }}"
```

> **Zones that are off:** unlike `source`, `source_id` stays present when a zone is powered off, reporting the last source it was on. If your automation should only match while the zone is playing, pair it with a state check: `is_state('media_player.kitchen', 'on') and state_attr('media_player.kitchen', 'source_id') == 'Source 3'`.

**Already have automations matching on `source`?** Replace `state_attr(entity, 'source') == 'sonos'` with `state_attr(entity, 'source_id') == 'Source 14'`, using the source's number as shown in the integration's settings. Nothing breaks if you don't — `source` behaves exactly as it always has — but those automations stay vulnerable to the next rename.

> **Avoid naming a source after another source's generic label** (giving source 5 the display name `"Source 3"`, for example). `"Source N"` always refers to source N, so a source named this way cannot be selected by that name.

### Home Assistant entity name overrides

If you have manually renamed an entity directly in Home Assistant (via **Settings → Devices & Services → Entities**), that name takes precedence over whatever the integration provides. The integration cannot override a name you have set manually.

To let the integration's name take effect, clear the manual override:

1. Go to **Settings → Devices & Services → Entities**
2. Find the entity and open it
3. Click the name field and delete the custom value (leave it blank / reset to default)
4. Save — the entity will now use the name from the integration

## Zone Filtering (Hide Unused Zones)

During initial setup or reconfigure, you can choose to filter zones so that only the zones you actually use appear in Home Assistant.

- Enable zone filtering with the checkbox, then select which zones are active.
- Entities for deselected zones are **disabled by the integration** — they remain in the registry and can be manually re-enabled per-entity in **Settings → Devices & Services → Entities** if needed.
- Disable zone filtering at any time via reconfigure to restore all zones.

## Source Filtering (Per-Zone Source List)

You can restrict which sources appear in the source selection dropdown for each zone.

- During setup or reconfigure, enable source filtering.
- For each zone, choose which sources should be available.
- Sources not selected are removed from that zone's source list in Home Assistant.
- Useful when only a subset of sources are wired to certain zones.

## EQ Controls (Bass, Treble, Balance)

Each zone exposes three `number` entities for equalizer adjustments:

| Entity | Default | Range (Lync) | Range (MCA) |
|--------|---------|-------------|-------------|
| Bass   | Enabled | -10 to +10, step 1 | -12 to +12, step 4 |
| Treble | Enabled | -10 to +10, step 1 | -12 to +12, step 4 |
| Balance | **Hidden** | -18 to +18, step 1 | -12 to +12, step 6 |

Bass and Treble appear automatically on the device page. Balance is created but hidden by default because most fixed-speaker whole-home audio setups never need it.

**To enable Balance:** Go to **Settings → Devices & Services → your HTD device** → find the Balance entity for the zone you want → click the toggle to enable it.

## DND (Do Not Disturb)

*Lync systems only.*

Each Lync zone has a **DND switch** entity. When DND is on for a zone:

- The zone is excluded from party mode and all-zones-on commands.
- Individual control of the zone is unaffected — you can still power it on/off and adjust volume independently.

DND state is read from and written to the controller. Toggling the switch in Home Assistant sends the command immediately.

## Offline Behavior

If your amplifier is powered off when Home Assistant restarts, HTD entities are created
anyway, using the model detected the last time the two were able to talk. Previously
the integration re-asked the amplifier what it was on every startup, so with the amplifier
off it could not tell how many zones or sources existed and created no entities at all —
every HTD card showed `Unavailable`, sometimes for days.

**Upgrading? This will appear to do nothing at first.** The fix relies on the amplifier's
model having been recorded, and existing config entries do not have it yet. The first time
Home Assistant successfully connects after upgrading, the model is written to the config
entry, and every restart from then on works with the amplifier off. Until that one
successful connection, behavior is exactly what it was before.

**First-time setup still requires a powered-on device.** Adding the integration probes the
amplifier to identify it; there is no way around that on a new install.

### Restoring last known state

By default, entities that have no live data report `Unavailable` — the same as before, just
with the entities now present rather than missing. To have them show what the zone was doing
the last time Home Assistant could see it, enable **Restore last known state when the device
is offline** in the integration's options (Settings → Devices & Services → Home Theater
Direct → Configure).

With it on, a zone that was off reads `off` instead of `Unavailable`, its volume, mute state
and source come back, and the same applies to the EQ sliders and the DND switches. Home
Assistant marks these entities as *assumed state*, which is why the card shows explicit
on/off buttons instead of a single toggle — it is telling you the value may be stale.

**A restored value can be wrong.** If someone turns a zone on at the keypad while Home
Assistant is down, Home Assistant will keep reading `off` until the amplifier reconnects.
That is inherent to showing a remembered value, which is why the option is off by default.

### Controls while offline

Turning a zone on, changing volume, selecting a source, moving an EQ slider or toggling DND
while the amplifier is unreachable fails with a visible error, and the failure appears in
automation traces. Commands are deliberately **not** queued for later — a "turn on the
kitchen" firing hours later when the amplifier happens to be powered for something else is a
worse outcome than an error you can see.

When the amplifier comes back, the integration reconnects on its own (retrying every second
at first, backing off to once a minute) and entities switch from restored to live values
without a restart.

## Installation

### Via HACS (Home Assistant Community Store)

Easiest installation is via [HACS](https://hacs.xyz/):

Please click this button below to install the integration:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hikirsch&repository=htd-home-assistant&category=integration)

After you add the repository for the integration, you will then be able to install it into Home Assistant.

### Manually

Download all the files from this repo and place them in your `config/custom_components/htd/` directory.

### Configuration

Go to **Settings → Devices & Services → Add Integration → Home Theater Direct**, then choose how your gateway is connected: **Network** or **Serial**.

#### Network connection

The integration will attempt to auto-discover your device via DHCP. If it is not found automatically, enter the IP address and port (default: `10006`) manually.

#### Serial (USB) connection

Enter the serial device path for your HTD gateway. Prefer a stable path under `/dev/serial/by-id/` (run `ls /dev/serial/by-id/` on the machine running Home Assistant) over a path like `/dev/ttyUSB0`, whose number can shift if the adapter is unplugged/replugged or the system reboots.

Serial devices get the same setup experience as network devices — device registry entry, options flow, zone/source naming, and zone/source filtering.

## Code Credits
- https://github.com/dustinmcintire/htd-lync
- https://github.com/whitingj/mca66
- https://github.com/qguernsey/Lync12
- https://github.com/steve28/mca66
- http://www.brandonclaps.com/?p=173
- https://github.com/lounsbrough/htd-mca-66-api
- **Thank you to [steve28](https://github.com/steve28)** — for extensive and patient testing of serial control on the MCA-66 system.
- **Special thanks to [kingfetty](https://github.com/kingfetty/python-htd)** — whose foundational work on full Lync support (zone/source naming, DND, device discovery, and all-zone queries) made this integration significantly more capable.
