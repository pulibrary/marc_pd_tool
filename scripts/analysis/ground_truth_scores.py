#!/usr/bin/env python3
"""
LCCN Ground Truth Analysis Tool

Script demonstrating how to extract ground truth pairs and analyze similarity scores.

This script shows how to:
1. Extract LCCN-verified ground truth pairs from datasets
2. Analyze similarity score distributions for those pairs
3. Generate recommended thresholds based on empirical data
4. Export detailed score data for further analysis

Usage:
    python scripts/analyze_ground_truth_scores.py \\
        --marcxml path/to/marc/file.marcxml \\
        --copyright-dir path/to/copyright/xml/ \\
        --renewal-dir path/to/renewal/tsv/ \\
        --output-report ground_truth_analysis.txt \\
        --output-scores ground_truth_scores.csv
"""

# Standard library imports
from argparse import ArgumentParser
from logging import INFO
from logging import basicConfig
from sys import exit

# Third party imports
from ground_truth_extractor import GroundTruthExtractor
from score_analyzer import ScoreAnalyzer

# Local imports
from marc_pd_tool.loaders import CopyrightDataLoader
from marc_pd_tool.loaders import MarcLoader
from marc_pd_tool.loaders import RenewalDataLoader


def main():
    """Main entry point for ground truth analysis"""
    parser = ArgumentParser(
        description="Analyze similarity scores for LCCN-verified ground truth pairs"
    )

    # Data input arguments
    parser.add_argument("--marcxml", required=True, help="Path to MARC XML file")
    parser.add_argument(
        "--copyright-dir",
        default="nypl-reg/xml/",
        help="Path to copyright registration XML directory",
    )
    parser.add_argument(
        "--renewal-dir", default="nypl-ren/data/", help="Path to renewal TSV data directory"
    )

    # Output arguments
    parser.add_argument(
        "--output-report",
        default="ground_truth_analysis.txt",
        help="Path for analysis report output",
    )
    parser.add_argument(
        "--output-scores",
        default="ground_truth_scores.csv",
        help="Path for detailed score CSV export",
    )

    # Analysis options
    parser.add_argument(
        "--max-records", type=int, help="Maximum MARC records to process (for testing)"
    )
    parser.add_argument("--min-year", type=int, help="Minimum publication year filter")
    parser.add_argument("--max-year", type=int, help="Maximum publication year filter")

    # Logging
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    log_level = INFO
    if args.debug:
        # Standard library imports
        from logging import DEBUG

        log_level = DEBUG

    basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    try:
        # Load MARC data
        print("Loading MARC records...")
        marc_loader = MarcLoader(
            marc_path=args.marcxml, min_year=args.min_year, max_year=args.max_year
        )
        marc_batches = marc_loader.extract_all_batches()

        # Limit records if specified
        if args.max_records:
            total_records = sum(len(batch) for batch in marc_batches)
            if total_records > args.max_records:
                print(f"Limiting to {args.max_records} records (found {total_records})")
                limited_batches = []
                record_count = 0
                for batch in marc_batches:
                    if record_count >= args.max_records:
                        break
                    remaining = args.max_records - record_count
                    if len(batch) <= remaining:
                        limited_batches.append(batch)
                        record_count += len(batch)
                    else:
                        limited_batches.append(batch[:remaining])
                        break
                marc_batches = limited_batches

        # Load copyright data
        copyright_pubs = []
        if args.copyright_dir:
            print("Loading copyright registration data...")
            copyright_loader = CopyrightDataLoader(args.copyright_dir)
            copyright_pubs = copyright_loader.load_all_copyright_data()

        # Load renewal data
        renewal_pubs = []
        if args.renewal_dir:
            print("Loading renewal data...")
            renewal_loader = RenewalDataLoader(args.renewal_dir)
            renewal_pubs = renewal_loader.load_all_renewal_data()

        # Extract ground truth pairs
        print("Extracting LCCN-verified ground truth pairs...")
        extractor = GroundTruthExtractor()
        ground_truth_pairs, stats = extractor.extract_ground_truth_pairs(
            marc_batches, copyright_pubs, renewal_pubs
        )

        if not ground_truth_pairs:
            print(
                "No ground truth pairs found! Check that your datasets contain overlapping LCCN values."
            )
            exit(1)

        # Apply filters if specified
        if args.min_year or args.max_year:
            print(f"Filtering by year range: {args.min_year or 'any'} - {args.max_year or 'any'}")
            ground_truth_pairs = extractor.filter_by_year_range(
                ground_truth_pairs, args.min_year, args.max_year
            )

        if not ground_truth_pairs:
            print("No ground truth pairs remain after filtering!")
            exit(1)

        # Analyze similarity scores
        print("Analyzing similarity score distributions...")
        analyzer = ScoreAnalyzer()
        analysis = analyzer.analyze_ground_truth_scores(ground_truth_pairs)

        # Generate analysis report
        print(f"Generating analysis report: {args.output_report}")
        report = analyzer.generate_analysis_report(analysis)

        with open(args.output_report, "w") as f:
            f.write(report)

        # Print key findings to console
        print("\\n" + "=" * 50)
        print("GROUND TRUTH ANALYSIS SUMMARY")
        print("=" * 50)
        print(f"Total ground truth pairs: {analysis.total_pairs:,}")
        print(f"Registration pairs: {analysis.registration_pairs:,}")
        print(f"Renewal pairs: {analysis.renewal_pairs:,}")
        print()

        # Show recommended thresholds
        conservative = analysis.get_recommended_thresholds(5)
        moderate = analysis.get_recommended_thresholds(10)

        print("RECOMMENDED THRESHOLDS:")
        print("Conservative (5th percentile):")
        for field, threshold in conservative.items():
            print(f"  {field}: {threshold:.1f}")
        print("Moderate (10th percentile):")
        for field, threshold in moderate.items():
            print(f"  {field}: {threshold:.1f}")

        # Export detailed scores
        print(f"Exporting detailed score data: {args.output_scores}")
        analyzer.export_score_data(analysis, args.output_scores)

        print(f"\\nComplete analysis report saved to: {args.output_report}")
        print(f"Detailed score data saved to: {args.output_scores}")

    except Exception as e:
        print(f"Error during analysis: {e}")
        if args.debug:
            # Standard library imports
            import traceback

            traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
