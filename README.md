# Prova de Conceito (PoC): Arquitetura MAPE-K de Auto-Healing Code em Python

> **Repositório acadêmico desenvolvido para a disciplina de Engenharia de Software (Prospecção Teórica e Tecnológica).**  
> **Tema:** Auto-healing Code: Uso de IA para detecção e correção autônoma de falhas em tempo real (Tópico 36: Engenharia de Software com IA).

---

## 1. Visão Geral do Projeto

Este repositório contém a implementação prática de um motor de **Auto-Healing Code** focado em **Reparo Automatizado de Programas (*Automated Program Repair* — APR)** em tempo de execução (*runtime*).

Diferente de abordagens tradicionais de infraestrutura (como orquestradores de contêineres que apenas reiniciam processos caídos sem sanar a falha lógica), este projeto implementa um ciclo de controle autonômico em malha fechada **MAPE-K** (*Monitor, Analyze, Plan, Execute over Knowledge*). O sistema intercepta falhas não tratadas, diagnostica o código-fonte vivo via reflexão/introspecção, consulta um Grande Modelo de Linguagem (**Google Gemini 3.8 Flash via API oficial**) para sintetizar um *patch*, submete a proposta a um **Sandbox de Quarentena com análise sintática (AST)** e aplica a correção diretamente na memória RAM (*hot-swap*), gerando um relatório em formato *Unified Diff* para auditoria humana (*Human-in-the-Loop*).

---

## 2. Arquitetura MAPE-K e Funcionamento Interno

A aplicação opera sob quatro etapas coordenadas e sequenciais:
```
              ┌──────────────────────────────────────────────┐
              │                 KNOWLEDGE                    │
              │   - Oráculo de Testes (ORACLE_TEST_SUITE)    │
              │   - Regras Sintáticas e Guardrails de AST    │
              │   - Histórico de Tentativas de Reparo (cap=3)│
              └──────┬──────────────┬──────────────┬─────────┘
                     │              │              │
  ┌──────────────────▼──┐    ┌──────▼──────┐   ┌───▼────────────────┐
  │       MONITOR       │    │   ANALYZE   │   │        PLAN        │
  │ Interceptação via   ├────► Introspecção├─► │ Consulta LLM Real  │
  │ Decorador @auto_heal│    │ de Código & │   │ (Google Gemini) ou │
  │                     │    │ Stack Trace │   │ Fallback Sintético │
  └─────────────────────┘    └─────────────┘   └──────────┬─────────┘
                                                          │
                             ┌────────────────────────────▼─────────┐
                             │          EXECUTE & VERIFY            │
                             │  1. Guardrail AST (Sem except: pass) │
                             │  2. Compilação em Sandbox Isolado    │
                             │  3. Bateria Oráculo (PASS & FAIL)    │
                             │  4. Hot-Swap em RAM & Unified Diff   │
                             └──────────────────────────────────────┘
```

1. **Monitor (`@auto_heal`):** O decorador intercepta exceções em tempo de execução (`KeyError`, `ZeroDivisionError`) antes que o processo da aplicação seja derrubado.
2. **Analyze (`inspect` & `traceback`):** O motor extrai dinamicamente o código-fonte textual da função defeituosa, sua assinatura, os argumentos exatos que provocaram o *crash* e o *stack trace* isolado da falha.
3. **Plan (`LLMRepairAgent`):**
   * **Modo Conectado (API Real):** Envia um prompt técnico contendo o contexto completo do erro para o modelo multimodal **`gemini-3.8-flash`** via SDK oficial `google-genai`.
   * **Modo Resiliente (Fallback Determinístico):** Caso a variável de ambiente `GEMINI_API_KEY` não esteja presente ou ocorra falha de rede/cota, o sistema ativa um sintetizador semântico local, assegurando que o código sempre execute e possa ser avaliado sem travar.
