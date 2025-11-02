#!/usr/bin/env python3
"""
Command-line interface for the Levels Detection Module

Usage:
    python levels_cli.py --file data/MNQ_1m.csv --asof "2025-10-01 10:15" --symbol MNQ --output json
    python levels_cli.py --file data/MNQ_1m.csv --asof "2025-10-01 10:15" --symbol MNQ --premarket "04:00-09:30" --rth "09:30-16:00"

Author: Trading Strategy Development
Date: November 1, 2025
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add modules directory to path
sys.path.append(str(Path(__file__).parent))
from levels import LevelsDetector, detect_levels_from_file


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Detect intraday support/resistance levels from OHLCV data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python levels_cli.py --file data/MNQ_1m.csv --asof "2025-10-01 10:15"

  # With custom session windows
  python levels_cli.py --file data/MNQ_1m.csv --asof "2025-10-01 10:15" \\
    --premarket "04:00-09:30" --rth "09:30-16:00"

  # With custom parameters
  python levels_cli.py --file data/MNQ_1m.csv --asof "2025-10-01 10:15" \\
    --symbol MNQ --merge-bps 10 --swing-window 7

  # Save to file
  python levels_cli.py --file data/MNQ_1m.csv --asof "2025-10-01 10:15" \\
    --output-file levels_result.json
        """
    )

    # Required arguments
    parser.add_argument(
        '--file',
        required=True,
        help='Path to CSV file with 1-minute OHLCV data'
    )

    parser.add_argument(
        '--asof',
        required=True,
        help='As-of timestamp (e.g., "2025-10-01 10:15" or "2025-10-01T10:15:00")'
    )

    # Optional arguments
    parser.add_argument(
        '--symbol',
        default='UNKNOWN',
        help='Trading symbol (default: UNKNOWN)'
    )

    parser.add_argument(
        '--output',
        choices=['json', 'pretty'],
        default='json',
        help='Output format (default: json)'
    )

    parser.add_argument(
        '--output-file',
        help='Save output to file instead of stdout'
    )

    # Session window parameters
    parser.add_argument(
        '--premarket',
        default='04:00-09:29',
        help='Premarket session window (default: 04:00-09:29)'
    )

    parser.add_argument(
        '--rth',
        default='09:30-16:00',
        help='Regular trading hours window (default: 09:30-16:00)'
    )

    # Detection parameters
    parser.add_argument(
        '--merge-bps',
        type=int,
        default=8,
        help='Merge tolerance in basis points (default: 8)'
    )

    parser.add_argument(
        '--swing-window',
        type=int,
        default=5,
        help='Window for swing high/low detection (default: 5)'
    )

    parser.add_argument(
        '--atr-period',
        type=int,
        default=14,
        help='Period for ATR calculation (default: 14)'
    )

    parser.add_argument(
        '--htf-timeframes',
        nargs='+',
        default=['1H', '4H'],
        help='Higher timeframes for swing detection (default: 1H 4H)'
    )

    # Timezone
    parser.add_argument(
        '--timezone',
        default='America/New_York',
        help='Timezone for data (default: America/New_York)'
    )

    # Verbose output
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    return parser.parse_args()


