import argparse
import json
import os
from pathlib import Path

def create_rich_prompt(task):
    files = task.get("files", [])
    files_list = "\n".join([f"- {f}" for f in files]) if files else "See repository"
    
    return f"""## Task: {task['task_id']}

### Bug Description
{task['message']}

### Files to Modify
The following files need to be fixed:
{files_list}

### Your Task
1. Read and understand the bug description above
2. Examine the relevant source files in `/home/ubuntu/repo/`
3. Analyze the test files in `/home/ubuntu/repo/tests/` to understand expected behavior
4. Modify the source files to fix the bug
5. **VERIFY LOCALLY:** You are explicitly ALLOWED and ENCOURAGED to verify your changes locally:
   - Go to build directory
   - Compile: `ninja`
   - Run Tests: `ctest`
6. Once you're confident with all your fixes, you can opt to create a summary of the changes made (do this once only).
7. **SUBMIT:** Call the `evaluate()` grader (`grade_problem`) to test your changes and evaluate your score.

### 🛑 CRITICAL INSTRUCTIONS - READ THESE CAREFULLY BEFORE BEGINNING 🛑

### 1. ONE SHOT SUBMISSION
* **You can only call `evaluate()` ONCE at the end of your coding session.**
* This is your final submission.
* **Do not** use the `grade_problem` to debug. Use local tools (`ninja`, `ctest`) instead.

#### 2. SECURITY & SCOPE
* **ONLY** modify the source files listed above.
* **DO NOT** touch `CMakeLists.txt`, hidden `.git` directories, or build scripts.

### Repository Location
`/home/ubuntu/repo/`
"""

def main():
    parser = argparse.ArgumentParser(description="Generate the benchmark JSON file.")
    parser.add_argument("--image", type=str, help="The HUD Cloud Image ID (from `hud push`).")
    args = parser.parse_args()

    source_file = "hud_tasks.json" 
    
    if not os.path.exists(source_file):
        print(f"❌ Error: {source_file} not found.")
        return

    with open(source_file, "r") as f:
        raw_tasks = json.load(f)

    benchmark_tasks = []
    cwd = Path.cwd().as_posix()

    print(f"Generating benchmark from {source_file}...")

    for t in raw_tasks:
        prompt_text = create_rich_prompt(t)

        if args.image:
            mcp_config = {
                "default": {
                    "url": "https://mcp.hud.ai/v3/mcp",
                    "headers": {
                        "Authorization": "Bearer ${HUD_API_KEY}", 
                        "Mcp-Image": args.image
                    }
                }
            }
        else:
            mcp_config = {
                "local": {
                    "command": "docker",
                    "args": [
                        "run", 
                        "--rm", 
                        "-i", 
                        "--network", "none",
                        "-v", f"{cwd}/src/hud_controller/extractors:/evaluation/src/hud_controller/extractors",
                        "transmission-env:0.1.0"
                    ]
                }
            }

        task = {
            "id": t["task_id"],
            "prompt": prompt_text,
            "mcp_config": mcp_config,
            "setup_tool": {
                "name": "setup_problem",
                "arguments": {"problem_id": t["task_id"]}
            },
            "evaluate_tool": {
                "name": "grade_problem",
                "arguments": {"problem_id": t["task_id"]}
            }
        }
        benchmark_tasks.append(task)

    output_file = "transmission_benchmark.json"
    with open(output_file, "w") as f:
        json.dump(benchmark_tasks, f, indent=2)

    print(f"Successfully generated {output_file}")
    if args.image:
        print(f"Configured for Cloud Image: {args.image}")
    else:
        print(f"Configured for Local Docker")

if __name__ == "__main__":
    main()