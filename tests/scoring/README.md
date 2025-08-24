# Scoring Algorithm Testing

This directory contains tests that validate the scoring algorithm against a baseline of known matches and mismatches. These tests are **not** run as part of the regular test suite.

## Purpose

The scoring tests serve to:

1. Detect unintended changes in scoring behavior
1. Validate improvements to the algorithm
1. Provide statistics on score distributions
1. Ensure consistency across algorithm updates

## Running the Tests

### Run all scoring tests

```bash
pdm run test-regression
```

### Run with detailed output

```bash
pdm run pytest tests/scoring/test_scoring_regression.py -s -v
```

### Run specific test

```bash
# Test baseline matching
pdm run pytest tests/scoring/test_scoring_regression.py::TestScoringRegression::test_scoring_matches_baseline -s

# Test score distribution
pdm run pytest tests/scoring/test_scoring_regression.py::TestScoringRegression::test_score_distribution -s

# Test field statistics
pdm run pytest tests/scoring/test_scoring_regression.py::TestScoringRegression::test_field_score_statistics -s

# Test score separation (matches vs mismatches)
pdm run pytest tests/scoring/test_scoring_regression.py::TestScoringRegression::test_score_separation -s
```

## Updating Baselines

When making improvements to the scoring algorithm:

1. **Run the scoring test first** to see what changes:

   ```bash
   pdm run test-regression
   ```

1. **Review the changes** - ensure they are improvements, not regressions

1. **Update the baseline scores**:

   ```bash
   pdm run python scripts/generate_baseline_scores.py
   ```

1. **Commit both the algorithm changes and the new baselines** together

## Test Data

- **Match Data**: `tests/fixtures/known_matches_with_baselines.csv` - Known correct matches with baseline scores
  - Size: ~19,600 true positive matches (manually curated)
- **Mismatch Data**: `tests/fixtures/known_mismatches_with_baselines.csv` - Known false positives removed during curation
  - Size: ~377 false positives (LCCN errors)
- **Note**: Files are maintained in-place - generate_baseline_scores.py updates scores after algorithm changes

## What the Tests Check

### 1. Baseline Matching (`test_scoring_matches_baseline`)

- Compares current scores against baseline
- Reports any deviations (improvements or regressions)
- Fails if scores regress

### 2. Score Distribution (`test_score_distribution`)

- Shows how many matches exceed various thresholds (50, 60, 70, 80, 90)
- Helps understand impact of threshold changes

### 3. Field Statistics (`test_field_score_statistics`)

- Provides detailed statistics for each field (title, author, publisher)
- Shows mean, median, quartiles, and distribution
- Helps identify scoring imbalances

### 4. Score Separation (`test_score_separation`)

- Compares scores of true matches vs false positives
- Identifies overlap zones where both exist
- Tests various thresholds to find optimal separation
- Calculates precision, recall, and F1 scores for each threshold

## Interpreting Results

### Baseline Test Output

```
============================================================
SCORING REGRESSION TEST RESULTS
============================================================
Total records tested: 19971

✅ All scores match baseline - no regressions detected!
```

### Field Statistics Output

Shows distribution for each field:

- **Title scores**: Usually high (mean ~90) as titles are well-normalized
- **Author scores**: More variable (mean ~50) due to name variations
- **Publisher scores**: Generally high (mean ~85) with good normalization
- **Combined scores**: Target mean of 75-85 for known matches

## Best Practices

1. **Always run scoring tests** before merging scoring algorithm changes
1. **Document why baselines changed** in commit messages
1. **Review score distributions** to ensure changes don't adversely affect match quality
1. **Keep test data updated** - add new known matches periodically
1. **Don't ignore failing tests** - investigate and understand all changes
