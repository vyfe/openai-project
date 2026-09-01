"""策略表达式引擎 —— 受限 AST 求值，替代 eval()。

设计目标：
- 安全：白名单 AST walker，默认拒绝一切未明确允许的节点。
- 性能：编译结果 lru_cache，逐 bar 求值时不能再 reparse。
- 序列友好：支持 prev(x)/ref(x, n)/x[n] 访问历史值，cross_up/cross_down 跨 bar 判定。
- 容错：求值遇 None（指标预热期数据不足）→ 整体返回 None，不抛异常。

不在白名单的节点（Class/Import/Lambda/Starred/comprehension/Attribute 任意访问）
一律抛 ExpressionError，错误信息尽量给到行号/列号。

支持语法：
- 数字 / 字符串 / True / False / None 常量
- 标识符：变量名（bar 字段 + 指标输出名）
- 比较：==  !=  >  <  >=  <=
- 布尔：and / or / not
- 一元：-x  +x
- 二元：+ - * / // % **
- 三元：x if cond else y
- 元组：x, y
- 调用：仅白名单函数 prev/ref/avg/abs/min/max/cross_up/cross_down/length/any_/all_
- 下标：name[n] —— n 必须是非负整数常量；name 是变量名或字符串名
- 字面量集合/列表：禁止（避免内存炸弹）

白名单函数：
- prev(x) ≡ x 的前 1 根（与 ref(x, 1) 等价；prev(x, n) ≡ ref(x, n)）
- ref(x, n) 取 x 在 n 根前的值；n 必须是非负整数常量
- avg(x, n) 取 x 在最近 n 根（含当前）的均值；等价于 sum/x 的简单语义
- abs/min/max Python 原生
- cross_up(a, b)：a 上穿 b（当前 a > b 且上一根 a <= b）
- cross_down(a, b)：a 下穿 b
- length(seq) —— 仅用于 indicator 序列，不在此处定义；见 evaluate_series
- any_(...) / all_(...) —— Python any/all 的安全别名（避免与 keyword 冲突）
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Optional, Sequence


class ExpressionError(ValueError):
    """表达式语法或语义错误。"""


# ---------------------------------------------------------------------------
# 编译：把表达式字符串解析为可执行的 AST 程序
# ---------------------------------------------------------------------------

# Python <3.8 没有 ast.unparse，低版本会要求"可哈希"的常量；这里只读不写。
_ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp,
    ast.Compare, ast.Name, ast.Load, ast.Constant,
    ast.Call, ast.Subscript, ast.IfExp, ast.Tuple,
    # 比较运算符
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    # 布尔运算符
    ast.And, ast.Or, ast.Not,
    # 一元 / 二元运算符
    ast.UAdd, ast.USub,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
)


_FORBIDDEN_NAMES: tuple[str, ...] = (
    "__import__", "eval", "exec", "compile", "globals", "locals",
    "open", "input", "getattr", "setattr", "delattr", "vars", "dir",
    "class", "lambda", "yield", "await", "import",
)


def _check_safety(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExpressionError(
                f"不支持的语法: {type(node).__name__}（位置 {getattr(node, 'lineno', '?')}:{getattr(node, 'col_offset', '?')}）"
            )
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ExpressionError(f"禁止访问 dunder: {node.id}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ExpressionError(f"禁止使用内置名: {node.id}")
        if isinstance(node, ast.Call):
            # 不允许 keyword arguments（*.args 也禁止 *args/**kwargs）
            if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
                raise ExpressionError("禁止使用 keyword args / *args / **kwargs")
            if not isinstance(node.func, ast.Name):
                raise ExpressionError("只允许调用白名单中的名字")
            if node.func.id not in _SAFE_FUNCTIONS:
                raise ExpressionError(f"禁止调用函数: {node.func.id}")
        if isinstance(node, ast.Subscript):
            # name[n] 中 n 必须是常量非负整数
            sl = node.slice
            if not isinstance(sl, ast.Constant) or not isinstance(sl.value, int) or sl.value < 0:
                raise ExpressionError(
                    f"下标必须是常量非负整数（位置 {getattr(node, 'lineno', '?')}）"
                )
            if not isinstance(node.value, ast.Name):
                raise ExpressionError(
                    f"下标的左值必须是变量名（位置 {getattr(node, 'lineno', '?')}）"
                )


@lru_cache(maxsize=4096)
def compile_expression(expr: str) -> ast.Expression:
    """编译表达式为 AST。同一表达式重复调用走 lru_cache。"""
    if not isinstance(expr, str) or not expr.strip():
        raise ExpressionError("表达式不能为空")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"语法错误: {exc.msg}") from exc
    _check_safety(tree)
    return tree


# ---------------------------------------------------------------------------
# 白名单函数
# ---------------------------------------------------------------------------


def _fn_prev(x: Any, n: int = 1) -> Any:
    """x 的前 n 根取值。语义由 evaluate() 上下文注入（lookback_in_series）。"""
    # 此函数不会被直接调用；evaluate() 会把序列和当前位置传进来。
    raise ExpressionError("prev 必须在序列上下文中调用")


def _fn_cross_up(a: Any, b: Any) -> bool:
    """a 上穿 b：当前 a > b 且 prev(a) <= prev(b)。需在 evaluate 上下文。"""
    raise ExpressionError("cross_up 必须在序列上下文中调用")


def _fn_cross_down(a: Any, b: Any) -> bool:
    raise ExpressionError("cross_down 必须在序列上下文中调用")


def _fn_avg(x: Any, n: int = 1) -> Any:
    raise ExpressionError("avg 必须在序列上下文中调用")


def _fn_ref(x: Any, n: int = 1) -> Any:
    raise ExpressionError("ref 必须在序列上下文中调用")


def _fn_abs(x: Any) -> Any:
    if x is None:
        return None
    return abs(x)


def _fn_min(*args):
    cleaned = [a for a in args if a is not None]
    if not cleaned:
        return None
    return min(cleaned)


def _fn_max(*args):
    cleaned = [a for a in args if a is not None]
    if not cleaned:
        return None
    return max(cleaned)


def _fn_any_(*args) -> bool:
    return any(bool(a) for a in args if a is not None)


def _fn_all_(*args) -> bool:
    # all([]) 在 Python 是 True，这里沿用；调用方自行决定
    return all(bool(a) for a in args if a is not None)


_SAFE_FUNCTIONS: dict[str, Callable] = {
    "prev": _fn_prev,
    "ref": _fn_ref,
    "avg": _fn_avg,
    "abs": _fn_abs,
    "min": _fn_min,
    "max": _fn_max,
    "cross_up": _fn_cross_up,
    "cross_down": _fn_cross_down,
    "any_": _fn_any_,
    "all_": _fn_all_,
}


# ---------------------------------------------------------------------------
# 序列上下文求值（evaluate_series 用）
# ---------------------------------------------------------------------------


def _seq_lookup(seq: Sequence, idx: int, name: str) -> Any:
    """支持 x[n] 与 prev(x) 访问；越界返回 None。"""
    if seq is None or len(seq) == 0:
        return None
    target = idx + (name or 0) if False else idx + (name or 0)
    # 此函数由 evaluate 包装调用
    raise ExpressionError("internal: should be overridden")


@dataclass
class SeriesView:
    """一组命名序列（指标 / bar 字段）的轻量视图。

    evaluate 时构建：每个 Name 取 seqs[name]；下标 x[n] 取 seqs[name][idx - n]；
    prev/avg/cross_* 通过它做时间位移。
    """

    seqs: dict[str, list]
    idx: int

    def get(self, name: str, offset: int = 0) -> Any:
        seq = self.seqs.get(name)
        if seq is None:
            raise ExpressionError(f"未知变量: {name}")
        # seqs 与 bars_desc 对齐：index 0 = 当前 bar，index 1 = 前 1 根，...
        # offset=1 表示"前 1 根"，对应 seqs[idx + 1]。
        target = self.idx + offset
        if target < 0 or target >= len(seq):
            return None
        return seq[target]

    def avg(self, name: str, n: int) -> Any:
        seq = self.seqs.get(name)
        if seq is None:
            raise ExpressionError(f"未知变量: {name}")
        start = self.idx
        end = self.idx + n
        window = seq[start:end]
        cleaned = [v for v in window if v is not None]
        if not cleaned:
            return None
        return sum(cleaned) / len(cleaned)


# 替换占位符：实际求值时直接走 SeriesView，避免函数 call 开销。
class _Evaluator:
    """遍历编译好的 AST，逐节点在 SeriesView + 当前 bar 上下文求值。

    设计原则：
    - 遇到 None 直接传播（数学/布尔/比较都返回 None），避免空指标拖崩策略。
    - 比较：与 None 比较返回 None（不是 False）。
    - 布尔：None and x = None；None or x = x；not None = None。
    - 短路：and/or 不对右侧求值如果左侧决定结果。
    """

    def __init__(self, view: SeriesView, scalar_vars: dict[str, Any]):
        self.view = view
        self.scalars = scalar_vars

    def eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.scalars:
                return self.scalars[node.id]
            return self.view.get(node.id)
        if isinstance(node, ast.UnaryOp):
            v = self.eval(node.operand)
            if v is None:
                return None
            if isinstance(node.op, ast.UAdd):
                return +v
            if isinstance(node.op, ast.USub):
                return -v
            if isinstance(node.op, ast.Not):
                return not v
            raise ExpressionError(f"未知一元运算: {type(node.op).__name__}")
        if isinstance(node, ast.BinOp):
            l = self.eval(node.left)
            r = self.eval(node.right)
            if l is None or r is None:
                return None
            try:
                if isinstance(node.op, ast.Add):
                    return l + r
                if isinstance(node.op, ast.Sub):
                    return l - r
                if isinstance(node.op, ast.Mult):
                    return l * r
                if isinstance(node.op, ast.Div):
                    if r == 0:
                        return None
                    return l / r
                if isinstance(node.op, ast.FloorDiv):
                    if r == 0:
                        return None
                    return l // r
                if isinstance(node.op, ast.Mod):
                    if r == 0:
                        return None
                    return l % r
                if isinstance(node.op, ast.Pow):
                    return l ** r
            except Exception as exc:  # noqa: BLE001
                raise ExpressionError(f"二元运算失败: {exc}") from exc
            raise ExpressionError(f"未知二元运算: {type(node.op).__name__}")
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result: Any = True
                for v in node.values:
                    result = self.eval(v)
                    if result is False:
                        return False
                    if result is None:
                        return None
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for v in node.values:
                    result = self.eval(v)
                    if result is True:
                        return True
                    if result is None:
                        # 继续尝试右侧
                        continue
                return result
            raise ExpressionError(f"未知布尔运算: {type(node.op).__name__}")
        if isinstance(node, ast.Compare):
            left = self.eval(node.left)
            for op, comp_node in zip(node.ops, node.comparators):
                right = self.eval(comp_node)
                if left is None or right is None:
                    return None
                ok = self._apply_compare(op, left, right)
                if not ok:
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            cond = self.eval(node.test)
            if cond is None:
                return None
            if cond:
                return self.eval(node.body)
            return self.eval(node.orelse)
        if isinstance(node, ast.Tuple):
            return tuple(self.eval(elt) for elt in node.elts)
        if isinstance(node, ast.Subscript):
            base = self.eval(node.value)
            offset = node.slice.value  # compile 时已校验为非负 int
            if isinstance(base, str) and offset == 0:
                return base  # 字符串字面量下标给字符串
            # 序列下标走 name + offset
            if not isinstance(node.value, ast.Name):
                raise ExpressionError("下标的左值必须是变量名")
            return self.view.get(node.value.id, offset)
        if isinstance(node, ast.Call):
            return self._call(node)
        raise ExpressionError(f"未实现节点: {type(node).__name__}")

    def _apply_compare(self, op: ast.AST, l: Any, r: Any) -> bool:
        try:
            if isinstance(op, ast.Eq):
                return l == r
            if isinstance(op, ast.NotEq):
                return l != r
            if isinstance(op, ast.Lt):
                return l < r
            if isinstance(op, ast.LtE):
                return l <= r
            if isinstance(op, ast.Gt):
                return l > r
            if isinstance(op, ast.GtE):
                return l >= r
        except TypeError:
            return None
        raise ExpressionError(f"未知比较运算: {type(op).__name__}")

    def _call(self, node: ast.Call) -> Any:
        name = node.func.id
        # 序列函数需要从原始 AST 拿变量名（不能先 eval 成值）
        if name in ("prev", "ref", "avg"):
            if not node.args or not isinstance(node.args[0], ast.Name):
                raise ExpressionError(f"{name} 的第一个参数必须是变量名")
            seq_name = node.args[0].id
            n = 1
            if len(node.args) > 1:
                n_val = self.eval(node.args[1])
                if not isinstance(n_val, int) or n_val < 0:
                    raise ExpressionError(f"{name} 的第二个参数必须是非负整数")
                n = n_val
            if name == "avg":
                return self.view.avg(seq_name, n)
            return self.view.get(seq_name, n)
        if name in ("cross_up", "cross_down"):
            if len(node.args) != 2 or not all(isinstance(a, ast.Name) for a in node.args):
                raise ExpressionError(f"{name} 的参数必须都是变量名")
            a_name, b_name = node.args[0].id, node.args[1].id
            cur_a = self.view.get(a_name)
            cur_b = self.view.get(b_name)
            prev_a = self.view.get(a_name, 1)
            prev_b = self.view.get(b_name, 1)
            if None in (cur_a, cur_b, prev_a, prev_b):
                return None
            if name == "cross_up":
                return prev_a <= prev_b and cur_a > cur_b
            return prev_a >= prev_b and cur_a < cur_b
        # 普通函数：args 先求值
        args = [self.eval(a) for a in node.args]
        if name == "abs":
            return _fn_abs(args[0])
        if name == "min":
            return _fn_min(*args)
        if name == "max":
            return _fn_max(*args)
        if name == "any_":
            return _fn_any_(*args)
        if name == "all_":
            return _fn_all_(*args)
        raise ExpressionError(f"未实现函数: {name}")


def _call_seq_name(arg: Any) -> str:
    """cross_up(a, b) 之类的调用，参数通常是 Name（变量）。"""
    if isinstance(arg, str):
        return arg  # cross_up("macd_dif", "macd_dea") —— 不支持但也不阻塞
    raise ExpressionError("函数参数必须是变量名")


def evaluate(expr_ast: ast.Expression, view: SeriesView, scalars: Optional[dict] = None) -> Any:
    """对 SeriesView 的当前位置 idx 求值。scalars 允许注入一次性常量（如 gate id）。"""
    evaluator = _Evaluator(view, scalars or {})
    return evaluator.eval(expr_ast)


# ---------------------------------------------------------------------------
# 校验与变量收集（前端/dry_run 预校验）
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    ok: bool
    error: str = ""
    used_vars: tuple = ()  # 引用的变量名


def validate_expression(expr: str, known_vars: set[str]) -> ValidationResult:
    """编译并扫描所有用到的变量名。

    不做语义求值，只做语法 + 白名单 + 变量已知性检查。
    """
    try:
        tree = compile_expression(expr)
    except ExpressionError as exc:
        return ValidationResult(ok=False, error=str(exc))
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
        elif isinstance(node, ast.Call):
            for a in node.args:
                if isinstance(a, ast.Name):
                    used.add(a.id)
    unknown = sorted(v for v in used if v not in known_vars and v not in _SAFE_FUNCTIONS)
    if unknown:
        return ValidationResult(
            ok=False,
            error=f"引用未知变量: {unknown}",
            used_vars=tuple(sorted(used)),
        )
    return ValidationResult(ok=True, used_vars=tuple(sorted(used)))


def infer_indicators_from_expr(expr: str, registry_keys: set[str]) -> set[str]:
    """从表达式推断需要哪些指标 key。

    ma_5/boll_mid/macd_dif/.../td_signal/bottom_divergence
    按前缀映射回 registry key（ma/boll/macd/kdj/td_sequential/bottom_structure）；
    vol_ratio_10/period_return_5/rolling_high_20/rolling_low_20 同样按前缀映射。
    """
    try:
        tree = compile_expression(expr)
    except ExpressionError:
        return set()
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
        elif isinstance(node, ast.Call):
            for a in node.args:
                if isinstance(a, ast.Name):
                    used.add(a.id)
    out: set[str] = set()
    for name in used:
        if name in registry_keys:
            out.add(name)
            continue
        if name.startswith("ma_") and "ma" in registry_keys:
            out.add("ma")
        elif name.startswith("boll_") and "boll" in registry_keys:
            out.add("boll")
        elif name.startswith("macd_") and "macd" in registry_keys:
            out.add("macd")
        elif name.startswith("kdj_") and "kdj" in registry_keys:
            out.add("kdj")
        elif name.startswith("td_") and "td_sequential" in registry_keys:
            out.add("td_sequential")
        elif name == "bottom_divergence" and "bottom_structure" in registry_keys:
            out.add("bottom_structure")
        elif name.startswith("vol_ratio_") and "vol_ratio" in registry_keys:
            out.add("vol_ratio")
        elif name.startswith("period_return_") and "period_return" in registry_keys:
            out.add("period_return")
        elif name.startswith("rolling_high_") or name.startswith("rolling_low_"):
            if "rolling_high_low" in registry_keys:
                out.add("rolling_high_low")
    return out


# 给前端 IDE 用的补全数据
BAR_FIELD_NAMES: tuple[str, ...] = (
    "open_price", "high_price", "low_price", "close_price",
    "volume", "amount",
    "pct_change", "turnover_rate",
)


EXPRESSION_FUNCTION_NAMES: tuple[str, ...] = tuple(_SAFE_FUNCTIONS.keys())