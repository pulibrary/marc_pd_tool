# Copyright Status Rules Documentation

This document explains the copyright status determination logic used by the MARC PD Tool.

## Overview

The tool determines copyright status based on:

1. **Country of publication** (US, Non-US, or Unknown)
1. **Publication year**
1. **Registration status** (found in copyright registration data)
1. **Renewal status** (found in copyright renewal data)

## Copyright Statuses

### Definitely Public Domain

- **`PD_PRE_MIN_YEAR`**: Published before min_year (current year - 96)

  - Rule: `us_pre_min_year`
  - All works published before the minimum year are in the public domain

- **`PD_US_NOT_RENEWED`**: US works (min_year-1977) with registration but no renewal

  - Rule: `us_not_renewed`
  - These works required renewal to maintain copyright and weren't renewed

### Likely Public Domain (Needs Verification)

- **`PD_US_NO_REG_DATA`**: US work with no registration data found

  - Rule: `us_no_reg_data`
  - No evidence of copyright registration found, likely unregistered

- **`PD_US_REG_NO_RENEWAL`**: US work registered but no renewal found (outside renewal period)

  - Rule: `us_registered_no_renewal`
  - Has registration but no renewal; applies to years after 1977

### Unknown Status

- **`UNKNOWN_US_NO_DATA`**: US works (min_year-1977) with no registration/renewal data
  - Rule: `us_no_reg_data_renewal_period`
  - Critical period where renewal was required; no data means unknown status

### In Copyright

- **`IN_COPYRIGHT`**: Has renewal or other evidence of copyright

  - Rule: `us_renewal_found` - Renewal record found
  - Rule: `us_registered_and_renewed` - Both registration and renewal found

- **`IN_COPYRIGHT_US_RENEWED`**: US works (min_year-1977) that were renewed

  - Rule: `us_renewed`
  - Work from renewal period that was properly renewed

### Non-US Works

- **`RESEARCH_US_STATUS`**: Non-US work with US copyright activity

  - Rule: `foreign_us_activity`
  - Foreign work that was registered/renewed in US; complex copyright status

- **`RESEARCH_US_ONLY_PD`**: Non-US work with no US copyright activity

  - Rule: `foreign_no_us_activity`
  - May be PD in US but needs research for country of origin

### Other

- **`COUNTRY_UNKNOWN`**: Country of publication unknown
  - Rule: `unknown_country`
  - Cannot determine copyright status without knowing country

## Status Rules

Status rules provide the legal reasoning for each copyright determination:

### US Pre-Min Year Rules

- `us_pre_min_year`: Published before current year - 96 → Always public domain

### US Renewal Period Rules (Min Year-1977)

During the renewal period (currently 1929-1977), US copyright law required renewal for continued protection:

- `us_not_renewed`: Found registration but no renewal → Public domain
- `us_renewed`: Found both registration and renewal → Still in copyright
- `us_no_reg_data_renewal_period`: No registration or renewal data found → Unknown status

### General US Rules (Other Years)

- `us_registered_no_renewal`: Registration found but no renewal (needs year-specific analysis)
- `us_renewal_found`: Renewal record found (likely still in copyright)
- `us_no_reg_data`: No registration or renewal data (likely never registered)
- `us_registered_and_renewed`: Both registration and renewal found (in copyright)

### Foreign Work Rules

- `foreign_us_activity`: Non-US work with US registration/renewal activity
- `foreign_no_us_activity`: Non-US work with no US copyright records

### Special Cases

- `unknown_country`: Cannot determine country of publication
- `missing_year`: No publication year available (appended to other rules)

## Decision Tree

```
Publication
├── Year < min_year (current year - 96)?
│   └── YES → PD_PRE_MIN_YEAR (us_pre_min_year)
│
├── Country = US?
│   ├── Year between min_year and 1977?
│   │   ├── Has Registration?
│   │   │   ├── Has Renewal?
│   │   │   │   └── YES → IN_COPYRIGHT_US_RENEWED (us_renewed)
│   │   │   └── NO → PD_US_NOT_RENEWED (us_not_renewed)
│   │   └── NO → UNKNOWN_US_NO_DATA (us_no_reg_data_renewal_period)
│   │
│   └── Other Years (after 1977)
│       ├── Has Renewal? → IN_COPYRIGHT (us_renewal_found or us_registered_and_renewed)
│       ├── Has Registration Only? → PD_US_REG_NO_RENEWAL (us_registered_no_renewal)
│       └── No Data? → PD_US_NO_REG_DATA (us_no_reg_data)
│
├── Country = Non-US?
│   ├── Has US Activity? → RESEARCH_US_STATUS (foreign_us_activity)
│   └── No US Activity? → RESEARCH_US_ONLY_PD (foreign_no_us_activity)
│
└── Country = Unknown?
    └── COUNTRY_UNKNOWN (unknown_country)
```

## Export Format

In all export formats, copyright status information includes:

- `status`: The copyright status enum value
- `status_rule`: The rule that was applied
- `status_reason`: Human-readable explanation (in some formats)

## Important Notes

1. **Conservative Approach**: When in doubt, the tool assumes works may be in copyright
1. **US-Centric**: This tool focuses on US copyright status; foreign works need additional research
1. **Missing Year Modifier**: If no year can be extracted, "\_missing_year" is appended to the rule
1. **Data Limitations**: Status is based only on available registration/renewal data
