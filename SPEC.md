# SPEC: Limpeza de Harness by Jair Lima

## 1. Objetivo
Automatizar a manutenção e higienização mensal dos diretórios de trabalho de todos os harnesses de IA do usuário (Antigravity, Claude, Codex, Copilot, Gemini, Grok, Hermes, Kimi, Kiro, Qwen, OpenCode, Droid, Kilo), removendo com segurança dupla e modelo **fail-closed** apenas pastas descartáveis, compilados temporários e dependências facilmente reinstaláveis da internet, sem nunca comprometer código-fonte original, bancos de dados, arquivos de configuração ou documentos.

## 2. Escopo
* **Diretórios Abrangidos:** Subpastas sob `C:\Users\jairs\<Harness>\<Projeto>\<Alvo>` com fronteira estrita de diretório.
* **Alvos Permitidos (Allowlist Estrita):**
  * Node.js: `node_modules`, `.next`, `.nuxt`, `.turbo`
  * Python: `venv`, `.venv`, `env` (este último requer obrigatoriamente `pyvenv.cfg` interno para distinguir de pastas de configuração), `__pycache__`, `.pytest_cache`
  * Compilações: `build`, `dist`
  * .NET / C#: `bin`, `obj`
* **Fora de Escopo e Proteção Absoluta:**
  * Quaisquer pastas fora dos diretórios de harness permitidos (incluindo pastas com prefixos similares como `ClaudeBackup`).
  * Pastas com profundidade menor que 6 níveis (garantindo que o alvo esteja contido dentro de um subprojeto específico).
  * Pastas que contenham bancos de dados (`.db`, `.sqlite`, `.fdb`, `.mdb`, `.mdf`, `.ldf`), chaves/certificados (`.key`, `.pem`, `.pfx`, `.cer`, `id_rsa`, `id_ed25519`), arquivos de ambiente (`.env`, `.env.*`), credenciais JSON ou repositórios `.git`.
  * Links simbólicos e junções NTFS (Junctions).

