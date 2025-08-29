# tests/scoring/test_threshold_calibration.py

"""Test different threshold and LCCN boost combinations for optimal performance."""

# Standard library imports
from csv import DictReader
from pathlib import Path

# Third party imports
from pytest import mark

# Local imports
from marc_pd_tool.application.processing.matching._core_matcher import CoreMatcher
from marc_pd_tool.core.domain.publication import Publication


class TestThresholdCalibration:
    """Test various threshold and LCCN boost combinations"""

    def load_test_data(self):
        """Load test datasets"""
        matches = []
        path = Path("tests/fixtures/known_matches_with_baselines.csv")
        with open(path, "r") as f:
            reader = DictReader(f)
            matches = list(reader)

        mismatches = []
        path = Path("tests/fixtures/known_mismatches_with_baselines.csv")
        if path.exists():
            with open(path, "r") as f:
                reader = DictReader(f)
                mismatches = list(reader)

        return matches, mismatches

    def test_threshold_scenarios(self):
        """Test various threshold and LCCN boost combinations"""
        matches, mismatches = self.load_test_data()

        # Test a few key scenarios
        scenarios = [
            {"lccn_boost": 20, "threshold": 25, "name": "Current production settings"},
            {"lccn_boost": 35, "threshold": 40, "name": "Original settings"},
            {"lccn_boost": 15, "threshold": 30, "name": "Lower boost, medium threshold"},
        ]

        for scenario in scenarios:
            results = self._test_scenario(
                matches, mismatches, scenario["lccn_boost"], scenario["threshold"], scenario["name"]
            )

            # Print results for analysis
            tp_rate = (results["tp_with_lccn"] + results["tp_without_lccn"]) / results[
                "total_matches"
            ]
            fp_rate = (
                results["fp"] / results["total_mismatches"]
                if results["total_mismatches"] > 0
                else 0
            )

            # Silent assertions - we want high TP rate and low FP rate
            assert tp_rate > 0.8, f"True positive rate too low for {scenario['name']}"
            assert fp_rate < 0.2, f"False positive rate too high for {scenario['name']}"

    def _test_scenario(self, matches, mismatches, lccn_boost, threshold, name, with_lccn_rate=0.01):
        """Test a specific configuration scenario

        Args:
            matches: Known good matches
            mismatches: Known false positives
            lccn_boost: LCCN boost value to test
            threshold: Base threshold to test
            name: Name of the scenario for reporting
            with_lccn_rate: Proportion of records that have LCCNs (default 1%)
        """
        # Configure matcher - use the real config system with overrides
        # Local imports
        from marc_pd_tool.infrastructure.config import get_config

        config = get_config()
        # Override the LCCN boost for testing
        if hasattr(config, "matching") and hasattr(config.matching, "lccn_score_boost"):
            config.matching.lccn_score_boost
            config.matching.lccn_score_boost = lccn_boost
        matcher = CoreMatcher(config)

        true_positives_with_lccn = 0
        true_positives_without_lccn = 0
        false_positives = 0

        # Test matches
        for row in matches:
            # Create publications
            marc_pub = Publication(
                title=row["marc_title_original"],
                author=row["marc_author_original"],
                main_author=row["marc_main_author_original"],
                publisher=row["marc_publisher_original"],
                year=int(row["marc_year"]) if row["marc_year"] else None,
                lccn=row.get("marc_lccn", ""),
                source_id=row["marc_id"],
            )

            # Simulate with_lccn_rate: most records won't have LCCN in real world
            # Standard library imports
            import random

            random.seed(hash(row["marc_id"]))  # Deterministic per record
            has_lccn_in_real_world = random.random() < with_lccn_rate

            if has_lccn_in_real_world and marc_pub.lccn:
                marc_pub.normalized_lccn = row.get("marc_lccn_normalized", "")
                copyright_lccn = row.get("marc_lccn", "")
            else:
                # Simulate missing LCCN (vast majority)
                marc_pub.lccn = ""
                marc_pub.normalized_lccn = ""
                copyright_lccn = ""

            copyright_pub = Publication(
                title=row["match_title"],
                author=row["match_author"],
                publisher=row["match_publisher"],
                year=int(row["match_year"]) if row["match_year"] else None,
                lccn=copyright_lccn,
                source_id=row.get("match_source_id", ""),
            )
            if copyright_lccn:
                copyright_pub.normalized_lccn = row.get("marc_lccn_normalized", "")

            # Test match
            result = matcher.find_best_match(
                marc_pub,
                [copyright_pub],
                title_threshold=threshold,
                author_threshold=threshold * 0.75,  # Slightly lower for author
                year_tolerance=2,
            )

            if result:
                if has_lccn_in_real_world:
                    true_positives_with_lccn += 1
                else:
                    true_positives_without_lccn += 1

        # Test mismatches (false positives)
        for row in mismatches:
            marc_pub = Publication(
                title=row["marc_title_original"],
                author=row["marc_author_original"],
                main_author=row["marc_main_author_original"],
                publisher=row["marc_publisher_original"],
                year=int(row["marc_year"]) if row["marc_year"] else None,
                lccn="",  # No LCCN for false positive testing
                source_id=row["marc_id"],
            )

            copyright_pub = Publication(
                title=row["match_title"],
                author=row["match_author"],
                publisher=row["match_publisher"],
                year=int(row["match_year"]) if row["match_year"] else None,
                lccn="",
                source_id=row.get("match_source_id", ""),
            )

            result = matcher.find_best_match(
                marc_pub,
                [copyright_pub],
                title_threshold=threshold,
                author_threshold=threshold * 0.75,
                year_tolerance=2,
            )

            if result:
                false_positives += 1

        return {
            "tp_with_lccn": true_positives_with_lccn,
            "tp_without_lccn": true_positives_without_lccn,
            "fp": false_positives,
            "total_matches": len(matches),
            "total_mismatches": len(mismatches),
        }

    @mark.scoring
    def test_threshold_analysis(self):
        """Test various threshold and boost combinations"""
        matches, mismatches = self.load_test_data()

        # Test scenarios
        scenarios = [
            # (lccn_boost, base_threshold, description)
            (35, 40, "Current: High threshold + high boost"),
            (35, 30, "Proposed: Lower threshold + high boost"),
            (35, 25, "Aggressive: Very low threshold + high boost"),
            (20, 30, "Moderate: Low threshold + moderate boost"),
            (10, 30, "Conservative: Low threshold + small boost"),
            (0, 30, "No boost: Field matching only"),
        ]

        # Silent test - just verify scenarios

        best_config = None
        best_score = -1

        for lccn_boost, threshold, description in scenarios:
            results = self._test_scenario(
                matches[:1000],  # Test subset for speed
                mismatches[:100] if mismatches else [],
                lccn_boost,
                threshold,
                description,
                with_lccn_rate=0.01,  # 1% have LCCNs
            )

            total_tp = results["tp_with_lccn"] + results["tp_without_lccn"]
            tp_rate = total_tp / min(1000, results["total_matches"]) * 100
            fp_rate = (
                results["fp"] / min(100, results["total_mismatches"]) * 100
                if results["total_mismatches"]
                else 0
            )

            # Score: maximize TP, minimize FP
            score = tp_rate - (fp_rate * 2)  # Weight FP more heavily

            if score > best_score:
                best_score = score
                best_config = (lccn_boost, threshold, description)

        # Just verify we found a best configuration
        assert best_config is not None, "Failed to find best configuration"
        assert best_score > 0, "Best score should be positive"
