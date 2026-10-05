# Readable unittest coverage guides refactoring and boundary fixes

## Scenario
Task: add regression coverage for a `FocusReportDataMapper` boundary bug, then refactor the mapper internals without changing the now-protected behavior.

## Repository Evidence
This repository colocates tests beside implementation with `*_test.py` names, so the focused test belongs in `investiment_analyzer/economy/data_source/focus_report_data_mapper_test.py`, not in a new top-level test tree. The full-suite command remains:

```bash
poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"
```

The boundary is a BCB JSON payload. A one-field drift can be represented with a tiny dict; a real PDF fixture would obscure the behavior being tested.

## Poor Approach
Do not switch to `pytest`, add a large captured BCB response, and write one broad test that asserts dates, PDF extraction, cache state, and exception behavior together. Also do not mock `FocusReportDataMapper.get_reference_dates()` itself; that removes the boundary being characterized.

## Why It Fails
That approach fails because it ignores repository tooling, makes the failure hard to localize, and lets a refactor proceed before the reported behavior has a small failing test.

## Preferred Approach
First add the smallest failing `unittest` regression for the reported malformed payload. Then add the accepted payload case with explicit setup. After those tests pin behavior, extract a parser helper from `_get_reference_dates` and rerun the focused test module before broader validation.

Use parameterization only if several date payloads differ by values alone. Here the accepted case and malformed case express different concepts, so separate tests read better.

## Decision Checkpoints
- The task is using a TDD-style fix, so the next failing test comes before implementation; that does not make TDD mandatory for unrelated work.
- The refactor is behavior-preserving only after the bug fix is covered.
- The malformed payload is a boundary and failure-path case, so correctness beats preserving a cryptic `KeyError`.
- Coverage output may justify checking this branch, but no percentage target is invented.
- If extracting the parser requires patching network calls in every assertion, that is design feedback: isolate payload parsing instead of expanding mocks.

## Resulting Change
Focused test and implementation shape:

```diff
 class TestFocusReportDataMapper(TestCase):
+    def test_get_reference_dates_maps_bcb_payload_dates(self):
+        self.http_get_mock().json.return_value = {
+            "conteudo": [{"DataReferencia": "2024-01-05"}]
+        }
+
+        self.assertEqual(
+            self.focus_mapper.get_reference_dates(),
+            (date(2024, 1, 5),),
+        )
+
+    def test_get_reference_dates_rejects_missing_conteudo(self):
+        self.http_get_mock().json.return_value = {"items": []}
+
+        with self.assertRaisesRegex(ValueError, "conteudo"):
+            self.focus_mapper.get_reference_dates()
+
 class FocusReportDataMapper(...):
     def _get_reference_dates(self) -> tuple[date, ...]:
         response = requests.get(_GET_REFERENCE_DATES_URL)
-        return tuple(
-            datetime.fromisoformat(focus_data["DataReferencia"]).date()
-            for focus_data in response.json()["conteudo"]
-        )
+        return self._reference_dates_from_bcb_payload(response.json())
+
+    def _reference_dates_from_bcb_payload(self, payload: dict) -> tuple[date, ...]:
+        if "conteudo" not in payload:
+            raise ValueError("BCB focus payload is missing conteudo")
+        return tuple(
+            datetime.fromisoformat(item["DataReferencia"]).date()
+            for item in payload["conteudo"]
+        )
```

Multiple assertions in the accepted case are not split further because they describe one concept: one payload maps to one tuple of dates.

## Verification
Focused first:

```bash
poetry run python -m unittest investiment_analyzer.economy.data_source.focus_report_data_mapper_test -v
```

Broad after the refactor:

```bash
poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"
poetry run ruff check .
poetry run ruff format --check .
```

Use `poetry run coverage run -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"` only when coverage or repeated failures are being used diagnostically.

## Completion Report
Changed surfaces: one mapper test module and one private parser helper. Behavior changed only for malformed BCB payloads, which now fail clearly; accepted payload behavior is preserved through characterization tests.

Report statuses honestly, for example: "Focused mapper tests passed; full discovery failed in `portfolio_test.py`; coverage diagnostics were not applicable because no coverage gap was being investigated; `make lint` was unavailable because dependencies were not installed; live-service checks were skipped because database services were unavailable."

## Exception Or Counterexample
A broad smoke test using the existing PDF fixture is acceptable when the task is validating PDF extraction end to end. It is the wrong tool for a one-field JSON drift because it hides the boundary and makes a narrow mapper refactor riskier.
