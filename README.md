# Limpeza de Harness by Jair Lima

Utilitário de linha de comando e automação mensal para manutenção preventiva de espaço em disco nos diretórios de trabalho de IA (`Antigravity`, `Claude`, `Codex`, `Gemini`, `Grok`, `Hermes`, etc.).

## Recursos Principais
* **Dupla Segurança:** Valida nomes de pastas, caminhos, profundidade, ausência de dados sensíveis/bancos de dados e presença de manifestos de recriação.
* **Preservação de Projetos em Uso:** Opção de ignorar pastas modificadas recentemente para não interromper trabalhos ativos.
* **Exclusão de Alto Desempenho:** Utiliza rotinas nativas do Windows para remoção quase instantânea de estruturas densas como `node_modules`.
* **Modo Simulação:** Permite verificar com `--dry-run` o volume de espaço a ser liberado antes de qualquer alteração física.
* **Histórico e Logs:** Registra detalhes de cada execução em `C:\Users\jairs\.gemini\harness_cleanup.log`.

## Como Usar

### 1. Simulação (Sem apagar nada)
```powershell
harness-clean --dry-run
```

### 2. Limpeza Padrão com Carência de 14 Dias (Modo Automático / Mensal)
```powershell
harness-clean --auto
```

### 3. Limpeza Geral Imediata
```powershell
harness-clean --all
```

## Licença
MIT License by Jair Lima.
