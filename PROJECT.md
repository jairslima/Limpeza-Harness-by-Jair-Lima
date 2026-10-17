# Limpeza de Harness by Jair Lima

## Descrição

Utilitário de linha de comando que limpa, com várias camadas de segurança fail-closed, as pastas descartáveis (`node_modules`, `venv`, `.venv`, `env`, `build`, `dist`, `bin`, `obj`, `.next`, `__pycache__` e similares) dos workspaces de IA em `%USERPROFILE%\<Harness>\<Projeto>`. Roda sozinho todo dia 1 pela tarefa `HarnessMonthlyCleanup by Jair Lima`.

## Stack e dependências

- Python 3, somente biblioteca padrão.
- Chama `powershell` (lista de processos) e `schtasks` (tarefas agendadas) para levantar o que está em uso.

## Estrutura

- `harness_clean.py`: ferramenta (única fonte de verdade da limpeza).
- `test_harness_clean.py`: 24 testes automatizados (`unittest`), incluindo execução real em árvore de teste.
- `SPEC.md`: especificação e todas as proteções (seções 1 a 5).
- `README.md`, `GEMINI.md`: documentação de uso e continuidade.
- Alias global: `%USERPROFILE%\bin\harness-clean.cmd` e `harness-clean.ps1`.

## Comandos essenciais

```text
python harness_clean.py                 simulação (padrão, não apaga nada)
python harness_clean.py --dry-run       simulação explícita
python harness_clean.py --auto          execução real com carência de 14 dias (usada pela tarefa mensal)
python harness_clean.py --all           execução real sem carência (só com pedido explícito do Jair)
python harness_clean.py --days N        define a carência
python harness_clean.py --force-large   ignora o teto de segurança, depois de revisar a simulação
python test_harness_clean.py            roda os testes
```

## Decisões arquiteturais

- Simulação por padrão; execução real exige `--auto` ou `--all`.
- Fail-closed: qualquer erro ao levantar referências, processos ou arquivos bloqueia a exclusão.
- Pasta só é apagada se estiver na lista de nomes autorizados, dentro de uma raiz de harness, com manifesto de recriação (`package.json`, `requirements.txt`...), sem dados vitais, sem uso e sem referência.
- Preserva o que é apontado por lançador, atalho, tarefa agendada, configuração de harness (MCP etc.) ou atalho global do `npm`; preserva `venv` e `node_modules` de projeto em uso; preserva `dist`/`bin` com executável que não está instalado em `%USERPROFILE%\bin`; nunca toca em `.claude`, `.codex`, `.gemini`, `.mira` e similares.
- `venv` sem manifesto de dependências nunca é apagado (o ambiente é o único registro).
- Teto por execução real: mais de 15 pastas pesadas (tudo que não é cache) ou 2 GB abortam sem apagar nada.
- Os registros da própria ferramenta (`*_manifest.json`) são ignorados na varredura de configurações.
- A exclusão nunca passa por shell: `shutil.rmtree` direto, com prefixo de caminho longo do Windows e tratamento de somente leitura (revisão de segurança de 2026-10-15: `cmd /c rd` interpretaria `&`, `%` e `^` em nomes de pasta sem espaço).

## Estado atual

- Em uso. Origem do endurecimento: incidente de 2026-10-14, em que um script improvisado de uma sessão do agy apagou 109 pastas (10 GB) sem usar esta ferramenta.
- 24 testes passam. Simulação real com carência de 14 dias: 73 candidatas (3 pesadas), 8 preservadas, 6,6 MB.
- Executada de verdade pelo Agendador do Windows em 2026-10-14 (73 pastas removidas, 0 bloqueadas, 0 falhas, 9 preservadas, 6,6 MB) e de novo em 2026-10-15 com a exclusão sem shell.

## Próximos passos e problemas conhecidos

- Próxima execução automática: 01/11/2026 às 00:00 (tarefa `HarnessMonthlyCleanup by Jair Lima`, `--auto`).
- Limitação: caminhos montados por variáveis de ambiente ou dinamicamente por um script não são detectados; por isso o app instalado deve ficar em `%USERPROFILE%\bin`.
- O projeto não tinha repositório git até 2026-10-15; commits locais, sem remote.
