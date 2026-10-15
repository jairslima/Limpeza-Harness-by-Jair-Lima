# Resumo Técnico: Limpeza de Harness by Jair Lima

Este documento fornece um resumo técnico detalhado do utilitário e do fluxo de trabalho de limpeza inteligente dos workspaces de IA, garantindo a continuidade do trabalho por qualquer outra inteligência artificial.

## Visão Geral do Sistema
O projeto consiste em um sistema de auditoria e higienização programática dos diretórios de trabalho de todos os harnesses de IA utilizados pelo autor (`Antigravity`, `Claude`, `Codex`, `Copilot`, `Gemini`, `Grok`, `Hermes`, `Kimi`, `Kiro`, `Qwen`, `OpenCode`, `Droid`, `Kilo`).

O objetivo é manter o disco C: livre de dados temporários inflados (como `node_modules`, `build`, `dist`, `.next`, `venv`, `bin`, `obj`), os quais podem ser regenerados a qualquer momento pela internet com `npm install` ou `pip install`, sem jamais comprometer manuscritos, códigos-fonte, repositórios ou bancos de dados locais.

---

## Estrutura de Arquivos
* `harness_clean.py`: Motor principal em Python 3 puro com algoritmo de dupla segurança fail-closed e exclusão otimizada no Windows.
* `SPEC.md`: Especificação técnica de requisitos, arquitetura e decisões de projeto.
* `GEMINI.md`: Este resumo técnico para continuidade por outros modelos de IA.
* `LICENSE`: Licença de software livre MIT.
* `README.md`: Guia de utilização para linha de comando e agendador de tarefas.
* `C:\Users\jairs\bin\harness-clean.ps1`: Wrapper executável no PowerShell.
* `C:\Users\jairs\bin\harness-clean.cmd`: Wrapper executável no CMD e atalhos em lote.

---

## Protocolo de Dupla Segurança e Hardening (Auditado por Grok / DeepSeek)
1. **Filtro Estrutural e de Fronteira:**
   * Apenas pastas com nomes autorizados na allowlist: `node_modules`, `.next`, `.nuxt`, `venv`, `.venv`, `env`, `build`, `dist`, `bin`, `obj`, `__pycache__`, `.pytest_cache`, `.turbo`.
   * Para a pasta `env`, exige obrigatoriamente a presença interna de `pyvenv.cfg` para evitar apagar pastas de configuração homônimas.
   * Fronteira estrita com separador (`\`) para não casar com diretórios de backup como `ClaudeBackup`.
   * Profundidade mínima de 6 níveis na árvore de pastas para garantir que o alvo seja sempre uma subpasta de um projeto.
   * Verificação de manifesto de recriação no diretório pai imediato do projeto (`package.json`, `requirements.txt`, etc.).
2. **Blindagem de Dados e Fail-Closed:**
   * Modelo Fail-Closed: Qualquer erro de permissão ou falha de leitura bloqueia imediatamente a exclusão.
   * Bloqueio preventivo cobrindo dotfiles (`.env`, `.env.*`), chaves privadas (`id_rsa`, `id_ed25519`, `.key`, `.pem`, `.pfx`), certificados, arquivos SQL/dump, credenciais JSON e repositórios `.git`.
   * Ignora links simbólicos e junctions NTFS.
   * Inatividade real calculada recursivamente a partir do timestamp mais recente de todos os arquivos internos (14 dias em rotinas automáticas).
   * Padrão sem argumentos opera em modo de simulação (`--dry-run`).

---

## Agendamento Mensal no Windows (00:00)
A tarefa é registrada no Agendador de Tarefas do Windows via comando administrativo:
```powershell
schtasks /Create /TN "HarnessMonthlyCleanup by Jair Lima" /TR "powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\jairs\bin\harness-clean.ps1\" --auto" /SC MONTHLY /D 1 /ST 00:00 /RL HIGHEST /F
```
Essa instrução roda no dia 1º de cada mês às 00:00, salvando o relatório em `C:\Users\jairs\.gemini\harness_cleanup.log` e o manifesto em `C:\Users\jairs\.gemini\harness_cleanup_manifest.json`.
