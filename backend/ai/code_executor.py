import subprocess
import tempfile
import os
import sys
import ast
import textwrap

_BLOCKED_MODULES = {
    'os', 'subprocess', 'shutil', 'sys', 'pathlib', 'glob', 'shlex',
    'socket', 'requests', 'urllib', 'http', 'ftplib', 'poplib', 'smtplib',
    'ctypes', 'signal', 'multiprocessing', 'threading', 'importlib',
    'builtins.__import__', 'compile', 'exec', 'eval', 'open',
    'pickle', 'shelve', 'marshal', 'base64',
    '_thread', '_socket',
}


def _check_code_safety(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f'Syntax error: {e}'
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == '__builtins__':
                    return False, f'Blocked: __builtins__.{func.attr}'
                if func.attr in ('__import__', 'exec', 'eval', 'compile', 'open'):
                    return False, f'Blocked: {func.attr}()'
            if isinstance(func, ast.Name) and func.id in ('exec', 'eval', 'compile', '__import__', 'open'):
                return False, f'Blocked: {func.id}()'
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _BLOCKED_MODULES or any(alias.name.startswith(m + '.') for m in _BLOCKED_MODULES):
                    return False, f'Blocked import: {alias.name}'
        if isinstance(node, ast.ImportFrom):
            if node.module in _BLOCKED_MODULES or any(node.module.startswith(m + '.') for m in _BLOCKED_MODULES):
                return False, f'Blocked import: {node.module}'
    return True, None


def execute_code(code, timeout=10):
    safe, error = _check_code_safety(code)
    if not safe:
        return {'success': False, 'error': error}

    code = textwrap.dedent(code)
    code = (
        'import sys, math, random, datetime, collections, itertools, json, re, statistics, textwrap, fractions, decimal\n'
        + 'sys.stdout_buffer = sys.stdout\n'
        + code
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, 'script.py')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(code)

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={'PYTHONIOENCODING': 'utf-8', 'PATH': os.environ.get('PATH', '')},
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout.strip() if result.stdout else '',
                'stderr': result.stderr.strip() if result.stderr else '',
                'returncode': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': f'Execution timed out ({timeout}s)'}
