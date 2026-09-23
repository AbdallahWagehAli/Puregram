# Patches against submodules

The desktop client pulls some of its code from git submodules that belong to
upstream projects. We cannot commit into those repositories, and a gitlink
pointing at a commit only this machine has would be worse than useless to
anyone cloning — it would simply fail to fetch.

So changes we make inside a submodule live here as patches. They are part of
the corresponding source for the binaries published at puregram.app: apply them
after `git submodule update --init --recursive` and the build reproduces what
we ship.

| Patch | Applies to | What it changes |
|-------|-----------|-----------------|
| `lib_ui-puregram-green.patch` | `telegram/tdesktop/Telegram/lib_ui` | Brand accent: Telegram blue → Puregram green (`#2E9E4F`) in the day palette |

To apply:

```sh
cd telegram/tdesktop/Telegram/lib_ui
git apply ../../../../patches/lib_ui-puregram-green.patch
```

Note that the day palette is only half of the theming: dark mode reads
`telegram/tdesktop/Telegram/Resources/night.tdesktop-theme`, which is a ZIP and
is committed normally in this repository.
