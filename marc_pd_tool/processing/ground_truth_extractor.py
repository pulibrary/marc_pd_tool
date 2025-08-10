# marc_pd_tool/processing/ground_truth_extractor.py

"""Extract ground truth pairs based on LCCN matching"""

# Standard library imports
from collections import defaultdict
from logging import getLogger
from pickle import load

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.ground_truth import GroundTruthStats
from marc_pd_tool.data.publication import MatchResult
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator

logger = getLogger(__name__)


class GroundTruthExtractor:
    """Extracts LCCN-verified ground truth pairs for algorithm validation and optimization"""

    def __init__(self) -> None:
        self.logger = getLogger(self.__class__.__name__)
        self.similarity_calculator = SimilarityCalculator()

    def extract_ground_truth_pairs(
        self,
        marc_batches: list[list[Publication]],
        copyright_publications: list[Publication],
        renewal_publications: list[Publication] | None = None,
    ) -> tuple[list[Publication], GroundTruthStats]:
        """Extract all LCCN-matched pairs from the datasets

        Args:
            marc_batches: List of MARC publication batches
            copyright_publications: List of copyright registration publications
            renewal_publications: Optional list of renewal publications

        Returns:
            Tuple of (marc_publications_with_matches, statistics)
        """
        if renewal_publications is None:
            renewal_publications = []

        self.logger.info("Starting ground truth extraction based on LCCN matching")

        # Flatten MARC batches
        marc_records = []
        for batch in marc_batches:
            marc_records.extend(batch)

        # Build LCCN indexes for fast lookup
        copyright_lccn_index = self._build_lccn_index(copyright_publications)
        renewal_lccn_index = (
            self._build_lccn_index(renewal_publications) if renewal_publications else {}
        )

        self.logger.info(
            f"Built LCCN indexes: {len(copyright_lccn_index)} copyright, {len(renewal_lccn_index)} renewal"
        )

        # Extract matching pairs
        matched_marc_records = []

        # Track statistics
        total_marc_records = len(marc_records)
        marc_with_lccn = 0
        registration_matches = 0
        renewal_matches = 0
        matched_lccns = set()

        for marc_record in marc_records:
            if not marc_record.normalized_lccn:
                continue

            marc_with_lccn += 1
            lccn = marc_record.normalized_lccn
            has_match = False

            # Check for copyright registration matches
            if lccn in copyright_lccn_index:
                for copyright_record in copyright_lccn_index[lccn]:
                    # Calculate similarity scores even though we know it's a match
                    title_score = self.similarity_calculator.calculate_title_similarity(
                        marc_record.title or "", copyright_record.title or ""
                    )
                    author_score = self.similarity_calculator.calculate_author_similarity(
                        marc_record.author or "", copyright_record.author or ""
                    )
                    publisher_score = self.similarity_calculator.calculate_publisher_similarity(
                        marc_record.publisher or "", copyright_record.publisher or ""
                    )
                    combined_score = (title_score + author_score + publisher_score) / 3

                    # Create MatchResult
                    match_result = MatchResult(
                        matched_title=copyright_record.title
                        or copyright_record.original_title
                        or "",
                        matched_author=copyright_record.author
                        or copyright_record.original_author
                        or "",
                        similarity_score=combined_score,
                        title_score=title_score,
                        author_score=author_score,
                        publisher_score=publisher_score,
                        year_difference=abs((marc_record.year or 0) - (copyright_record.year or 0)),
                        source_id=copyright_record.source_id or "",
                        source_type="registration",
                        matched_date=copyright_record.pub_date or "",
                        matched_publisher=copyright_record.publisher
                        or copyright_record.original_publisher,
                        match_type=MatchType.LCCN,
                        normalized_title=copyright_record.title or "",
                        normalized_author=copyright_record.author or "",
                    )

                    # Attach to MARC record
                    marc_record.registration_match = match_result
                    registration_matches += 1
                    matched_lccns.add(lccn)
                    has_match = True

            # Check for renewal matches
            if lccn in renewal_lccn_index:
                for renewal_record in renewal_lccn_index[lccn]:
                    # Calculate similarity scores
                    title_score = self.similarity_calculator.calculate_title_similarity(
                        marc_record.title or "", renewal_record.title or ""
                    )
                    author_score = self.similarity_calculator.calculate_author_similarity(
                        marc_record.author or "", renewal_record.author or ""
                    )
                    publisher_score = self.similarity_calculator.calculate_publisher_similarity(
                        marc_record.publisher or "", renewal_record.publisher or ""
                    )
                    combined_score = (title_score + author_score + publisher_score) / 3

                    # Create MatchResult
                    match_result = MatchResult(
                        matched_title=renewal_record.title or renewal_record.original_title or "",
                        matched_author=renewal_record.author
                        or renewal_record.original_author
                        or "",
                        similarity_score=combined_score,
                        title_score=title_score,
                        author_score=author_score,
                        publisher_score=publisher_score,
                        year_difference=abs((marc_record.year or 0) - (renewal_record.year or 0)),
                        source_id=renewal_record.source_id or "",
                        source_type="renewal",
                        matched_date=renewal_record.pub_date or "",
                        matched_publisher=renewal_record.publisher
                        or renewal_record.original_publisher,
                        match_type=MatchType.LCCN,
                        normalized_title=renewal_record.title or "",
                        normalized_author=renewal_record.author or "",
                    )

                    # Attach to MARC record
                    marc_record.renewal_match = match_result
                    renewal_matches += 1
                    matched_lccns.add(lccn)
                    has_match = True

            if has_match:
                # Determine copyright status based on matches
                marc_record.determine_copyright_status()
                matched_marc_records.append(marc_record)

        # Compile statistics
        stats = GroundTruthStats(
            total_marc_records=total_marc_records,
            marc_with_lccn=marc_with_lccn,
            total_copyright_records=len(copyright_publications),
            copyright_with_lccn=len(copyright_lccn_index),
            total_renewal_records=len(renewal_publications),
            registration_matches=registration_matches,
            renewal_matches=renewal_matches,
            unique_lccns_matched=len(matched_lccns),
            unique_lccns=len(set(r.normalized_lccn for r in marc_records if r.normalized_lccn)),
        )

        self.logger.info(f"Ground truth extraction complete:")
        self.logger.info(
            f"  MARC records with LCCN: {marc_with_lccn:,} ({stats.marc_lccn_coverage:.1f}%)"
        )
        self.logger.info(
            f"  Copyright records with LCCN: {len(copyright_lccn_index):,} ({stats.copyright_lccn_coverage:.1f}%)"
        )
        self.logger.info(f"  Registration matches: {registration_matches:,}")
        self.logger.info(f"  Renewal matches: {renewal_matches:,}")
        self.logger.info(f"  Total matched MARC records: {len(matched_marc_records):,}")
        self.logger.info(f"  Unique LCCNs matched: {len(matched_lccns):,}")

        return matched_marc_records, stats

    def extract_ground_truth_from_pickles(
        self,
        batch_paths: list[str],
        copyright_publications: list[Publication],
        renewal_publications: list[Publication] | None = None,
    ) -> tuple[list[Publication], GroundTruthStats]:
        """Extract ground truth pairs from pickled MARC batch files for streaming mode

        Args:
            batch_paths: List of paths to pickled MARC batch files
            copyright_publications: List of copyright registration publications
            renewal_publications: Optional list of renewal publications

        Returns:
            Tuple of (marc_publications_with_matches, statistics)
        """
        if renewal_publications is None:
            renewal_publications = []

        self.logger.info("Starting streaming ground truth extraction based on LCCN matching")

        # Build LCCN indexes for fast lookup
        copyright_lccn_index = self._build_lccn_index(copyright_publications)
        renewal_lccn_index = (
            self._build_lccn_index(renewal_publications) if renewal_publications else {}
        )

        self.logger.info(
            f"Built LCCN indexes: {len(copyright_lccn_index)} copyright, {len(renewal_lccn_index)} renewal"
        )

        # Extract matching pairs by processing pickled batches one at a time
        matched_marc_records = []

        # Track statistics
        total_marc_records = 0
        marc_with_lccn = 0
        registration_matches = 0
        renewal_matches = 0
        matched_lccns = set()

        self.logger.info(
            f"Processing {len(batch_paths)} pickled batches for ground truth extraction"
        )

        for i, batch_path in enumerate(batch_paths):
            self.logger.debug(f"Processing batch {i+1}/{len(batch_paths)}: {batch_path}")

            try:
                # Load batch from pickle file
                with open(batch_path, "rb") as f:
                    marc_batch: list[Publication] = load(f)

                # Process each record in the batch
                for marc_record in marc_batch:
                    total_marc_records += 1

                    if not marc_record.normalized_lccn:
                        continue

                    marc_with_lccn += 1
                    lccn = marc_record.normalized_lccn
                    has_match = False

                    # Check for copyright registration matches
                    if lccn in copyright_lccn_index:
                        for copyright_record in copyright_lccn_index[lccn]:
                            # Calculate similarity scores
                            title_score = self.similarity_calculator.calculate_title_similarity(
                                marc_record.title or "", copyright_record.title or ""
                            )
                            author_score = self.similarity_calculator.calculate_author_similarity(
                                marc_record.author or "", copyright_record.author or ""
                            )
                            publisher_score = (
                                self.similarity_calculator.calculate_publisher_similarity(
                                    marc_record.publisher or "", copyright_record.publisher or ""
                                )
                            )
                            combined_score = (title_score + author_score + publisher_score) / 3

                            # Create MatchResult
                            match_result = MatchResult(
                                matched_title=copyright_record.title
                                or copyright_record.original_title
                                or "",
                                matched_author=copyright_record.author
                                or copyright_record.original_author
                                or "",
                                similarity_score=combined_score,
                                title_score=title_score,
                                author_score=author_score,
                                publisher_score=publisher_score,
                                year_difference=abs(
                                    (marc_record.year or 0) - (copyright_record.year or 0)
                                ),
                                source_id=copyright_record.source_id or "",
                                source_type="registration",
                                matched_date=copyright_record.pub_date or "",
                                matched_publisher=copyright_record.publisher
                                or copyright_record.original_publisher,
                                match_type=MatchType.LCCN,
                                normalized_title=copyright_record.title or "",
                                normalized_author=copyright_record.author or "",
                            )

                            # Attach to MARC record
                            marc_record.registration_match = match_result
                            registration_matches += 1
                            matched_lccns.add(lccn)
                            has_match = True

                    # Check for renewal matches
                    if lccn in renewal_lccn_index:
                        for renewal_record in renewal_lccn_index[lccn]:
                            # Calculate similarity scores
                            title_score = self.similarity_calculator.calculate_title_similarity(
                                marc_record.title or "", renewal_record.title or ""
                            )
                            author_score = self.similarity_calculator.calculate_author_similarity(
                                marc_record.author or "", renewal_record.author or ""
                            )
                            publisher_score = (
                                self.similarity_calculator.calculate_publisher_similarity(
                                    marc_record.publisher or "", renewal_record.publisher or ""
                                )
                            )
                            combined_score = (title_score + author_score + publisher_score) / 3

                            # Create MatchResult
                            match_result = MatchResult(
                                matched_title=renewal_record.title
                                or renewal_record.original_title
                                or "",
                                matched_author=renewal_record.author
                                or renewal_record.original_author
                                or "",
                                similarity_score=combined_score,
                                title_score=title_score,
                                author_score=author_score,
                                publisher_score=publisher_score,
                                year_difference=abs(
                                    (marc_record.year or 0) - (renewal_record.year or 0)
                                ),
                                source_id=renewal_record.source_id or "",
                                source_type="renewal",
                                matched_date=renewal_record.pub_date or "",
                                matched_publisher=renewal_record.publisher
                                or renewal_record.original_publisher,
                                match_type=MatchType.LCCN,
                                normalized_title=renewal_record.title or "",
                                normalized_author=renewal_record.author or "",
                            )

                            # Attach to MARC record
                            marc_record.renewal_match = match_result
                            renewal_matches += 1
                            matched_lccns.add(lccn)
                            has_match = True

                    if has_match:
                        # Determine copyright status based on matches
                        marc_record.determine_copyright_status()
                        matched_marc_records.append(marc_record)

                # Clear batch from memory immediately
                del marc_batch

            except Exception as e:
                self.logger.error(f"Error processing batch {batch_path}: {e}")
                continue

        # Compile statistics
        stats = GroundTruthStats(
            total_marc_records=total_marc_records,
            marc_with_lccn=marc_with_lccn,
            total_copyright_records=len(copyright_publications),
            copyright_with_lccn=len(copyright_lccn_index),
            total_renewal_records=len(renewal_publications),
            registration_matches=registration_matches,
            renewal_matches=renewal_matches,
            unique_lccns_matched=len(matched_lccns),
            unique_lccns=0,  # We don't have all records to count unique LCCNs in streaming mode
        )

        self.logger.info(f"Streaming ground truth extraction complete:")
        self.logger.info(
            f"  MARC records with LCCN: {marc_with_lccn:,} ({stats.marc_lccn_coverage:.1f}%)"
        )
        self.logger.info(
            f"  Copyright records with LCCN: {len(copyright_lccn_index):,} ({stats.copyright_lccn_coverage:.1f}%)"
        )
        self.logger.info(f"  Registration matches: {registration_matches:,}")
        self.logger.info(f"  Renewal matches: {renewal_matches:,}")
        self.logger.info(f"  Total matched MARC records: {len(matched_marc_records):,}")
        self.logger.info(f"  Unique LCCNs matched: {len(matched_lccns):,}")

        return matched_marc_records, stats

    def _build_lccn_index(self, publications: list[Publication]) -> dict[str, list[Publication]]:
        """Build an index of publications by normalized LCCN

        Args:
            publications: List of publications to index

        Returns:
            Dictionary mapping normalized LCCN to list of publications
        """
        index: dict[str, list[Publication]] = defaultdict(list)

        for pub in publications:
            if pub.normalized_lccn:
                index[pub.normalized_lccn].append(pub)

        return dict(index)

    def filter_by_year_range(
        self, pairs: list[Publication], min_year: int | None = None, max_year: int | None = None
    ) -> list[Publication]:
        """Filter ground truth pairs by year range

        Args:
            pairs: List of MARC publications with matches
            min_year: Minimum publication year (inclusive)
            max_year: Maximum publication year (inclusive)

        Returns:
            Filtered list of publications
        """
        if min_year is None and max_year is None:
            return pairs

        filtered = []
        for pub in pairs:
            if pub.year is None:
                continue
            if min_year is not None and pub.year < min_year:
                continue
            if max_year is not None and pub.year > max_year:
                continue
            filtered.append(pub)

        return filtered

    def get_coverage_report(
        self,
        marc_batches: list[list[Publication]],
        copyright_publications: list[Publication],
        renewal_publications: list[Publication] | None = None,
    ) -> dict[str, float | int]:
        """Generate a coverage report for LCCN presence in the datasets

        Args:
            marc_batches: List of MARC publication batches
            copyright_publications: List of copyright registration publications
            renewal_publications: Optional list of renewal publications

        Returns:
            Dictionary with coverage statistics
        """
        if renewal_publications is None:
            renewal_publications = []

        # Flatten MARC batches
        marc_records = []
        for batch in marc_batches:
            marc_records.extend(batch)

        # Count LCCN presence
        marc_total = len(marc_records)
        marc_with_lccn = sum(1 for r in marc_records if r.normalized_lccn)

        copyright_total = len(copyright_publications)
        copyright_with_lccn = sum(1 for r in copyright_publications if r.normalized_lccn)

        renewal_total = len(renewal_publications)
        renewal_with_lccn = sum(1 for r in renewal_publications if r.normalized_lccn)

        return {
            "marc_total": marc_total,
            "marc_with_lccn": marc_with_lccn,
            "marc_lccn_percentage": (marc_with_lccn / marc_total * 100) if marc_total > 0 else 0,
            "copyright_total": copyright_total,
            "copyright_with_lccn": copyright_with_lccn,
            "copyright_lccn_percentage": (
                (copyright_with_lccn / copyright_total * 100) if copyright_total > 0 else 0
            ),
            "renewal_total": renewal_total,
            "renewal_with_lccn": renewal_with_lccn,
            "renewal_lccn_percentage": (
                (renewal_with_lccn / renewal_total * 100) if renewal_total > 0 else 0
            ),
        }
