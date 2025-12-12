import json
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

INPUT_FILE = "hud_tasks.json"
OUTPUT_FILE = "src/hud_controller/extractors/transmission_tasks.py"

def generate_tasks():
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    try:
        with open(INPUT_FILE, "r") as f:
            tasks = json.load(f)
        logger.info(f"Loaded {len(tasks)} tasks from {INPUT_FILE}")
    except Exception as e:
        logger.error(f"Failed to load tasks: {e}")
        return

    output_code = """import logging
from hud_controller.spec import EnvironmentState, Grade, problem
from hud_controller.graders import AgentPatchGrader

logger = logging.getLogger(__name__)

# AUTOMATICALLY GENERATED FROM hud_tasks.json
"""

    for task in tasks:
        func_name = task['task_id'].replace("-", "_")
        safe_msg = task['message'].replace('"', "'").replace('\n', ' ')
        
        files_list = "\\n".join([f"  - {f}" for f in task.get('files', [])])
        
        description = f"""
Task: {task['task_id']}
Bug: {safe_msg}

Files to Modify:
{files_list}

Instructions:
1. Examine the source files in /home/ubuntu/repo/
2. Read the tests in /home/ubuntu/repo/tests/ to understand expected behavior.
3. Modify the source files to fix the bug.
4. Once you're confident with all your fixes, you can opt to create a summary of the changes made (do this once only).
5. Call the `evaluate_tool()` grader (`grade_problem`) to test your changes and evaluate your score.

CRITICAL RULES (READ CAREFULLY BEFORE BEGINNING):
- NO MASSIVE OUTPUT: Do NOT print 100+ lines. Use `head` to limit output.
- DIRECT EDITING: Use `str_replace_editor` to edit files directly.
"""

        task_code = f"""
@problem(
    id="{task['task_id']}",
    description=\"\"\"
{description}
    \"\"\",
    hints=[],
    difficulty="hard",
    task_type="coding",
    review_level="no-review",
    base="{task['buggy_commit']}",
    test="{task['golden_commit']}", 
    golden="{task['golden_commit']}",
)
def {func_name}(state: EnvironmentState) -> Grade:
    return Grade.from_subscores([
        AgentPatchGrader.grade(
            state=state,
            weight=1.0,
            base="{task['buggy_commit']}",
            test="{task['golden_commit']}", 
            golden="{task['golden_commit']}",
            jest_test_files={json.dumps(task['files'])}, 
        )
    ])
"""
        output_code += task_code

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output_code)

    logger.info(f"✅ Generated {len(tasks)} tasks in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_tasks()