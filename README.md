# PoC: Arquitetura MAPE-K de Auto-Healing Code em Python

Este repositório contém a Prova de Conceito (PoC) desenvolvida para o trabalho de Prospecção Teórica e Tecnológica da disciplina de Engenharia de Software.

# Sobre o Projeto

Demonstração prática do ciclo fechado MAPE-K (Monitor, Analyze, Plan, Execute over Knowledge) aplicado ao Reparo Automatizado de Programas (APR / Auto-Healing Code):

1. Monitor & Analyze: O decorador @auto_heal intercepta exceções em tempo de execução (ZeroDivisionError, KeyError) e utiliza introspecção nativa (inspect, traceback) para extrair o código-fonte e o stack trace exato.

2. Plan: O LLMRepairAgent sintetiza um patch corretivo preservando a assinatura e as regras de negócio da função.

3. Execute & Verify (Prevenção de Patch Overfitting): Antes de aplicar o hot-swap da função em memória, o SandboxVerifier analisa a Árvore Sintática Abstrata (ast) para bloquear supressões silenciosas de erro (except: pass) ou comandos inseguros, e valida o código contra uma suíte de testes contendo casos PASS_TO_PASS (regressão) e FAIL_TO_PASS.

# Pré-requisitos

Python 3.10 ou superior (utiliza apenas bibliotecas nativas da Standard Library, sem necessidade de pip install externo para o modo determinístico de demonstração).

# Como Executar

Clone o repositório e execute o script principal:
```bash
git clone https://github.com/SEU-USUARIO/poc-auto-healing-code-apr.git
cd poc-auto-healing-code-apr
python auto_heal_poc.py
```
