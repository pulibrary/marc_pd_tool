# Testing Guide

This document provides comprehensive information about testing in the MARC Copyright Analysis Tool, including both traditional example-based tests and property-based tests.

## Overview

The project uses a multi-layered testing approach:

- **Example-based tests**: Traditional unit tests with specific inputs and expected outputs
- **Property-based tests**: Tests that verify mathematical properties hold for all inputs
- **Integration tests**: Tests that verify components work together correctly
- **Performance benchmarks**: Tests that measure and track performance metrics

## Running Tests

### Basic Test Commands

```bash
# Run all tests
pdm test

# Run with verbose output
pdm run pytest tests/ -v

# Run specific test file
pdm run pytest tests/test_processing/test_indexing.py -v

# Run tests matching a pattern
pdm run pytest tests/ -k "lccn" -v

# Run single test with output
pdm run pytest -xvs tests/test_utils/test_lccn.py::test_normalize_lccn

# Run only property-based tests
pdm run pytest tests/test_*/test_*_properties.py -v
```

### Useful Testing Options

```bash
# Stop on first failure
pdm run pytest -x

# Run last failed tests
pdm run pytest --lf

# Show local variables in tracebacks
pdm run pytest -l

# Run tests in parallel (requires pytest-xdist)
pdm run pytest -n auto

# Generate coverage report
pdm run pytest --cov=marc_pd_tool --cov-report=html
```

## Property-Based Testing

### What is Property-Based Testing?

Property-based testing verifies that certain properties or invariants hold true for all possible inputs, not just specific test cases. This approach helps discover edge cases that developers might not think to test.

### Property Test Files

The project includes 83 property-based tests across 4 files:

1. **`tests/test_utils/test_lccn_properties.py`** (18 tests)
1. **`tests/test_utils/test_text_properties.py`** (29 tests)
1. **`tests/test_processing/test_processing_properties.py`** (19 tests)
1. **`tests/test_processing/test_similarity_properties.py`** (17 tests)

### Common Properties Tested

#### Idempotency

Running a function twice should give the same result:

```python
@given(st.text())
def test_normalize_idempotent(self, text: str) -> None:
    once = normalize(text)
    twice = normalize(once)
    assert once == twice
```

#### Bounded Ranges

Output values should be within expected bounds:

```python
@given(st.text(), st.text())
def test_similarity_range(self, text1: str, text2: str) -> None:
    score = calculate_similarity(text1, text2)
    assert 0 <= score <= 100
```

#### Symmetry

Order shouldn't matter for certain operations:

```python
@given(st.text(), st.text())
def test_similarity_symmetric(self, a: str, b: str) -> None:
    assert similarity(a, b) == similarity(b, a)
```

#### Type Safety

Functions should handle any valid input without crashing:

```python
@given(st.text())
def test_handles_any_input(self, text: str) -> None:
    try:
        result = process_text(text)
        assert isinstance(result, str)
    except Exception as e:
        assert False, f"Unexpected exception: {e}"
```

### Discovered Edge Cases

Property testing has uncovered several important edge cases:

1. **LCCN Year Extraction Bug**

   - Input: "0:"
   - Issue: `extract_lccn_year` returns ":" which contains non-digits
   - Impact: Could cause downstream processing errors

