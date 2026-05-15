# Backups, Cloud Sync, and Recovery

LoreForge Lite is local-first. Your working files, registry database, sidecars, backups, and settings live on your machine unless you configure cloud backup.

The safety model is simple:

**Back up first, write carefully, keep metadata nearby, and make recovery understandable.**

## Local Backups

LoreForge creates local backups before protected dataset mutations.

Protected operations include workflows such as:

- edits
- deletes
- validation repairs
- split and join
- merge-related saves
- tag lifecycle changes
- registry-sensitive updates

Backups give you a recovery point if you need to roll back.

## Dataset Backups

Dataset backups protect JSONL files.

They are useful when:

- an edit was wrong
- a repair changed more than expected
- a split or join needs to be reversed
- a dataset save was interrupted

Dataset backups preserve the training entries themselves.

## DB Backups

DB backups protect LoreForge app metadata.

This can include:

- tag registry data
- tag lifecycle and aliases
- character registry
- character mappings
- system prompt templates
- settings
- other local registry metadata

The database is where much of LoreForge's organizational context lives.

## Sidecar Safety

Sidecars are refreshed near dataset saves so portable metadata stays close to the JSONL file.

If a sidecar looks mismatched or unsafe during load, LoreForge can skip that sidecar metadata rather than trusting it blindly.

Keep sidecars with their matching datasets when moving or archiving work.

## Working Copy Safety

Working copies protect original untrusted files.

If LoreForge loads a dataset that did not clearly come from the current LoreForge identity model, it may copy the file into the managed dataset area and work on that copy.

That protects the original source from accidental edits.

## Cloud Sync

Cloud sync is optional.

It mirrors the latest backup material to a configured cloud sync folder, such as a OneDrive, Google Drive, Dropbox, iCloud Drive, Box, or custom folder location.

Cloud sync is not live collaboration.

It is a batch safety copy that can run:

- manually from Settings
- when the app closes, if configured

LoreForge stages cloud sync output before publishing it so a failed sync should not replace the last known good cloud backup.

## Local Backup Folder vs Cloud Backup

Keep your local backup folder local.

Do not use a cloud-synced folder as the main local backup folder. Use the Cloud Backup section for cloud destinations instead.

This reduces the chance of sync tools touching files while LoreForge is still writing locally.

## What to Back Up Together

For the best recovery picture, keep these together:

- dataset JSONL files
- matching `.registry.json` sidecars
- dataset backups
- DB backups
- settings export if you are moving machines

The JSONL contains entries. The sidecar and database preserve organization and project context.

## Partial-Failure Window

LoreForge writes across several systems:

- JSONL files
- sidecars
- SQLite database
- local backups
- optional cloud sync folders

Those systems cannot be made into one perfect global transaction in every case.

There is a known partial-failure window in some durable operations: a JSONL dataset save may succeed before a later database commit fails. For example, a tag lifecycle operation could update the dataset file and then fail while committing registry metadata.

This is rare in normal local use, and LoreForge creates recovery material before protected operations.

## Recovery Workflow

If something goes wrong:

1. Stop making further edits.
2. Close LoreForge Lite.
3. Find the most recent dataset backup for the affected dataset.
4. Find the matching recent DB backup if registry metadata also changed.
5. Restore the most consistent pair.
6. Reopen LoreForge and run Validation.

If the issue only affected the JSONL file, a dataset backup may be enough.

If the issue involved tags, characters, mappings, settings, or prompt templates, restore the database backup that matches the dataset state.

## Cloud Restore Expectations

Cloud backup can help if the local machine loses data or you move to a new machine.

It is still a copy of local backup material, not a real-time multi-user sync system.

If cloud backup finds usable material during startup, LoreForge may offer restore options. Review the path and choose deliberately.

## Common Mistake

**Mistake:** Treating cloud sync like a live shared workspace.

**Better mental model:** LoreForge is local-first. Cloud sync is a backup mirror, not collaborative editing.

## Practical Tips

- Let LoreForge create backups before protected operations.
- Keep local backups out of cloud-synced folders.
- Use Cloud Backup for cloud destinations.
- Keep JSONL and sidecar files together.
- Export settings when moving machines.
- Run Validation after restoring from backup.

