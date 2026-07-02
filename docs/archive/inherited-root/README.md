# Inherited Root Archive

This folder preserves root-level files from the inherited project while the repo is reorganized
around the `tail-chasing` package.

`config.legacy.json` is the old runtime config. It is archived because it is not used by the new
package scaffold and contains stale assumptions: a `/home/matt/...` Kismet log path, old ignore-list
filenames, and a fixed Arizona search bounding box.
