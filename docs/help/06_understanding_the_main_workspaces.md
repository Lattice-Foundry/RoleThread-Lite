# Understanding the Main Workspaces

RoleThread Lite is designed as a workflow ecosystem.

The pages are not isolated tools you are expected to use equally. Each page has a job. Some pages are daily work surfaces. Others are deeper workspaces, review tools, or final handoff steps.

You do not need to master every page at once. Start with the main workflow, then add structure as the dataset asks for it.

Fresh installs start empty. Create a small dataset manually or load an existing
JSONL/ChatML file first, then use the workspaces below as the dataset grows.
Prompt Generation (Beta) can also help compile source-material prompts for an
external AI system, but RoleThread does not generate dataset content for you.

## The Basic Mental Model

Most RoleThread work follows this pattern:

1. Use **Manage Dataset** as the operational hub.
2. Use **Create Entry** to add focused new examples.
3. Use **Deep Edit** when an entry needs deeper work.
4. Use **Validation** and **Insights** for review passes.
5. Use Metadata pages to keep organization stable.
6. Use **Export** when the dataset is ready to leave RoleThread.

Manage Dataset is where much of the day-to-day work happens.

Deep Edit is for deeper drill-down work.

Validation and Insights help you decide what deserves attention.

## Manage Dataset

**Manage Dataset is the primary operational workspace.**

It is not just a browser.

This is where many users will spend most of their workflow, especially during cleanup and review passes.

Use Manage Dataset for:

- loading and creating datasets
- seeing the current loaded dataset
- filtering by tags
- searching entry content
- focused review from Validation or Insights
- quick editing
- selecting entries
- bulk tagging
- duplicate review
- duplicating entries
- joining selected entries
- deleting entries
- renaming the dataset
- preparing selected or filtered entries for export

If you are working through a batch of entries, Manage Dataset is usually the right starting point.

This is also the best place to learn on a small starter dataset. You can
filter, search, quick edit, duplicate, join, tag, and prepare exports while
learning how the rest of the app connects.

Example workflow:

1. Filter to untagged entries.
2. Search for a recurring phrase.
3. Quick Edit simple fixes.
4. Select related entries.
5. Add tags or join entries.
6. Open only the complex cases in Full Edit.

That is the intended rhythm: broad operational work first, deep editing only when needed.

## Create Entry

**Create Entry is for structured writing.**

Use it when you are adding new examples to the loaded dataset.

Create Entry is optimized for:

- system prompts
- system prompt templates
- planned exchanges
- user/assistant message pairs
- tags during creation
- Default mode
- Group Chat mode
- quick focused entry writing

It is the cleanest place to grow a dataset intentionally.

After saving, new entries become part of the normal Manage Dataset workflow.

## Deep Edit

**Deep Edit is the deeper editing workspace.**

It is not necessarily where most editing time needs to happen.

Use Deep Edit when an entry needs more than quick operational cleanup.

It is best for:

- Full Edit
- multi-turn restructuring
- system prompt refinement
- Group Chat refinement
- detailed character mapping review
- adding or removing exchanges
- split workflows
- careful content tuning

Think of Deep Edit as the surgical workspace. Manage Dataset helps you find and triage the work. Deep Edit helps you do the detailed work.

## Validation

**Validation is review and cleanup tooling.**

It is especially useful for:

- imported datasets
- ShareGPT conversion review
- externally or manually edited files
- merge cleanup
- large cleanup passes
- final export review
- consistency inspection

Normal entries created through RoleThread are guarded against most structural problems before save. That means Validation is not something you need to run constantly during normal writing.

Use it when you want a broader audit of the dataset.

## Insights

**Insights is pattern review.**

It helps you understand the dataset as a whole.

Use Insights for:

- response quality review
- narrative/dialogue balance
- exchange depth
- prompt concentration
- near-duplicate review
- tag coverage
- metadata integrity
- cleanup recommendations

Insights is best after a writing, editing, merge, or cleanup pass. It helps you decide what to review next.

When Insights links to affected entries, the work usually continues in Manage Dataset.

## Tag Management

**Tag Management supports organization.**

Use it for:

- creating categories
- creating custom tags
- reviewing active tags
- adopting archived/imported tags
- renaming or deleting custom tags
- keeping tag vocabulary stable

Most tagging of entries happens in Manage Dataset or Create Entry. Tag Management is where you maintain the tag system itself.

## Character Management

**Character Management supports Group Chat continuity.**

Use it for:

- creating reusable characters
- editing character descriptions
- deactivating characters
- reviewing character organization

Character assignments happen while writing or editing entries in Group Chat mode. Character Management maintains the registry those dropdowns use.

## System Prompts

**System Prompts supports reusable setup text.**

Use it for:

- creating reusable prompt templates
- editing templates
- deactivating templates
- keeping common scene setups consistent

Prompt templates speed up Create Entry and Full Edit. They do not automatically rewrite entries that already used them.

## Export

**Export is the handoff stage.**

Use it when entries are ready for training, sharing, or archiving.

Export supports:

- full dataset export
- selected or filtered export
- ChatML output
- ShareGPT output
- clean export
- sidecar metadata for project continuity

For training tools, clean export is often the right choice. For future RoleThread work, keep the sidecar with the dataset.

## Settings

**Settings controls safe local defaults.**

Use it for:

- default dataset folder
- local backup folder
- backup retention
- cloud backup destination
- data normalization behavior
- delete confirmations
- preview display names
- settings import/export

Most users can keep the defaults until their workflow needs a change.

## How the Pages Work Together

A practical cleanup pass might look like this:

1. Open Manage Dataset.
2. Filter to a problem area.
3. Quick Edit simple entries.
4. Send complex entries to Full Edit.
5. Split or join where structure needs work.
6. Run Validation.
7. Check Insights.
8. Return to Manage Dataset for the next focused pass.
9. Export when ready.

That loop is the heart of RoleThread Lite.

## Start Simple

You do not need a perfect workflow on day one.

Start with:

- Manage Dataset
- Create Entry
- Quick Edit
- Validation before export
- a small dataset you create manually or import

Then add:

- tags
- search
- Group Chat mode
- Insights
- split/join
- prompt templates
- sidecar-aware archive habits

RoleThread is built around guided complexity. The structure is there when you need it, but you can grow into it.
