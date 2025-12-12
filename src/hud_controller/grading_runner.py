# #!/usr/bin/env python3
# """
# Grading Runner for C++/Transmission Benchmark

# Simplified architecture - builds in place without copying:
# 1. Reset test files from secure git (anti-cheat)
# 2. Run ninja (incremental build)
# 3. Run ctest
# 4. Calculate score

# Since we build directly in /home/ubuntu/repo (same paths as Docker build),
# there's no path mismatch issues and ccache works perfectly.
# """

# import logging
# import os
# import subprocess
# import xml.etree.ElementTree as ET
# from pathlib import Path
# import shutil
# import time

# logger = logging.getLogger(__name__)


# class GradingRunner:
#     """Handles the grading workflow for C++/Transmission tasks."""

#     def __init__(
#         self,
#         base: str,
#         test: str,
#         golden: str,
#         test_files: list[str] | None = None,
#         playwright_test_files: list[str] | None = None,  
#         mocha_test_files: list[str] | None = None,     
#         test_patch_path: str = "/home/ubuntu/test.patch",
#         golden_patch_path: str = "/home/ubuntu/golden.patch",
#         only_server: bool = False,
#     ):
#         self.use_base = base
#         self.use_test = test
#         self.use_golden = golden
#         self.test_patch_path = test_patch_path
#         self.golden_patch_path = golden_patch_path
#         self.test_files = test_files or []
        
#         # Build directly in the agent's repo - no copying needed!
#         self.repo_path = os.environ.get("REPO_PATH", "/home/ubuntu/repo")
#         self.build_dir = Path(self.repo_path) / "build"
#         self.secure_git = os.environ.get("SECURE_GIT_DIR", "/evaluation/secure_git")

#     def _format_junit_xml(self, test_name: str, message: str, stdout: str, stderr: str) -> str:
#         """Generate JUnit XML for error cases (build failure, etc.)"""
#         def escape(s):
#             return (s.replace("&", "&amp;")
#                      .replace("<", "&lt;")
#                      .replace(">", "&gt;")
#                      .replace('"', "&quot;"))
        
#         return f"""<?xml version="1.0" encoding="UTF-8"?>
# <testsuites>
#   <testsuite name="{escape(test_name)}" tests="1" failures="1" errors="0" skipped="0">
#     <testcase classname="{escape(test_name)}" name="test" time="0.0">
#       <failure type="TestFailure">{escape(message)}</failure>
#       <system-out>{escape(stdout[:5000])}</system-out>
#       <system-err>{escape(stderr[:5000])}</system-err>
#     </testcase>
#   </testsuite>
# </testsuites>"""

#     def _calculate_score(self, junit_xml_content: str) -> float:
#         """
#         Calculate score from JUnit XML test results.
        
#         Scoring formula (dense reward for RL):
#         - 0.0:       Build failure
#         - 0.1:       Build success but all tests fail
#         - 0.1 → 1.0: Linear scale based on test pass rate
#         - 1.0:       All tests pass
#         """
#         try:
#             root = ET.fromstring(junit_xml_content)
#             total_tests = 0
#             failures = 0
#             errors = 0
            
#             suites = root.findall('testsuite') if root.tag == 'testsuites' else [root]
            
#             for suite in suites:
#                 tests_attr = suite.get('tests')
#                 if tests_attr:
#                     total_tests += int(tests_attr)
#                     failures += int(suite.get('failures', 0))
#                     errors += int(suite.get('errors', 0))
#                 else:
#                     total_tests += len(suite.findall('testcase'))
#                     failures += len(suite.findall("testcase/failure"))
#                     errors += len(suite.findall("testcase/error"))

#             if total_tests == 0:
#                 logger.warning("No tests found in JUnit XML")
#                 return 0.1

#             passed = total_tests - (failures + errors)
#             pass_rate = passed / total_tests
            
#             score = 0.1 + (0.9 * pass_rate)
            
#             logger.info(f"📊 Test results: {passed}/{total_tests} passed ({pass_rate*100:.1f}%)")
#             return round(score, 4)

#         except ET.ParseError as e:
#             logger.error(f"Failed to parse JUnit XML: {e}")
#             return 0.0

#     def _reset_test_files(self):
#         """
#         Anti-cheat: Reset test files from secure git.
        
#         This prevents agents from modifying test files to make them pass
#         without actually fixing the bug.
#         """
#         if not self.use_golden:
#             return
            
#         logger.info("🛡️ Anti-cheat: Resetting test files from secure source...")
        
