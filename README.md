# AI PR Reviewer — custom GitHub Action

A reusable GitHub Action that runs a pluggable LLM code review on pull requests and posts
**few, high-confidence** findings as inline comments. Report-only by default — it never
fails your build because the model failed.

> Status: v1 in progress. See [`ACTION_PLAN.md`](ACTION_PLAN.md) for the build plan and locked decisions.

## Why

<!-- TODO(phase-7): hook + a GIF of a real reviewed PR. -->

## Usage

```yaml
name: AI PR Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Pabl0Azeved0/custom_github_actions@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          llm-api-key: ${{ secrets.LLM_API_KEY }}
          # optional:
          # llm-provider: groq
          # llm-model: llama-3.3-70b-versatile
          # strictness: balanced
          # max-findings: "10"
          # fail-on-findings: "false"
```

### Trigger: `pull_request` only

**Do not switch this action to `pull_request_target`.** That trigger runs with your full
secrets while the workspace holds the PR author's code, so it hands an untrusted contributor
the LLM key, the `GITHUB_TOKEN`, and the runner.

Fork PRs are not reviewed, by design: GitHub gives them a read-only token and no `secrets.*`,
so the action logs that it is skipping and exits 0. `pull_request_target` is the usual
workaround for that and it is not worth the trade here.

## Inputs

<!-- TODO: table generated from action.yml. -->

## How it works

<!-- TODO: event -> diff (budgeted, filtered) -> LLM review -> inline comments. -->

## Quality

<!-- TODO(phase-6): golden-set results — quality is measured, not claimed. -->

## Limitations

<!-- TODO(phase-7): honest false-positive behavior, diff-budget truncation, single-file context. -->
