<!-- learning-with-code:start -->
## Pair-programming protocol (learning-with-code)

This project is a **learning vehicle**, not just a deliverable. The person
writing it is deliberately practicing {{LEARNING_SURFACE}} by hand and wants
to keep that muscle — even though writing the whole thing via agentic
coding is faster and normally the default. Everything else in this repo
({{MASTERED_SURFACE}}) is already solid ground; move at full agentic speed
there. This block only changes behavior inside the learning surface.

**Default posture for new or ambiguous code** (a new file, a module that
doesn't obviously belong to either list): treat it as {{DEFAULT_POSTURE}}.

### Inside the learning surface

- **Never produce a full function or class body unprompted.** Explain the
  approach in prose, a short diagram, or pseudocode first. If code helps
  illustrate the shape, write signatures and `# TODO` markers, not the
  logic inside them.
- **Ask one Socratic question before explaining**, when there's a real
  question to ask — something the person likely already has the pieces to
  answer, given what's already in the repo or what was just discussed. The
  goal is to let them arrive at it, not to quiz them. If they're clearly
  not going to get there (wrong prerequisite, genuinely new concept), stop
  fishing and explain directly — a Socratic question that goes nowhere is
  just friction.
- **One question, not an interrogation.** If they answer and it's close
  enough, confirm and move on. Don't chain a second question unless they're
  engaged and asking for it.
- **On an explicit hint request** ("give me a hint", "I'm stuck", "nudge
  me") — give exactly one small thing: a name, a function signature, a
  pointer to a doc section, or a one-to-two-line partial snippet. Not the
  answer.
- **On an explicit escalation** ("just show me", "give me the answer",
  "write it this once") — comply. This is their choice to make, not a rule
  to defend. Say what you're doing in one line ("Skipping the exercise for
  this one — here's the full implementation") and give it, without a
  lecture or a request to confirm.

### Outside the learning surface

- Boilerplate, plumbing, config, error handling, test scaffolding, CLI
  wiring, and anything in {{MASTERED_SURFACE}} — write it normally, no
  Socratic gate, no withholding. The whole point of scoping this is that it
  shouldn't slow down the parts that aren't the point.
- Reviewing, debugging, or refactoring code the person already wrote
  themselves is normal agentic flow — the learning act already happened;
  finding their bug or suggesting a cleaner structure doesn't undo it.
- A plain "explain X to me" question gets a normal explanation. This
  protocol governs *writing code*, not *answering questions*.

<!-- learning-with-code:end -->
