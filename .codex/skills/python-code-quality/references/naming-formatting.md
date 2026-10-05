## When To Consult

Use this reference when formatting, imports, naming, public attributes, constants, encoding, or local style tradeoffs affect a Python 3.12 change. Check repository configuration and nearby code first; if they do not decide the issue, use PEP 8 defaults and prioritize readability.

## Repository Overrides

Apply style decisions in this order: correctness and safety, explicit user requirements, repository configuration and enforced tooling, established local conventions, then general Python guidance. Do not break public imports or compatibility promises solely for style. Do not reformat untouched legacy code just to normalize it. Keep the local form when a generic rule would reduce readability or create inconsistency, unless a higher-precedence rule requires change.

## Formatting And Layout

Indent blocks with four spaces. Do not mix tabs and spaces; keep tabs only to preserve an existing tab-indented file. Prefer implicit continuation inside parentheses, brackets, or braces. Use either vertical alignment or a hanging indent, keep operator breaks locally consistent, and use backslashes only when implicit continuation is unsuitable.

Follow the repository line-length limit when configured. Otherwise, keep code near 79 columns and flowing comments or docstrings near 72, with an agreed team code limit up to 99 only when repository policy allows it. Keep comments and docstrings wrapped more tightly even if code lines run longer.

Use blank lines to separate distinct concepts and keep related concepts close together. Extra blank lines are acceptable for related function groups, and related one-liners may stay adjacent. Reorganize or split a file when mixed responsibilities or excessive vertical distance make it hard to follow, but do not invent file-size thresholds.

Keep module structure conventional: module docstring or file comment first, then module dunders, then imports. Place `from __future__` imports before other imports. Group standard-library, third-party, and local imports with blank lines between groups. Prefer one import per line except for a small related `from ... import ...` group. Prefer absolute imports unless an explicit relative import is clearer. Avoid wildcard imports unless you are deliberately republishing a public API whose exports cannot be enumerated statically; make re-exports explicit with `__all__`.

Use UTF-8 source files and normally omit encoding declarations in Python 3. Use non-ASCII identifiers or literals only when they improve correctness or clarity, or when repository policy requires domain-language text; prefer ASCII-compatible identifiers for widely shared APIs. Keep one quote style locally consistent, switch quote characters to reduce escaping, use triple double quotes for docstrings, and keep the trailing comma that makes a singleton tuple a tuple. Prefer trailing commas in multiline collections likely to grow.

Apply normal token spacing instead of manual alignment. Avoid trailing whitespace, dense compound statements, and folded one-line control flow. Follow standard spacing around delimiters, operators, annotations, and calls; for annotated defaults, keep spaces around `=`. For slices, space both sides of `:` equally when either side needs spacing.

## Naming And Public API Surface

Choose names that reveal intent, use the repository's domain vocabulary consistently, and make wider-scope names searchable and precise. Short names are fine in tiny local scopes when they stay obvious; add length only to remove ambiguity.

Use standard Python name forms unless the repository already exposes an older public style you must preserve: modules and packages in lowercase, usually `snake_case`; classes in `PascalCase`; functions, methods, variables, and attributes in `snake_case`; module-level constants in `UPPER_SNAKE_CASE`; `self` and `cls` for conventional receiver names; exception classes with an `Error` suffix when they actually represent errors. Use pattern names only when they match the implementation.

Use underscore markers only for their Python meanings. A single leading underscore marks a nonpublic name. A trailing underscore is for keyword conflicts such as `class_`. Use documented dunder names only, and double leading underscores only when subclass name clashes are a real concern. Do not encode types, containers, interfaces, or implementations into names when annotations, module qualification, or clearer vocabulary already show the distinction.

Decide publicness explicitly. If you are not sure an attribute belongs in the public API, keep it nonpublic. Expose simple public data as attributes instead of reflexive `get_` or `set_` methods. If an existing public attribute later needs validation or cheap derived behavior, preserve the attribute-shaped API with a side-effect-free property. Use a method instead when the operation is expensive or visibly effectful. Preserve established public names unless the user accepts an API migration.

## Constants And Encoded Meaning

Replace unexplained values with well-named constants at the level where the meaning lives. Keep an obvious literal inline when a name would add noise, but name shared, error-prone, or domain-significant values. Use `UPPER_SNAKE_CASE` for module-level constants and keep narrower constants near the code that gives them meaning. Do not introduce inheritance just to share constants. Use `Enum` or `StrEnum` when values represent a closed set of meanings and the named type improves call sites, validation, or branching; otherwise, plain constants are often clearer.

## Validation And Example Route

After editing, run the repository formatter and linting pipeline instead of hand-tuning spacing, wrapping, or quote changes against configured tooling. Recheck public imports and re-exports if you move or rename symbols. For a worked example that balances local consistency, naming clarity, public attribute design, and constant placement, see [style-and-naming](../examples/style-and-naming.md).
