# import asyncio
# import logging
# import os
# import subprocess
# import shutil
# from pathlib import Path
# from typing import Any

# try:
#     from .manual_dinit import ServiceLoader, SimpleDinit
# except ImportError:
#     ServiceLoader = None
#     SimpleDinit = None

# logger = logging.getLogger(__name__)

# TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]
# XFCE_STARTUP_DELAY = 0
# CHROMIUM_STARTUP_DELAY = 0


# def touch_build_artifacts(build_dir: Path) -> int:
#     """
#     Update timestamps on all build artifacts to be NEWER than source files.
    
#     After extracting source files at the buggy commit, they have "now" timestamps.
#     The .o files have timestamps from Docker build time (older).
    
#     Without this fix: ninja sees source (newer) > object (older) → rebuilds everything
#     With this fix: ninja sees object (now+1s) > source (now) → skips rebuild
    
#     Only files the agent actually modifies will be newer and get rebuilt.
    
#     Returns:
#         Number of files touched
#     """
#     logger.info("⏰ Updating build artifact timestamps...")
    
#     # We touch with a timestamp slightly in the future to guarantee they're "newer"
#     import time
#     future_time = time.time() + 2  # 2 seconds in the future
    
#     touched_count = 0
    
#     # File extensions that ninja tracks
#     extensions_to_touch = ['.o', '.d', '.a', '.so', '.stamp']
    
#     for ext in extensions_to_touch:
#         for filepath in build_dir.rglob(f'*{ext}'):
#             try:
#                 os.utime(filepath, (future_time, future_time))
#                 touched_count += 1
#             except Exception as e:
#                 logger.warning(f"Could not touch {filepath}: {e}")
    
#     # Touch ninja and cmake files
#     important_files = [
#         'build.ninja', 'rules.ninja', 'CMakeCache.txt', 
#         'cmake_install.cmake', '.ninja_deps', '.ninja_log'
#     ]
    
#     for filename in important_files:
#         for filepath in build_dir.rglob(filename):
#             try:
#                 os.utime(filepath, (future_time, future_time))
#                 touched_count += 1
#             except Exception:
#                 pass
    
#     # Touch everything in CMakeFiles directories
#     for cmake_dir in build_dir.rglob('CMakeFiles'):
#         if cmake_dir.is_dir():
#             for filepath in cmake_dir.rglob('*'):
#                 if filepath.is_file():
#                     try:
#                         os.utime(filepath, (future_time, future_time))
#                         touched_count += 1
#                     except Exception:
#                         pass
    
#     logger.info(f"✅ Updated timestamps on {touched_count} build artifacts")
#     return touched_count


# async def start_dinit():
#     """
#     Starts background services (GUI, etc). 
#     For Headless C++ tasks, we skip this if /etc/dinit.d doesn't exist.
#     """
#     dinit_dir = Path("/etc/dinit.d")
    
#     if not dinit_dir.exists():
#         logger.info("ℹ️ /etc/dinit.d not found. Skipping GUI service startup.")
#         return

#     if ServiceLoader is None:
#         logger.warning("manual_dinit module not found. Skipping services.")
#         return

#     logger.info("Starting dinit services...")
#     loader = ServiceLoader(dinit_dir)
#     services = loader.load_all()
#     if services:
#         engine = SimpleDinit(services)
#         engine.start("boot")
#     else:
#         logger.info("No services found to start.")


# def subprocess_run(cmd, cwd=None, check=True, shell=False):
#     """Helper to run shell commands with logging."""
#     try:
#         result = subprocess.run(
#             cmd, cwd=cwd, check=check, capture_output=True, text=True, shell=shell
#         )
#         return result
#     except subprocess.CalledProcessError as e:
#         logger.error(f"Command failed: {cmd}\nStderr: {e.stderr}\nStdout: {e.stdout}")
#         raise e


# def setup_codebase(base: str, test: str, golden: str):
#     """
#     Set up the codebase for the agent to work on.
    
#     Architecture:
#     - /home/ubuntu/repo is pre-built at HEAD during Docker build
#     - We extract source files at the buggy commit using git archive
#     - Build artifacts (.o files) remain from HEAD build
#     - We touch timestamps so ninja knows objects are "up to date"
#     - Agent modifies source → only those files get rebuilt
    
#     Anti-cheat:
#     - .git directory was moved to /evaluation/secure_git (root-only)
#     - Agent cannot access git history
#     - Agent cannot see the golden/fix commit
#     """
#     repo_path = os.environ.get("REPO_PATH", "/home/ubuntu/repo")
#     secure_git = os.environ.get("SECURE_GIT_DIR", "/evaluation/secure_git")
#     build_dir = Path(repo_path) / "build"
    
#     logger.info("=" * 50)
#     logger.info(f"🔧 SETTING UP TASK")
#     logger.info(f"   Buggy commit: {base[:8]}")
#     logger.info(f"   Golden commit: {golden[:8] if golden else 'N/A'}")
#     logger.info("=" * 50)
    
#     try:
#         # =================================================================
#         # Step 1: Extract source files at buggy commit
#         # This overwrites source files but preserves the build/ directory
#         # =================================================================
#         logger.info(f"📦 Extracting source at buggy commit {base[:8]}...")
        
