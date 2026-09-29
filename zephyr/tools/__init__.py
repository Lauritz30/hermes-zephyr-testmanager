"""Tool handler modules for the Zephyr Scale plugin.

Import surface for the handlers themselves; ``HANDLERS`` maps every tool name to its callable.
"""

from __future__ import annotations

from .doctor import DOCTOR_TOOLS, zephyr_doctor
from .read import (
    READ_TOOLS,
    zephyr_get_test_case,
    zephyr_get_test_cycle,
    zephyr_get_test_execution,
    zephyr_list_test_cases,
    zephyr_list_test_cycles,
    zephyr_list_test_executions,
)
from .write import (
    WRITE_TOOLS,
    zephyr_add_test_cases_to_cycle,
    zephyr_create_test_case,
    zephyr_update_test_execution_status,
)

HANDLERS = {**DOCTOR_TOOLS, **READ_TOOLS, **WRITE_TOOLS}

__all__ = [
    "DOCTOR_TOOLS",
    "HANDLERS",
    "READ_TOOLS",
    "WRITE_TOOLS",
    "zephyr_add_test_cases_to_cycle",
    "zephyr_create_test_case",
    "zephyr_doctor",
    "zephyr_get_test_case",
    "zephyr_get_test_cycle",
    "zephyr_get_test_execution",
    "zephyr_list_test_cases",
    "zephyr_list_test_cycles",
    "zephyr_list_test_executions",
    "zephyr_update_test_execution_status",
]
