#!/usr/bin/env python3
"""Benchmark script to measure LCCN indexing performance improvements

This script compares the performance of the matching engine with and without
LCCN indexing to quantify the improvement.
"""

# Standard library imports
from argparse import ArgumentParser
from pathlib import Path
from time import time

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.loaders.copyright_loader import CopyrightDataLoader
from marc_pd_tool.loaders.marc_loader import MarcLoader
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.text_processing import GenericTitleDetector


def create_test_publication_with_lccn(lccn: str, title: str = "Test Title") -> Publication:
    """Create a test publication with an LCCN"""
    pub = Publication(
        title=title,
        author="Test Author",
        pub_date="1950",
        publisher="Test Publisher",
        source_id=f"test_{lccn}",
    )
    pub.year = 1950
    pub.lccn = lccn
    pub.normalized_lccn = lccn  # Assume already normalized
    return pub


def benchmark_lccn_lookups(
    indexer: DataIndexer, test_records: list[Publication], iterations: int = 100
) -> dict[str, float]:
    """Benchmark LCCN lookup performance"""
    print(f"\nBenchmarking {len(test_records)} records with {iterations} iterations each...")

    # Test with LCCN lookups
    start_time = time()
    lccn_matches = 0
    for _ in range(iterations):
        for record in test_records:
            candidates = indexer.find_candidates(record, year_tolerance=1)
            if candidates:
                lccn_matches += 1
    lccn_time = time() - start_time

    # Test without LCCN (simulate by clearing LCCN)
    start_time = time()
    no_lccn_matches = 0
    for _ in range(iterations):
        for record in test_records:
            # Temporarily clear LCCN to force other index lookups
            orig_lccn = record.normalized_lccn
            record.normalized_lccn = None
            candidates = indexer.find_candidates(record, year_tolerance=1)
            if candidates:
                no_lccn_matches += 1
            record.normalized_lccn = orig_lccn
    no_lccn_time = time() - start_time

    return {
        "lccn_time": lccn_time,
        "no_lccn_time": no_lccn_time,
        "speedup": no_lccn_time / lccn_time if lccn_time > 0 else 0,
        "lccn_matches": lccn_matches,
        "no_lccn_matches": no_lccn_matches,
    }


def main() -> None:
    """Main benchmark function"""
    parser = ArgumentParser(description="Benchmark LCCN indexing performance")
    parser.add_argument(
        "--marc-file", type=Path, help="MARC XML file to use for testing (optional)"
    )
    parser.add_argument(
        "--copyright-dir", type=Path, default=Path("nypl-reg"), help="Copyright data directory"
    )
    parser.add_argument(
        "--renewal-dir", type=Path, default=Path("nypl-ren"), help="Renewal data directory"
    )
    parser.add_argument(
        "--max-records", type=int, default=1000, help="Maximum number of records to test"
    )
    parser.add_argument(
        "--iterations", type=int, default=10, help="Number of iterations for benchmarking"
    )
    args = parser.parse_args()

    print("LCCN Indexing Performance Benchmark")
    print("=" * 50)

    # Load configuration
    config = ConfigLoader()

    # Load some real data if available
    if args.marc_file and args.marc_file.exists():
        print(f"\nLoading MARC records from {args.marc_file}...")
        marc_loader = MarcLoader(str(args.marc_file))
        marc_records = marc_loader.load_publications()[: args.max_records]
        print(f"Loaded {len(marc_records)} MARC records")

        # Filter to records with LCCNs
        lccn_records = [r for r in marc_records if r.normalized_lccn]
        print(f"Found {len(lccn_records)} records with LCCNs")
    else:
        print("\nNo MARC file provided, using synthetic test data...")
        # Create synthetic test records
        lccn_records = []
        for i in range(100):
            pub = create_test_publication_with_lccn(f"n78{str(i).zfill(6)}", f"Test Title {i}")
            lccn_records.append(pub)

    if not lccn_records:
        print("No records with LCCNs found for testing!")
        return

    # Load copyright data
    print(f"\nLoading copyright data from {args.copyright_dir}...")
    copyright_loader = CopyrightDataLoader(config)
    copyright_pubs = copyright_loader.load_copyright_data(str(args.copyright_dir))
    print(f"Loaded {len(copyright_pubs)} copyright records")

    # Build index
    print("\nBuilding word-based index...")
    start_time = time()
    indexer = DataIndexer(config)
    for pub in copyright_pubs:
        indexer.add_publication(pub)
    index_time = time() - start_time
    print(f"Index built in {index_time:.2f} seconds")

    # Get index statistics
    stats = indexer.get_stats()
    print("\nIndex Statistics:")
    print(f"  Total publications: {stats['total_publications']:,}")
    print(f"  LCCN keys: {stats['lccn_keys']:,}")
    print(f"  Title keys: {stats['title_keys']:,}")
    print(f"  Author keys: {stats['author_keys']:,}")
    print(f"  Avg LCCN keys per pub: {stats['avg_lccn_keys_per_pub']:.2f}")

    # Run benchmarks
    results = benchmark_lccn_lookups(indexer, lccn_records[:100], args.iterations)

    print("\nBenchmark Results:")
    print(f"  With LCCN index: {results['lccn_time']:.3f} seconds")
    print(f"  Without LCCN index: {results['no_lccn_time']:.3f} seconds")
    print(f"  Speedup: {results['speedup']:.1f}x")
    print(f"  LCCN matches found: {results['lccn_matches']}")
    print(f"  Non-LCCN matches found: {results['no_lccn_matches']}")

    # Test real matching performance
    if args.marc_file:
        print("\nTesting real matching performance...")
        engine = DataMatcher(config=config)
        detector = GenericTitleDetector(
            copyright_publications=copyright_pubs[:10000],  # Use subset for speed
            renewal_publications=[],
        )

        # Time matching with LCCNs
        start_time = time()
        lccn_match_count = 0
        for record in lccn_records[:50]:
            candidates = indexer.get_candidates_list(record)
            if candidates:
                match = engine.find_best_match(
                    record,
                    candidates,
                    title_threshold=40,
                    author_threshold=30,
                    year_tolerance=1,
                    publisher_threshold=30,
                    early_exit_title=95,
                    early_exit_author=90,
                    generic_detector=detector,
                )
                if match and match.get("is_lccn_match"):
                    lccn_match_count += 1
        matching_time = time() - start_time

        print(f"\nMatched {lccn_match_count} records via LCCN in {matching_time:.3f} seconds")
        print(f"Average time per record: {matching_time/50*1000:.1f} ms")

    print("\nConclusion:")
    if results["speedup"] > 1.5:
        print(
            f"✅ LCCN indexing provides significant performance improvement ({results['speedup']:.1f}x faster)"
        )
    else:
        print(f"⚠️  LCCN indexing provides modest improvement ({results['speedup']:.1f}x faster)")
    print("\nNote: Real-world improvement depends on the percentage of records with LCCNs")


if __name__ == "__main__":
    main()
