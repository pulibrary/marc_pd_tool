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

- **`PD_PRE_1928`**: Published before 1928

  - Rule: `us_pre_1928`
  - All works published before 1928 are in the public domain

- **`PD_US_1930_1963_NOT_RENEWED`**: US works 1930-1963 with registration but no renewal

  - Rule: `us_1930_1963_no_renewal`
  - These works required renewal to maintain copyright and weren't renewed

### Likely Public Domain (Needs Verification)

- **`PD_US_NO_REG_DATA`**: US work with no registration data found

  - Rule: `us_no_reg_data`
  - No evidence of copyright registration found, likely unregistered

- **`PD_US_REG_NO_RENEWAL`**: US work registered but no renewal found (outside 1930-1963)

  - Rule: `us_registered_no_renewal`
  - Has registration but no renewal; copyright status depends on specific year

### Unknown Status

- **`UNKNOWN_US_1930_1963_NO_DATA`**: US 1930-1963 with no registration/renewal data
  - Rule: `us_1930_1963_no_reg_data`
  - Critical period where renewal was required; no data means unknown status

### In Copyright

- **`IN_COPYRIGHT`**: Has renewal or other evidence of copyright

  - Rule: `us_renewal_found` - Renewal record found
  - Rule: `us_registered_and_renewed` - Both registration and renewal found

- **`IN_COPYRIGHT_US_1930_1963_RENEWED`**: US 1930-1963 that was renewed

  - Rule: `us_1930_1963_renewed`
  - Work from critical period that was properly renewed

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

### US Pre-1928 Rules

- `us_pre_1928`: Published before January 1, 1928 → Always public domain

### US 1930-1963 Special Period Rules

During 1930-1963, US copyright law required renewal for continued protection:

- `us_1930_1963_no_renewal`: Found registration but no renewal → Public domain
- `us_1930_1963_renewed`: Found both registration and renewal → Still in copyright
- `us_1930_1963_no_reg_data`: No registration or renewal data found → Unknown status

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
├── Year < 1928?
│   └── YES → PD_PRE_1928 (us_pre_1928)
│
├── Country = US?
│   ├── Year 1930-1963?
│   │   ├── Has Registration?
│   │   │   ├── Has Renewal?
│   │   │   │   └── YES → IN_COPYRIGHT_US_1930_1963_RENEWED (us_1930_1963_renewed)
│   │   │   └── NO → PD_US_1930_1963_NOT_RENEWED (us_1930_1963_no_renewal)
│   │   └── NO → UNKNOWN_US_1930_1963_NO_DATA (us_1930_1963_no_reg_data)
│   │
│   └── Other Years
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