## 3. Arquitetura e Mecanismo de Dupla Segurança
* **Camada 1 (Filtro Estrutural e de Assinatura):**
  * Validação exata do nome contra a lista estrita permitida.
  * Validação de caminho com fronteira explícita de separador (`\`) para prevenir colisão com nomes de pastas de backup.
  * Profundidade mínima de 6 níveis para exigir que o alvo resida dentro de uma pasta de projeto.
  * Validação estrita de existência de manifesto de recriação no diretório pai imediato (`package.json`, `requirements.txt`, `setup.py`, `pyproject.toml`, etc.). Não consulta diretórios avós para evitar leituras acidentais da home do usuário.
* **Camada 2 (Blindagem Fail-Closed e Inatividade Real):**
  * **Modelo Fail-Closed:** Qualquer erro de leitura, exceção de permissão ou falha de acesso resulta em bloqueio imediato da exclusão daquela pasta.
  * Inspeção preventiva de conteúdo cobrindo dotfiles (`.env*`), chaves sem extensão (`id_rsa*`, `id_ed25519*`), credenciais JSON e extensões de bancos de dados.
  * Filtro de inatividade recursivo: calcula o timestamp mais recente de todos os arquivos e subpastas internas, garantindo que projetos com arquivos modificados recentemente nos últimos 14 dias não sejam considerados inativos.
  * Princípio do Menor Privilégio: executar o script sem argumentos opera em modo de simulação (`--dry-run`), exigindo `--auto` ou `--all` explícitos para qualquer exclusão física.
  * Exclusão otimizada via comando nativo `cmd /c rd /s /q` com rotina de contingência para remoção de atributos somente leitura (`read-only`).
  * Auditoria centralizada: gravação de histórico de operações em `C:\Users\jairs\.gemini\harness_cleanup.log` e manifesto estruturado em `C:\Users\jairs\.gemini\harness_cleanup_manifest.json`.

## 4. Dependências
* Python 3.8+ (biblioteca padrão: `os`, `sys`, `json`, `time`, `shutil`, `stat`, `argparse`, `subprocess`, `datetime`, `pathlib`).
* Sem necessidade de pacotes externos via pip.
* PowerShell 5.1 / 7+ para wrappers de execução e agendamento.

## 5. Decisões Técnicas
* **Auditoria Cruzada Grok (DeepSeek V4 Pro):** Implementação de todas as recomendações de segurança, incluindo correção de dotfiles, modelo fail-closed, cálculo exato de bytes e validação estrita de fronteiras e profundidade.
* **Uso de Python puro e comandos nativos:** Garante portabilidade universal no ambiente Windows e altíssima velocidade de exclusão em árvores densas de arquivos como `node_modules`.
* **Separação entre Simulação e Execução:** Padrão seguro em modo simulação caso nenhuma flag seja informada.

## 6. Instruções Operacionais
* Executar simulação: `harness-clean --dry-run` ou apenas `harness-clean`
* Executar limpeza com carência de 14 dias (padrão mensal): `harness-clean --auto`
* Executar limpeza completa imediata de todos os descartáveis: `harness-clean --all`
* Consultar logs de execução: `Get-Content C:\Users\jairs\.gemini\harness_cleanup.log -Tail 50`
* Consultar manifesto JSON: `Get-Content C:\Users\jairs\.gemini\harness_cleanup_manifest.json`

## 5. Proteção contra uso e referências (2026-10-14)

Motivo: em 2026-10-14 uma sessão do agy apagou 109 pastas (10 GB) com um script próprio, sem carência e sem checar uso. O `dist` de um app em execução, o `dist` de 4 apps com lançador em `C:\Users\jairs\bin` e o `venv` de um CLI foram removidos. Esta ferramenta já tinha manifesto, carência, bloqueio de dados vitais e fail-closed, mas não verificava uso. Passou a verificar.

Checagem 5b (executada antes da varredura pesada de arquivos críticos), sempre FAIL-CLOSED:

1. **Referenciada:** a pasta é preservada se algum lançador/script em `C:\Users\jairs\bin` e `Scripts`, atalho (`.lnk`) da Área de Trabalho ou do Menu Iniciar, ou tarefa agendada (`schtasks`) contém um caminho dentro dela.
2. **Em uso:** preservada se algum processo em execução tem executável ou linha de comando dentro dela (o instantâneo é renovado a cada 20 s, inclusive na revalidação imediatamente antes de apagar).
3. **Dependência de execução:** `venv`, `.venv` e `env` são preservados se um script do próprio projeto executa `venv\Scripts\...` ou `venv/bin/python`; `node_modules` se um script usa `node_modules\.bin`.
4. Se não for possível levantar as referências ou listar os processos, **nada é apagado**.
5. O log lista as pastas preservadas por uso (`PRESERVADA <pasta> (<motivo>)`).

Proteções acrescentadas na mesma data, depois de restaurar as dependências e simular o pior caso (`--days 0`):

6. **Configurações de harness** (`.claude.json`, `settings.json`, `config.toml`, MCP etc. nas pastas `.claude`, `.codex`, `.gemini`, `.qwen`, `.copilot`, `.kimi`, `.kiro`, `.grok`, `.hermes`, `.cursor`, `.config\opencode`) contam como referência, assim como os atalhos do `npm` global (`AppData\Roaming\npm`). Os registros desta própria ferramenta (`*_manifest.json`, `harness_cleanup*`) são ignorados, senão a lista de uma execução protegeria a seguinte.
7. **Dependência de projeto em uso:** `node_modules`, `venv`, `.venv` e `env` são preservados se qualquer lançador, configuração, tarefa ou atalho aponta para dentro do **projeto** que os contém (o servidor MCP aponta para `server.js`, não para `node_modules`, mas precisa dele).
8. **Única cópia instalada:** `dist` ou `bin` com executável (`.exe`, `.scr`) que não existe em `C:\Users\jairs\bin` é preservado.
9. **Pastas de configuração de harness** (`.claude`, `.codex`, `.gemini`, `.mira`, `.agents`, `.qwen`, `.kimi`, `.kiro`, `.github`) nunca entram na limpeza, em qualquer profundidade.
10a. **Exclusão sem shell:** `remove_directory` usa `shutil.rmtree` (prefixo `\\?\` no Windows), nunca `cmd /c rd`, para que nomes de pasta com `&`, `%` ou `^` não sejam interpretados por um shell.
10. **Teto por execução real:** mais de 15 pastas **pesadas** (tudo que não é `__pycache__` ou `.pytest_cache`) ou mais de 2 GB abortam a execução inteira sem apagar nada; só `--force-large`, depois de revisar a simulação, ignora o teto. Dezenas de caches pequenos são normais e não acionam o teto.

Testes: `python test_harness_clean.py` (24 casos, incluindo falhas de levantamento, execução real em árvore de teste e remoção de caminho longo, somente leitura e nomes com metacaracteres). Limitação conhecida: caminhos montados por variáveis de ambiente ou construídos dinamicamente por um script não são detectados; por isso o app instalado deve ficar em `C:\Users\jairs\bin`, fora das pastas de projeto.
