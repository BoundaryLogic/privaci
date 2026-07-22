"""Security AST visitor for dynamic, SQL, HTTP, logging, and packaging rules."""

from __future__ import annotations

import ast

from security_ast.constants import (
    ARTICLE_I_PACKAGES,
    BANNED_DYNAMIC_CALLS,
    BANNED_HTTP_MODULES,
    BANNED_PACKAGING_MODULES,
    DB_CALL_NAMES,
    LOGGER_METHODS,
    SUBPROCESS_CALLS,
)
from security_ast.findings import Finding
from security_ast.helpers import (
    call_name,
    is_allowlisted,
    is_interpolated,
    module_banned,
    name_looks_pii,
)


class SecurityVisitor(ast.NodeVisitor):
    """Single-pass collector for security AST rules."""

    def __init__(
        self,
        *,
        rel_path: str,
        allowlist: set[str],
        check_http: bool,
        full_rules: bool,
    ) -> None:
        self.rel_path = rel_path
        self.allowlist = allowlist
        self.check_http = check_http
        self.full_rules = full_rules
        self.findings: list[Finding] = []
        self._fn_stack: list[str] = []
        self._subprocess_modules: set[str] = set()
        self._subprocess_call_names: set[str] = set()
        self._subprocess_star = False
        self._interpolated_names: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_like(node)

    def _visit_function_like(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self._fn_stack.append(node.name)
        prior = set(self._interpolated_names)
        self.generic_visit(node)
        self._interpolated_names = prior
        self._fn_stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._maybe_ban_import(node.lineno, alias.name)
            if alias.name == "subprocess" or alias.name.startswith("subprocess."):
                self._subprocess_modules.add(alias.asname or alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        self._maybe_ban_import(node.lineno, module)
        if module == "subprocess":
            for alias in node.names:
                if alias.name == "*":
                    self._subprocess_star = True
                elif alias.name in SUBPROCESS_CALLS:
                    self._subprocess_call_names.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.full_rules:
            self._check_call(node)
        elif self.check_http:
            self._check_importlib_http(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.full_rules:
            for target in node.targets:
                if isinstance(target, ast.Name) and is_interpolated(node.value):
                    self._interpolated_names.add(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            self.full_rules
            and isinstance(node.target, ast.Name)
            and node.value is not None
            and is_interpolated(node.value)
        ):
            self._interpolated_names.add(node.target.id)
        self.generic_visit(node)

    def _current_symbol(self) -> str | None:
        return self._fn_stack[-1] if self._fn_stack else None

    def _flag(
        self,
        line: int,
        rule: str,
        detail: str,
        *,
        symbol: str | None = None,
    ) -> None:
        resolved = symbol if symbol is not None else self._current_symbol()
        if is_allowlisted(
            rel_path=self.rel_path,
            line=line,
            symbol=resolved,
            rule=rule,
            allowlist=self.allowlist,
        ):
            return
        self.findings.append(
            Finding(
                rel_path=self.rel_path,
                line=line,
                rule=rule,
                detail=detail,
                symbol=resolved,
            )
        )

    def _maybe_ban_import(self, line: int, module: str) -> None:
        if module_banned(module, BANNED_PACKAGING_MODULES):
            self._flag(line, "packaging-import", f"banned packaging import {module}")
            return
        if not self.check_http or not module_banned(module, BANNED_HTTP_MODULES):
            return
        self._flag(
            line,
            "article-i-import",
            f"banned HTTP import {module}",
            symbol=self._current_symbol() or module,
        )

    def _check_call(self, node: ast.Call) -> None:
        name = call_name(node)
        if name in BANNED_DYNAMIC_CALLS:
            self._flag(node.lineno, "dynamic-exec", f"banned call {name}()")
        if self._is_subprocess_shell_true(node):
            self._flag(
                node.lineno,
                "subprocess-shell",
                "subprocess call with shell=True",
            )
        if name in DB_CALL_NAMES and self._sql_call_is_interpolated(node):
            self._flag(
                node.lineno,
                "sql-concat",
                f"string-built SQL passed to {name}()",
            )
        self._check_importlib_http(node)
        self._check_logging_call(node, name)

    def _sql_call_is_interpolated(self, node: ast.Call) -> bool:
        for arg in node.args:
            if self._expr_is_sql_risk(arg):
                return True
        for keyword in node.keywords:
            if keyword.arg is None:
                return True
            if self._expr_is_sql_risk(keyword.value):
                return True
        return False

    def _expr_is_sql_risk(self, node: ast.expr) -> bool:
        if is_interpolated(node):
            return True
        return isinstance(node, ast.Name) and node.id in self._interpolated_names

    def _is_subprocess_shell_true(self, node: ast.Call) -> bool:
        if not self._call_is_subprocess(node):
            return False
        for keyword in node.keywords:
            if keyword.arg is None:
                return True
            if keyword.arg != "shell":
                continue
            if isinstance(keyword.value, ast.Constant):
                return keyword.value.value is not False and keyword.value.value != 0
            return True
        return False

    def _call_is_subprocess(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in self._subprocess_call_names:
                return True
            return self._subprocess_star and func.id in SUBPROCESS_CALLS
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr not in SUBPROCESS_CALLS:
            return False
        if isinstance(func.value, ast.Name):
            return (
                func.value.id in self._subprocess_modules
                or func.value.id == "subprocess"
            )
        return False

    def _check_importlib_http(self, node: ast.Call) -> None:
        if not self.check_http:
            return
        name = call_name(node)
        if name != "import_module" or not node.args:
            return
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if module_banned(arg.value, BANNED_HTTP_MODULES):
                self._flag(
                    node.lineno,
                    "article-i-import",
                    f"banned HTTP import via import_module({arg.value!r})",
                )
            return
        # Fail closed: non-literal module names cannot be proven safe.
        self._flag(
            node.lineno,
            "article-i-import",
            "import_module() with non-constant module name on Article I path",
        )

    def _check_logging_call(self, node: ast.Call, name: str | None) -> None:
        if name not in LOGGER_METHODS or not isinstance(node.func, ast.Attribute):
            return
        for arg in node.args:
            if is_interpolated(arg):
                self._flag(
                    node.lineno,
                    "logging-interpolation",
                    f"logger.{name}() uses string interpolation",
                )
                return
            if isinstance(arg, ast.Name) and name_looks_pii(arg.id):
                self._flag(
                    node.lineno,
                    "logging-pii-name",
                    f"logger.{name}() passes PII-ish name {arg.id!r}",
                )
                return
        self._check_logging_extra(node, name)

    def _check_logging_extra(self, node: ast.Call, name: str | None) -> None:
        for keyword in node.keywords:
            if keyword.arg != "extra" or not isinstance(keyword.value, ast.Dict):
                continue
            for key, value in zip(
                keyword.value.keys, keyword.value.values, strict=False
            ):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if name_looks_pii(key.value):
                        self._flag(
                            node.lineno,
                            "logging-pii-extra",
                            f"logger.{name}() extra key {key.value!r} looks like PII",
                        )
                        return
                if isinstance(key, ast.Name) and name_looks_pii(key.id):
                    self._flag(
                        node.lineno,
                        "logging-pii-extra",
                        f"logger.{name}() extra key name {key.id!r} looks like PII",
                    )
                    return
                if isinstance(value, ast.Name) and name_looks_pii(value.id):
                    self._flag(
                        node.lineno,
                        "logging-pii-extra",
                        f"logger.{name}() extra value name {value.id!r} looks like PII",
                    )
                    return


def package_uses_http(package: str | None) -> bool:
    """Return True when Article I HTTP bans apply to ``package``."""
    return package in ARTICLE_I_PACKAGES