#         try:
#             # Extract tests directory from golden commit
#             cmd = (
#                 f"git --git-dir={self.secure_git} archive {self.use_golden} -- tests/ | "
#                 f"tar -x -C {self.repo_path}"
#             )
#             subprocess.run(cmd, shell=True, check=True, capture_output=True)
#             logger.info("✅ Test files reset successfully")
#         except subprocess.CalledProcessError as e:
#             logger.warning(f"⚠️ Could not reset test files: {e}")

#     def _run_build(self) -> tuple[bool, str, str, float]:
    
#         logger.info(f"🔨 Running incremental build...")
        
#         # =======================================================
#         # DIAGNOSTIC PHASE: Understand what ninja plans to do
#         # =======================================================
#         try:
#             # First, do a dry-run to count planned steps
#             logger.info("📋 Running ninja dry-run to analyze build plan...")
#             dry_run = subprocess.run(
#                 ["ninja", "-n"],
#                 cwd=str(self.build_dir),
#                 capture_output=True,
#                 text=True,
#                 timeout=60
#             )
            
#             # Count lines that look like build steps: [1/N] ...
#             build_lines = [l for l in dry_run.stdout.split('\n') if l.strip().startswith('[')]
#             step_count = len(build_lines)
            
#             logger.info(f"📊 Ninja plans to execute {step_count} build steps")
            
#             if step_count == 0:
#                 logger.info("✅ Nothing to rebuild - build is up to date")
#             elif step_count <= 10:
#                 logger.info(f"✅ Incremental build detected ({step_count} steps)")
#                 # Show what will be built
#                 for line in build_lines:
#                     logger.info(f"   → {line}")
#             else:
#                 # This is concerning - might be doing a full rebuild
#                 logger.warning(f"⚠️ HIGH STEP COUNT: {step_count} steps - possible full rebuild!")
#                 logger.warning("First 10 planned steps:")
#                 for line in build_lines[:10]:
#                     logger.warning(f"   → {line}")
                
#                 # Get detailed explanation of WHY ninja is rebuilding
#                 logger.info("🔍 Getting ninja rebuild explanation...")
#                 explain_run = subprocess.run(
#                     ["ninja", "-n", "-d", "explain"],
#                     cwd=str(self.build_dir),
#                     capture_output=True,
#                     text=True,
#                     timeout=60
#                 )
                
#                 # Parse and log the explanation (first 2000 chars)
#                 explain_output = explain_run.stdout[:2000]
#                 logger.warning(f"Ninja explain output:\n{explain_output}")
                
#                 if explain_run.stderr:
#                     logger.warning(f"Ninja explain stderr:\n{explain_run.stderr[:500]}")
            
#             # Check for CMake reconfiguration
#             if "Re-running CMake" in dry_run.stdout or "cmake" in dry_run.stdout.lower():
#                 logger.warning("⚠️ CMake reconfiguration detected! This will be slow.")
                
#         except subprocess.TimeoutExpired:
#             logger.warning("⚠️ Ninja dry-run timed out after 60s")
#         except Exception as e:
#             logger.warning(f"⚠️ Could not run ninja dry-run diagnostic: {e}")
        
#         # =======================================================
#         # CHECK TIMESTAMPS: Are objects newer than sources?
#         # =======================================================
#         try:
#             logger.info("🕐 Checking sample file timestamps...")
            
#             # Find a sample source and object file
#             sample_source = Path(self.repo_path) / "libtransmission" / "net.cc"
#             sample_obj_pattern = "net.cc.o"
            
#             if sample_source.exists():
#                 source_mtime = sample_source.stat().st_mtime
#                 logger.info(f"   Source net.cc mtime: {source_mtime}")
                
#                 # Find the corresponding object file
#                 result = subprocess.run(
#                     ["find", str(self.build_dir), "-name", sample_obj_pattern],
#                     capture_output=True, text=True, timeout=10
#                 )
#                 if result.stdout.strip():
#                     obj_path = Path(result.stdout.strip().split('\n')[0])
#                     if obj_path.exists():
#                         obj_mtime = obj_path.stat().st_mtime
#                         logger.info(f"   Object net.cc.o mtime: {obj_mtime}")
                        
#                         if obj_mtime > source_mtime:
#                             logger.info("   ✅ Object is NEWER than source (good)")
#                         else:
#                             logger.warning("   ❌ Object is OLDER than source (will rebuild!)")
#         except Exception as e:
#             logger.warning(f"⚠️ Could not check timestamps: {e}")
        
#         # =======================================================
#         # ACTUAL BUILD PHASE
#         # =======================================================
#         logger.info("🚀 Starting actual ninja build...")
#         start_time = time.time()
        
