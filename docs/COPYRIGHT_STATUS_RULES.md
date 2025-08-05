# Copyright Status Rules Documentation

This document explains the copyright status determination logic used by the MARC PD Tool.

## Overview

The tool determines copyright status based on:

1. **Country of publication** (US, Non-US, or Unknown)
1. **Publication year**
1. **Registration status** (found in copyright registration data)
1. **Renewal status** (found in copyright renewal data)

## Key Concepts

- **Copyright Expiration Year**: Always calculated as current_year - 96 (e.g., in 2025, works before 1929 have expired copyrights)
- **Renewal Period**: Years between copyright_expiration_year and 1977, when renewal was required
- **Data Coverage**: Registration data covers 1923-1977, renewal data covers 1950-1991
- **Dynamic Status Values**: Status names now include year and country information

## Copyright Status Categories

### US Publications

#### Pre-Copyright Expiration

- **`US_PRE_{YEAR}`** (e.g., `US_PRE_1929`)
  - Rule: `US_PRE_COPYRIGHT_EXPIRATION`
  - Works published before copyright_expiration_year
  - Always in public domain due to age

#### Within Renewal Period (copyright_expiration_year-1977)

- **`US_REGISTERED_NOT_RENEWED`**

  - Rule: `US_RENEWAL_PERIOD_NOT_RENEWED`
  - Registration found but no renewal
  - Public domain (renewal was required but not done)

- **`US_RENEWED`**

  - Rule: `US_RENEWAL_PERIOD_RENEWED`
  - Renewal found (with or without registration)
  - Still under copyright (was properly renewed)

- **`US_NO_MATCH`**

  - Rule: `US_RENEWAL_PERIOD_NO_MATCH`
  - No registration or renewal found
  - Status uncertain

#### After Renewal Period (1978-1991)

- **`US_REGISTERED_NOT_RENEWED`**

  - Rule: `US_REGISTERED_NO_RENEWAL`
  - Registration but no renewal
  - Status uncertain (renewals not required after 1977)

- **`US_RENEWED`**

  - Rule: `US_RENEWAL_FOUND` or `US_BOTH_REG_AND_RENEWAL`
  - Renewal found
  - Still under copyright

- **`US_NO_MATCH`**

  - Rule: `US_NO_MATCH`
  - No matches found
  - Status uncertain

#### Beyond Data Range (after 1991)

- **`OUT_OF_DATA_RANGE_{YEAR}`** (e.g., `OUT_OF_DATA_RANGE_1991`)
  - Rule: `OUT_OF_DATA_RANGE`
  - Published after our data coverage ends
  - Cannot analyze

### Non-US Publications

#### Pre-Copyright Expiration

- **`FOREIGN_PRE_{YEAR}_{COUNTRY}`** (e.g., `FOREIGN_PRE_1929_GBR`)
  - Rule: `FOREIGN_PRE_COPYRIGHT_EXPIRATION`
  - Foreign works published before copyright_expiration_year
  - Complex status (depends on country and treaties)

#### Within Copyright Term

- **`FOREIGN_RENEWED_{COUNTRY}`** (e.g., `FOREIGN_RENEWED_FRA`)

  - Rule: `FOREIGN_RENEWED`
  - Foreign work with US renewal found
  - Has US copyright protection

- **`FOREIGN_REGISTERED_NOT_RENEWED_{COUNTRY}`**

  - Rule: `FOREIGN_REGISTERED_NOT_RENEWED`
  - Foreign work with US registration but no renewal
  - Complex status (depends on publication year and treaties)

- **`FOREIGN_NO_MATCH_{COUNTRY}`**

  - Rule: `FOREIGN_NO_MATCH`
  - Foreign work with no US copyright activity
  - May be public domain in US (no US formalities)

### Unknown Country Publications

- **`COUNTRY_UNKNOWN_RENEWED`**

  - Rule: `COUNTRY_UNKNOWN_RENEWED`
  - Renewal found but country unknown
  - Cannot determine full status

- **`COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED`**

  - Rule: `COUNTRY_UNKNOWN_REGISTERED`
  - Registration but no renewal, country unknown
  - Cannot determine full status

- **`COUNTRY_UNKNOWN_NO_MATCH`**

  - Rule: `COUNTRY_UNKNOWN_NO_MATCH`
  - No matches, country unknown
  - Cannot determine status without country

Unknown country occurs when:

- MARC field 008 is too short (less than 18 characters)
- Country code positions 15-17 are empty or blank
- Record lacks reliable country information

## Legal Interpretation

The tool provides data matches only. Legal interpretation of copyright status requires:

- Understanding publication dates and copyright terms
- Checking renewal requirements for the specific publication year
- Considering international copyright treaties
- Analyzing special cases (government documents, etc.)

## Important Notes

1. **Min/Max Year Filtering**: The `--min-year` and `--max-year` options filter which records to process but do NOT affect copyright determination

1. **Copyright Expiration**: Always based on current_year - 96, not configurable

1. **Country Codes**: Foreign status values include the 3-letter MARC country code when available

1. **Data Limitations**: Our analysis is limited by available data (registrations 1923-1977, renewals 1950-1991)
