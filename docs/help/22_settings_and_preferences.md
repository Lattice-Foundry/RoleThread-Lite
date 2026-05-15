# Settings and Preferences

Settings lets you adjust the parts of LoreForge Lite that should match your local workflow.

The defaults are intentionally conservative. LoreForge tries to expose useful control without making you configure everything before you can work.

## Configuration Philosophy

LoreForge Lite is local-first.

Settings are about:

- where local files live
- how backups behave
- whether cloud backup is configured
- how previews display names
- how settings can be exported or imported
- how much automatic cleanup should happen during load

Most users can keep the defaults until they have a reason to change them.

## Default Dataset Folder

The default dataset folder is where LoreForge creates and manages local dataset folders by default.

Use this setting to choose the place where your normal working datasets should live.

A practical layout might look like:

```text
training_data/
  project_alpha/
    project_alpha.jsonl
    project_alpha.registry.json
  project_beta/
    project_beta.jsonl
    project_beta.registry.json
```

Changing the default folder affects future browsing, new dataset creation, and the default managed workspace. It does not automatically move existing datasets.

## Backup Settings

Backup settings control local backup behavior.

The main options are:

- whether automatic backups are enabled before protected operations
- where local backups are stored
- how many backups to keep per dataset

The safe default is to keep automatic backups enabled.

Local backups are meant to stay local. Do not use a cloud-synced folder as the local backup folder. Use Cloud Backup for cloud destinations instead.

## Cloud Backup Destination

Cloud Backup is optional.

When configured, LoreForge can mirror the latest backup material to a cloud sync folder. Supported provider choices include local-only mode, OneDrive on Windows, and common custom sync folders such as Google Drive, Dropbox, iCloud Drive, and Box.

Cloud sync is batch backup, not live collaboration.

It can run:

- manually from Settings
- when the app closes, if configured

For cloud providers, LoreForge stores backups under a LoreForge-specific subfolder so your sync folder stays organized.

## Data Normalization

The Data Normalization setting controls broader deterministic repair during load.

When enabled, LoreForge can apply safe validation-related cleanup for predictable issues during loading.

Baseline normalization still happens where needed for safe metadata, roles, and simple text cleanup. This setting is about broader automatic correction, not creative rewriting.

If you are importing messy external datasets, keeping this enabled is usually helpful.

## Editing Safety

Editing Safety includes confirmation behavior for destructive actions such as deleting entries.

The conservative default is to confirm before deletion.

This adds one extra click, but it protects against accidental bulk operations.

## Conversation Preview Names

Conversation preview names control how Default mode conversations are displayed in the app.

They are cosmetic only.

They do not change training roles, JSONL structure, or exported data.

In Group Chat mode, per-turn character assignments override these preview names.

Use preview names that make entries comfortable to read while you work.

## Settings Portability

Settings can be exported and imported.

This is useful when:

- moving to another machine
- preserving app configuration
- restoring after setup changes
- keeping a known-good preferences snapshot

Settings export is not the same as dataset export. It saves app preferences, not the dataset entries.

## What Changes Immediately

Some settings affect the current session right away, such as:

- preview display names
- delete confirmations
- backup count
- cloud backup destination

Other settings affect future actions, such as:

- default dataset folder for future browsing or dataset creation
- backup folder for future backup writes
- normalization behavior on future loads

If a change does not seem to affect something already loaded, it may apply the next time you load, save, or create a dataset.

## Practical Recommendations

- Keep automatic backups enabled.
- Keep local backups in a local folder.
- Use Cloud Backup only for cloud sync destinations.
- Export settings before moving machines.
- Keep preview names simple unless Group Chat mode needs specific characters.
- Change normalization settings only if you understand the import workflow you want.

## Common Mistake

**Mistake:** Pointing the local backup folder directly at a cloud-synced folder.

**Better mental model:** Local backup is the stable local recovery point. Cloud Backup mirrors backup material separately.

