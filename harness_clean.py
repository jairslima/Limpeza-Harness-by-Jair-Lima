#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitário de Limpeza Inteligente dos Workspaces de IA by Jair Lima
Licença MIT

Auditoria e higienização programática com fail-closed e dupla checagem rigorosa
de todos os workspaces de IA (Antigravity, Claude, Codex, Copilot, Gemini, Grok, Hermes, etc.).
"""

import os
import sys
import json
import time
import shutil
import stat
import re
import argparse
import subprocess
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
from pathlib import Path

# Allowlist estrita de pastas descartáveis
DISPOSABLE_NAMES = {
    "node_modules", ".next", ".nuxt", "venv", ".venv", "env",
    "build", "dist", "bin", "obj", "__pycache__", ".pytest_cache", ".turbo"
}

# Raízes autorizadas para busca (apenas pastas de harnesses do usuário)
ALLOWED_HARNESS_ROOTS = [
    HOME + r"\Antigravity",
    HOME + r"\Claude",
    HOME + r"\Codex",
    HOME + r"\Copilot",
    HOME + r"\Gemini",
    HOME + r"\Grok",
    HOME + r"\Hermes",
    HOME + r"\Kimi",
    HOME + r"\Kiro",
    HOME + r"\Qwen",
    HOME + r"\OpenCode",
    HOME + r"\Droid",
    HOME + r"\Kilo"
]

# Extensões vitais blindadas: se uma pasta contiver arquivos desse tipo, ela NUNCA será apagada
CRITICAL_EXTENSIONS = {
    ".db", ".sqlite", ".sqlite3", ".fdb", ".mdb", ".accdb", ".mdf", ".ldf",
    ".key", ".pem", ".pfx", ".cer", ".crt", ".p12", ".ppk", ".kdbx",
    ".sql", ".bak", ".dump"
}

# Nomes e prefixos de arquivos vitais sem extensão padrão
CRITICAL_NAME_PREFIXES = (
    ".env", "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa",
    "credentials", "serviceaccount", "service-account", "secrets"
)

DEFAULT_LOG_PATH = HOME + r"\.gemini\harness_cleanup.log"
DEFAULT_MANIFEST_PATH = HOME + r"\.gemini\harness_cleanup_manifest.json"

def log_message(msg: str, log_file: str = DEFAULT_LOG_PATH, to_console: bool = True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    if to_console:
        print(msg)
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def get_folder_size_bytes(path: str) -> int:
    """Calcula tamanho total em bytes sem arredondamentos intermediários."""
    total_bytes = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    total_bytes += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total_bytes += get_folder_size_bytes(entry.path)
            except (PermissionError, FileNotFoundError):
                continue
    except (PermissionError, FileNotFoundError):
        pass
    return total_bytes

def is_critical_file(filename: str) -> bool:
    """Verifica se o nome ou a extensão do arquivo corresponde a dado confidencial ou banco de dados."""
    fn_lower = filename.lower()
    
    # Tratamento explícito de dotfiles (.env, .env.local, etc.) e chaves SSH/credenciais sem extensão
    if fn_lower == ".env" or fn_lower.startswith(".env."):
        return True
        
    for prefix in CRITICAL_NAME_PREFIXES:
        if fn_lower == prefix or fn_lower.startswith(prefix + ".") or fn_lower.startswith(prefix + "_") or fn_lower.startswith(prefix + "-"):
            return True
            
    ext = os.path.splitext(fn_lower)[1]
    if ext in CRITICAL_EXTENSIONS:
        return True
        
    return False

def has_critical_files(path: str) -> tuple:
    """
    Inspeciona a pasta recursivamente procurando bancos de dados ou chaves.
    Opera com FAIL-CLOSED: qualquer erro de permissão ou falha de leitura
    retorna (True, erro), bloqueando imediatamente a deleção.
    """
    try:
        for root, dirs, files in os.walk(path):
            if ".git" in dirs:
                return True, "Contém repositório git (.git)"
                
            for file in files:
                if is_critical_file(file):
                    return True, f"Contém arquivo protegido: {file}"
    except Exception as e:
        # Fail-closed: se não foi possível varrer completamente, bloqueia
        return True, f"Erro ao inspecionar diretório ({str(e)})"
        
    return False, "Nenhum arquivo crítico encontrado"

def get_latest_content_mtime(path: str) -> float:
    """
    Obtém recursivamente o timestamp mais recente entre todos os arquivos e subdiretórios.
    No Windows, o mtime da pasta raiz não é atualizado quando arquivos internos são alterados.
    """
    latest_mtime = 0.0
    try:
        latest_mtime = max(latest_mtime, os.path.getmtime(path))
        for root, dirs, files in os.walk(path):
            for d in dirs:
                dp = os.path.join(root, d)
                try:
                    if not os.path.islink(dp):
                        latest_mtime = max(latest_mtime, os.path.getmtime(dp))
                except Exception:
                    pass
            for f in files:
                fp = os.path.join(root, f)
                try:
                    latest_mtime = max(latest_mtime, os.path.getmtime(fp))
                except Exception:
                    pass
    except Exception:
        # Se falhar a leitura, assume que o arquivo é recente para fail-closed
        return time.time()
        
    return latest_mtime

def has_project_manifest(parent_path: str, folder_type: str, full_target_path: str) -> tuple:
    """
    Valida estritamente se na pasta pai imediata existe um manifesto que comprove
    que os dados são recriáveis a partir da internet ou compilador.
    """
    if not os.path.isdir(parent_path):
        return False, "Pasta pai inexistente"
        
    try:
        files = set(os.listdir(parent_path))
    except Exception as e:
        return False, f"Falha ao ler diretório pai ({str(e)})"
        
    if folder_type in ("node_modules", ".next", ".nuxt", ".turbo"):
        if "package.json" in files:
            return True, "Validado por package.json"
        return False, "Ausência de package.json no projeto"
        
    elif folder_type in ("venv", ".venv"):
        if any(f in files for f in ("requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "poetry.lock")):
            return True, "Validado por manifesto Python"
        # Sem manifesto de dependências o venv é o ÚNICO registro do que o projeto precisa: não é reproduzível.
        return False, "Nenhum manifesto de dependências (requirements.txt, pyproject.toml...): ambiente não reproduzível"
        
    elif folder_type == "env":
        # Proteção contra pastas de configuração chamadas 'env':
        # Para ser considerado virtualenv, DEVE conter pyvenv.cfg dentro de si
        pyvenv_cfg = os.path.join(full_target_path, "pyvenv.cfg")
        if not os.path.isfile(pyvenv_cfg):
            return False, "Pasta 'env' sem pyvenv.cfg (possível diretório de configurações, não virtualenv)"
        return True, "Validado como virtualenv Python por pyvenv.cfg interno"
        
    elif folder_type in ("build", "dist"):
        if any(f in files for f in ("package.json", "setup.py", "pyproject.toml", "CMakeLists.txt", "Cargo.toml")):
            return True, "Validado por arquivo de compilação do projeto"
        if any(f.endswith((".spec", ".csproj", ".sln", ".vcxproj")) for f in files):
            return True, "Validado por projeto ou spec de compilação"
        return False, "Nenhum manifesto ou arquivo de compilação correspondente"
        
    elif folder_type in ("bin", "obj"):
        if any(f.endswith((".csproj", ".fsproj", ".sln", ".vcxproj")) for f in files):
            return True, "Validado por projeto .NET"
        return False, "Não é um projeto .NET compilado"
        
    elif folder_type in ("__pycache__", ".pytest_cache"):
        return True, "Cache interno recriável"
        
    return False, "Tipo não reconhecido"

# Onde ficam lançadores, atalhos e scripts que apontam para executáveis dentro de projetos
# (pasta, extensões, varrer subpastas?). Qualquer pasta apontada por eles NUNCA é apagada.
LAUNCHER_DIRS = [
    (HOME + r"\bin", (".cmd", ".bat", ".ps1", ".vbs"), False),
    (HOME + r"\Scripts", (".cmd", ".bat", ".ps1", ".vbs"), False),
    (HOME + r"\AppData\Roaming\npm", (".cmd", ".ps1"), False),
    (HOME + r"\Desktop", (".lnk", ".cmd", ".bat"), True),
    (HOME + r"\AppData\Roaming\Microsoft\Windows\Start Menu\Programs", (".lnk",), True),
]
CHECK_SCHEDULED_TASKS = True

# Arquivos de configuração de harnesses (servidores MCP etc.) que também contam como referência.
# (pasta, varrer subpastas?) Só .json/.toml/.yaml/.yml/.jsonc; documentação .md não conta.
CONFIG_FILES = [HOME + r"\.claude.json"]
CONFIG_DIRS = [
    HOME + r"\.claude", HOME + r"\.codex", HOME + r"\.gemini", HOME + r"\.qwen",
    HOME + r"\.copilot", HOME + r"\.kimi", HOME + r"\.kiro", HOME + r"\.grok",
    HOME + r"\.hermes", HOME + r"\.cursor", HOME + r"\.config\opencode",
    HOME + r"\.gemini\antigravity-cli",
]
CONFIG_EXTENSIONS = (".json", ".toml", ".yaml", ".yml", ".jsonc")
# Registros desta própria ferramenta listam caminhos de execuções anteriores; nunca contam como configuração em uso.
CONFIG_IGNORED_NAME_PARTS = ("cleanup_manifest", "harness_cleanup", "_manifest.json")

# Pasta onde ficam os apps instalados: um dist/bin com executável que NÃO existe aqui pode ser a única cópia.
INSTALL_DIR = HOME + r"\bin"
EXE_NAMES_IGNORED = {"unins000.exe", "python.exe", "pythonw.exe"}

# Dependências de execução: se o PROJETO que as contém é apontado por lançador/configuração/tarefa, são preservadas.
DEPENDENCY_FOLDERS = {"node_modules", "venv", ".venv", "env"}

# Pastas de configuração de harness: nunca entram na limpeza, em qualquer profundidade.
PROTECTED_PATH_COMPONENTS = {".claude", ".codex", ".gemini", ".mira", ".agents", ".qwen", ".kimi", ".kiro", ".github"}

# Teto de segurança por execução automática (real): acima disso nada é apagado.
# Conta só pastas PESADAS (tudo que não é cache): dezenas de __pycache__ minúsculos são normais, 109 build/dist/venv não.
CACHE_FOLDER_NAMES = {"__pycache__", ".pytest_cache"}
MAX_AUTO_ITEMS = 15
MAX_AUTO_BYTES = 2 * 1024 ** 3
RUNTIME_SCRIPT_EXTENSIONS = (".bat", ".cmd", ".ps1", ".sh", ".vbs")

# Guardas contra uso (lançadores, tarefas, processos, scripts do projeto). Ver SPEC.md, seção 5.
_GUARD = {"refs": None, "refs_failed": False, "running": None, "running_at": 0.0}
PRESERVED_FOR_USE = []
USE_REASON_PREFIXES = ("Referenciado por", "Há processo em execução", "Script do projeto", "Pode ser a única cópia",
                       "Dentro de pasta de configuração")


def _harness_path_regex():
    raizes = "|".join(re.escape(os.path.abspath(r)) for r in ALLOWED_HARNESS_ROOTS)
    return re.compile("(?:" + raizes + r")[^\"'\r\n<>|*?]*", re.IGNORECASE)


def collect_launcher_references():
    """
    Lista (caminho_minúsculo, origem) de tudo que aponta para dentro das raízes de harness:
    lançadores/scripts em bin e Scripts, atalhos e tarefas agendadas. Retorna None em falha
    (o chamador trata como fail-closed).
    """
    rx = _harness_path_regex()
    refs = []
    try:
        for base, exts, recursive in LAUNCHER_DIRS:
            if not os.path.isdir(base):
                continue
            walker = os.walk(base) if recursive else [(base, [], os.listdir(base))]
            for root, _dirs, files in walker:
                for fn in files:
                    fp = os.path.join(root, fn)
                    if not fn.lower().endswith(exts) or not os.path.isfile(fp):
                        continue
                    with open(fp, "rb") as f:
                        data = f.read(1_000_000)
                    texto = (data.decode("utf-16-le", "ignore") + "\n" + data.decode("cp1252", "ignore")).replace("\x00", "")
                    for m in rx.finditer(texto):
                        refs.append((m.group(0).lower(), fp))
        config_paths = [p for p in CONFIG_FILES if os.path.isfile(p)]
        for base in CONFIG_DIRS:
            if os.path.isdir(base):
                for fn in os.listdir(base):
                    fp = os.path.join(base, fn)
                    if fn.lower().endswith(CONFIG_EXTENSIONS) and os.path.isfile(fp) \
                            and not any(parte in fn.lower() for parte in CONFIG_IGNORED_NAME_PARTS):
                        config_paths.append(fp)
        for fp in config_paths:
            with open(fp, "rb") as f:
                data = f.read(3_000_000)
            texto = data.decode("utf-8", "ignore").replace("\\\\", "\\").replace("/", "\\")
            for m in rx.finditer(texto):
                refs.append((m.group(0).lower(), "configuração " + os.path.basename(fp)))
        if CHECK_SCHEDULED_TASKS:
            out = subprocess.run(["schtasks", "/query", "/fo", "csv", "/v"], capture_output=True, timeout=180)
            if len(out.stdout) < 200:
                return None
            for line in out.stdout.decode("cp1252", "replace").splitlines():
                for m in rx.finditer(line):
                    nome = line.split('","')[1] if '","' in line else "?"
                    refs.append((m.group(0).lower(), "tarefa agendada " + nome))
    except Exception:
        return None
    return refs


def get_running_process_lines():
    """Executável e linha de comando de todos os processos em execução (minúsculos). None em falha."""
    comando = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "Get-CimInstance Win32_Process | ForEach-Object { $_.ExecutablePath; $_.CommandLine }"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
                           capture_output=True, timeout=120)
        if r.returncode != 0 or len(r.stdout) < 50:
            return None
        return [l.strip().lower() for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
    except Exception:
        return None


def refresh_guard_context():
    if _GUARD["refs"] is None and not _GUARD["refs_failed"]:
        _GUARD["refs"] = collect_launcher_references()
        _GUARD["refs_failed"] = _GUARD["refs"] is None
    if _GUARD["running"] is None or time.time() - _GUARD["running_at"] > 20:
        _GUARD["running"] = get_running_process_lines()
        _GUARD["running_at"] = time.time()


def folder_use_reason(norm: str, basename: str, parent: str):
    """Motivo (str) se a pasta está referenciada, em uso ou é dependência de execução; None se livre."""
    refresh_guard_context()
    if _GUARD["refs"] is None:
        return "Não foi possível levantar lançadores, atalhos e tarefas que apontam para projetos (fail-closed)"
    if _GUARD["running"] is None:
        return "Não foi possível listar os processos em execução (fail-closed)"
    prefixo = norm.lower().rstrip(os.sep) + os.sep
    for caminho, origem in _GUARD["refs"]:
        if caminho.startswith(prefixo):
            return f"Referenciado por {origem}"
    if basename in DEPENDENCY_FOLDERS:
        projeto = parent.lower().rstrip(os.sep) + os.sep
        for caminho, origem in _GUARD["refs"]:
            if caminho.startswith(projeto):
                return f"Referenciado por {origem} (dependência de projeto em uso)"
    if any(prefixo in linha for linha in _GUARD["running"]):
        return "Há processo em execução usando arquivos desta pasta"
    return project_scripts_use_folder(parent, basename)


def installed_file_names():
    """Nomes (minúsculos) de todos os arquivos em INSTALL_DIR, até 3 níveis. None se a pasta não existir."""
    if not os.path.isdir(INSTALL_DIR):
        return None
    nomes = set()
    base_depth = INSTALL_DIR.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(INSTALL_DIR):
        if root.count(os.sep) - base_depth >= 3:
            dirs[:] = []
        nomes.update(f.lower() for f in files)
    return nomes


def only_installed_copy_reason(norm: str, basename: str):
    """dist/bin com executável que não existe em INSTALL_DIR: pode ser a única cópia do app entregue."""
    if basename not in ("dist", "bin"):
        return None
    instalados = installed_file_names()
    if instalados is None:
        return "Pasta de instalação (bin) ausente, não é possível confirmar cópia instalada (fail-closed)"
    faltando = []
    base_depth = norm.count(os.sep)
    try:
        for root, dirs, files in os.walk(norm):
            dirs[:] = [d for d in dirs if d.lower() not in ("_internal", "node_modules", "lib", "libs", "runtimes", "resources", "locales")]
            if root.count(os.sep) - base_depth >= 3:
                dirs[:] = []
            for f in files:
                fl = f.lower()
                if fl.endswith((".exe", ".scr")) and fl not in EXE_NAMES_IGNORED and fl not in instalados:
                    faltando.append(f)
    except Exception as e:
        return f"Erro ao inspecionar executáveis ({e}) (fail-closed)"
    if faltando:
        return f"Pode ser a única cópia instalada: {', '.join(faltando[:3])} não existe em {INSTALL_DIR}"
    return None


def project_scripts_use_folder(parent: str, basename: str):
    """Scripts do próprio projeto que EXECUTAM a partir de venv/node_modules (ex.: venv\\Scripts\\python.exe)."""
    if basename in ("venv", ".venv", "env"):
        rx = re.compile(r"(?<![A-Za-z_.])" + re.escape(basename) + r"[\\/](?:scripts|bin[\\/]python)", re.IGNORECASE)
    elif basename == "node_modules":
        rx = re.compile(r"node_modules[\\/]\.bin", re.IGNORECASE)
    else:
        return None
    try:
        for fn in os.listdir(parent):
            fp = os.path.join(parent, fn)
            if fn.lower().endswith(RUNTIME_SCRIPT_EXTENSIONS) and os.path.isfile(fp):
                with open(fp, "rb") as f:
                    texto = f.read(500_000).decode("utf-8", "ignore")
                if rx.search(texto):
                    return f"Script do projeto ({fn}) executa a partir de '{basename}'"
    except Exception as e:
        return f"Script do projeto ilegível ({e}) (fail-closed)"
    return None


def is_path_strictly_within_harness(norm_path: str) -> bool:
    """Exige fronteira exata com separador de diretório para evitar casamento com pastas tipo ClaudeBackup."""
    for hr in ALLOWED_HARNESS_ROOTS:
        hr_boundary = os.path.abspath(hr).rstrip(os.sep) + os.sep
        if norm_path.lower().startswith(hr_boundary.lower()):
            return True
    return False

def double_check_safety(path: str, min_inactive_days: int = 0) -> tuple:
    """
    Camada Dupla de Segurança com FAIL-CLOSED:
    1. Nome e caminho estritamente autorizados, fronteira estrita de harness e profundidade mínima.
    2. Ausência comprovada de arquivos vitais (.db, chaves, .env) e manifesto de recriação.
    """
    norm = os.path.abspath(path)
    
    # Checagem de symlinks e junctions: nunca seguir atalhos para fora
    if os.path.islink(norm):
        return False, "É um link simbólico ou junction NTFS (bloqueado por segurança)"
        
    basename = os.path.basename(norm).lower()
    
    # Checagem 1: Nome na allowlist
    if basename not in DISPOSABLE_NAMES:
        return False, f"Nome '{basename}' não consta na lista segura"
        
    # Checagem 2: Pertencimento com fronteira estrita aos harnesses autorizados
    if not is_path_strictly_within_harness(norm):
        return False, "Fora das pastas autorizadas ou colidindo com sufixo (ex: ClaudeBackup)"
        
    # Checagem 2b: pastas de configuração de harness (.claude, .codex, .gemini...) são intocáveis
    if any(p.lower() in PROTECTED_PATH_COMPONENTS for p in norm.split(os.sep)[:-1]):
        return False, "Dentro de pasta de configuração de harness (protegida)"

    # Checagem 3: Profundidade mínima de 6 níveis (ex: <HOME>\<Harness>\<Projeto>\<Alvo>)
    parts = norm.split(os.sep)
    if len(parts) < 6:
        return False, f"Profundidade insuficiente ({len(parts)} níveis), não está contido em um subprojeto"
        
    # Checagem 4: Deve ser diretório físico
    if not os.path.isdir(norm):
        return False, "Não é um diretório físico válido"
        
    parent = os.path.dirname(norm)
    
    # Checagem 5: Verificação estrita de manifesto de recriação no diretório pai imediato
    ok_manifest, manifest_reason = has_project_manifest(parent, basename, norm)
    if not ok_manifest:
        return False, f"Manifesto reprovado: {manifest_reason}"
        
    # Checagem 5b: lançadores/atalhos/tarefas que apontam para a pasta, processos em uso e
    # scripts do projeto que executam a partir dela (incidente de 2026-10-14)
    uso = folder_use_reason(norm, basename, parent) or only_installed_copy_reason(norm, basename)
    if uso:
        return False, uso

    # Checagem 6: Blindagem fail-closed de dados vitais (bancos de dados, chaves, .env, .git)
    has_crit, crit_reason = has_critical_files(norm)
    if has_crit:
        return False, f"Blindagem ativa: {crit_reason}"
        
    # Checagem 7: Inatividade real recursiva (se solicitada)
    if min_inactive_days > 0:
        try:
            latest_mtime = get_latest_content_mtime(norm)
            last_mod = datetime.fromtimestamp(latest_mtime)
            if datetime.now() - last_mod < timedelta(days=min_inactive_days):
                return False, f"Modificado recentemente ({last_mod.strftime('%d/%m/%Y %H:%M')}), em desenvolvimento ativo"
        except Exception as e:
            # Fail-closed: se não conseguiu auditar o timestamp, bloqueia
            return False, f"Erro ao verificar data de inatividade ({str(e)})"
            
    return True, "Aprovado com dupla segurança"

def scan_disposable_folders(min_inactive_days: int = 0) -> list:
    """Varre as raízes de harness e identifica todas as pastas elegíveis com fail-closed."""
    candidates = []
    
    for hr in ALLOWED_HARNESS_ROOTS:
        if not os.path.isdir(hr):
            continue
            
        try:
            for root, dirs, files in os.walk(hr):
                dirs_to_remove = []
                for d in dirs:
                    d_lower = d.lower()
                    if d_lower in DISPOSABLE_NAMES:
                        full_dir = os.path.join(root, d)
                        ok, reason = double_check_safety(full_dir, min_inactive_days)
                        if not ok and reason.startswith(USE_REASON_PREFIXES):
                            PRESERVED_FOR_USE.append((os.path.relpath(full_dir, os.path.dirname(hr)), reason))
                        if ok:
                            candidates.append({
                                "path": full_dir,
                                "name": d,
                                "rel_path": os.path.relpath(full_dir, os.path.dirname(hr)),
                                "harness": os.path.basename(hr)
                            })
                        dirs_to_remove.append(d)
                for d in dirs_to_remove:
                    dirs.remove(d)
        except Exception:
            continue
            
    return candidates

def remove_directory(path: str) -> bool:
    """
    Remove o diretório SEM passar por shell: `cmd /c rd` interpretaria &, %, ^ e afins em nomes de pasta
    sem espaço (revisão de segurança de 2026-10-15). Usa o prefixo de caminho longo do Windows (node_modules
    costuma passar de 260 caracteres) e limpa o atributo somente leitura quando necessário.
    """
    alvo = os.path.abspath(path)
    if os.name == "nt" and not alvo.startswith("\\\\?\\"):
        alvo = "\\\\?\\" + alvo

    def remove_readonly(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    try:
        try:
            shutil.rmtree(alvo, onexc=remove_readonly)
        except TypeError:  # Python anterior a 3.12
            shutil.rmtree(alvo, onerror=remove_readonly)
    except Exception:
        pass

    return not os.path.exists(path)


def main():
    parser = argparse.ArgumentParser(
        description="Utilitário de Limpeza Inteligente dos Workspaces de IA by Jair Lima"
    )
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula a limpeza e exibe o que seria removido")
    parser.add_argument("--auto", action="store_true", help="Modo automático para agendador (aplica carência de inatividade de 14 dias)")
    parser.add_argument("--all", action="store_true", help="Modo forçado: remove todos os itens elegíveis sem carência de inatividade")
    parser.add_argument("--days", type=int, default=None, help="Número de dias mínimos de inatividade (padrão: 14 para --auto)")
    parser.add_argument("--force-large", action="store_true", help="Ignora o teto de segurança por execução (só depois de revisar a simulação)")
    parser.add_argument("--log-file", type=str, default=DEFAULT_LOG_PATH, help="Caminho do arquivo de log")
    parser.add_argument("--manifest-file", type=str, default=DEFAULT_MANIFEST_PATH, help="Caminho do manifesto JSON")
    
    args = parser.parse_args()
    
    # Princípio do Menor Privilégio: Se nenhuma ação for informada, o padrão absoluto é SIMULAÇÃO
    is_simulation = args.dry_run or (not args.auto and not args.all)
    
    if args.days is not None:
        min_days = args.days
    elif args.all:
        min_days = 0
    elif args.auto:
        min_days = 14
    else:
        min_days = 14
        
    header = f"=== Limpeza Inteligente de Harness de IA by Jair Lima ==="
    log_message(header, args.log_file)
    log_message(f"Modo: {'SIMULAÇÃO (--dry-run)' if is_simulation else 'EXECUÇÃO REAL'}", args.log_file)
    log_message(f"Filtro de Inatividade: {min_days} dias sem alteração", args.log_file)
    log_message("Varrendo repositórios e pastas de projetos com verificação Fail-Closed...", args.log_file)
    
    candidates = scan_disposable_folders(min_inactive_days=min_days)

    if PRESERVED_FOR_USE:
        log_message(f"Preservadas por estarem em uso ou referenciadas: {len(PRESERVED_FOR_USE)}", args.log_file)
        for rel_p, motivo in PRESERVED_FOR_USE[:50]:
            log_message(f"    PRESERVADA {rel_p} ({motivo})", args.log_file)

    if not candidates:
        log_message("Nenhum item descartável elegível encontrado no momento. Ambiente 100% limpo!", args.log_file)
        return
        
    log_message(f"Encontrados {len(candidates)} diretórios candidatos a limpeza:", args.log_file)
    
    total_freed_bytes = 0
    success_count = 0
    audit_records = []

    if not is_simulation and not args.force_large:
        total_candidates_bytes = sum(get_folder_size_bytes(c["path"]) for c in candidates)
        heavy_count = sum(1 for c in candidates if c["name"].lower() not in CACHE_FOLDER_NAMES)
        if heavy_count > MAX_AUTO_ITEMS or total_candidates_bytes > MAX_AUTO_BYTES:
            log_message(
                f"ABORTADO: {heavy_count} pastas pesadas (fora caches) e {total_candidates_bytes / 1024 ** 3:.2f} GB excedem o teto de segurança "
                f"({MAX_AUTO_ITEMS} pastas pesadas / {MAX_AUTO_BYTES / 1024 ** 3:.0f} GB por execução). Nada foi apagado. "
                "Revise com --dry-run e, se estiver de acordo, rode com --force-large.", args.log_file)
            return
    
    for i, it in enumerate(candidates, 1):
        path = it["path"]
        size_bytes = get_folder_size_bytes(path)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        rel = it["rel_path"]
        
        record = {
            "path": path,
            "rel_path": rel,
            "size_mb": size_mb,
            "timestamp": datetime.now().isoformat(),
            "status": "simulated" if is_simulation else "pending"
        }
        
        if is_simulation:
            total_freed_bytes += size_bytes
            log_message(f"[{i}/{len(candidates)}] [SIMULAÇÃO] {size_mb:>6.1f} MB | {rel}", args.log_file)
            audit_records.append(record)
        else:
            # Revalidação de dupla segurança em tempo real antes de apagar
            ok, reason = double_check_safety(path, min_inactive_days=min_days)
            if not ok:
                record["status"] = f"blocked: {reason}"
                audit_records.append(record)
                log_message(f"[{i}/{len(candidates)}] BLOQUEADO: {rel} ({reason})", args.log_file)
                continue
                
            removed = remove_directory(path)
            if removed:
                total_freed_bytes += size_bytes
                success_count += 1
                record["status"] = "deleted"
                audit_records.append(record)
                log_message(f"[{i}/{len(candidates)}] REMOVIDO:  {size_mb:>6.1f} MB | {rel}", args.log_file)
            else:
                record["status"] = "failed_in_use"
                audit_records.append(record)
                log_message(f"[{i}/{len(candidates)}] FALHA (bloqueado em uso): {rel}", args.log_file)
                
    total_freed_mb = total_freed_bytes / (1024 * 1024)
    total_freed_gb = total_freed_bytes / (1024 * 1024 * 1024)
    
    summary = (
        f"\n=== Resumo da Operação ===\n"
        f"Total de itens processados: {len(candidates)}\n"
        f"Itens removidos com sucesso: {success_count if not is_simulation else len(candidates)}\n"
        f"Espaço total {'que seria liberado' if is_simulation else 'liberado'}: {total_freed_mb:.1f} MB ({total_freed_gb:.2f} GB)\n"
    )
    log_message(summary, args.log_file)
    
    # Grava manifesto JSON para auditoria
    try:
        manifest_data = {
            "last_run": datetime.now().isoformat(),
            "mode": "simulation" if is_simulation else "execution",
            "freed_mb": round(total_freed_mb, 2),
            "freed_gb": round(total_freed_gb, 2),
            "items_count": len(audit_records),
            "items": audit_records
        }
        with open(args.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

if __name__ == "__main__":
    main()
