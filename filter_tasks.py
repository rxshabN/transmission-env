import json
import re
import os

def filter_transmission_tasks():
    # Configuration
    id_file_path = 'transmission_ids.txt'
    json_file_path = 'hud_tasks.json'
    output_filename = 'hud_final_tasks.json'
    prefix = 'transmission'

    # 1. Load Valid IDs
    valid_ids = set()
    pattern = rf'{re.escape(prefix)}-[a-zA-Z0-9]+'
    
    try:
        with open(id_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            found_ids = re.findall(pattern, content)
            valid_ids.update(found_ids)
        print(f"Loaded {len(valid_ids)} valid IDs from '{id_file_path}'.")
    except FileNotFoundError:
        print(f"Error: The ID file '{id_file_path}' was not found.")
        return

    # 2. Load JSON tasks
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The JSON file '{json_file_path}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON.")
        return

    # 3. Filter tasks
    filtered_tasks = [task for task in data if task.get('task_id') in valid_ids]
    
    print(f"Filtered out {len(data) - len(filtered_tasks)} tasks. Keeping {len(filtered_tasks)} tasks.")

    # 4. Save Output
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(filtered_tasks, f, indent=2)
        print(f"[SUCCESS] Saved to: {os.path.abspath(output_filename)}")
    except IOError as e:
        print(f"Error writing file: {e}")

if __name__ == "__main__":
    filter_transmission_tasks()