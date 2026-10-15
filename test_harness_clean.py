# -*- coding: utf-8 -*-
"""Testes das proteções de uso e referência da Limpeza de Harness by Jair Lima (incidente de 2026-10-14)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness_clean as h  # noqa: E402


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=r"C:\Temp\claude")
        self.root = os.path.join(self.tmp, "Harness")
        self.proj = os.path.join(self.root, "Proj")
        self.bin = os.path.join(self.tmp, "binx")
        self.desktop = os.path.join(self.tmp, "Desktopx")
        for d in (self.proj, self.bin, self.desktop):
            os.makedirs(d)
        self.install = os.path.join(self.tmp, "instalados")
        os.makedirs(self.install)
        self.cfg = os.path.join(self.tmp, "cfg")
        os.makedirs(self.cfg)
        self._salvo = (h.ALLOWED_HARNESS_ROOTS, h.LAUNCHER_DIRS, h.CHECK_SCHEDULED_TASKS,
                       h.get_running_process_lines, h.collect_launcher_references,
                       h.INSTALL_DIR, h.CONFIG_FILES, h.CONFIG_DIRS, h.MAX_AUTO_ITEMS, h.MAX_AUTO_BYTES)
        h.INSTALL_DIR = self.install
        h.CONFIG_FILES = []
        h.CONFIG_DIRS = [self.cfg]
        self._escreve(os.path.join(self.install, "app.exe"), "instalado")
        h.ALLOWED_HARNESS_ROOTS = [self.root]
        h.LAUNCHER_DIRS = [(self.bin, (".cmd", ".bat", ".ps1", ".vbs"), False),
                           (self.desktop, (".lnk",), True)]
        h.CHECK_SCHEDULED_TASKS = False
        h.get_running_process_lines = lambda: ["c:\\windows\\system32\\svchost.exe"]
        h._GUARD.update({"refs": None, "refs_failed": False, "running": None, "running_at": 0.0})

    def tearDown(self):
        (h.ALLOWED_HARNESS_ROOTS, h.LAUNCHER_DIRS, h.CHECK_SCHEDULED_TASKS,
         h.get_running_process_lines, h.collect_launcher_references,
         h.INSTALL_DIR, h.CONFIG_FILES, h.CONFIG_DIRS, h.MAX_AUTO_ITEMS, h.MAX_AUTO_BYTES) = self._salvo
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _escreve(self, caminho, conteudo, modo="w", **kw):
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, modo, **kw) as f:
            f.write(conteudo)

    def _projeto_com_dist(self):
        self._escreve(os.path.join(self.proj, "app.spec"), "# spec")
        self._escreve(os.path.join(self.proj, "dist", "app.exe"), "x")
        return os.path.join(self.proj, "dist")

    def test_dist_livre_e_aprovado(self):
        dist = self._projeto_com_dist()
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertTrue(ok, motivo)

    def test_dist_referenciado_por_lancador_e_preservado(self):
        dist = self._projeto_com_dist()
        self._escreve(os.path.join(self.bin, "app.cmd"), f'@echo off\r\n"{dist}\\app.exe" %*\r\n')
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Referenciado por"), motivo)

    def test_dist_referenciado_por_atalho_lnk_e_preservado(self):
        dist = self._projeto_com_dist()
        self._escreve(os.path.join(self.desktop, "App.lnk"), (dist + "\\app.exe").encode("utf-16-le"), "wb")
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Referenciado por"), motivo)

    def test_pasta_com_processo_em_execucao_e_preservada(self):
        dist = self._projeto_com_dist()
        h.get_running_process_lines = lambda: [(dist + "\\app.exe").lower()]
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Há processo em execução"), motivo)

    def test_venv_executado_por_script_do_projeto_e_preservado(self):
        self._escreve(os.path.join(self.proj, "requirements.txt"), "requests")
        self._escreve(os.path.join(self.proj, "venv", "pyvenv.cfg"), "home = x")
        self._escreve(os.path.join(self.proj, "run.bat"), '"%~dp0venv\\Scripts\\python.exe" app.py\r\n')
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "venv"), 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Script do projeto"), motivo)

    def test_venv_sem_manifesto_de_dependencias_nao_e_reproduzivel_e_e_preservado(self):
        self._escreve(os.path.join(self.proj, "app.py"), "import requests")
        self._escreve(os.path.join(self.proj, ".venv", "pyvenv.cfg"), "home = x")
        ok, motivo = h.double_check_safety(os.path.join(self.proj, ".venv"), 0)
        self.assertFalse(ok)
        self.assertIn("não reproduzível", motivo)

    def test_venv_sem_uso_e_aprovado(self):
        self._escreve(os.path.join(self.proj, "requirements.txt"), "requests")
        self._escreve(os.path.join(self.proj, "venv", "pyvenv.cfg"), "home = x")
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "venv"), 0)
        self.assertTrue(ok, motivo)

    def test_node_modules_bin_usado_por_script_e_preservado(self):
        self._escreve(os.path.join(self.proj, "package.json"), "{}")
        self._escreve(os.path.join(self.proj, "node_modules", "x.js"), "x")
        self._escreve(os.path.join(self.proj, "start.cmd"), "node_modules\\.bin\\vite\r\n")
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "node_modules"), 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Script do projeto"), motivo)

    def test_falha_ao_levantar_referencias_bloqueia(self):
        dist = self._projeto_com_dist()
        h.collect_launcher_references = lambda: None
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertFalse(ok)
        self.assertIn("fail-closed", motivo)

    def test_falha_ao_listar_processos_bloqueia(self):
        dist = self._projeto_com_dist()
        h.get_running_process_lines = lambda: None
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertFalse(ok)
        self.assertIn("fail-closed", motivo)

    def test_dist_com_executavel_sem_copia_instalada_e_preservado(self):
        self._escreve(os.path.join(self.proj, "app.spec"), "# spec")
        self._escreve(os.path.join(self.proj, "dist", "outro.exe"), "x")
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "dist"), 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Pode ser a única cópia"), motivo)

    def test_config_de_mcp_que_aponta_para_a_pasta_e_preservada(self):
        dist = self._projeto_com_dist()
        cfg = '{"mcpServers": {"x": {"command": "node", "args": ["' + (dist + "\\server.js").replace("\\", "\\\\") + '"]}}}'
        self._escreve(os.path.join(self.cfg, "settings.json"), cfg)
        ok, motivo = h.double_check_safety(dist, 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Referenciado por configuração"), motivo)

    def test_dependencia_de_projeto_referenciado_por_configuracao_e_preservada(self):
        self._escreve(os.path.join(self.proj, "package.json"), "{}")
        self._escreve(os.path.join(self.proj, "server.js"), "x")
        self._escreve(os.path.join(self.proj, "node_modules", "dep.js"), "x")
        cfg = '{"mcpServers": {"x": {"command": "node", "args": ["' + os.path.join(self.proj, "server.js").replace("\\", "\\\\") + '"]}}}'
        self._escreve(os.path.join(self.cfg, "settings.json"), cfg)
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "node_modules"), 0)
        self.assertFalse(ok)
        self.assertIn("dependência de projeto em uso", motivo)

    def test_manifesto_de_execucao_anterior_nao_conta_como_configuracao(self):
        self._escreve(os.path.join(self.proj, "package.json"), "{}")
        self._escreve(os.path.join(self.proj, "node_modules", "dep.js"), "x")
        listado = os.path.join(self.proj, "node_modules").replace("\\", "\\\\")
        self._escreve(os.path.join(self.cfg, "harness_cleanup_manifest.json"), '{"items": [{"path": "' + listado + '"}]}')
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "node_modules"), 0)
        self.assertTrue(ok, motivo)

    def test_node_modules_de_projeto_sem_referencia_continua_apagavel(self):
        self._escreve(os.path.join(self.proj, "package.json"), "{}")
        self._escreve(os.path.join(self.proj, "node_modules", "dep.js"), "x")
        ok, motivo = h.double_check_safety(os.path.join(self.proj, "node_modules"), 0)
        self.assertTrue(ok, motivo)

    def test_pasta_de_configuracao_de_harness_e_protegida(self):
        self._escreve(os.path.join(self.proj, ".claude", "package.json"), "{}")
        self._escreve(os.path.join(self.proj, ".claude", "node_modules", "dep.js"), "x")
        ok, motivo = h.double_check_safety(os.path.join(self.proj, ".claude", "node_modules"), 0)
        self.assertFalse(ok)
        self.assertTrue(motivo.startswith("Dentro de pasta de configuração"), motivo)

    def _roda_main(self, *argumentos):
        import contextlib
        import io
        salvo = sys.argv
        sys.argv = ["harness_clean.py", "--log-file", os.path.join(self.tmp, "log.txt"),
                    "--manifest-file", os.path.join(self.tmp, "man.json"), *argumentos]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                h.main()
        finally:
            sys.argv = salvo
        with open(os.path.join(self.tmp, "log.txt"), encoding="utf-8") as f:
            return f.read()

    def _cria_caches(self, n):
        pastas = []
        for i in range(n):
            p = os.path.join(self.root, f"Proj{i}", "__pycache__")
            self._escreve(os.path.join(p, "x.pyc"), "x")
            pastas.append(p)
        return pastas

    def test_execucao_real_apaga_cache_e_preserva_o_que_esta_em_uso(self):
        pastas = self._cria_caches(2)
        dist = self._projeto_com_dist()
        self._escreve(os.path.join(self.bin, "app.cmd"), f'"{dist}\\app.exe"\r\n')
        h.PRESERVED_FOR_USE.clear()
        log = self._roda_main("--auto", "--days", "0")
        self.assertTrue(all(not os.path.exists(p) for p in pastas), "os caches deveriam ter sido apagados")
        self.assertTrue(os.path.isdir(dist), "o dist referenciado nao pode ser apagado")
        self.assertIn("PRESERVADA", log)

    def _cria_pesadas(self, n):
        pastas = []
        for i in range(n):
            self._escreve(os.path.join(self.root, f"Pesado{i}", "package.json"), "{}")
            p = os.path.join(self.root, f"Pesado{i}", "node_modules")
            self._escreve(os.path.join(p, "dep.js"), "x")
            pastas.append(p)
        return pastas

    def test_muitos_caches_nao_acionam_o_teto(self):
        pastas = self._cria_caches(30)
        h.MAX_AUTO_ITEMS = 2
        log = self._roda_main("--auto", "--days", "0")
        self.assertNotIn("ABORTADO", log)
        self.assertTrue(all(not os.path.exists(p) for p in pastas))

    def test_teto_por_execucao_aborta_sem_apagar_nada(self):
        pastas = self._cria_pesadas(3)
        h.MAX_AUTO_ITEMS = 2
        log = self._roda_main("--auto", "--days", "0")
        self.assertIn("ABORTADO", log)
        self.assertTrue(all(os.path.isdir(p) for p in pastas), "nada deveria ter sido apagado")

    def test_force_large_ignora_o_teto(self):
        pastas = self._cria_pesadas(3)
        h.MAX_AUTO_ITEMS = 2
        self._roda_main("--auto", "--days", "0", "--force-large")
        self.assertTrue(all(not os.path.exists(p) for p in pastas))

    def test_preservada_aparece_no_relatorio_do_scan(self):
        dist = self._projeto_com_dist()
        self._escreve(os.path.join(self.bin, "app.cmd"), f'"{dist}\\app.exe"\r\n')
        h.PRESERVED_FOR_USE.clear()
        candidatos = h.scan_disposable_folders(0)
        self.assertEqual(candidatos, [])
        self.assertEqual(len(h.PRESERVED_FOR_USE), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
