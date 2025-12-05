"""
Syntax validation tests - ensure all Python files compile without syntax errors
"""
import py_compile
import os
from pathlib import Path


def test_discovery_syntax():
    """Test that discovery.py has no syntax errors"""
    discovery_path = Path(__file__).parent.parent / "app" / "tasks" / "discovery.py"
    try:
        py_compile.compile(str(discovery_path), doraise=True)
        assert True, "discovery.py compiled successfully"
    except py_compile.PyCompileError as e:
        pytest.fail(f"discovery.py has syntax errors: {e}")


def test_enrichment_service_syntax():
    """Test that enrichment.py has no syntax errors"""
    enrichment_path = Path(__file__).parent.parent / "app" / "services" / "enrichment.py"
    try:
        py_compile.compile(str(enrichment_path), doraise=True)
        assert True, "enrichment.py compiled successfully"
    except py_compile.PyCompileError as e:
        pytest.fail(f"enrichment.py has syntax errors: {e}")


def test_enrichment_task_syntax():
    """Test that enrichment task has no syntax errors"""
    task_path = Path(__file__).parent.parent / "app" / "tasks" / "enrichment.py"
    try:
        py_compile.compile(str(task_path), doraise=True)
        assert True, "enrichment task compiled successfully"
    except py_compile.PyCompileError as e:
        pytest.fail(f"enrichment task has syntax errors: {e}")


def test_hunter_client_syntax():
    """Test that hunter.py has no syntax errors"""
    hunter_path = Path(__file__).parent.parent / "app" / "clients" / "hunter.py"
    try:
        py_compile.compile(str(hunter_path), doraise=True)
        assert True, "hunter.py compiled successfully"
    except py_compile.PyCompileError as e:
        pytest.fail(f"hunter.py has syntax errors: {e}")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