#         # Use git archive to extract files (excludes .git)
#         # We extract everything except the build directory
#         archive_cmd = f"git --git-dir={secure_git} archive {base} | tar -x -C {repo_path}"
#         subprocess_run(archive_cmd, shell=True)
        
#         # =================================================================
#         # Step 2: Update submodules to match buggy commit
#         # Submodules might point to different commits at different points in history
#         # =================================================================
#         logger.info("🔄 Extracting submodules at buggy commit...")
        
#         # Get list of submodules and their commits at the buggy commit
#         try:
#             # This gets the submodule state at the buggy commit
#             ls_tree_cmd = f"git --git-dir={secure_git} ls-tree -r {base}"
#             result = subprocess_run(ls_tree_cmd, shell=True)
            
#             for line in result.stdout.strip().split('\n'):
#                 if not line:
#                     continue
#                 parts = line.split()
#                 if len(parts) >= 4 and parts[1] == 'commit':
#                     # This is a submodule reference
#                     submodule_commit = parts[2]
#                     submodule_path = parts[3]
                    
#                     # Check if this submodule exists in our third-party
#                     full_submodule_path = Path(repo_path) / submodule_path
#                     if full_submodule_path.exists() and 'third-party' in submodule_path:
#                         logger.debug(f"   Submodule {submodule_path}: {submodule_commit[:8]}")
#                         # For most bug fixes, submodules don't change, so we skip this
#                         # If needed, we could extract specific submodule states here
#         except Exception as e:
#             logger.warning(f"Could not process submodules: {e}")
        
#         # =================================================================
#         # Step 3: Touch build artifacts
#         # Make .o files "newer" than source files so ninja skips rebuilding
#         # =================================================================
#         if build_dir.exists():
#             touch_build_artifacts(build_dir)
#         else:
#             logger.warning("⚠️ Build directory not found - grading will do full build")
        
#         # =================================================================
#         # Step 4: Inject tests from golden commit
#         # Tests define expected behavior - agent reads these to understand the fix
#         # =================================================================
#         if golden:
#             logger.info(f"💉 Injecting tests from golden commit {golden[:8]}...")
            
#             # Extract only the tests directory from golden commit
#             test_archive_cmd = (
#                 f"git --git-dir={secure_git} archive {golden} -- tests/ 2>/dev/null | "
#                 f"tar -x -C {repo_path} 2>/dev/null || true"
#             )
#             subprocess_run(test_archive_cmd, shell=True)
        
#         # =================================================================
#         # Step 5: Initialize a fresh git repo for agent's use
#         # Agent can use git diff, git status etc. but can't see history
#         # =================================================================
#         logger.info("✨ Initializing clean git repo for agent...")
        
#         # Remove any .git files/directories that might have been extracted
#         for item in Path(repo_path).rglob('.git'):
#             if item.is_dir():
#                 shutil.rmtree(item)
#             elif item.is_file():
#                 item.unlink()
        
#         # Initialize fresh repo
#         subprocess_run(["git", "init"], cwd=repo_path)
#         subprocess_run(["git", "add", "."], cwd=repo_path)
#         subprocess_run(
#             ["git", "commit", "-m", "Initial state (contains bug to fix)"],
#             cwd=repo_path
#         )
        
#         # =================================================================
#         # Step 6: Set ownership
#         # =================================================================
#         subprocess_run(["chown", "-R", "ubuntu:ubuntu", repo_path])
        
#         logger.info("=" * 50)
#         logger.info("✅ SETUP COMPLETE")
#         logger.info("=" * 50)
#         logger.info(f"   Workspace: {repo_path}")
#         logger.info("   ")
#         logger.info("   Agent instructions:")
#         logger.info("   • Read tests in tests/ to understand expected behavior")
#         logger.info("   • Modify source files to fix the bug")
#         logger.info("   • Call evaluate() when done")
#         logger.info("   • DO NOT build or run tests manually")
        
#     except Exception as e:
#         logger.error(f"Setup failed: {e}")
#         raise


# def start_dinit_script():
#     """Entry point for the start_dinit script."""
#     asyncio.run(start_dinit())


# async def default_setup(template: dict[str, Any]) -> None:
#     """Default setup function that initializes the environment for coding tasks."""
#     logger.info("=== ENVIRONMENT SETUP ===")
#     logger.info(f"Task: {template.get('id', 'unknown')}")

#     await start_dinit()

#     await asyncio.to_thread(
#         setup_codebase,
#         base=template["base"],
#         test=template["test"],
#         golden=template["golden"],
#     )
    
#     logger.info("Environment ready for agent.")

import asyncio
import logging
import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import Any

try:
    from .manual_dinit import ServiceLoader, SimpleDinit
except ImportError:
    ServiceLoader = None
    SimpleDinit = None

logger = logging.getLogger(__name__)

