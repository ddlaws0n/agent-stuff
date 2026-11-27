# Blameless Postmortem

What happened, what it cost, why the system allowed it, and who fixes what by when.

## The core rule

**Name the gaps in the system that let the failure happen, never a person or team to blame.** Assume everyone acted in good faith on the best information they had. A postmortem is a factual record: impact, actions taken, root causes, and follow-up actions that reduce the chance or impact of a repeat.

Workflow: `collect the data and logs` → `fill the template below` → `write the timeline in one timezone` → `write action items with type, owner, and bug` → `get a review` → `run the Verify checklist`.

## Mechanics

1. **Use the example postmortem's fields, in order.** Title with incident number, Date, Authors, Status, Summary, Impact, Root Causes, Trigger, Resolution, Detection, Action Items, Lessons Learned, Timeline, Supporting information. Add Background and Glossary when readers outside the team need context.
2. **Summary is one or two sentences.** What failed, for how long, and under what conditions. Example: "Shakespeare Search down for 66 minutes during period of very high interest in Shakespeare due to discovery of a new sonnet."
3. **Impact has numbers.** Users, queries, revenue, duration. If you have no exact data, give a labeled estimate. An estimate beats no data. Never "significant" or "major" without a number.
4. **Root Causes and Trigger are separate.** Root causes are the latent conditions (for example, a resource leak). The trigger is the event that exposed them (for example, a traffic spike). Go deep enough to drive the action items. "Human error" is never a root cause: ask what let the error reach production.
5. **Blameless language.** Write about "what" went wrong, not "who" caused it. No judgment words: careless, negligent, ignored, failed to, should have known, sloppy. No dramatic words: disaster, meltdown, catastrophic. Replace each with verifiable data. Names may appear in the timeline to record who did what; they never appear next to a cause.
6. **Detection says how you found out.** Name the alert or the human report. If a person found it before monitoring did, say so: that is a monitoring gap and needs an action item.
7. **Resolution lists each step that stopped or fixed the impact.** One line per step, in order.
8. **Timeline in one timezone.** State it once in the header: "2015-10-21 (all times UTC)". Each entry: 24-hour `HH:MM`, then the event. Mark **OUTAGE BEGINS**, **OUTAGE ENDS**, and **INCIDENT ENDS**. Start before the outage, at the first relevant event. Link full chat logs and system logs; do not paste them.
9. **Action items are a table: Action Item | Type | Owner | Bug.** Type is one of: prevent, mitigate, detect, repair, investigate, process, other. Owner is one person. Bug is a tracking ID with status (TODO or DONE), or "n/a" if done without one. The bug carries the priority.
10. **Action items have a verifiable end state.** No "improve", "make better", "be more careful". Prefer changes to systems and automation over changes to human behavior. Each theme needs at least one prevent or mitigate item.
11. **Lessons Learned has three lists.** What went well, What went wrong, Where we got lucky.
12. **One owner, many contributors.** Include everyone who took part in the incident as authors or reviewers. Publish soon, while memory is fresh, and share as widely as the content allows.

Template:

```
# <Service> Postmortem (incident #<n>)
Date: YYYY-MM-DD   Authors: <names>   Status: <e.g. Complete, action items in progress>
Summary: <what failed, how long, under what conditions>
Impact: <numbers; label estimates>
Root Causes: <latent conditions>        Trigger: <the event that exposed them>
Resolution: <steps, in order>           Detection: <alert or report that found it>
Action Items: | Action Item | Type | Owner | Bug |
Lessons Learned: What went well / What went wrong / Where we got lucky
Timeline: YYYY-MM-DD (all times <TZ>)  HH:MM <event> ...
Supporting information: <links to logs, dashboards, chat>
```

## Verify

- Every field from mechanic 1 is present and in order; empty fields say why
- Impact contains at least one number with a unit; estimates are labeled
- Root Causes and Trigger are separate fields, and no root cause is "human error"
- Zero judgment or dramatic words from mechanic 5; no person or team named as a cause
- Timeline states one timezone in its header; every entry starts with `HH:MM`; OUTAGE BEGINS and OUTAGE ENDS are marked
- Every action item has a type from the list, one owner, and a bug ID or "n/a"; each open bug has a priority
- Zero action items that start with "improve", "make better", or "be more careful"
- At least one prevent or mitigate action item exists
- A reviewer can answer yes to: Is the impact complete? Is the root cause deep enough? Is the action plan right, at the right priority?

## Do not

- Blame a person or team, even indirectly ("the on-call engineer missed the page")
- Write action items that ask people to try harder; change the system instead
- Leave impact as adjectives because exact numbers are missing
- Paste raw logs into the body; summarize and link
- Leave a postmortem unreviewed or unshared. The SRE Book says an unreviewed postmortem "might as well never have existed"
- Invent numbers, owners, or bug IDs to fill the template; mark them `[TBD]`

## Example transformations

**Before:** "Sam carelessly pushed a bad config at 3pm and took down checkout. This was a total disaster. The on-call team was asleep at the wheel and didn't notice until customers complained 40 minutes later. Sam needs to be more careful."

**After:** "Root Causes: A bad config change reached production. [Describe the error, and why no check caught it before production.] Trigger: Config push at 15:00 [timezone]. Detection: Customer reports, 40 minutes after the push. No alert fired. Impact: Checkout down [duration, users affected: TBD]. Action Items: | Add automated validation for config pushes | prevent | [owner] | [bug] | Add an alert for checkout failures | detect | [owner] | [bug] |"

**Before:** "Action items: improve monitoring, make the deploy process better, team to be more careful with database migrations, look into the timeout issue."

**After:** "| Action Item | Type | Owner | Bug |
| [Name the alert and its threshold] | detect | [owner] | [bug] TODO |
| [Name the deploy step to add or automate] | prevent | [owner] | [bug] TODO |
| [Name the automated check for migrations] | prevent | [owner] | [bug] TODO |
| Investigate the timeout issue; report its root cause | investigate | [owner] | [bug] TODO |"
