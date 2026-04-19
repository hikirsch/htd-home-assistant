# HTD Home Assistant Integration (naming-ux fork)

This is a fork of [hikirsch/htd-home-assistant](https://github.com/hikirsch/htd-home-assistant)
with added UI for zone naming and per-zone source filtering.

**All protocol, transport, power, volume, and source-selection logic is unchanged**
from upstream — those were working great and we didn't touch them. The
audio control still flows through the upstream `htd_client` PyPI package.

## What's different from upstream

* **Per-zone friendly names** — replace the default `Zone N (device)` label
  with whatever you want (e.g. `Kitchen`, `Primary Bath`, `Deck`).
* **Per-zone source filtering** — each zone's source dropdown shows only
  the sources you've marked as allowed for it. Your garage doesn't need
  to see `Turntable` in its source list, and your kitchen doesn't need
  to see `Theater Room`.
* **Global source labels** — rename `Source 3` to `Sonos Port` and every
  zone that can use it shows `Sonos Port`.
* **Enable/disable toggle per zone** — suppress unused zones entirely.

All of these are **UI-only** — the HTD controller's own stored names are
left alone. Physical keypads continue to show whatever they were showing.

## Installation (HACS)

1. In HACS, add this repo as a custom Integration repository:
   `https://github.com/YOUR_USERNAME/htd-home-assistant`
2. Install **Home Theater Direct** from HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration → Home Theater Direct**.
5. Enter your gateway host/port as you would with the upstream integration.
6. Once added, click **Configure** on the integration tile to walk through
   the naming wizard.

## Configuration wizard

From the integration's **Configure** button, you get a menu with:

- **Configure Zones** — walk through each zone, setting a friendly name,
  enable/disable toggle, and check off which sources should appear in
  its dropdown.
- **Rename Sources** — one field per physical source to set its global
  label (e.g. Source 7 → "Apple TV").
- **Connection Settings** — original host/port editor from upstream.
- **Save & Exit**

## Keeping in sync with upstream

```bash
# One-time setup to track upstream:
git remote add upstream https://github.com/hikirsch/htd-home-assistant.git

# Whenever you want the latest:
git fetch upstream
git checkout main
git merge upstream/main

# If you're on a branch (e.g. naming-ux):
git checkout naming-ux
git rebase main
```

## Credits

All of the hard protocol work, volume stepping, connection handling, and
the upstream [htd_client](https://pypi.org/project/htd_client/) Python
package are by [@hikirsch](https://github.com/hikirsch). This fork just
adds a config-UX layer on top.
