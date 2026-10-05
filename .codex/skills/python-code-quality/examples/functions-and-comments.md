## Scenario

Task: make `AverageDirectionIndex` easier to read before fixing a zero-division edge case, without changing current numeric output.

## Repository Evidence

Technical indicator calculators live in `investiment_analyzer/technical_analysis/domain/technical_indicators/calculators/`. The shared calculator tests are colocated in `technical_indicators_calculation_test.py` and use `unittest`, small spreadsheet fixtures, and `pd.testing.assert_frame_equal`. Numeric behavior is sensitive, so the cleanup is characterized before the bug fix.

## Poor Approach

Do not rewrite the ADX formula, add the zero-denominator fix, and "clean up" comments in one patch:

```python
# calculate positive
p = dmi["positive direction movement"]
# calculate negative
n = dmi["negative direction movement"]

def value(data, smooth: bool, positive: bool):
    return smooth_mean(data, 14) if smooth else data

# result = old_result
dx = 100 * (p - n).abs() / (p + n).abs()
```

## Why It Fails

This patch mixes a behavior change with extraction before characterization, so a changed fixture cannot show whether the formula cleanup or zero-denominator handling caused it. The comments restate assignments, the selector-argument helper hides branching behind booleans, and helper reach-through would cross the calculator collaboration boundary instead of clarifying the formula.

## Preferred Approach

First preserve behavior behind the existing fixture test, then extract concepts the formula already contains. Keep only comments that names cannot express, remove commented-out code and stale bookkeeping, and leave the edge-case fix for a second patch with its own failing test.

## Decision Checkpoints

- Characterization first: run the focused calculator test before moving formula code.
- Names before comments: use `directional_movement`, `movement_spread`, `total_movement`, and `directional_index` instead of comments that narrate assignments.
- Function shape: extract real steps, not one-line helpers whose only purpose is lowering line count.
- Arguments: avoid a helper such as `movement(data, smooth=True, positive=True)` because the flags select behavior; use explicit functions or direct local names.
- Returns and side effects: keep helpers value-returning only; no cache mutation or collaborator calls hidden inside formula helpers.
- Order: keep the public `calculate_from_prices` method above private helpers so the module reads from orchestration to detail.
- Collaboration boundary: call `DirectionalMovementIndexCalculator` once in the public method, then pass the resulting frame to formula helpers instead of making helpers reach through `self._directional_movement_index_calculator`.
- Documentation: add a concise class docstring only if the public calculator contract needs it; private formula helpers do not get boilerplate docstrings.

## Resulting Change

```diff
 class AverageDirectionIndex(AbstractTechnicalIndicator):
+    """Calculate ADX from positive and negative directional movement."""
+
     def calculate_from_prices(self, prices_ohlcv: DataFrame[OHLCVSchema]) -> pd.DataFrame:
-        directional_movement = self._directional_movement_index_calculator.calculate_from_prices(prices_ohlcv)
-        positive_movement = directional_movement["positive direction movement"]
-        negative_movement = directional_movement["negative direction movement"]
-        # calculate dx
-        dx = 100 * (positive_movement - negative_movement).abs() / (positive_movement + negative_movement).abs()
-        # smooth dx
-        result = smooth_mean(dx, self._smoothing_periods)
+        directional_movement = (
+            self._directional_movement_index_calculator.calculate_from_prices(
+                prices_ohlcv
+            )
+        )
+        directional_index = self._calculate_directional_index(directional_movement)
+        result = smooth_mean(directional_index, self._smoothing_periods)
         return result.to_frame("average directional index")
+
+    def _calculate_directional_index(self, directional_movement: pd.DataFrame) -> pd.Series:
+        positive_movement = directional_movement["positive direction movement"]
+        negative_movement = directional_movement["negative direction movement"]
+        movement_spread = (positive_movement - negative_movement).abs()
+        total_movement = (positive_movement + negative_movement).abs()
+
+        # Keep pandas division semantics here; zero-denominator handling is a
+        # separate behavior change covered by the next regression test.
+        return 100 * movement_spread / total_movement
```

## Verification

- Focused characterization to run before and after extraction: `poetry run python -m unittest discover -v -s "./investiment_analyzer/technical_analysis/domain/technical_indicators/calculators" -p "technical_indicators_calculation_test.py"`
- Broad regression to run after the behavior-preserving extraction: `poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"`
- Formatter check to run for the touched calculator: `poetry run ruff format --check investiment_analyzer/technical_analysis/domain/technical_indicators/calculators/average_directional_index.py`
- Ruff check to run for the touched calculator: `poetry run ruff check investiment_analyzer/technical_analysis/domain/technical_indicators/calculators/average_directional_index.py`

## Completion Report

Changed only `average_directional_index.py`. Validation is not marked passed here; report each command above only after actual execution with output evidence, and classify any unrun `make lint`, Pyright, or codespell coverage as skipped, not applicable, or unavailable with a reason. The refactor is intended to preserve fixture output, remove narrative comments and commented-out history, keep one constraint comment, and avoid expanding collaborator chains.

## Exception or Counterexample

A natural dyad such as `between(start, end)` or a direct data-frame column lookup can stay as-is. Not every two-argument helper or field access needs a parameter object or new method.
