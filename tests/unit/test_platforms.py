import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from ci.audit_macos import inspect_text
from ci.build_wheels import link_environment
from ci.plan import plan


class MacAuditTests(unittest.TestCase):
    def audit(self, **kwargs):
        values = dict(exports="000 T _PyInit__mysql\n", imports="_PyLong_FromLong\n_malloc\n",
                      libraries="module.so:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n",
                      load_commands="cmd LC_BUILD_VERSION\n minos 11.0\n", architecture="arm64")
        values.update(kwargs)
        return inspect_text(**values)["errors"]

    def test_system_runtime_is_allowed(self):
        self.assertEqual(self.audit(), [])

    def test_homebrew_dependency_is_rejected(self):
        self.assertTrue(self.audit(libraries="module.so:\n /opt/homebrew/lib/libssl.3.dylib (compatibility version 3.0.0)"))

    def test_private_symbol_import_is_rejected(self):
        self.assertTrue(self.audit(imports="_SSL_new\n"))

    def test_private_symbol_export_is_rejected(self):
        self.assertTrue(self.audit(exports="000 T _PyInit__mysql\n001 T _SSL_new\n"))

    def test_newer_os_requirement_is_rejected(self):
        self.assertTrue(self.audit(load_commands="minos 13.0"))

    def test_intel_binary_is_rejected(self):
        self.assertTrue(self.audit(architecture="x86_64"))


class PlatformConfigurationTests(unittest.TestCase):
    def test_native_mysql_instances_use_separate_paths_and_version_options(self):
        from ci.run_macos import MacRunner

        runner = MacRunner.__new__(MacRunner)
        runner.work = Path("/test/run")
        runner.certs = Path("/test/certs")
        runner.logs = Path("/test/logs")
        runner.password = "test-password"
        runner.servers = {}
        process = Mock()
        process.poll.return_value = None
        runner.service = Mock(return_value=process)
        runner.admin = Mock(side_effect=["8.0.46", "", "caching_sha2_password", "",
                                         "8.4.13", "", "caching_sha2_password", ""])

        def command(args, **kwargs):
            return f"/brew/{args[-1]}" if args[0] == "brew" else ""

        with patch("ci.run_macos.run", side_effect=command):
            runner.start_server(dict(version="8.0.46", port=33063))
            runner.start_server(dict(version="8.4.13", port=33064, enable_native=True))
        old, new = runner.servers["8.0.46"], runner.servers["8.4.13"]
        self.assertNotEqual(old["socket"], new["socket"])
        self.assertNotEqual(old["bin"], new["bin"])
        self.assertNotEqual(old["port"], new["port"])
        args80, args84 = [call.args[0] for call in runner.service.call_args_list]
        self.assertNotIn("--mysql-native-password=ON", args80)
        self.assertIn("--mysql-native-password=ON", args84)

    def test_native_matrix_covers_mysql80_and_mysql84_with_both_auth_methods(self):
        with patch.dict(os.environ, {"MCS_PLATFORM": "macos"}):
            rows = plan()
        self.assertEqual(len(rows), 76)
        self.assertEqual(sum(r["status"] == "NOT_RUN" for r in rows), 74)
        self.assertEqual(sum(r["status"] == "EXCLUDED" for r in rows), 2)
        self.assertEqual({r["mysql"] for r in rows}, {"8.0.46", "8.4.13"})
        self.assertEqual({r["auth"] for r in rows}, {"mysql_native_password", "caching_sha2_password"})
        self.assertEqual(sum(r["suite"] == "driver" for r in rows), 28)
        for profile in ("django32-py310", "django52-py312"):
            self.assertEqual({r["suite"] for r in rows if r["django"] == profile},
                             {"orm", "wsgi", "asgi", "celery"})

    def test_each_platform_links_explicit_static_archives(self):
        for target in ("macos", "linux"):
            env = link_environment(target, Path("/native"))
            self.assertIn("/native/lib/libmysqlclient-static.a", env["MYSQLCLIENT_LDFLAGS"])
            self.assertIn("/native/lib/libcrypto.a", env["MYSQLCLIENT_LDFLAGS"])
        self.assertNotIn("--version-script", link_environment("macos", Path("/native"))["MYSQLCLIENT_LDFLAGS"])

    def test_environment_selects_the_requested_interpreter_variant(self):
        from ci.run_macos import MacRunner
        for target, request in [('3.9', '3.9'), ('3.10', '3.10'), ('3.13', '3.13'),
                                ('3.14', '3.14+gil'), ('3.14t', '3.14t')]:
            with self.subTest(target=target):
                runner = MacRunner.__new__(MacRunner)
                runner.work = Path('/work')
                runner.logs = Path('/logs')
                runner.c = {'crypto_tool': 'cryptography==46.0.3'}
                runner.images = {}
                runner.image_errors = {}
                with patch('ci.common.run') as create, patch('ci.run_macos.run'), \
                     patch('ci.run_macos.wheel_for', return_value=Path('/wheel.whl')):
                    runner.environment('environment', target)
                self.assertFalse(runner.image_errors)
                args = create.call_args_list[-1].args[0]
                self.assertEqual(args[args.index('--python') + 1], request)
                if target == '3.14':
                    self.assertEqual(create.call_args_list[0].args[0],
                                     ['uv', 'python', 'install', '--no-bin', '3.14'])
                else:
                    self.assertEqual(create.call_count, 1)
