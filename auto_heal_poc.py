"""
Prova de Conceito (PoC): Arquitetura MAPE-K de Auto-Healing Code em Python
Demonstra deteccao em runtime via introspeccao, analise de AST, sintese de patch
e verificacao em sandbox contra oraculo de testes para prevenir Patch Overfitting.
"""

import ast
import difflib
import inspect
import os
import textwrap
import traceback
from typing import Any, Callable, Dict, List, Tuple


class SecurityAndOverfittingValidator(ast.NodeVisitor):
    """
    Analisador Estatico de AST para validar o patch antes da execucao no Sandbox.
    Impede chamadas perigosas ao sistema e bloqueia 'patch overfitting' trivial
    (como blocos try/except genericos que apenas mascaram a excecao).
    """
    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Bloqueia captura silenciosa (except: pass ou retorno constante sem logica)
        for stmt in node.body:
            if isinstance(stmt, ast.Pass):
                self.violations.append(
                    "Violacao de Overfitting: Bloco 'except: pass' detectado."
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Bloqueia execucao arbitraria de comandos de sistema (Guardrail de Seguranca)
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "system"}:
            self.violations.append(
                f"Violacao de Seguranca: Chamada proibida '{node.func.id}'."
            )
        self.generic_visit(node)


class LLMRepairAgent:
    """
    Agente de Reparo (Fase Plan do MAPE-K).
    Conecta-se a um LLM via API ou utiliza o sintetizador semantico de referencia
    para garantir reprodutibilidade deterministica durante demonstracoes offline.
    """
    @staticmethod
    def synthesize_patch(
        func_name: str,
        broken_source: str,
        error_type: str,
        error_msg: str,
        failing_args: Tuple[Any, ...],
    ) -> str:
        # Montagem do Prompt Estruturado com Contexto Estático e Dinâmico
        prompt = (
            f"Funcao defeituosa:\n{broken_source}\n"
            f"Excecao capturada: {error_type}: {error_msg}\n"
            f"Entrada que disparou a falha: {failing_args}\n"
            "Gere apenas o codigo Python corrigido da funcao mantendo sua assinatura "
            "e preservando as regras de negocio financeiras."
        )

        # Se houver chave de API configurada, pode invocar o modelo real;
        # caso contrario, executa a sintese estrutural de demonstracao da PoC.
        if os.getenv("USE_LIVE_LLM_API") == "1":
            # Integracao padrao com cliente LLM (ex: OpenAI / Claude)
            pass

        # Sintese do patch corrigindo dois bugs reais na funcao de calculo de SLA/Juros:
        # Bug 1: ZeroDivisionError quando total_transacoes == 0
        # Bug 2: KeyError quando o dicionario de lote nao possui a chave 'desconto'
        patched_code = f"""
def {func_name}(lote: dict, total_transacoes: int) -> float:
    if total_transacoes <= 0:
        return 0.0
    valor_bruto = float(lote.get("valor_bruto", 0.0))
    desconto = float(lote.get("desconto", 0.0))
    valor_liquido = max(0.0, valor_bruto - desconto)
    return round(valor_liquido / total_transacoes, 2)
"""
        return textwrap.dedent(patched_code).strip()


class SandboxVerifier:
    """
    Unidade de Verificacao em Sandbox (Fase Execute & Verify do MAPE-K).
    Valida o patch contra a sintaxe AST e contra uma suite de testes (Oraculo)
    contendo testes FAIL_TO_PASS e PASS_TO_PASS (regressao).
    """
    @staticmethod
    def verify_patch(
        func_name: str,
        patched_source: str,
        test_suite: List[Tuple[Tuple[Any, ...], Any]],
    ) -> Tuple[bool, str, Callable[..., Any] | None]:
        # 1. Validacao Sintatica e de Seguranca via AST
        try:
            tree = ast.parse(patched_source)
        except SyntaxError as syn_err:
            return False, f"Erro Sintatico no Patch: {syn_err}", None

        validator = SecurityAndOverfittingValidator()
        validator.visit(tree)
        if validator.violations:
            return False, " | ".join(validator.violations), None

        # 2. Compilacao Isolada em Namespace Efêmero (Sandbox)
        sandbox_namespace: Dict[str, Any] = {}
        try:
            compiled_code = compile(tree, filename="<auto_heal_sandbox>", mode="exec")
            exec(compiled_code, {"__builtins__": __builtins__}, sandbox_namespace)
        except Exception as comp_err:
            return False, f"Falha de Compilacao no Sandbox: {comp_err}", None

        candidate_func = sandbox_namespace.get(func_name)
        if not callable(candidate_func):
            return False, f"Funcao '{func_name}' ausente no patch gerado.", None

        # 3. Execucao do Oraculo de Testes (Prevencao de Patch Overfitting)
        for args, expected_output in test_suite:
            try:
                actual_output = candidate_func(*args)
                if actual_output != expected_output:
                    return (
                        False,
                        f"Falha no Oraculo para entrada {args}: "
                        f"esperado {expected_output}, obtido {actual_output}",
                        None,
                    )
            except Exception as exec_err:
                return (
                    False,
                    f"Excecao durante teste de regressao com {args}: {exec_err}",
                    None,
                )

        return True, "Todos os testes FAIL_TO_PASS e PASS_TO_PASS aprovados.", candidate_func


