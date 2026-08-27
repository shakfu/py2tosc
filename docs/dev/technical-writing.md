## Technical Writing

Applies to CHANGELOG entries, docs, docstrings, comments, commit messages.

State what changed, then why that option over the alternative. Stop.

- **One idea per paragraph, stated once.** If a point appears twice, delete the weaker instance. Restating for emphasis is the most common bloat.

- **No metaphor or personification.** A value does not "ride" a property, geometry is not "free", a decision does not "buy" anything, work is not "the part that is hard". Say what the code does.

- **Cut rhetorical scaffolding**: "which is the whole reason", "and that is the trade", "not X, but Y", "it is worth saying that". Either state the fact plainly or drop the sentence.

- **Lists over prose** for three or more parallel items (rules, options, trade-offs, failure modes).

- **Numbers over adjectives.** "27 controls composite into one rectangle" beats "the result is illegible".

- **Name the thing.** `grid-faders.tosc`, `--v`, `_needs` -- not "the corpus", "the value channel", "the table".

- **Do not pre-empt objections.** Explaining why something is *not* a problem costs a paragraph and answers a question nobody asked. One clause, or none.

- **Delete rather than soften.** If a sentence could be removed without changing what a reader does, remove it.

Length budgets (soft):

| | |
|-|-|
| Code comment | 1-2 lines |
| Docstring | one-line summary, then args/returns/raises. Design rationale
belongs in the module docstring or `docs/dev/`, not here |
| CHANGELOG entry | one paragraph, plus a code block if the syntax is new.
Three paragraphs is the ceiling, and only for a change with lasting
design consequences |

Never restate the CHANGELOG in the docs, or the module docstring in a function Never restate the CHANGELOG in the docs, or the module docstring in a function docstring. Cross-reference instead.

Finish with a deletion pass: re-read and cut. First-draft length is not the target.

Two notes on using it:

- The deletion pass is the rule that does the work. The others describe symptoms; that one is the habit that prevents them.

- It deliberately doesn't repeat your existing Documentation rules (no emoji, no "surface" as a verb, bullets where appropriate) — append it under that section rather than replacing it.