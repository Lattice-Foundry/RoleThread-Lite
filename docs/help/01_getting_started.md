# Getting Started

LoreForge Lite helps you build, inspect, repair, organize, and export local training datasets for narrative AI workflows. It is designed for creators who want direct control over their data: your JSONL files, registry database, backups, and metadata stay on your machine unless you choose to configure cloud backup.

This guide gives you the basic first-session path.

## The Short Version

Most sessions follow this rhythm:

1. Create or load a dataset in **Manage Dataset**.
2. Use **Manage Dataset** as the main operational workspace for browsing, filtering, tagging, searching, quick editing, duplication, joining, and export preparation.
3. Create entries or use Deep Edit for surgical work.
4. Use **Validation** for imported data, larger cleanup passes, and final review.
5. Use **Insights** to understand dataset shape and weak spots.
6. Export when the dataset is ready for training or sharing.

You do not need to understand every advanced system on day one. Start with loading or creating a dataset, then use Manage Dataset as your home base while the other pages support specific jobs.

## First Session Workflow

### 1. Open LoreForge Lite

When you open the app, start in **Manage Dataset**. This is not just a file browser. It is the main operational workspace for loading files, creating a new dataset, browsing entries, filtering, searching, tagging, quick editing, renaming, duplicating, joining, deleting, and preparing entries for export.

If no dataset is loaded, other pages will point you back to Manage Dataset.

LoreForge Lite ships with three curated example datasets so you can explore the app safely before working on your own material. One example dataset may load automatically on first launch. The examples are there for learning: inspect their tags, sidecars, prompts, character mappings, Validation results, and Insights behavior. You can edit, duplicate, validate, merge, or export them like normal datasets.

### 2. Create or Load a Dataset

You have two normal starting points:

- **New Dataset**: creates a fresh local dataset file you can begin filling.
- **Load**: opens an existing JSONL dataset.

If you load a file created outside LoreForge Lite, LoreForge may create a protected **working copy** before editing. That is intentional. It protects your original source file from accidental mutation.

### 3. Add Entries or Use Deep Edit

Use **Create Entry** for new training examples.

Use the entry actions in **Manage Dataset** for most day-to-day cleanup and review:

- **Quick Edit** for smaller message edits.
- **Duplicate** when you want to build a similar entry from an existing one.
- tag filters, search, selection, join, and bulk actions for operational cleanup.

Use **Deep Edit** when you need deeper work:

- **Full Edit** for system prompts, tags, multi-turn edits, Group Chat mode, and split tools.
- detailed character mapping review.
- careful multi-turn tuning.

Entries are still normal training records. Group Chat mode adds character display metadata, but exported training roles remain standard `system`, `user`, and `assistant` roles.

### 4. Validate and Repair

Go to **Validation** when you are reviewing imported data, doing a cleanup pass, checking a merge, or preparing for export.

Entries created through normal LoreForge forms are guarded against most structural problems before save. Validation is still valuable as an audit and cleanup tool, especially when data came from outside LoreForge or was changed in bulk.

Validation helps you find:

- missing or malformed message fields
- role issues
- empty or incomplete content
- duplicate system messages
- AI refusal or meta-language
- formatting leakage
- inactive character references
- entries that may benefit from splitting

Some issues can be repaired automatically. Others are shown for manual review. Validation is not a punishment system or an emergency loop for normal writing. It is there so problems are visible instead of silent.

### 5. Organize With Tags and Characters

Tags help you find, group, and export meaningful slices of a dataset. Characters help preserve who is speaking in creative workflows.

You can manage:

- tag categories
- custom tags
- archived/imported tags
- character definitions
- system prompt templates

You can learn these gradually. A small dataset can start with only a few tags.

### 6. Review Insights

The **Insights** page gives a dataset quality report. It looks at response length, diversity, structure, metadata integrity, narrative/dialogue balance, exchange depth, tag balance, character coverage, and related signals.

Treat the score as guidance, not absolute truth. Creative goals vary. Insights are best used to find patterns you might want to review.

### 7. Export

Use **Export** when you are ready to produce a training file.

You can export:

- all loaded entries
- selected or filtered entries
- ChatML or ShareGPT format
- clean output without LoreForge metadata

LoreForge keeps sidecar metadata near normal exports so your registry information can travel with the dataset. Clean export removes LoreForge metadata from the training records themselves.

## Backups at a High Level

LoreForge Lite creates backups before protected operations such as edits, repairs, deletes, splits, joins, merges, and tag lifecycle changes.

There are two main backup types:

- **Dataset backups** for JSONL files.
- **Database backups** for tags, characters, settings, prompt templates, and registry metadata.

Optional cloud backup can mirror the latest backup material to a configured sync folder. It is not real-time sync. It is a batch safety copy.

## Practical Tips

- Start small. Create or load one dataset, then use Manage Dataset as your home base.
- Explore the included example datasets if you want to see complete workflows before creating your own.
- Run Validation early for imported or manually edited data, and again before export.
- Keep your source files somewhere safe. LoreForge working copies protect untrusted files, but good file organization still helps.
- Use tags early. Even a simple tag system makes search, filtering, export, and Insights more useful.
- Run clean export only when you want training records without LoreForge metadata.
- Do not manually edit sidecar files unless you know exactly why.

## Where to Go Next

If you are brand new, read these next:

- **What LoreForge Lite Does**
- **Dataset Formats**
- **Loading Datasets and Working Copies**
- **Creating a New Dataset**
- **Understanding the Main Workspaces**