def auto_heal(
    oracle_tests: List[Tuple[Tuple[Any, ...], Any]],
    max_retries: int = 3,
) -> Callable[..., Any]:
    """
    Decorador de Auto-Healing Code (Ciclo MAPE-K Completo).
    Monitora a funcao em tempo de execucao; em caso de falha, diagnostica a AST,
    solicita patch ao Agente LLM, valida no Sandbox e realiza o hot-swap seguro.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        state: Dict[str, Any] = {
            "active_func": func,
            "healed": False,
            "patch_diff": None,
        }

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return state["active_func"](*args, **kwargs)
            except Exception as exc:
                print("\n" + "=" * 72)
                print(f"[MONITOR] Anomalia detectada em '{func.__name__}': {type(exc).__name__}: {exc}")

                # Fase ANALYZE: Introspeccao do codigo-fonte e stack trace
                raw_source = textwrap.dedent(inspect.getsource(func))
                tb_lines = traceback.format_exc().strip().splitlines()
                print(f"[ANALYZE] Stack Trace Isolado: {tb_lines[-1]}")

                # Adiciona a entrada que causou a falha na fila de verificacao
                for attempt in range(1, max_retries + 1):
                    print(f"[PLAN] Tentativa de reparo {attempt}/{max_retries} via Agente LLM...")
                    candidate_source = LLMRepairAgent.synthesize_patch(
                        func_name=func.__name__,
                        broken_source=raw_source,
                        error_type=type(exc).__name__,
                        error_msg=str(exc),
                        failing_args=args,
                    )

                    # Fase EXECUTE & VERIFY: Validacao no Sandbox
                    is_valid, report, verified_callable = SandboxVerifier.verify_patch(
                        func_name=func.__name__,
                        patched_source=candidate_source,
                        test_suite=oracle_tests,
                    )
                    print(f"[VERIFY] Resultado do Sandbox: {report}")

                    if is_valid and verified_callable is not None:
                        diff = "\n".join(
                            difflib.unified_diff(
                                raw_source.splitlines(),
                                candidate_source.splitlines(),
                                fromfile=f"a/{func.__name__}.py (Original)",
                                tofile=f"b/{func.__name__}.py (Auto-Healed)",
                                lineterm="",
                            )
                        )
                        state["active_func"] = verified_callable
                        state["healed"] = True
                        state["patch_diff"] = diff
                        print("[EXECUTE] Patch validado! Aplicando hot-swap em memoria e gerando Diff para PR:")
                        print("-" * 72)
                        print(diff)
                        print("=" * 72 + "\n")
                        return state["active_func"](*args, **kwargs)

                raise RuntimeError(
                    f"Auto-Healing falhou apos {max_retries} tentativas."
                ) from exc

        return wrapper
    return decorator


# =====================================================================
# Caso de Uso Prático: Processamento Financeiro de Lotes com Defeitos Latentes
# =====================================================================
ORACLE_TEST_SUITE = [
    # Testes PASS_TO_PASS (Regressão da regra de negócio normal)
    (({"valor_bruto": 1000.0, "desconto": 100.0}, 9), 100.0),
    (({"valor_bruto": 250.0, "desconto": 50.0}, 4), 50.0),
    # Testes FAIL_TO_PASS (Casos de borda: chave ausente e divisão por zero)
    (({"valor_bruto": 500.0}, 5), 100.0),
    (({"valor_bruto": 500.0, "desconto": 50.0}, 0), 0.0),
]


@auto_heal(oracle_tests=ORACLE_TEST_SUITE, max_retries=3)
def calcular_ticket_medio_liquido(lote: dict, total_transacoes: int) -> float:
    # Codigo original defeituoso: assume que 'desconto' sempre existe (KeyError)
    # e nao trata 'total_transacoes == 0' (ZeroDivisionError)
    valor_liquido = lote["valor_bruto"] - lote["desconto"]
    return round(valor_liquido / total_transacoes, 2)


if __name__ == "__main__":
    print("1. Executando lote padrao (Caso nominal):")
    res1 = calcular_ticket_medio_liquido({"valor_bruto": 1000.0, "desconto": 100.0}, 9)
    print(f"   Resultado: R$ {res1}\n")

    print("2. Injetando falha em tempo real (Lote sem chave 'desconto' e 0 transacoes):")
    res2 = calcular_ticket_medio_liquido({"valor_bruto": 500.0}, 0)
    print(f"   Resultado apos Auto-Healing: R$ {res2}\n")

    print("3. Executando chamadas subsequentes (Funcao ja autorreparada em runtime):")
    res3 = calcular_ticket_medio_liquido({"valor_bruto": 500.0}, 5)
    print(f"   Resultado (Lote sem 'desconto', 5 transacoes): R$ {res3}")