def subprocess_run(cmd, cwd=None, check=True, shell=False):
    """Helper to run shell commands with logging."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=check, capture_output=True, text=True, shell=shell
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd}\nStderr: {e.stderr}\nStdout: {e.stdout}")
        raise e

def touch_build_artifacts(build_dir: Path) -> int:
    """
    Update timestamps on all build artifacts to be NEWER than source files.
    Required for C++ incremental builds to prevent full rebuilds after git archive.
    """
    logger.info("⏰ Updating build artifact timestamps...")
    
    future_time = time.time() + 2
    touched_count = 0
    
    extensions = ['.o', '.d', '.a', '.so', '.stamp']
    important_files = [
        'build.ninja', 'rules.ninja', 'CMakeCache.txt', 
        'cmake_install.cmake', '.ninja_deps', '.ninja_log'
    ]
    
    for ext in extensions:
        for filepath in build_dir.rglob(f'*{ext}'):
            try:
                os.utime(filepath, (future_time, future_time))
                touched_count += 1
            except Exception:
                pass
    
    for filename in important_files:
        for filepath in build_dir.rglob(filename):
            try:
                os.utime(filepath, (future_time, future_time))
                touched_count += 1
            except Exception:
                pass

    # Touch everything in CMakeFiles
    for cmake_dir in build_dir.rglob('CMakeFiles'):
        if cmake_dir.is_dir():
            for filepath in cmake_dir.rglob('*'):
                if filepath.is_file():
                    try:
                        os.utime(filepath, (future_time, future_time))
                        touched_count += 1
                    except Exception:
                        pass
    
    logger.info(f"✅ Updated timestamps on {touched_count} build artifacts")
    return touched_count

async def start_dinit():
    """
    Starts background services (GUI, etc) if configured.
    """
    dinit_dir = Path("/etc/dinit.d")
    
    if not dinit_dir.exists():
        logger.info("/etc/dinit.d not found. Skipping service startup.")
        return

    if ServiceLoader is None:
        logger.warning("manual_dinit module not found. Skipping services.")
        return

    logger.info("Starting dinit services...")
    loader = ServiceLoader(dinit_dir)
    services = loader.load_all()
    if services:
        engine = SimpleDinit(services)
        engine.start("boot")
    else:
        logger.info("No services found to start.")

def setup_codebase(base: str, test: str, golden: str):
    repo_path = os.environ.get("REPO_PATH", "/home/ubuntu/repo")
    secure_git = os.environ.get("SECURE_GIT_DIR", "/evaluation/secure_git/repo.git")
    build_dir = Path(repo_path) / "build"
    
    logger.info("=" * 50)
    logger.info(f"SETTING UP C++ TASK")
    logger.info(f"   Buggy commit: {base[:8]}")
    logger.info(f"   Golden commit: {golden[:8] if golden else 'N/A'}")
    logger.info("=" * 50)
    
    try:
        logger.info("Cleaning workspace (preserving build artifacts)...")
        if os.path.exists(repo_path):
            for item in Path(repo_path).iterdir():
                if item.name in ['build', 'third-party']:
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            os.makedirs(repo_path, exist_ok=True)

        logger.info(f"Extracting source at buggy commit {base[:8]}...")
        
        archive_cmd = f"git --git-dir={secure_git} archive {base} | tar -x -C {repo_path}"
        subprocess_run(archive_cmd, shell=True)
        
        if build_dir.exists():
            touch_build_artifacts(build_dir)
        else:
            logger.warning("⚠️ Build directory not found - expect full rebuild")
        
        if golden:
            logger.info(f"💉 Injecting tests from golden commit {golden[:8]}...")
            test_archive_cmd = (
                f"git --git-dir={secure_git} archive {golden} -- tests/ 2>/dev/null | "
                f"tar -x -C {repo_path} 2>/dev/null || true"
            )
            subprocess_run(test_archive_cmd, shell=True)
        
        logger.info("Initializing clean git repo for agent...")
        
        for item in Path(repo_path).rglob('.git'):
            if item.is_dir():
                shutil.rmtree(item)
            elif item.is_file():
                item.unlink()
        
        subprocess_run(["git", "init"], cwd=repo_path)
        subprocess_run(["git", "add", "."], cwd=repo_path)
        subprocess_run(
            ["git", "commit", "-m", "Initial state (contains bug to fix)"],
            cwd=repo_path
        )
        
        subprocess_run(["chown", "-R", "ubuntu:ubuntu", repo_path])
        
        logger.info("=" * 50)
        logger.info("SETUP COMPLETE")
        logger.info("=" * 50)
        logger.info(f"   Workspace: {repo_path}")
        logger.info("   ")
        logger.info("   Agent instructions:")
        logger.info("   • Read tests in tests/ to understand expected behavior")
        logger.info("   • Modify source files to fix the bug")
        logger.info("   • Call evaluate() when done")
        logger.info("   • DO NOT build manually (use evaluate)")
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise

async def default_setup(template: dict[str, Any]) -> None:
    """Default setup function that initializes the environment for coding tasks."""
    logger.info("=== ENVIRONMENT SETUP ===")
    logger.info(f"Task: {template.get('id', 'unknown')}")

    await start_dinit()

    await asyncio.to_thread(
        setup_codebase,
        base=template["base"],
        test=template["test"],
        golden=template["golden"],
    )
    
    logger.info("Environment ready for agent.")