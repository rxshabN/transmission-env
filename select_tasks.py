#!/usr/bin/env python3
"""
Filter JSON objects by task IDs.

Usage:
    python filter_tasks.py <json_file> <task_id1> <task_id2> ...
    python filter_tasks.py <json_file> --ids-file <file_with_ids>

Examples:
    python filter_tasks.py tasks.json tekton-01f1039 tekton-0fa0994
    python filter_tasks.py tasks.json --ids-file task_ids.txt
    python filter_tasks.py tasks.json tekton-01f1039 -o custom_output.json
    python filter_tasks.py tasks.json tekton-01f1039 --stdout  # print to terminal instead

Output:
    By default, writes to 'filtered_tasks.json' with pretty formatting.
"""

import json
import argparse
import sys
from pathlib import Path


def load_json(filepath: str) -> list | dict:
    """Load and parse a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def filter_by_task_ids(data: list | dict, task_ids: set, id_field: str = "id") -> list:
    """
    Filter JSON objects that match the given task IDs.
    
    Args:
        data: The JSON data (either a list of objects or a dict with a list)
        task_ids: Set of task IDs to filter by
        id_field: The field name containing the task ID (default: "id")
    
    Returns:
        List of matching objects
    """
    # If data is a dict, try common patterns for where the list might be
    if isinstance(data, dict):
        # Check common keys that might contain the task list
        for key in ["tasks", "items", "results", "data"]:
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # If no common key found, check if any value is a list
            for value in data.values():
                if isinstance(value, list):
                    data = value
                    break
    
    if not isinstance(data, list):
        print(f"Warning: Could not find a list of objects in the JSON file", file=sys.stderr)
        return []
    
    # Filter objects whose id field matches one of the task IDs
    matches = []
    for obj in data:
        if isinstance(obj, dict):
            obj_id = obj.get(id_field) or obj.get("task_id") or obj.get("taskId")
            if obj_id in task_ids:
                matches.append(obj)
    
    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Filter JSON objects by task IDs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("json_file", help="Path to the JSON file to filter")
    parser.add_argument("task_ids", nargs="*", help="Task IDs to filter by")
    parser.add_argument("--ids-file", "-f", help="File containing task IDs (one per line)")
    parser.add_argument("--id-field", "-i", default="id", help="Field name for task ID (default: id)")
    parser.add_argument("--output", "-o", default="tasks_for_testing.json", help="Output file (default: filtered_tasks.json)")
    parser.add_argument("--pretty", "-p", action="store_true", default=True, help="Pretty print JSON output (default: True)")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of file")
    
    args = parser.parse_args()
    
    # Collect task IDs from arguments and/or file
    task_ids = set(args.task_ids) if args.task_ids else set()
    
    if args.ids_file:
        ids_path = Path(args.ids_file)
        if ids_path.exists():
            with open(ids_path) as f:
                for line in f:
                    line = line.strip()
                    if line:  # Skip empty lines
                        task_ids.add(line)
        else:
            print(f"Error: IDs file not found: {args.ids_file}", file=sys.stderr)
            sys.exit(1)
    
    if not task_ids:
        print("Error: No task IDs provided. Use positional args or --ids-file", file=sys.stderr)
        sys.exit(1)
    
    # Load and filter the JSON
    try:
        data = load_json(args.json_file)
    except FileNotFoundError:
        print(f"Error: JSON file not found: {args.json_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.json_file}: {e}", file=sys.stderr)
        sys.exit(1)
    
    matches = filter_by_task_ids(data, task_ids, args.id_field)
    
    # Output results
    indent = 2 if args.pretty else None
    output_json = json.dumps(matches, indent=indent)
    
    if args.stdout:
        print(output_json)
    else:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Wrote {len(matches)} matching objects to {args.output}")
    
    print(f"Found {len(matches)}/{len(task_ids)} requested task IDs")


if __name__ == "__main__":
    main()