1. **Unicode Whitespace Handling**

   - Input: "\\r", "\\n", "\\t"
   - Issue: `normalize_lccn` only removes regular spaces (U+0020)
   - Reason: Following [Library of Congress standard](https://www.loc.gov/marc/lccn-namespace.html)

1. **Case-Sensitive Stopword Filtering**

   - Input: Mixed case stopwords
   - Issue: `extract_significant_words` filters case-sensitively
   - Impact: Inconsistent stopword removal

1. **Abbreviation Expansion Casing**

   - Input: "Vol.", "VOL.", "vol."
   - Issue: `expand_abbreviations` always returns lowercase
   - Impact: May affect case-sensitive operations

1. **Short Text Filtering**

   - Input: Single characters like "A", "1", "?"
   - Issue: Filtered out as too short (< 2 chars)
   - Impact: Identical single-char titles return 0% similarity instead of 100%

### Writing Property Tests

#### Basic Structure

```python
from hypothesis import given, strategies as st, assume

class TestMyFunctionProperties:
    @given(st.text())
    def test_my_property(self, input_text: str) -> None:
        """Test description"""
        # Optionally filter inputs
        assume(len(input_text) > 0)
        
        # Run function
        result = my_function(input_text)
        
        # Check property
        assert some_property_holds(result)
```

#### Useful Hypothesis Strategies

```python
# Basic types
st.text()                          # Any string
st.text(min_size=1, max_size=100) # Bounded string
st.integers(min_value=1900, max_value=2025)  # Year range
st.booleans()                      # True/False
st.none()                          # None values

# Collections
st.lists(st.text())                # List of strings
st.sets(st.integers())             # Set of integers
st.dictionaries(st.text(), st.integers())  # Dict mapping

# Specific patterns
st.text(alphabet=string.ascii_letters)  # Letters only
st.text(alphabet=string.digits)         # Digits only
st.sampled_from(["eng", "fre", "ger"]) # Fixed choices

# Composite strategies
@st.composite
def marc_records(draw):
    return {
        'title': draw(st.text(min_size=1)),
        'author': draw(st.text()),
        'year': draw(st.integers(1900, 2025))
    }
```

#### Best Practices

1. **Start Simple**: Begin with basic properties before complex ones
1. **Use Assumptions**: Filter out irrelevant inputs with `assume()`
1. **Set Bounds**: Limit string lengths and collection sizes for performance
1. **Document Properties**: Clearly explain what property is being tested
1. **Handle Exceptions**: Decide if exceptions are acceptable or bugs

### Hypothesis Configuration

Configure test behavior with settings:

```python
from hypothesis import settings

@settings(max_examples=500, deadline=None)
@given(st.text())
def test_slow_function(self, text: str) -> None:
    """Test that may take time"""
    # ...
```

Common settings:

- `max_examples`: Number of test cases to generate (default: 100)
- `deadline`: Time limit per test case (None to disable)
- `verbosity`: Level of output detail
- `print_blob`: Print failing example for debugging

## Test Organization

### Directory Structure

```
tests/
├── test_utils/                    # Utility function tests
│   ├── test_lccn.py              # LCCN normalization tests
│   ├── test_lccn_properties.py   # LCCN property tests
│   ├── test_text.py              # Text processing tests
│   └── test_text_properties.py   # Text property tests
├── test_processing/               # Processing logic tests
│   ├── test_indexing.py          # Indexing tests
│   ├── test_matching.py          # Matching algorithm tests
│   ├── test_processing_properties.py   # Processing property tests
│   └── test_similarity_properties.py  # Similarity property tests
├── test_loaders/                  # Data loader tests
│   ├── test_marc_loader.py       # MARC XML loading
│   └── test_year_filtering.py    # Year filter tests
└── test_cli/                      # CLI and integration tests
    ├── test_main.py              # Main CLI tests
    └── test_logging.py           # Logging configuration tests
```

### Test Naming Conventions

- **Test files**: `test_<module_name>.py`
- **Property test files**: `test_<module>_properties.py`
- **Test classes**: `Test<ClassName>`
- **Test methods**: `test_<what_is_being_tested>`
- **Property tests**: `test_<property_name>_<constraint>`

Examples:

- `test_normalize_lccn_removes_spaces`
- `test_similarity_score_bounded_between_0_and_100`
- `test_normalization_idempotent`

## Debugging Failed Tests

### Property Test Failures

When a property test fails, Hypothesis provides a minimal failing example:

```
Falsifying example: test_extract_year_numeric_only(
    self=<TestLCCNComponentExtraction object at 0x...>,
    lccn='0:',
)
```

To debug:

1. Run the test with the specific input
1. Add print statements or use debugger
1. Fix the issue
1. Re-run to ensure no regression

### Reproducing Failures

Hypothesis saves failing examples for regression testing:

```python
# This will automatically run any previously failing examples
pdm run pytest tests/test_utils/test_lccn_properties.py -v
```

### Common Issues

1. **Unicode Handling**: Test with various Unicode characters
1. **Empty Strings**: Always test empty string behavior
1. **Boundary Values**: Test minimum and maximum values
1. **Type Mismatches**: Ensure consistent types throughout
1. **Performance**: Some property tests may be slow with large inputs

## Performance Testing

While not comprehensive, some tests include basic performance checks:

```python
def test_indexing_performance(self):
    """Indexing should handle large datasets efficiently"""
    publications = [create_test_publication() for _ in range(10000)]
    
    start_time = time.time()
    index = indexer.build_index(publications)
    elapsed = time.time() - start_time
    
    assert elapsed < 5.0  # Should complete in under 5 seconds
```

## Continuous Integration

Tests are automatically run on:

- Every commit via Git hooks
- Pull requests via GitHub Actions
- Before releases

Ensure all tests pass before submitting pull requests.

## Future Testing Improvements

1. **Mutation Testing**: Verify test quality by introducing bugs
1. **Fuzzing**: Random input generation for security testing
1. **Load Testing**: Verify system handles production loads
1. **Integration Testing**: End-to-end workflow tests
1. **Regression Testing**: Automated checks for known issues

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Property-Based Testing Guide](https://hypothesis.works/articles/what-is-property-based-testing/)
