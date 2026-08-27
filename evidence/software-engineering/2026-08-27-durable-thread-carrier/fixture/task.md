\
# Fixture implementation task

In the fixture repository, add `dedupe_labels(values: list[str]) -> list[str]`
to `src/labels.py`.

Required behavior:

- normalize every input with the existing `normalize_label`
- discard labels whose normalized value is empty
- compare normalized labels with `casefold()`
- preserve the first occurrence order
- return the preserved normalized spellings
- add focused tests in `tests/test_labels.py`
- run `python3 -m unittest discover -s tests -v`
- do not edit files outside `src/labels.py` and `tests/test_labels.py`
- do not commit