def format_pretty_output(result: dict) -> str:
    """Format result as pretty text output"""
    lines = []
    lines.append("🎯 INTRADAY LEVELS ANALYSIS")
    lines.append("=" * 50)
    lines.append(f"Symbol: {result['symbol']}")
    lines.append(f"As of: {result['asof']}")
    lines.append(f"Last Price: ${result['last_price']}")
    lines.append(f"5M ATR: {result['meta']['atr_5m']}")
    lines.append("")

    # Daily anchors
    lines.append("📅 DAILY ANCHORS")
    lines.append("-" * 20)
    levels = result['levels']

    if 'PDH' in levels:
        lines.append(f"PDH (Prev Day High): ${levels['PDH']}")
    if 'PDL' in levels:
        lines.append(f"PDL (Prev Day Low):  ${levels['PDL']}")
    if 'PMH' in levels:
        lines.append(f"PMH (Premarket High): ${levels['PMH']}")
    if 'PML' in levels:
        lines.append(f"PML (Premarket Low):  ${levels['PML']}")
    lines.append("")

    # Intraday levels
    lines.append("📊 INTRADAY LEVELS")
    lines.append("-" * 20)
    if result['meta']['ib_high']:
        lines.append(f"IB High: ${result['meta']['ib_high']}")
    if result['meta']['ib_low']:
        lines.append(f"IB Low:  ${result['meta']['ib_low']}")

    for key in ['5MH', '5ML', '15MH', '15ML']:
        if key in levels:
            lines.append(f"{key}: ${levels[key]}")
    lines.append("")

    # Next resistance levels
    lines.append("🔴 NEXT RESISTANCE LEVELS")
    lines.append("-" * 25)
    for i, level in enumerate(result['next_levels']['resistance'], 1):
        distance_sign = "+" if level['distance'] > 0 else ""
        lines.append(f"{i}. ${level['level']} ({distance_sign}{level['distance']}) "
                     f"[Score: {level['score']}, ATR: {level['distance_atr']}]")
        lines.append(f"   Tags: {', '.join(level['tags'])}")
    lines.append("")

    # Next support levels
    lines.append("🟢 NEXT SUPPORT LEVELS")
    lines.append("-" * 22)
    for i, level in enumerate(result['next_levels']['support'], 1):
        distance_sign = "+" if level['distance'] > 0 else ""
        lines.append(f"{i}. ${level['level']} ({distance_sign}{level['distance']}) "
                     f"[Score: {level['score']}, ATR: {level['distance_atr']}]")
        lines.append(f"   Tags: {', '.join(level['tags'])}")
    lines.append("")

    # Major Historical Levels (NEW!)
    if 'major_historical_levels' in result:
        lines.append("📚 MAJOR HISTORICAL LEVELS")
        lines.append("-" * 28)

        # Historical Resistance
        if result['major_historical_levels']['resistance']:
            lines.append("🔴 Historical Resistance:")
            for i, level in enumerate(result['major_historical_levels']['resistance'], 1):
                distance_sign = "+" if level['distance'] > 0 else ""
                lines.append(f"   {i}. ${level['level']} ({distance_sign}{level['distance']}) "
                             f"[Score: {level['score']}, ATR: {level['distance_atr']}]")
                # Show key tags (filter out date tags for readability)
                key_tags = [tag for tag in level['tags'] if not tag.startswith('date_')]
                lines.append(f"      Tags: {', '.join(key_tags[:3])}")

        # Historical Support
        if result['major_historical_levels']['support']:
            lines.append("🟢 Historical Support:")
            for i, level in enumerate(result['major_historical_levels']['support'], 1):
                distance_sign = "+" if level['distance'] > 0 else ""
                lines.append(f"   {i}. ${level['level']} ({distance_sign}{level['distance']}) "
                             f"[Score: {level['score']}, ATR: {level['distance_atr']}]")
                # Show key tags (filter out date tags for readability)
                key_tags = [tag for tag in level['tags'] if not tag.startswith('date_')]
                lines.append(f"      Tags: {', '.join(key_tags[:3])}")
        lines.append("")

    # Parameters
    lines.append("⚙️  PARAMETERS")
    lines.append("-" * 12)
    params = result['meta']['params']
    lines.append(f"Merge tolerance: {params['merge_bps']} bps")
    lines.append(f"Premarket: {params['premarket']}")
    lines.append(f"RTH: {params['rth']}")
    lines.append(f"HTF timeframes: {', '.join(params['htf_timeframes'])}")

    return "\n".join(lines)


def main():
    """Main CLI function"""
    args = parse_arguments()

    # Validate file exists
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"📂 Loading data from: {file_path}")
        print(f"⏰ As-of timestamp: {args.asof}")
        print(f"🏷️  Symbol: {args.symbol}")
        print()

    try:
        # Detect levels
        result = detect_levels_from_file(
            file_path=str(file_path),
            asof_str=args.asof,
            symbol=args.symbol,
            merge_bps=args.merge_bps,
            premarket_window=args.premarket,
            rth_window=args.rth,
            htf_timeframes=args.htf_timeframes,
            swing_window=args.swing_window,
            atr_period=args.atr_period,
            output_file= args.output_file,
        )

        # Format output
        if args.output == 'json':
            output_text = json.dumps(result, indent=2)
        else:
            output_text = format_pretty_output(result)

        # Write output
        if args.output_file:
            output_path = Path(args.output_file)
            # output_path.write_text(output_text)
            if args.verbose:
                print(f"✅ Results saved to: {output_path}")
        else:
            print(output_text)

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()