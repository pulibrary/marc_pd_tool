# MARC Copyright Status Tool - Architecture

## 🎯 Application Purpose

This tool determines the copyright status of MARC bibliographic records by comparing them against historical copyright registration and renewal data from 1923-1991.

**Key Data:**

- **Input**: MARC XML files containing bibliographic records (potentially millions)
- **Registration Data**: ~2.1M copyright registrations (1923-1977) in `nypl-reg/xml/`
- **Renewal Data**: ~445K copyright renewals (1950-1991) in `nypl-ren/data/`
- **Output**: Copyright status determination (Public Domain, Not Public Domain, Undetermined)

## ⚠️ Critical Architecture Patterns (DO NOT BREAK THESE)

### 1. Memory Management via Streaming & Pickling

**Pattern**: Never load all data into memory at once. Stream and batch everything.

```python
# CORRECT: Stream MARC records, pickle in batches
for batch in stream_marc_records():
    pickle.dump(batch, file)  # Save to disk
    batch.clear()  # Free memory immediately

# WRONG: Load everything into memory
all_records = load_all_marc_records()  # DON'T DO THIS
```

**Key Files:**

- `infrastructure/persistence/_marc_loader.py`: Streams MARC XML, creates pickle batches
- `application/processing/matching_engine.py`: Processes batches one at a time

### 2. Multiprocessing Architecture

**Critical Issue**: macOS vs Linux differences in process spawning

```python
# PLATFORM DIFFERENCES:
# Linux: Defaults to 'fork' - child processes share memory with parent
# macOS: Defaults to 'spawn' - each child loads everything from scratch

# SOLUTION in _batch_processing.py:
if indexes_loaded and start_method == "spawn":
    set_start_method("fork", force=True)  # Force fork on macOS for memory sharing
```

**Memory Sharing Requirements:**

- Pre-loaded indexes (2.1M+ records) MUST be shared between processes
- Fork mode enables this sharing, spawn mode causes each worker to load independently
- Loading 2.1M records per worker = application hangs on small machines

**Signal Handler Interference:**

- NEVER register signal handlers in `__init__` methods
- Signal handlers break `multiprocessing.Pool` initialization
- Removed from `_analyzer.py` after causing failures

### 3. Result File Registration

**Critical Pattern**: Worker processes save results, main process MUST register them

```python
# In batch processing loop (_batch_processing.py):
for result in pool.imap_unordered(process_batch, batch_infos):
    batch_id, result_file_path, batch_stats = result
    
    # CRITICAL: Register the result file for later export
    self.results.add_result_file(result_file_path)  # DON'T FORGET THIS
```

Without this registration, exports will be empty because `load_all_publications()` won't find any files.

## 📊 Data Flow & Processing Pipeline

### Phase 1: Load Copyright Data

```
nypl-reg/xml/*.xml → Parse XML → Build Registration Index (2.1M records)
nypl-ren/data/*.xml → Parse XML → Build Renewal Index (445K records)
```

### Phase 2: Stream & Batch MARC Records

```
MARC XML → Stream Records → Filter (year, country) → Batch (1000 records) → Pickle to Disk
```

### Phase 3: Parallel Batch Processing

```
Pickled Batches → Worker Pool → Each Worker:
  1. Load batch from pickle
  2. Match against indexes (fuzzy matching)
  3. Score matches
  4. Determine copyright status
  5. Save results to pickle
  6. Return stats to main process
```

### Phase 4: Export Results

```
Result Pickles → Load All → Generate Reports (JSON, CSV, XLSX, HTML)
```

## 🔄 Multiprocessing Details

### Worker Initialization

```python
# matching_engine.py - process_batch_init()
# Called ONCE per worker process
def process_batch_init(reg_index, ren_index, config, use_shared_memory):
    global registration_index, renewal_index, matching_config
    
    if use_shared_memory:
        # Use pre-loaded indexes from parent (fork mode)
        registration_index = reg_index
        renewal_index = ren_index
    else:
        # Load indexes independently (spawn mode) - AVOID THIS
        registration_index = load_index()
```

### Batch Processing Function

```python
# matching_engine.py - process_batch()
def process_batch(batch_info):
    batch_num, pickle_path, result_temp_dir = batch_info
    
    # Load batch from pickle
    with open(pickle_path, 'rb') as f:
        publications = pickle.load(f)
    
    # Process each publication
    for pub in publications:
        # Complex matching logic here
        
    # Save results
    result_file = f"batch_{batch_num}_result.pkl"
    pickle.dump(processed_pubs, result_file)
    
    return batch_num, result_file, stats
```

## 🎯 Scoring & Matching Logic

### Similarity Scoring

**CRITICAL**: The scoring system uses weighted fuzzy matching with specific thresholds.

