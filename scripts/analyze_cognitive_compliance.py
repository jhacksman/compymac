#!/usr/bin/env python3
"""Analyze metacognitive compliance from trace store.

V5: This script analyzes cognitive events captured during agent execution
to generate compliance reports. It helps identify:
- Whether required thinking scenarios were satisfied
- Temptation encounter and resistance rates
- Decision point patterns
- Overall cognitive quality metrics

Usage:
    python scripts/analyze_cognitive_compliance.py <trace_id>
    python scripts/analyze_cognitive_compliance.py --all  # Analyze all traces
    python scripts/analyze_cognitive_compliance.py --recent 10  # Last 10 traces
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compymac.trace_store import TraceStore, create_trace_store


def analyze_compliance(trace_id: str, store: TraceStore) -> dict:
    """Generate compliance report for a single trace.

    Args:
        trace_id: The trace ID to analyze
        store: The TraceStore instance

    Returns:
        Dictionary containing compliance metrics
    """
    # Get cognitive events for this trace
    events = store.get_cognitive_events(trace_id)

    # Categorize events by type
    thinking_events = [e for e in events if e.event_type == "think"]
    temptation_events = [e for e in events if e.event_type == "temptation_awareness"]
    decision_events = [e for e in events if e.event_type == "decision_point"]
    reflection_events = [e for e in events if e.event_type == "reflection"]

    # Check required thinking scenarios
    required_scenarios = [
        "before_claiming_completion",
        "before_advancing_to_fix",
        "before_git_operations",
    ]

    scenario_compliance = {}
    for scenario in required_scenarios:
        satisfied = any(
            scenario in (e.metadata.get("trigger", "") or "")
            for e in thinking_events
        )
        scenario_compliance[scenario] = satisfied

    # Calculate compliance rate
    satisfied_count = sum(1 for v in scenario_compliance.values() if v)
    compliance_rate = satisfied_count / len(required_scenarios) if required_scenarios else 1.0

    # Analyze temptation resistance
    temptation_stats = {
        "total_encountered": len(temptation_events),
        "recognized": sum(1 for e in temptation_events if e.metadata.get("recognized", False)),
        "resisted": sum(1 for e in temptation_events if e.metadata.get("resisted", False)),
    }
    temptation_stats["resistance_rate"] = (
        temptation_stats["resisted"] / temptation_stats["total_encountered"]
        if temptation_stats["total_encountered"] > 0
        else 1.0
    )

    return {
        "trace_id": trace_id,
        "event_counts": {
            "thinking": len(thinking_events),
            "temptation_awareness": len(temptation_events),
            "decision_point": len(decision_events),
            "reflection": len(reflection_events),
            "total": len(events),
        },
        "scenario_compliance": scenario_compliance,
        "compliance_rate": compliance_rate,
        "temptation_stats": temptation_stats,
    }


def print_report(report: dict) -> None:
    """Print a formatted compliance report.

    Args:
        report: The compliance report dictionary
    """
    print(f"\n{'='*60}")
    print(f"Trace: {report['trace_id']}")
    print(f"{'='*60}")

    # Event counts
    counts = report["event_counts"]
    print(f"\nCognitive Events:")
    print(f"  Thinking events: {counts['thinking']}")
    print(f"  Temptation awareness: {counts['temptation_awareness']}")
    print(f"  Decision points: {counts['decision_point']}")
    print(f"  Reflections: {counts['reflection']}")
    print(f"  Total: {counts['total']}")

    # Required scenarios
    print(f"\nRequired Thinking Scenarios:")
    for scenario, satisfied in report["scenario_compliance"].items():
        status = "[PASS]" if satisfied else "[FAIL]"
        print(f"  {status} {scenario}")

    print(f"\nCompliance Rate: {report['compliance_rate']:.1%}")

    # Temptation stats
    stats = report["temptation_stats"]
    print(f"\nTemptation Awareness:")
    print(f"  Encountered: {stats['total_encountered']}")
    print(f"  Recognized: {stats['recognized']}")
    print(f"  Resisted: {stats['resisted']}")
    print(f"  Resistance Rate: {stats['resistance_rate']:.1%}")


def main():
    """Main entry point for the compliance analyzer."""
    parser = argparse.ArgumentParser(
        description="Analyze metacognitive compliance from trace store"
    )
    parser.add_argument(
        "trace_id",
        nargs="?",
        help="Specific trace ID to analyze"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all traces in the store"
    )
    parser.add_argument(
        "--recent",
        type=int,
        metavar="N",
        help="Analyze the N most recent traces"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the trace store database"
    )

    args = parser.parse_args()

    # Create trace store
    store = create_trace_store(db_path=args.db_path)

    if args.trace_id:
        # Analyze single trace
        report = analyze_compliance(args.trace_id, store)
        print_report(report)
    elif args.all or args.recent:
        # Get list of traces
        # Note: This would need a method to list traces - for now, show usage
        print("Batch analysis requires trace listing support.")
        print("Please provide a specific trace_id for now.")
        print("\nUsage: python analyze_cognitive_compliance.py <trace_id>")
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
