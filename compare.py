"""
MARC Publication Data Comparison Tool

Main entry point for comparing MARC publication data
with copyright registry entries to identify potential matches.

This is a convenience wrapper that calls the main CLI function.
"""

if __name__ == "__main__":
    # Import and run the main CLI function
    # Local imports
    from marc_pd_tool.cli.main import main

    main()
