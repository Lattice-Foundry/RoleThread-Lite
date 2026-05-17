# Searching and Filtering Entries

Search and filters help you work with the entries that matter right now. They are especially useful once a dataset grows beyond what you can comfortably scan by hand.

Most search and filtering work starts in **Manage Dataset** because that page is the main operational workspace. It combines browsing, tag filters, entry search, selection, quick edits, duplication, join, delete, and export preparation.

**Deep Edit** uses the same shared search state, but it is best when the filtered result set needs deeper content work.

RoleThread Lite gives you three main ways to narrow the browser:

- tag filters
- entry text search
- focused entry links from pages like Insights and Validation

## Filtering Order

The normal browser order is:

1. loaded entries
2. tag filters
3. entry search
4. pagination

This means search scans the filtered entry set, not only the current page. Pagination happens last.

If you search for a phrase while a tag filter is active, RoleThread searches only entries that passed the tag filter.

## Tag Filters

Tag filters are useful when you know the kind of entry you want.

Depending on the page, you may see match modes such as:

- **Any**: show entries that have at least one selected tag
- **All**: show entries that have every selected tag
- **Exact**: show entries whose tag set matches the selected tags

Use tag filters for organization questions:

- "Show me all romance entries."
- "Show entries tagged both dialogue and high intensity."
- "Show entries that are exactly in this review bucket."

## Entry Search

Entry search looks inside message content.

Use it when you remember a phrase, scene detail, or response pattern but not where the entry lives.

Search supports message scopes:

- **Include System** searches system prompts.
- **Include User** searches user messages.
- **Include Assistant** searches assistant responses.

The default is user and assistant content. System prompts are excluded unless you include them.

## Match Modes

Entry search supports three match modes:

- **Contains**: finds the search text as a normal substring.
- **All Words**: every word in the query must appear somewhere in the selected message scopes.
- **Exact Phrase**: the phrase must appear as written after basic case-insensitive matching.

Examples:

- Use **Contains** for a remembered sentence fragment.
- Use **All Words** when you know several important words but not the order.
- Use **Exact Phrase** when you want a specific phrase.

## Search Persistence

Search state is shared between **Manage Dataset** and **Deep Edit**.

If you search in Manage Dataset, then move to Deep Edit, the same query and options remain active while the same dataset is loaded.

Search clears when:

- you load a different dataset
- you click **Clear Search**
- you use a broader clear-filters action

Clear Search clears only the query. Scope and match settings remain so you can keep your preferred search style.

## Pagination

Pagination happens after filtering and search.

That means:

- a search can find entries beyond the current page
- result counts reflect the narrowed set
- Previous and Next move through the results, not through the original full dataset

If a result disappears after editing, check whether the edit changed the text or tags that made it match.

## Selecting Filtered Results

Selection works against the currently visible browser results.

This is useful for:

- bulk tagging
- deleting a reviewed set
- joining related entries
- exporting selected or filtered entries

Before bulk actions, check the result count and current filters so you know exactly what you are operating on.

## Focused Results From Insights and Validation

Some pages can send you to Manage Dataset with a focused list of entries.

Examples:

- entries with no tags
- entries with short responses
- entries with validation issues
- entries that may benefit from splitting
- entries referencing inactive characters

When this happens, Manage Dataset shows a banner explaining the focused view. Use **Clear filter** or **Clear all filters** when you are ready to return to the normal browser.

## Workflow Examples

### Find Untagged Entries

1. Open Manage Dataset or Insights.
2. Use the untagged entry count or metadata recommendation if available.
3. Review the focused entries.
4. Add tags.
5. Clear the filter when finished.

### Find a Remembered Exchange

1. Open Manage Dataset.
2. Enter a phrase in Search Entries.
3. Choose **Contains** or **All Words**.
4. Include System if the phrase is in the system prompt.
5. Use Quick Edit for simple fixes or Full Edit for deeper work.

### Work Through a Problem Category

1. Apply a tag filter.
2. Add a search query if needed.
3. Use Manage Dataset actions for quick cleanup, tagging, selection, or duplication.
4. Open entries in Full Edit when they need deeper restructuring.
5. Run Validation after larger cleanup passes or before export.

## Common Mistake

**Mistake:** Thinking search only checks the current page.

**Better mental model:** Search checks all entries that passed tag filtering. The page view is only the final display slice.

