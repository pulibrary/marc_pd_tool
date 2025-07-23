# Example Scripts

This directory contains example scripts demonstrating how to use the marc_pd_tool library API.

## Analysis Scripts

The `analysis/` subdirectory contains scripts for specialized analysis tasks:

- **ground_truth_scores.py** - Analyze similarity scores for LCCN-verified ground truth pairs
- **ground_truth_extractor.py** - Module for extracting ground truth pairs from datasets
- **score_analyzer.py** - Module for analyzing score distributions

### Running Analysis Scripts

```bash
# Analyze ground truth scores
python scripts/analysis/ground_truth_scores.py \
    --marcxml path/to/marc/file.marcxml \
    --copyright-dir path/to/copyright/xml/ \
    --renewal-dir path/to/renewal/tsv/ \
    --output-report ground_truth_analysis.txt \
    --output-scores ground_truth_scores.csv
```

These scripts demonstrate advanced usage of the marc_pd_tool API for research and analysis purposes.