4. **Execute & Verify (`SandboxVerifier` & `SecurityAndOverfittingValidator`):**
   * **Prevenção de Patch Overfitting:** Antes de qualquer execução, a árvore sintática (`ast`) da sugestão da IA é inspecionada para bloquear construções perigosas (`eval`, `exec`, `os.system`) e supressões artificiais de erro (`except: pass`).
   * **Quarentena e Oráculo:** O código proposto é compilado em um *namespace* efêmero e testado contra casos nominais (**PASS_TO_PASS**) e casos de borda (**FAIL_TO_PASS**).
   * **Hot-Swap em Memória:** Sendo aprovado em 100% dos testes, a referência ativa da função em memória é substituída em tempo real (`state["active_func"] = verified_callable`), permitindo que requisições subsequentes executem sem custo adicional de inferência.

---

## 3. O Cenário de Exemplo: Processamento de Lote Financeiro

A PoC simula um módulo crítico de processamento de pagamentos: `calcular_ticket_medio_liquido(lote: dict, total_transacoes: int)`.

### A Lógica Defeituosa Original
```python
@auto_heal(oracle_tests=ORACLE_TEST_SUITE, max_retries=3)
def calcular_ticket_medio_liquido(lote: dict, total_transacoes: int) -> float:
    # Defeito 1: Assume acesso direto via colchetes (dispara KeyError se 'desconto' não vier)
    # Defeito 2: Divide diretamente sem validar se 'total_transacoes' é zero (ZeroDivisionError)
    valor_liquido = lote["valor_bruto"] - lote["desconto"]
    return round(valor_liquido / total_transacoes, 2)
```
### O Oráculo de Verificação Multi-Teste (ORACLE_TEST_SUITE)
Para impedir que a IA forneça soluções que apenas mascarem a falha (retornando 0.0 para qualquer entrada), o oráculo exige:
Testes PASS_TO_PASS (Regressão de Negócio):
  Lote {"valor_bruto": 1000.0, "desconto": 100.0} com 9 transações $\rightarrow$ Deve retornar 100.0.
  Lote {"valor_bruto": 250.0, "desconto": 50.0} com 4 transações $\rightarrow$ Deve retornar 50.0.
Testes FAIL_TO_PASS (Casos de Borda e Falha):
  Lote {"valor_bruto": 500.0} (sem chave 'desconto') com 5 transações $\rightarrow$ Deve retornar 100.0. 
  Lote {"valor_bruto": 500.0, "desconto": 50.0} com 0 transações $\rightarrow$ Deve retornar 0.0 (sem disparar divisão por zero).

## 4. Como Executar

### Pré-requisitos
```
Python 3.10 ou superior.
(Opcional) Chave de API gratuita do Google AI Studio para executar via IA real na nuvem.
```

### Instalação das Dependências
Para habilitar a integração com o modelo Gemini real:

```Bash
pip install google-genai
```
(Nota: O projeto utiliza primordialmente a biblioteca padrão do Python: ast, inspect, traceback, difflib, textwrap).

### Execução no Modo 1: Com IA Real (Google Gemini 3.8 Flash)
Obtenha uma chave gratuita no Google AI Studio.

Defina a variável de ambiente no seu terminal:

Linux / macOS / Codespaces:

```Bash
export GEMINI_API_KEY="sua_chave_aqui"
python auto_heal_poc.py
```

Windows (PowerShell):

```PowerShell
$env:GEMINI_API_KEY="sua_chave_aqui"
python auto_heal_poc.py
```

Windows (Prompt de Comando CMD):

```DOS
set GEMINI_API_KEY=sua_chave_aqui
python auto_heal_poc.py
```

### Execução no Modo 2: Sem Chave de API (Fallback Determinístico para Correção Offline)
Caso o script seja executado sem a variável GEMINI_API_KEY, ele acionará automaticamente o modo de fallback, demonstrando o ciclo completo do motor sem depender de conexão externa:

```Bash
python auto_heal_poc.py
```
