# Exporting Datasets

Export creates files you can use outside RoleThread Lite.

Use it when you are ready to send data to a training workflow, archive a cleaned dataset, or share a selected subset.

## What Export Does

Export writes entries from the currently loaded dataset to a chosen output file.

Depending on your choices, export can include:

- all entries
- selected entries
- filtered entries
- ChatML format
- ShareGPT format
- clean records without RoleThread metadata

RoleThread can also write sidecar metadata alongside the exported JSONL so project context can travel with it.

## Full Export

Full export writes the loaded dataset entries.

Use full export when:

- the whole dataset is ready
- you want an archive copy
- you want to move the dataset to another machine
- you are preserving project continuity with sidecar metadata

## Selected or Filtered Export

Selected or filtered export writes only a focused subset.

This is useful when:

- you filtered by tag
- you searched for a specific theme
- Insights or Validation focused a group of entries
- you selected entries manually in Manage Dataset
- you want to train or review one slice of a larger dataset

Before exporting a subset, check the active filters and selection state so you know what will be included.

## ChatML Export

ChatML export keeps entries in a message-based structure with roles such as:

- `system`
- `user`
- `assistant`

Use ChatML when your training workflow expects that format.

## ShareGPT Export

ShareGPT export converts entries into a ShareGPT-style conversation format.

Use it when your downstream tool expects ShareGPT-shaped data.

If your source dataset was ShareGPT and RoleThread converted it during load, export lets you choose the shape you need now.

## Clean Export

Clean export removes RoleThread metadata from the training records.

That includes project management fields such as:

- RoleThread identity metadata
- entry UUID metadata
- dataset UUID metadata
- tags
- other non-message top-level fields

Clean export is useful when another tool should see only the training conversation structure.

## Sidecars During Export

Normal export can write sidecar metadata beside the exported dataset.

The sidecar may preserve:

- tag registry context
- archived/imported tags
- character definitions
- character mappings
- system prompt templates
- dataset identity context

This is helpful for archive or project continuity.

If you only need plain training records, use clean export and give the training tool the JSONL file it expects.

## Export for Training

For training, you usually want:

1. Validation reviewed.
2. Insights checked for obvious weak spots.
3. Format chosen for the training tool.
4. Clean export if the tool should not receive RoleThread metadata.

## Export for Archive or Continued Work

For archive or continued RoleThread work, keep:

- the JSONL file
- the `.registry.json` sidecar
- relevant local backups
- database backup if you are preserving the whole app state

This keeps more context available if you reopen the dataset later.

## Common Mistake

**Mistake:** Using clean export and expecting tags or character mappings to appear in the output records.

**Better mental model:** Clean export is for training-file cleanliness. Portable metadata belongs in the sidecar.

## Practical Tip

If you are unsure, export a normal archive copy first, then create a clean export for training.

## Related Articles

- **Validation and Repair**
- **Sidecars and Portable Metadata**
- **Preparing Datasets for LoRA and Fine-Tuning**


