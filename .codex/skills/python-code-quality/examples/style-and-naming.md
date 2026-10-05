# Scenario
Task: clean up a mapper helper and expose its result on a small domain-facing object without changing callers.

# Repository Evidence
This repo is a Poetry Python package under `investiment_analyzer`. `pyproject.toml` sets Ruff line length to 88, tests are colocated as `*_test.py`, and full tests run through `poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"`. The package spelling and existing public imports are compatibility constraints, even when they look like style cleanup opportunities.

# Poor Approach
Two tempting cleanup suggestions are to rename `investiment_analyzer` imports to `investment_analyzer` and wrap every touched line at 79 columns. In the same mapper patch, avoid adding `str_` and `dict_` prefixes, turning a simple result field into `get_net_yield()` / `set_net_yield()`, inventing `__raw_row__` for parser state, or extracting a global `TAX = 0.15` far from the one parser that uses it.

## Why It Fails
That fails because it breaks public import paths, fights configured formatting, encodes types already visible from annotations, invents unsupported dunder names, and imports Java-style accessors into a Python API. The constant is named but moved to the wrong abstraction level.

# Preferred Approach
Keep exported paths stable. Rename only local helpers and variables to financial vocabulary, keep ordinary public data as attributes, use a cheap property only to preserve an existing attribute name, and let Ruff choose 88-column wrapping. Put constants at the narrowest useful scope.

# Decision Checkpoints
- Inspect `pyproject.toml` and nearby mapper tests before applying generic defaults.
- Preserve public imports unless the user explicitly accepts an API migration.
- Prefer `gross_yield`, `tax_rate`, and `net_yield` over prefixes like `flt_value`.
- Use a leading underscore only for internal helpers, not to decorate public results.

# Exception or Counterexample
A 79-column wrap is not "more compliant" here; the repository formatter is the local authority. Likewise, preserve the existing package spelling unless the user explicitly accepts an API migration.

# Resulting Change
```diff
 class TreasuryRate:
-    def get_net_yield(self) -> Decimal:
-        return self._net_yield
+    net_yield: Decimal
 
-def __make_dict__(dict_row: dict[str, str]) -> TreasuryRate:
-    str_rate = dict_row["yield"]
-    return TreasuryRate(Decimal(str_rate) * (1 - 0.15))
+WITHHOLDING_TAX_RATE = Decimal("0.15")
+
+
+def _map_treasury_rate(row: dict[str, str]) -> TreasuryRate:
+    gross_yield = Decimal(row["yield"])
+    net_yield = gross_yield * (Decimal("1") - WITHHOLDING_TAX_RATE)
+    return TreasuryRate(net_yield=net_yield)
```

If callers already read `rate.net_yield`, keep it as a plain attribute. If `net_yield` later needs validation while preserving `rate.net_yield`, use a side-effect-free property; use a method only for expensive work or visible effects.

# Verification
- Focused: `poetry run python -m unittest investiment_analyzer.fixed_income.data_source.treasury_rate_data_mapper_test`
- Static wrapper: `make lint` for repository Ruff format-check, Ruff check, Pyright, and codespell coverage.
- Broad: `poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"`

# Completion Report
Changed only the mapper helper and the small result object surface. Behavior and public package paths were preserved. In this example, commands are the checks to run; do not report them as passed unless they actually complete.
