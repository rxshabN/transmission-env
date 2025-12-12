import git
import json

REPO_PATH = "env/transmission"

def is_test_file(filepath: str) -> bool:
    filepath_lower = filepath.lower()

    if 'tests/' in filepath_lower or 'test/' in filepath_lower:
        return True

    test_patterns = ['_test.cc', '_test.cpp', '_test.h', '-test.cc', '-test.cpp', '-test.h']
    for pattern in test_patterns:
        if filepath_lower.endswith(pattern):
            return True

    return False

def is_source_code_file(filepath: str) -> bool:
    return filepath.endswith(('.cc', '.h', '.cpp', '.c'))

def has_non_test_code_changes(files: list) -> bool:
    for f in files:
        if is_source_code_file(f) and not is_test_file(f):
            return True
    return False

def mine_tasks():    
    try:
        repo = git.Repo(REPO_PATH)
    except Exception as e:
        print(f"❌ Error: Could not open repo at {REPO_PATH}. Error: {e}")
        return

    tasks = []
    
    EXCLUDED_PREFIXES = ["feat", "perf", "chore", "build", "ci", "docs", "style", "test"]

    for commit in repo.iter_commits('main', max_count=17000):
        summary = str(commit.summary).strip().lower()
        msg = str(commit.message).lower()
        
        if any(summary.startswith(p) for p in EXCLUDED_PREFIXES):
            continue

        if any(k in msg for k in ["fix", "resolve", "close", "bug"]):
            
            stats = commit.stats.files
            files = [str(f) for f in stats.keys()]
            
            has_code = any(f.endswith(('.cc', '.h', '.cpp', '.c')) for f in files)
            has_test = any('tests/' in f for f in files)
            
            if has_code and has_test:
                if not has_non_test_code_changes(files):
                    continue

                tasks.append({
                    "task_id": f"transmission-{commit.hexsha[:7]}",
                    "buggy_commit": commit.parents[0].hexsha,
                    "golden_commit": commit.hexsha,
                    "message": commit.summary.strip(),
                    "files": files
                })

    print(f"Found {len(tasks)} valid tasks.")
    
    output_file = "hud_tasks.json"
    with open(output_file, "w") as f:
        json.dump(tasks, f, indent=2)

if __name__ == "__main__":
    mine_tasks()