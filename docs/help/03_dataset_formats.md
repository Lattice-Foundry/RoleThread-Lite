# Dataset Formats

LoreForge Lite works with JSONL datasets for narrative AI training. The two main conversation formats are **ChatML** and **ShareGPT**.

You do not need to memorize every detail, but it helps to understand what LoreForge expects and what it changes during import/export.

## JSONL Basics

JSONL means "JSON Lines." Each line is one JSON object.

A small dataset might look like this:

```jsonl
{"messages":[{"role":"system","content":"You are a helpful narrator."},{"role":"user","content":"Describe the old house."},{"role":"assistant","content":"The house leaned against the hill, windows dark and watchful."}],"tags":["setting_description"]}
{"messages":[{"role":"system","content":"You are a helpful narrator."},{"role":"user","content":"What does Mara notice?"},{"role":"assistant","content":"Mara notices the candle smoke moving against the draft."}],"tags":["observation"]}
```

Each entry is separate. LoreForge Lite loads those entries into a browser so you can inspect, edit, tag, validate, and export them.

## ChatML

ChatML is LoreForge Lite's main working format. A ChatML-style entry has a `messages` list with standard roles:

```json
{
  "messages": [
    {"role": "system", "content": "You are writing a grounded fantasy scene."},
    {"role": "user", "content": "What does the traveler see?"},
    {"role": "assistant", "content": "The road bends toward a watchtower half swallowed by ivy."}
  ],
  "tags": ["fantasy", "scene_description"]
}
```

The usual roles are:

- `system`: instructions or framing for the entry
- `user`: the prompt or human-side turn
- `assistant`: the response being trained

Most LoreForge editing tools work directly with this structure.

## ShareGPT

ShareGPT-style records usually use a `conversations` list instead of `messages`:

```json
{
  "conversations": [
    {"from": "human", "value": "Say hello as Nicole."},
    {"from": "gpt", "value": "Hi, Scott. I missed you."}
  ],
  "tags": ["greeting"]
}
```

When LoreForge Lite loads ShareGPT data, it converts it into ChatML-style entries for editing. Common role names are mapped into standard roles.

For example:

- `human` becomes `user`
- `gpt` becomes `assistant`
- system-like turns become `system`

If a ShareGPT record has no system prompt, LoreForge may inject a simple internal system prompt so the entry has a valid ChatML shape.

## LoreForge-Native Metadata

When LoreForge saves entries, it may add a `_loreforge` metadata block. That block can include:

- app version
- native/trusted save marker
- entry UUID
- dataset UUID
- validation timestamp

This metadata helps LoreForge preserve identity across edits, merges, sidecars, and selection workflows.

It is not meant to be part of the conversational training text.

## Entry UUID and Dataset UUID

An **entry UUID** is a stable identity for one entry. It helps LoreForge keep track of the same entry even after filtering, pagination, editing, or merging.

A **dataset UUID** identifies a saved LoreForge dataset identity. It helps LoreForge check that nearby sidecar metadata belongs with the dataset being loaded.

Most users do not need to manage UUIDs manually. They exist so the app can be safer and more predictable.

## Group Chat Mode Still Exports Standard Roles

Group Chat mode lets you assign characters to individual turns while editing. This is display and metadata support.

The JSONL training roles still remain:

- `system`
- `user`
- `assistant`

LoreForge does not export custom role names as training roles. Character names are preserved separately as metadata and sidecar information.

That distinction matters. It keeps exported datasets compatible with standard training expectations while still letting you organize multi-character scenes.

## Clean Export

Clean export removes LoreForge-specific metadata from the exported training records.

Clean export is useful when you want a plain dataset for training or sharing without:

- `_loreforge` metadata
- internal identity fields
- tags or other non-message fields, depending on export settings

Use clean export when the target system should only receive conversation records.

## Practical Guidance

- Use ChatML as the normal editing format in LoreForge Lite.
- Import ShareGPT when you already have data in that shape.
- Run Validation after import or conversion.
- Use clean export for final training files when you do not want LoreForge metadata included.
- Keep sidecar files with datasets when you want tags, characters, and prompt metadata to travel with them.

