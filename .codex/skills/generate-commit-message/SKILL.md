---
name: generate-commit-message
description: Generate a Conventional Commits message from the current staged Git changes. Use when the user asks for a commit message, requests a conventional commit for staged work, or provides a staged diff to summarize. This skill generates message text only and does not create or modify commits.
---

# Commit Message Generator

## Purpose

Generate one clear Conventional Commits message that accurately represents the current staged Git changes.

The result may contain:

* a required title
* an optional bullet-point body
* an optional breaking-change footer

## Use This Skill When

Use this skill when the user:

* asks for a commit message
* asks for a Conventional Commits message
* wants the current staged changes summarized as commit text
* provides a staged diff or staged-change summary
* wants a commit message without creating the commit

This skill is limited to commit-message generation.

## Repository Access

Treat repository access as read-only.

Use only staged changes as evidence. Ignore unstaged and untracked changes.

When repository tools are available, inspect staged changes with:

```bash
git diff --cached --stat
git diff --cached
```

Additional read-only commands may be used when they help interpret the staged diff, such as:

```bash
git status --short
git diff --cached --name-only
```

Do not stage files, modify files, create commits, amend history, or push changes.

## Workflow

### 1. Inspect the staged changes

Determine:

* which files changed
* what behavior or structure changed
* whether the change is user-facing
* whether it fixes a bug, adds a feature, restructures code, updates documentation, or performs maintenance
* whether the changes form one coherent commit

Base the message only on information supported by the staged diff or details supplied by the user.

### 2. Identify the primary intent

Choose the commit type that best represents the main purpose of the staged changes.

When several kinds of changes are present, select the type that reflects the most important behavioral or project-level outcome.

### 3. Choose a scope when useful

Add a scope when the affected area is clear and meaningful.

Good scopes include:

* `auth`
* `api`
* `ui`
* `billing`
* `config`
* `tests`
* `docs`

Omit the scope when:

* the changes affect several unrelated areas
* no concise scope is obvious
* the scope would repeat the type or title

### 4. Write the title

Use this format:

```text
<type>(<scope>): <description>
```

When no scope is needed:

```text
<type>: <description>
```

For a breaking change:

```text
<type>(<scope>)!: <description>
```

The title must:

* use lowercase
* use imperative language
* describe the main change clearly
* contain 50 characters or fewer
* have no period at the end
* avoid issue numbers unless the user requests them

Prefer specific titles such as:

```text
feat(auth): add jwt token validation
fix(api): handle missing user records
refactor(ui): simplify sidebar state
docs(readme): document local setup
```

Avoid vague titles such as:

```text
update files
fix stuff
make changes
code cleanup
misc improvements
```

### 5. Add a body when it improves understanding

The body is optional.

Use a body when the staged changes:

* contain multiple related updates
* require context that does not fit in the title
* address a non-obvious problem
* change important behavior
* have a meaningful reason or impact

Format the body as concise bullet points:

```text
- explain the reason or impact of the change
- summarize important related updates
```

Focus on why the change matters and its effect on the codebase or users.

Avoid repeating the title or listing every modified file.

### 6. Describe breaking changes when present

When the staged changes introduce an incompatible API, configuration, schema, or behavioral change:

* add `!` after the type or scope
* add a `BREAKING CHANGE:` footer when migration context is useful

Example:

```text
feat(api)!: replace legacy authentication

- migrate protected routes to oauth tokens
- remove support for session-based authentication

BREAKING CHANGE: clients must authenticate with oauth tokens
```

### 7. Validate the result

Before returning the message, verify that:

* the message reflects only staged changes
* the type matches the primary intent
* the scope is useful or omitted
* the title is lowercase
* the title is imperative
* the title is 50 characters or fewer
* the title has no trailing period
* the body is concise and high-level
* no unsupported details were invented

## Commit Types

| Type       | Use for                                                  |
| ---------- | -------------------------------------------------------- |
| `feat`     | New user-facing behavior or capability                   |
| `fix`      | Bug fixes or incorrect behavior                          |
| `refactor` | Internal restructuring without intended behavior changes |
| `perf`     | Performance improvements                                 |
| `docs`     | Documentation-only changes                               |
| `test`     | Adding, correcting, or restructuring tests               |
| `style`    | Formatting or stylistic changes without logic changes    |
| `build`    | Build system, packaging, or dependency configuration     |
| `ci`       | Continuous integration or deployment configuration       |
| `chore`    | Maintenance that does not fit another type               |
| `revert`   | Reverting an earlier change                              |

Choose the most specific applicable type.

For dependency updates:

* use `fix` or `feat` when the dependency change directly delivers that outcome
* use `build` when it mainly affects build or package configuration
* use `chore` for routine maintenance with no clearer category

## Output Format

Return exactly one commit message as plain text.

Title only:

```text
fix(api): handle missing user records
```

Title with body:

```text
feat(auth): add jwt token validation

- reject expired and malformed tokens
- centralize authentication error handling
```

Breaking change:

```text
feat(config)!: rename database settings

- align environment variables with service naming
- remove deprecated configuration aliases

BREAKING CHANGE: update database environment variable names
```

Do not include:

* explanations outside the commit message
* alternative messages
* markdown code fences
* shell commands
* generated-by attribution
* signatures
* advertisements

If a body is unnecessary, return only the title.

## No Staged Changes

When repository access is available and the staged diff is empty, return exactly:

```text
no staged changes found
```

Do not generate a speculative commit message.

When repository access is unavailable and the user has not supplied a staged diff or summary, ask for the staged diff produced by:

```bash
git diff --cached
```
