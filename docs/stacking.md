# Stacked pull requests

## Goal

Split one large change into a chain of small PRs, where each PR shows only its own diff and depends on the one
below it:

```text
main
└─ #101 part 1
   └─ #102 part 2
      └─ #103 part 3
```

The main target is LLVM, which squash-merges every PR and allows committers to create `users/<username>/` branches
in `llvm/llvm-project` specifically for stacked PRs (see the
[LLVM GitHub User Guide](https://llvm.org/docs/GitHub.html#branches)).

## Workflow

```bash
acp stack start                 # remember base branch, open a new stack
git add -p                      # stage part 1
acp pr "feat: part 1" -d        # PR #101 -> main
git add -p                      # stage part 2
acp pr "feat: part 2" -d        # PR #102 -> part 1
acp stack end                   # finalize stack comments, return to base branch

# later, after #101 is merged
acp stack sync                  # rebase #102 onto main and retarget it
```

## Commands

| Command | Description |
|---|---|
| `acp stack start [-d] [-r USERS]` | Open a stack on the current branch. Flags become defaults for every layer. |
| `acp pr "..."` | While a stack is open, add a new layer on top of the stack. |
| `acp stack status [ID]` | Show the stack topology and PR states. Without an open stack, list all stacks. |
| `acp stack end` | Refresh stack comments, mark the stack closed, check out the base branch. |
| `acp stack sync [ID] [--continue]` | Drop merged layers, rebase the remaining ones, retarget PRs, refresh comments. |
| `acp stack abort [ID]` | Delete local stack state only. PRs and remote branches are left untouched. |

`status` and `sync` default to the open stack, or else to the most recent stack that is not fully merged.

## Layer creation (`acp pr` inside a stack)

Unlike a normal `acp pr`, HEAD does **not** go back to the original branch. Every layer builds on the previous one,
so the previous layer's changes must stay in the working tree.

1. Check that HEAD is the stack tip (the base branch for layer 1, the previous layer otherwise).
2. `git checkout -b <layer-branch>`.
3. Commit staged changes. Unstaged changes stay in the working tree, so no stash is needed.
4. Push the branch (see [Remote selection](#remote-selection)).
5. `gh pr create --base <parent> --head <layer-branch>`.
6. Stay on the new layer branch.
7. Create or update the stack comment on every PR in the stack.

If the commit, push or PR creation fails, acp returns to the parent layer with the changes staged again, deletes the
new local branch, and deletes the remote branch if it was already pushed.

## Branch naming

Stack layers use `users/{gh_user}/acp-{stack_id}-{n}`, for example `users/zeyi2/acp-k3f9q2-2`.

- The `users/<username>/` prefix is required by LLVM for branches in the main repository.
- `stack_id` is a short random id, `n` is the 1-based layer index.
- Normal non-stack PRs keep the `acp/{user}/{random}` name.
- `acp branches` lists both kinds of branches, and `acp pr` outside a stack refuses to run on either.

## Remote selection

The base of a GitHub PR must be a branch in the target repository, so true stacking needs the layer branches in the
target repository.

| Repo type | Mode | Push to | PR base for layer n > 1 | PR `--head` |
|---|---|---|---|---|
| Non-fork | stacked | `origin` | previous layer branch | `branch` |
| Fork, write access to upstream | stacked | `upstream` | previous layer branch | `branch` |
| Fork, no write access to upstream | fallback | `origin` (fork) | base branch (`main`) | `owner:branch` |

Mode detection happens once, at `acp stack start`, using
`gh api repos/{upstream} --jq .permissions.push`. The mode is stored in the stack state.

### Fallback mode

- Every PR targets the base branch, so layer n shows the combined diff of layers 1..n.
- The stack comment says that only the last commit of each PR belongs to that PR, and links to the single-commit
  view (`https://github.com/{upstream}/pull/{number}/commits/{sha}`).
- After the bottom PR merges, `acp stack sync` still rebases the remaining layers onto the new base, so each PR
  drops the already-merged commit.

## Local state

Stored under `$(git rev-parse --git-common-dir)/acp/`, so it is never committed and is shared across worktrees.

```text
.git/acp/
├── current            # id of the open stack, absent if none
└── stacks/
    └── k3f9q2.json
```

```json
{
  "id": "k3f9q2",
  "status": "open",
  "mode": "stacked",
  "repo": "llvm/llvm-project",
  "head_repo": "llvm/llvm-project",
  "remote": "upstream",
  "base_remote": "upstream",
  "base_branch": "main",
  "base_sha": "abc123...",
  "gh_user": "zeyi2",
  "defaults": {"draft": true, "reviewers": null},
  "layers": [
    {
      "n": 1,
      "branch": "users/zeyi2/acp-k3f9q2-1",
      "parent_sha": "abc123...",
      "head_sha": "def456...",
      "pr_number": 101,
      "title": "feat: part 1",
      "comment_id": 987654,
      "merged": false
    }
  ]
}
```

- `status` is `open` until `acp stack end`, then `closed`, then `done` once every PR is merged.
- `parent_sha` is the tip of the parent layer that this layer is based on. `sync` uses it as the cut point for
  `git rebase --onto`.
- `comment_id` caches the stack comment. If the comment is missing, it is found again through the marker.
- `acp stack end` removes `current`, but keeps the file, because `sync` needs it after the PRs merge.
- `acp stack abort` deletes the file and `current`.
- While a sync is stopped on a conflict, a `sync` key holds its progress.

## Stack comment

One comment on every PR, updated on every `acp pr`, `acp stack end` and `acp stack sync`. The comment is found
through a hidden marker and edited with `gh api -X PATCH repos/{repo}/issues/comments/{id}`, so it is never
duplicated.

```markdown
<!-- acp-stack:k3f9q2 -->
**Stack** (3 PRs, base `main`), merge from the bottom up:

- `main`
  - ~~#101 feat: part 1~~ (merged)
    - **#102 feat: part 2** ← this PR
      - #103 feat: part 3 (draft)

_This stack is still in progress, more PRs may be added._

<sub>Managed by acp. This comment is updated automatically.</sub>
```

The "still in progress" line disappears after `acp stack end`.

## `acp stack sync`

1. Require a clean working tree, then fetch the base branch.
2. Query every layer's PR state with `gh pr view --json state,isDraft`.
3. Mark merged layers, starting from the bottom. A merged PR above an unmerged one only produces a warning.
4. For each remaining layer, bottom-up, run `git rebase --onto <new-parent> <parent_sha> <branch>`. The new parent
   is the fetched base branch for the new bottom layer and the rebased layer below otherwise. Layers whose parent
   did not move are skipped.
5. `git push --force-with-lease` every rebased layer.
6. In stacked mode, `gh pr edit --base <base>` the new bottom PR. This happens before the merged branches are deleted,
   so GitHub never sees an open PR whose base branch is gone.
7. Delete the remote and local branches of the merged layers, and return to the branch you were on (or the base
   branch, if that branch was merged).
8. Refresh every stack comment.

On a rebase conflict, `sync` stops, saves its progress in the state file, and asks you to resolve the conflict,
run `git rebase --continue`, then run `acp stack sync --continue`.

## Option rules inside a stack

- `--merge` is rejected. Merge from the bottom up, then run `acp stack sync`.
- `--auto-merge` is allowed only on layer 1. On higher layers it would merge into the parent branch, not into `main`.
- `-i/--interactive` prints `https://github.com/{repo}/compare/{parent}...{branch}?expand=1` so the base is correct.
  The PR number is looked up the next time the stack comments are refreshed.
- `-d` and `-r` given to `acp pr` apply to that layer. When the stack defaults set them, a single layer cannot turn
  them off.
- `-a/--add` works as usual.

## Errors

| Situation | Behavior |
|---|---|
| `acp stack start` with a stack already open | Error, suggest `acp stack end` or `acp stack abort`. |
| `acp stack start` when the base branch is not on the remote | Error, push the base branch first. |
| `acp pr` in a stack while HEAD is not the stack tip | Error, print the expected branch. |
| `acp stack end` with no layers | Remove the empty stack and print a message. |
| Push or PR creation fails | Roll back the layer, keep the changes staged on the parent. |
| Base branch moved since `start` | Allowed. Layers stay on the old base until `sync`. |

## Out of scope

- Branching (non-linear) stacks.
- Automatic restack after amending a middle layer. A manual `git rebase` plus `acp stack sync` covers it.
- Rebuilding local state from GitHub when the state file is lost.