#         try:
#             # Use Popen for real-time output logging
#             process = subprocess.Popen(
#                 ["ninja", "-j", str(os.cpu_count() or 2)],
#                 cwd=str(self.build_dir),
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.STDOUT,  # Merge stderr into stdout
#                 text=True
#             )
            
#             output_lines = []
#             last_progress_log = time.time()
            
#             # Read output line by line with timeout handling
#             while True:
#                 # Check if process is still running
#                 retcode = process.poll()
                
#                 # Try to read a line (non-blocking would be better but this works)
#                 try:
#                     if process.stdout is None:
#                         break
#                     line = process.stdout.readline()
#                     if line:
#                         output_lines.append(line)
                        
#                         # Log progress every 10 seconds or on interesting lines
#                         now = time.time()
#                         elapsed = now - start_time
                        
#                         # Always log build step lines
#                         if line.strip().startswith('['):
#                             logger.info(f"   [{elapsed:.0f}s] {line.strip()}")
#                             last_progress_log = now
#                         # Log errors immediately
#                         elif 'error:' in line.lower() or 'fatal:' in line.lower():
#                             logger.error(f"   [{elapsed:.0f}s] {line.strip()}")
#                         # Periodic progress update
#                         elif now - last_progress_log > 30:
#                             logger.info(f"   [{elapsed:.0f}s] Still building...")
#                             last_progress_log = now
                            
#                 except Exception:
#                     pass
                
#                 # Check for completion
#                 if retcode is not None:
#                     # Process finished, read any remaining output
#                     if process.stdout is not None:
#                         remaining = process.stdout.read()
#                         if remaining:
#                             output_lines.append(remaining)
#                     break
                
#                 # Check for timeout (5 minutes)
#                 if time.time() - start_time > 300:
#                     logger.error("❌ Build timeout reached (300s), killing process...")
#                     process.kill()
#                     process.wait()
#                     return False, ''.join(output_lines), "Build timed out after 5 minutes", 300.0
            
#             duration = time.time() - start_time
#             stdout_content = ''.join(output_lines)
#             success = process.returncode == 0
            
#             if success:
#                 logger.info(f"✅ Build successful in {duration:.1f}s")
#                 if duration > 30:
#                     logger.warning(f"⚠️ Build took {duration:.1f}s - may indicate timestamp issues")
#             else:
#                 logger.error(f"❌ Build failed in {duration:.1f}s (exit code {process.returncode})")
#                 # Log last 20 lines of output for debugging
#                 last_lines = stdout_content.strip().split('\n')[-20:]
#                 logger.error("Last 20 lines of build output:")
#                 for line in last_lines:
#                     logger.error(f"   {line}")
                
#             return success, stdout_content, "", duration
            
#         except Exception as e:
#             duration = time.time() - start_time
#             logger.error(f"❌ Build exception after {duration:.1f}s: {e}")
#             return False, "", str(e), duration

#     def _run_tests(self) -> tuple[str, float]:
#         """Run CTest and return JUnit XML output."""
#         logger.info(f"🧪 Running tests...")
#         start_time = time.time()
        
#         try:
#             result = subprocess.run(
#                 [
#                     "ctest",
#                     "--output-junit", "junit_results.xml",
#                     "--output-on-failure",
#                     "-j", str(os.cpu_count() or 2),
#                     "--timeout", "60"
#                 ],
#                 cwd=str(self.build_dir),
#                 capture_output=True,
#                 text=True,
#                 timeout=600
#             )
            
#             duration = time.time() - start_time
#             logger.info(f"Tests completed in {duration:.1f}s (exit code {result.returncode})")
            
#             xml_path = self.build_dir / "junit_results.xml"
#             if xml_path.exists():
#                 with open(xml_path) as f:
#                     return f.read(), duration
#             else:
#                 logger.error("CTest did not generate junit_results.xml")
#                 return self._format_junit_xml(
#                     "CTestError", 
#                     "CTest failed to generate results", 
#                     result.stdout, 
#                     result.stderr
#                 ), duration
                
#         except subprocess.TimeoutExpired:
#             duration = time.time() - start_time
#             logger.error(f"Tests timed out after {duration:.1f}s")
#             return self._format_junit_xml(
#                 "Timeout", 
#                 "Tests timed out after 10 minutes", 
#                 "", ""
#             ), duration

#     def run_grading(self) -> tuple[float, dict]:
#         """
#         Run the complete grading workflow.
        
#         Simplified flow (no copying needed):
#         1. Reset test files (anti-cheat)
#         2. Build (incremental)
#         3. Test
#         4. Score
#         """
#         total_start = time.time()
        
