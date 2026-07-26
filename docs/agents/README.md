# Parallel agent operating manual

## One-time setup (from repo root)
```powershell
.\scripts\setup_worktrees.ps1
```
Creates `../ce-worktrees/{extraction,sequencer,register,case-memory,ui,voice}`,
one checked-out branch each, and copies `.env` into every one.

## Launch an agent
```powershell
cd ..\ce-worktrees\extraction
claude
```
First message to every agent — paste verbatim:
> Read `CLAUDE.md` and `docs/agents/feat-<name>.md`, then execute that brief.
> Touch only the files your brief says you own. Run `.\scripts\verify.ps1`
> before committing. Report blockers immediately instead of redesigning.

## Who to start, and when

| Priority | Branch | Blocked by | Start |
|:--:|---|---|---|
| 1 | `feat/extraction` | API key + 1 photo | **the moment the key lands** |
| 2 | `feat/ui` | nothing | **now** |
| 3 | `feat/sequencer` | nothing | **now** |
| 4 | `feat/case-memory` | nothing | **now** |
| 5 | `feat/register` | a handwritten page | when sourced |
| 6 | `feat/voice` | API key | only if 1–5 are healthy |

Three agents (ui, sequencer, case-memory) need **no key and no documents** — start
them immediately.

## Rules that keep parallel work safe
1. `src/contracts.py` is **frozen**. It is the interface every branch codes
   against. Changing it requires a PR to main titled `CONTRACT-CHANGE:` plus a row
   in `IDEA_SCOPE.md` §16.
2. One owner per file. The ownership table is in `CLAUDE.md`; each brief repeats it.
3. `.\scripts\verify.ps1` must pass before any commit — it runs the tests **and**
   asserts the fixture golden path still produces a next action, a blocking edge,
   and the refusal. That fixture path is the demo fallback; it must never break.
4. Rebase on main before merging: `git fetch origin && git rebase origin/main`.
5. Merge from the main worktree only: `.\scripts\merge_branch.ps1 feat/<name>`
   (it verifies after merging and auto-rolls-back on failure).

## Merge order
`extraction → sequencer → register → case-memory → ui → voice`

Merge early and often. Do not save integration for the end — IDEA_SCOPE.md §14.

## Cut order if behind schedule
`voice → crop images → SQLite/case-listing → correction UI polish`
Never cut: the refusal behaviour, the blocking edges with quotes, or the fixture
golden path.
