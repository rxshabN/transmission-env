import glob
import os
from typing import Any, Dict, Literal, Tuple, Union

from hud_controller.grading_runner import GradingRunner
from hud_controller.spec import EnvironmentState, Grader


class DefaultTestCasesPassingGrader(Grader):
    """
    A grader that checks if the all test cases are passing, within the codebase.
    """
    name = "DefaultTestCasesPassingGrader"

    @classmethod
    def compute_score(cls, state: EnvironmentState) -> float:
        import subprocess
        if subprocess.run(["true"]).returncode == 0:
            return 1.0
        return 0.0


class AgentPatchGrader(Grader):
    """
    A grader that tests agent patches by applying them and running tests.
    """
    name = "AgentPatchGrader"

    @classmethod
    def compute_score(
        cls,
        state: EnvironmentState,
        base: str,
        test: str,
        golden: str,
        jest_test_files: list[str] | None = None,
        playwright_test_files: list[str] | None = None,
        mocha_test_files: list[str] | None = None,
        test_files: list[str] | None = None,
        **kwargs,
    ) -> tuple[float, dict]:
        """
        Compute a score based on whether the agent patch fixes the issue.
        """
        from .app import ONLY_SERVER

        actual_files_to_run = test_files or jest_test_files or []

        runner = GradingRunner(
            base=base,
            test=test,
            golden=golden,
            playwright_test_files=playwright_test_files,
            mocha_test_files=mocha_test_files,
            test_files=actual_files_to_run,
            only_server=ONLY_SERVER,
        )

        score, metadata = runner.run_grading()
        
        return (score, metadata)


class CodeFileGrader(Grader):
    """Disabled grader (Database removed)"""
    name = "CodeFileGrader"
    @classmethod
    def compute_score(cls, state: EnvironmentState, **kwargs) -> float:
        return 0.0


class FileSystemGrader(Grader):
    """Checks file existence/content."""
    name = "FileSystemGrader"

    @classmethod
    def compute_score(
        cls, state: EnvironmentState, file_path: str, content_check: str | None = None, **kwargs
    ) -> Union[float, Tuple[float, Dict[str, Any]]]:
        import os
        metadata = {
            "file_path": file_path,
            "file_exists": False,
            "content_check": content_check,
            "content_found": False,
        }

        if not os.path.exists(file_path):
            return (0.0, metadata)

        metadata["file_exists"] = True

        if content_check is None:
            return (1.0, metadata)

        try:
            with open(file_path, "r") as f:
                content = f.read()
                metadata["file_size"] = len(content)
                if content_check in content:
                    metadata["content_found"] = True
                    return (1.0, metadata)
        except Exception as e:
            metadata["error"] = str(e)
            return (0.0, metadata)

        return (0.0, metadata)


class DirectoryGrader(Grader):
    """Checks directory existence."""
    name = "DirectoryGrader"

    @classmethod
    def compute_score(
        cls, state: EnvironmentState, dir_path: str, file_count: int | None = None, file_pattern: str | None = None, **kwargs
    ) -> float:
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            return 0.0

        if file_count is not None:
            files = os.listdir(dir_path)
            if len(files) < file_count:
                return 0.0

        if file_pattern:
            pattern = os.path.join(dir_path, file_pattern)
            matching_files = glob.glob(pattern)
            if not matching_files:
                return 0.0

        return 1.0