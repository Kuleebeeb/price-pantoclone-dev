"""Restricted arithmetic formula evaluator used by the pricing application."""

from __future__ import annotations

import ast
import math
from typing import Mapping


class FormulaError(ValueError):
    """Raised when a configurable formula is invalid or unsafe."""


def _safe_round(value: float, digits: float = 0) -> float:
    if not float(digits).is_integer() or not -10 <= digits <= 10:
        raise ValueError("จำนวนตำแหน่งทศนิยมต้องเป็นจำนวนเต็มระหว่าง -10 ถึง 10")
    return round(value, int(digits))


_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": _safe_round,
    "ceil": math.ceil,
    "floor": math.floor,
    "sqrt": math.sqrt,
}


class _Evaluator(ast.NodeVisitor):
    def __init__(self, variables: Mapping[str, float]):
        self.variables = variables

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulaError("สูตรใช้ได้เฉพาะตัวเลข")
        return float(node.value)

    def visit_Name(self, node: ast.Name) -> float:
        if node.id not in self.variables:
            raise FormulaError(f"ไม่รู้จักตัวแปร: {node.id}")
        return float(self.variables[node.id])

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise FormulaError("เครื่องหมายนี้ไม่รองรับ")

    def visit_BinOp(self, node: ast.BinOp) -> float:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise FormulaError("สูตรหารด้วยศูนย์")
            result = left / right
        elif isinstance(node.op, ast.Mod):
            if right == 0:
                raise FormulaError("สูตรหารด้วยศูนย์")
            result = left % right
        elif isinstance(node.op, ast.Pow):
            if abs(right) > 8 or abs(left) > 1_000_000:
                raise FormulaError("เลขยกกำลังเกินขอบเขตที่อนุญาต")
            result = left**right
        else:
            raise FormulaError("เครื่องหมายนี้ไม่รองรับ")
        if not math.isfinite(result) or abs(result) > 1e15:
            raise FormulaError("ผลลัพธ์อยู่นอกช่วงที่รองรับ")
        return result

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise FormulaError("ฟังก์ชันนี้ไม่ได้รับอนุญาต")
        if node.keywords:
            raise FormulaError("สูตรไม่รองรับ named arguments")
        args = [self.visit(arg) for arg in node.args]
        try:
            result = float(_FUNCTIONS[node.func.id](*args))
        except (TypeError, ValueError, OverflowError) as exc:
            raise FormulaError(f"ใช้ฟังก์ชันไม่ถูกต้อง: {exc}") from exc
        if not math.isfinite(result):
            raise FormulaError("ผลลัพธ์ไม่ใช่ตัวเลขที่ใช้ได้")
        return result

    def generic_visit(self, node: ast.AST) -> float:
        raise FormulaError(f"ไม่อนุญาตให้ใช้ {type(node).__name__} ในสูตร")


def evaluate_formula(expression: str, variables: Mapping[str, float]) -> float:
    """Evaluate arithmetic only. No attributes, indexing, imports, or code execution."""
    if not expression or not expression.strip():
        raise FormulaError("กรุณากรอกสูตร")
    if len(expression) > 500:
        raise FormulaError("สูตรยาวเกินไป")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise FormulaError("รูปแบบสูตรไม่ถูกต้อง") from exc
    return _Evaluator(variables).visit(tree)


def validate_formula(expression: str, allowed_variables: set[str]) -> None:
    sample = {name: 1.0 for name in allowed_variables}
    evaluate_formula(expression, sample)
