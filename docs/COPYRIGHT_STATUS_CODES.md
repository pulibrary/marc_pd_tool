# Copyright Status Codes Reference

This document provides a complete reference for all copyright status codes that appear in analysis results, explaining what each status means and its implications for copyright.

## Status Code Categories

The tool assigns status codes based on three factors:

1. Country of publication (US, Foreign, or Unknown)
1. Presence of copyright registration and/or renewal records
1. Publication year relative to copyright law thresholds

## U.S. Publications

### Public Domain Statuses

#### US_PRE\_[YEAR]

- **Example**: `US_PRE_1929`
- **Meaning**: Published in the United States before the copyright expiration year (current year - 96)
- **Copyright Status**: **Public Domain**
- **Explanation**: Copyright has expired due to age. Works published before this threshold are automatically in the public domain.

#### US_REGISTERED_NOT_RENEWED

- **Meaning**: Work was registered for copyright but was not renewed
- **Copyright Status**: **Public Domain**
- **Explanation**: Under pre-1978 copyright law, works had to be renewed after 28 years. This work was registered but the copyright was allowed to lapse by non-renewal.
- **Applies to**: Works published 1923-1977

### Protected Statuses

#### US_RENEWED

- **Meaning**: Work was registered and successfully renewed
- **Copyright Status**: **In Copyright**
- **Explanation**: The copyright was properly renewed and remains protected. Copyright term extends 95 years from publication.

### Undetermined Statuses

#### US_NO_MATCH

- **Meaning**: No copyright registration or renewal records found
- **Copyright Status**: **Undetermined - Research Required**
- **Explanation**: Could mean:
  - Work was never registered (possibly public domain if published before 1978 with no notice)
  - Registration records not yet digitized
  - Title/author variations preventing match
- **Recommendation**: Manual research needed to determine status

## Foreign Publications

Foreign works have different copyright rules under U.S. law. The country code is appended to the status.

### With U.S. Copyright Activity

#### FOREIGN_PRE\_[YEAR]\_[COUNTRY]

- **Example**: `FOREIGN_PRE_1929_GBR`
- **Meaning**: Foreign work published before copyright expiration year
- **Copyright Status**: **Likely Public Domain in U.S.**
- **Explanation**: Very old foreign works may be in the public domain

#### FOREIGN_RENEWED\_[COUNTRY]

- **Example**: `FOREIGN_RENEWED_FRA`
- **Meaning**: Foreign work with U.S. copyright renewal
- **Copyright Status**: **Protected in U.S.**
- **Explanation**: Foreign work that was registered and renewed in the U.S.

#### FOREIGN_REGISTERED_NOT_RENEWED\_[COUNTRY]

- **Example**: `FOREIGN_REGISTERED_NOT_RENEWED_DEU`
- **Meaning**: Foreign work registered in U.S. but not renewed
- **Copyright Status**: **Complex - Legal Review Needed**
- **Explanation**: Foreign works may have restored copyrights under GATT/TRIPS agreements despite non-renewal

### Without U.S. Copyright Activity

#### FOREIGN_NO_MATCH\_[COUNTRY]

- **Example**: `FOREIGN_NO_MATCH_ITA`
- **Meaning**: No U.S. copyright registration or renewal found
- **Copyright Status**: **Undetermined**
- **Explanation**: Foreign work with no U.S. copyright records. Status depends on treaties and publication date.

## Unknown Country

When the country of publication cannot be determined:

#### COUNTRY_UNKNOWN_PRE\_[YEAR]

- **Example**: `COUNTRY_UNKNOWN_PRE_1929`
- **Meaning**: Unknown country, published before expiration year
- **Copyright Status**: **Likely Public Domain**

#### COUNTRY_UNKNOWN_RENEWED

- **Meaning**: Unknown country, but found U.S. renewal
- **Copyright Status**: **In Copyright**
- **Explanation**: Renewal indicates active copyright regardless of country

#### COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED

- **Meaning**: Unknown country, registered but not renewed
- **Copyright Status**: **Undetermined**
- **Explanation**: Need country information to apply correct rules

#### COUNTRY_UNKNOWN_NO_MATCH

- **Meaning**: Unknown country, no copyright records found
- **Copyright Status**: **Undetermined**
- **Explanation**: Cannot determine status without country information

## Special Statuses

#### OUT_OF_DATA_RANGE\_[YEAR]

- **Example**: `OUT_OF_DATA_RANGE_1991`
- **Meaning**: Published after the last year of available renewal data
- **Copyright Status**: **Cannot Determine**
- **Explanation**: Work published after our data coverage ends (currently 1991)

## Common Country Codes

The three-letter country codes appended to foreign statuses include:

- **GBR**: Great Britain/United Kingdom
- **FRA**: France
- **DEU**: Germany (Deutschland)
- **ITA**: Italy
- **ESP**: Spain
- **CAN**: Canada
- **AUS**: Australia
- **JPN**: Japan
- **CHN**: China
- **IND**: India
- **MEX**: Mexico
- **BRA**: Brazil
- **ARG**: Argentina
- **NLD**: Netherlands
- **BEL**: Belgium
- **CHE**: Switzerland

## Interpreting Results for Copyright Decisions

### High Confidence Public Domain

- `US_PRE_[YEAR]` - Expired copyright
- `US_REGISTERED_NOT_RENEWED` - Failed renewal requirement

### High Confidence Protected

- `US_RENEWED` - Active renewal
- `FOREIGN_RENEWED_[COUNTRY]` - Foreign work with U.S. renewal
- `COUNTRY_UNKNOWN_RENEWED` - Renewal found

### Requires Further Research

- `US_NO_MATCH` - Need to verify if ever copyrighted
- `FOREIGN_REGISTERED_NOT_RENEWED_[COUNTRY]` - Check restoration rules
- `FOREIGN_NO_MATCH_[COUNTRY]` - Check treaties and foreign copyright
- `COUNTRY_UNKNOWN_*` - Need country determination
- `OUT_OF_DATA_RANGE_[YEAR]` - Beyond available data

## Important Legal Notes

1. **This tool provides guidance, not legal advice**. Copyright status determination can be complex and fact-specific.

1. **Foreign works** are particularly complex due to:

   - International treaties (Berne Convention, TRIPS)
   - Copyright restoration under GATT/URAA
   - Different terms in country of origin

1. **Works from 1923-1977** require careful analysis of:

   - Copyright notice requirements
   - Registration and renewal requirements
   - Manufacturing clause for certain works

1. **Post-1978 works** follow different rules under the 1976 Copyright Act (effective 1978).

1. **Edge cases** requiring special attention:

   - Government publications
   - Works for hire
   - Posthumous works
   - Unpublished works

## Using Status Codes in Reports

In exported reports (CSV, XLSX, JSON), the status code appears in the `copyright_status` field. The status provides:

1. **Sorting and filtering** - Group works by status
1. **Workflow routing** - Different statuses need different follow-up
1. **Risk assessment** - Understand confidence level
1. **Legal documentation** - Record basis for copyright determination

For programmatic processing, status codes follow consistent patterns:

- Prefix indicates country category (US, FOREIGN, COUNTRY_UNKNOWN)
- Core status (RENEWED, REGISTERED_NOT_RENEWED, NO_MATCH)
- Suffix for country code (foreign works) or year (pre-expiration statuses)
