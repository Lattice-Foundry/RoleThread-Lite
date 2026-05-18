# Creating a New Dataset

Creating a new dataset gives you a clean local workspace for entries, tags, sidecar metadata, backups, and exports.

Start from **Manage Dataset**.

## Basic Workflow

1. Open **Manage Dataset**.
2. Choose or confirm the dataset folder/path.
3. Click **New Dataset**.
4. Give the dataset a clear name.
5. Start adding entries in **Create Entry**.
6. Run **Validation** once you have entries.
7. Export when ready.

## Naming a Dataset

Use names that describe the dataset clearly:

- `group_chat_examples`
- `fantasy_tavern_dialogue`
- `support_conversations_v1`
- `character_training_short_responses`

Avoid names that are too generic, such as:

- `dataset`
- `test`
- `new`
- `final_final`

Clear names make backups, sidecars, exports, and future merges much easier to understand.

## Dataset Folders

RoleThread Lite uses a folder-per-dataset layout.

For a dataset named `tavern_scenes`, the local folder may look like:

```text
training_data/
  tavern_scenes/
    tavern_scenes.jsonl
    tavern_scenes.registry.json
```

The `.jsonl` file stores the training entries.

The `.registry.json` sidecar stores portable metadata such as tags, categories, characters, mappings, prompt templates, and dataset identity.

## Empty Dataset Behavior

A new dataset may begin as an empty JSONL file. That is normal.

Once you save entries, RoleThread writes them as JSONL records and stamps them with stable identity metadata. The sidecar is refreshed as metadata becomes available.

An empty dataset is still a valid starting point.

## What Happens After First Save

After the first entry is saved, RoleThread can track:

- entry UUIDs for stable entry identity
- a dataset UUID for the saved dataset identity
- tags assigned to entries
- character mappings if Group Chat mode is used
- prompt templates and registry metadata through the sidecar

You do not need to edit this metadata manually.

## Backups

Protected operations create backups before writing changes. For a new dataset, backups become more useful once the dataset has content.

Backups are part of the normal safety model. They are there so edits, repairs, deletes, splits, joins, and tag lifecycle changes have recovery points.

## Sidecar Creation

RoleThread refreshes the sidecar beside the dataset when it saves registry-aware changes.

Keep the sidecar with the dataset if you move or archive the dataset. Without the sidecar, the JSONL entries may still load, but some portable metadata may not travel with them.

## Recommendations

- Create one dataset per clear training goal.
- Use descriptive names from the beginning.
- Add tags early, even if the tag system starts simple.
- Run Validation before large edit sessions.
- Use Export for final training files rather than manually copying working files.
- Keep dataset files and sidecars together.

## When To Create A New Dataset

Create a new dataset when:

- you are starting a new training theme
- you want a clean separation between projects
- you are experimenting with a new style or character set
- you want to merge selected material later instead of mixing everything now

If you already have useful source data, load it instead. RoleThread can create a working copy and convert supported formats safely.