```python
# Thresholds (from config):
TITLE_THRESHOLD = 25  # 25% similarity required
AUTHOR_THRESHOLD = 20  # 20% similarity required  
YEAR_TOLERANCE = 1    # ±1 year acceptable

# Scoring weights:
title_weight = 0.4
author_weight = 0.3
year_weight = 0.2
pagination_weight = 0.1
```

### Match Determination

1. **Title Match**: Uses token-based Jaccard similarity
1. **Author Match**: Fuzzy string matching with name normalization
1. **Year Match**: Exact or ±1 year tolerance
1. **Combined Score**: Weighted average must exceed threshold

### Copyright Status Logic

```python
if has_renewal_match:
    status = "Not Public Domain"  # Was renewed
elif has_registration_match and no_renewal_possible:
    status = "Public Domain"  # Not renewed when it could have been
else:
    status = "Undetermined"  # Unclear
```

## 🚨 Common Pitfalls & Solutions

### 1. Empty Reports

**Symptom**: Reports generate but contain no data
**Cause**: Result files not registered with AnalysisResults
**Fix**: Ensure `self.results.add_result_file(path)` is called in batch loop

### 2. Multiprocessing Hangs on macOS

**Symptom**: Application hangs after "Starting parallel processing"
**Cause**: Spawn mode causing each worker to load 2.1M records
**Fix**: Force fork mode when indexes are pre-loaded

### 3. Signal Handler Conflicts

**Symptom**: "signal only works in main thread" error
**Cause**: Signal handlers registered in wrong place
**Fix**: Never register signal handlers in `__init__` methods

### 4. Progress Bar Issues

**Symptom**: Garbled output, extra newlines
**Cause**: Complex progress bar library conflicts
**Fix**: Use simple logging instead of progress bars

### 5. Import Style Violations

**Symptom**: Code review complaints about imports
**Fix**: Always use `from module import function`, one per line

### 6. Type Safety Issues

**Symptom**: mypy errors, especially with JSON data
**Fix**: Use JSONDict/JSONList/JSONType, never Any

## 🧪 Testing & Validation

### Critical Tests to Run

```bash
pdm test  # Run all tests - MUST PASS
pdm mypy  # Type checking - MUST PASS
pdm format  # Code formatting
```

### Performance Benchmarks

- Target: 2,000-5,000+ records/minute
- Memory usage: Should stay constant (streaming)
- CPU usage: Should use all cores during batch processing

### Platform Testing

- **Linux**: Primary platform, fork mode works naturally
- **macOS**: Requires fork mode forcing for performance
- **Windows**: Not officially supported

## 📁 Key Files to Understand

1. **`adapters/api/_batch_processing.py`**: Orchestrates parallel processing
1. **`application/processing/matching_engine.py`**: Core matching logic
1. **`infrastructure/persistence/_marc_loader.py`**: MARC streaming/batching
1. **`application/processing/parallel_indexer.py`**: Index building
1. **`adapters/api/_analyzer.py`**: Main API entry point
1. **`application/models/analysis_results.py`**: Results storage/export

## 🔧 Configuration

### Key Configuration Values

```python
# From config files:
BATCH_SIZE = 1000  # Records per pickle batch
TASKS_PER_CHILD = 5  # Batches before worker restart
INDEX_CHUNK_SIZE = 10000  # Records per index chunk
```

### Memory Optimization Flags

- `--low-memory`: Reduces batch sizes
- `--num-workers N`: Control parallelism
- `--force-refresh`: Clear all caches

## 📝 Architecture Principles

1. **Stream Everything**: Never load full datasets into memory
1. **Batch Processing**: Work in chunks of ~1000 records
1. **Parallel When Possible**: Use all CPU cores for computation
1. **Cache Aggressively**: Indexes are expensive to build
1. **Fail Gracefully**: Always cleanup temp files on error
1. **Platform Aware**: Handle Linux/macOS differences explicitly

## ⚡ Quick Debugging Guide

### Application Hangs

1. Check multiprocessing mode (fork vs spawn)
1. Verify indexes are being shared, not reloaded
1. Look for signal handler issues

### Empty Output

1. Check result file registration
1. Verify batch processing completed
1. Check for exceptions in worker processes

### Performance Issues

1. Verify parallel processing is active
1. Check batch sizes
1. Monitor memory usage for leaks

### Type Errors

1. Never use `Any` type
1. Use JSONDict/JSONList for JSON data
1. Ensure all functions have type hints

## 🎓 Essential Context for Claude

When working on this codebase:

1. **Read `CLAUDE.md` first** for project-specific standards
1. **Read this `ARCHITECTURE.md`** for technical details
1. **Check `docs/PIPELINE.md`** for processing logic
1. **Always run tests** before considering work complete
1. **Never break the streaming pattern** - memory efficiency is critical
1. **Respect platform differences** - especially macOS spawn vs fork
1. **Register all result files** - or exports will be empty

Remember: This application processes potentially millions of records. Memory efficiency and parallel processing are not optimizations - they are essential for the application to function at all.