#         logger.info("=" * 60)
#         logger.info("🎯 GRADING STARTED")
#         logger.info("=" * 60)

#         try:
#             # Step 1: Anti-cheat - reset test files
#             self._reset_test_files()

#             # Step 2: Apply test patch if exists
#             if os.path.exists(self.test_patch_path):
#                 logger.info("📝 Applying test patch...")
#                 try:
#                     with open(self.test_patch_path) as f:
#                         subprocess.run(
#                             ["git", "apply", "--allow-empty"],
#                             cwd=self.repo_path,
#                             input=f.read().encode("utf-8"),
#                             check=True,
#                             capture_output=True
#                         )
#                 except subprocess.CalledProcessError as e:
#                     logger.warning(f"⚠️ Test patch failed to apply: {e}")

#             # Step 3: Build
#             build_success, build_stdout, build_stderr, build_duration = self._run_build()
            
#             if not build_success:
#                 total_duration = time.time() - total_start
#                 logger.info(f"❌ GRADING FAILED (build error) - Total: {total_duration:.1f}s")
                
#                 xml_content = self._format_junit_xml(
#                     "BuildError",
#                     "Compilation failed. Check your syntax and includes.",
#                     build_stdout,
#                     build_stderr
#                 )
#                 return 0.0, {
#                     "junit": xml_content,
#                     "build_success": False,
#                     "build_duration": build_duration,
#                     "total_duration": total_duration,
#                     "build_stdout": build_stdout[:2000],
#                     "build_stderr": build_stderr[:2000]
#                 }

#             # Step 4: Run tests
#             junit_xml, test_duration = self._run_tests()
            
#             # Step 5: Calculate score
#             score = self._calculate_score(junit_xml)
            
#             total_duration = time.time() - total_start
            
#             logger.info("=" * 60)
#             logger.info(f"✅ GRADING COMPLETE")
#             logger.info(f"   Score: {score:.4f}")
#             logger.info(f"   Build: {build_duration:.1f}s")
#             logger.info(f"   Tests: {test_duration:.1f}s")
#             logger.info(f"   Total: {total_duration:.1f}s")
#             logger.info("=" * 60)

#             return score, {
#                 "junit": junit_xml,
#                 "build_success": True,
#                 "build_duration": build_duration,
#                 "test_duration": test_duration,
#                 "total_duration": total_duration
#             }

#         except subprocess.TimeoutExpired as e:
#             total_duration = time.time() - total_start
#             logger.error(f"Timeout during grading: {e}")
#             xml_content = self._format_junit_xml("Timeout", str(e), "", "")
#             return 0.0, {"junit": xml_content, "error": "timeout", "total_duration": total_duration}
            
#         except Exception as e:
#             total_duration = time.time() - total_start
#             logger.exception(f"Grading failed: {e}")
#             xml_content = self._format_junit_xml("GradingError", str(e), "", "")
#             return 0.0, {"junit": xml_content, "error": str(e), "total_duration": total_duration}

#!/usr/bin/env python3

import logging
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class GradingRunner:
    """Handles the grading workflow for C++/Transmission tasks."""

    def __init__(
        self,
        base: str,
        test: str,
        golden: str,
        test_files: list[str] | None = None,
        test_patch_path: str = "/home/ubuntu/test.patch",
        golden_patch_path: str = "/home/ubuntu/golden.patch",
        only_server: bool = False,
        playwright_test_files: list[str] | None = None,
        mocha_test_files: list[str] | None = None,
    ):
        self.use_base = base
        self.use_test = test
        self.use_golden = golden
        self.test_patch_path = test_patch_path
        self.golden_patch_path = golden_patch_path
        self.test_files = test_files or []
        
        self.repo_path = os.environ.get("REPO_PATH", "/home/ubuntu/repo")
        self.build_dir = Path(self.repo_path) / "build"
        self.secure_git = os.environ.get("SECURE_GIT_DIR", "/evaluation/secure_git/repo.git")

    def _format_junit_xml(self, test_name: str, message: str, stdout: str, stderr: str) -> str:
        """Generate JUnit XML for error cases."""
        def escape(s):
            return (s.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace('"', "&quot;"))
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="{escape(test_name)}" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="{escape(test_name)}" name="test" time="0.0">
      <failure type="TestFailure">{escape(message)}</failure>
      <system-out>{escape(stdout[:5000])}</system-out>
      <system-err>{escape(stderr[:5000])}</system-err>
    </testcase>
  </testsuite>
