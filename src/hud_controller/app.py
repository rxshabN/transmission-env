import asyncio
import logging
import os
from typing import Optional
import click
from mcp.server.fastmcp import FastMCP 
from pydantic import Field

import hud_controller.extractors.transmission_tasks
from hud_controller.utils import import_submodules

from .setup import setup_codebase, start_dinit
from .spec import PROBLEM_REGISTRY, EnvironmentState, Grade, ProblemSpec
from .tools.base import ToolResult

from .tools.bash import BashTool
from .tools.edit import Command, EditTool

logger = logging.getLogger(__name__)

ONLY_SERVER = False 

mcp = FastMCP("transmission_eval", port=8039, log_level="DEBUG", debug=True)

edit_tool = EditTool()
bash_tool = BashTool()

@mcp.tool(name="str_replace_editor")
async def str_replace_editor(
    *, command: Command, path: str, file_text: Optional[str] = None, view_range: Optional[list[int]] = None, 
    old_str: Optional[str] = None, new_str: Optional[str] = None, insert_line: Optional[int] = None
) -> ToolResult:
    """Edit files using string replacement. Use absolute paths."""
    return await edit_tool(
        command=command, path=path, file_text=file_text, view_range=view_range,
        old_str=old_str, new_str=new_str, insert_line=insert_line
    )

@mcp.tool(name="bash")
async def bash(*, command: str, restart: bool = False) -> ToolResult:
    """Run bash commands."""
    return await bash_tool(command=command, restart=restart)


template = """
You are working on the Transmission (C++) codebase.
The repository is located at /home/ubuntu/repo.

TASK:
<STATEMENT>
"""

def spec_to_statement(spec: ProblemSpec) -> str:
    return template.replace("<STATEMENT>", spec.description)

def _get_spec(problem_id: str) -> ProblemSpec:
    for spec in PROBLEM_REGISTRY:
        if spec.id == problem_id:
            return spec
    raise ValueError(f"No problem found for id: {problem_id}")

@mcp.tool()
async def setup_problem(problem_id: str = Field(description="Task ID")) -> str:
    """Initialize the environment (Time Travel + Build Config)."""
    spec = _get_spec(problem_id)
    logger.info(f"Setting up problem: {problem_id}")
    await asyncio.to_thread(setup_codebase, spec.base, spec.test, spec.golden)
    return spec_to_statement(spec)

@mcp.tool()
async def grade_problem(problem_id: str) -> Grade:
    """Run tests and return the grade."""
    spec = _get_spec(problem_id)
    state = EnvironmentState()
    return await asyncio.to_thread(spec.solution_fn, state)

@click.command()
def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()