</testsuites>"""

    def _reset_test_files(self):
        if not self.use_golden: return
        logger.info("Anti-cheat: Resetting test files...")
        try:
            cmd = f"git --git-dir={self.secure_git} archive {self.use_golden} -- tests/ | tar -x -C {self.repo_path}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            logger.info("Test files reset successfully")
        except subprocess.CalledProcessError:
            pass

    def _run_tests(self) -> tuple[str, float, float]:
        start_time = time.time()
        
        logger.info("Starting Build (Ninja)...")
        try:
            build_proc = subprocess.run(
                ["ninja", "-j", str(os.cpu_count() or 2)],
                cwd=str(self.build_dir),
                capture_output=True,
                text=True,
            )
            
            if build_proc.returncode != 0:
                logger.error("Build Failed")
                duration = time.time() - start_time
                error_xml = self._format_junit_xml("BuildFailure", "Compilation failed", build_proc.stdout, build_proc.stderr)
                return error_xml, duration, 0.0
                
        except subprocess.TimeoutExpired:
            logger.error("Build Timed Out")
            duration = time.time() - start_time
            error_xml = self._format_junit_xml("BuildTimeout", "Build timed out after 300s", "", "")
            return error_xml, duration, 0.0

        # 2. Test Phase (CTest)
        logger.info("Running Tests (CTest)...")
        try:
            test_proc = subprocess.run(
                [
                    "ctest",
                    "--output-junit", "junit_results.xml",
                    "--output-on-failure",
                    "-j", str(os.cpu_count() or 2),
                ],
                cwd=str(self.build_dir),
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            logger.error("Tests Timed Out")
            duration = time.time() - start_time
            error_xml = self._format_junit_xml("TestTimeout", "Tests timed out after 600s", "", "")
            return error_xml, duration, 0.0

        duration = time.time() - start_time
        
        # 3. Scoring Phase
        xml_path = self.build_dir / "junit_results.xml"
        final_xml = ""
        score = 0.0

        if xml_path.exists():
            try:
                with open(xml_path) as f:
                    final_xml = f.read()
                
                # Calculate score based on pass rate
                root = ET.fromstring(final_xml)
                total_tests = 0
                failures = 0
                errors = 0
                
                suites = root.findall('testsuite') if root.tag == 'testsuites' else [root]
                for suite in suites:
                    # Try getting attributes first
                    t_attr = suite.get('tests')
                    if t_attr:
                        total_tests += int(t_attr)
                        failures += int(suite.get('failures', 0))
                        errors += int(suite.get('errors', 0))
                    else:
                        # Fallback to counting children
                        total_tests += len(suite.findall('testcase'))
                        failures += len(suite.findall("testcase/failure"))
                        errors += len(suite.findall("testcase/error"))

                if total_tests > 0:
                    passed = total_tests - (failures + errors)
                    pass_rate = passed / total_tests
                    # Linear scoring: 0.1 (compile success) to 1.0 (all pass)
                    score = 0.1 + (0.9 * pass_rate)
                    logger.info(f"Test results: {passed}/{total_tests} passed. Score: {score:.2f}")
                else:
                    # Compiled but no tests ran?
                    score = 0.1
            except ET.ParseError:
                logger.error("Failed to parse JUnit XML")
                score = 0.0
                final_xml = self._format_junit_xml("XMLParseError", "Generated XML was invalid", test_proc.stdout, test_proc.stderr)
        else:
            logger.error("No JUnit XML generated")
            score = 0.0
            final_xml = self._format_junit_xml("CTestError", "CTest failed to generate results", test_proc.stdout, test_proc.stderr)

        return final_xml, duration, score

    def run_grading(self) -> tuple[float, dict]:
        """Run the complete grading workflow."""
        total_start = time.time()
        logger.info("=" * 60)
        logger.info("GRADING STARTED")
        logger.info("=" * 60)

        try:
            self._reset_test_files()

            if os.path.exists(self.test_patch_path):
                subprocess.run(["git", "apply", "--allow-empty"], cwd=self.repo_path, input=open(self.test_patch_path, 'rb').read(), check=False)

            junit_xml, test_duration, score = self._run_tests()
                        
            total_duration = time.time() - total_start
            
            logger.info("=" * 60)
            logger.info(f"GRADING COMPLETE")
            logger.info(f"   Score: {score:.4f}")
            logger.info("=" * 60)

            return score, {
                "junit": junit_xml,
                "test_duration": test_duration,
                "total_duration": total_duration
            }
            
        except Exception as e:
            total_duration = time.time() - total_start
            logger.exception(f"Grading failed: {e}")
            return 0.0, {"error": str(e)}