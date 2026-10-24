import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from ci.audit import inspect_text
from ci.common import ROOT, abi, config, extract, python_tag, upstream_for, wheel_for
from ci.plan import plan
from ci.report import render

class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.rows = plan()
    def test_python_versions(self):
        self.assertEqual(self.c['python'], ['3.9','3.10','3.11','3.12','3.13','3.14','3.14t'])
    def test_abi_count(self):
        self.assertEqual(len({abi(p) for p in self.c['python']}), 7)
    def test_free_threaded_tags_and_upstream(self):
        self.assertEqual(python_tag('3.14t'), 'cp314')
        self.assertEqual(abi('3.14t'), 'cp314t')
        self.assertEqual(upstream_for('3.14t')['version'], '2.3.0')
    def test_regular_and_free_threaded_wheels_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            regular = Path(td)/'mysqlclient_static-2.3.0.post3-cp314-cp314-manylinux_2_28_x86_64.whl'
            threaded = Path(td)/'mysqlclient_static-2.3.0.post3-cp314-cp314t-manylinux_2_28_x86_64.whl'
            regular.touch()
            threaded.touch()
            self.assertEqual(wheel_for(td, '3.14'), regular)
            self.assertEqual(wheel_for(td, '3.14t'), threaded)
    def test_legacy_branch(self):
        self.assertEqual(upstream_for('3.9')['version'], '2.2.7')
    def test_current_branch(self):
        for py in self.c['python'][1:]:
            self.assertEqual(upstream_for(py)['version'], '2.3.0')
    def test_unknown_python_fails(self):
        with self.assertRaises(ValueError): upstream_for('3.15')
    def test_mysql_versions(self):
        self.assertEqual({d['version'] for d in self.c['mysql']}, {'8.0.11','8.0.27','8.0.46','8.4.13'})
    def test_unique_ports(self):
        self.assertEqual(len({d['port'] for d in self.c['mysql']}), 4)
    def test_two_auth_plugins(self):
        self.assertEqual(set(self.c['auth']), {'mysql_native_password','caching_sha2_password'})
    def test_driver_all_axes(self):
        rows = [r for r in self.rows if r['suite']=='driver']
        self.assertEqual(len(rows),7*4*2)
    def test_required_orm(self):
        for p in ['django32-py310','django52-py312']:
            rows = [r for r in self.rows if r['suite']=='orm' and r['django']==p]
            self.assertEqual(len(rows),8)
            self.assertTrue(all(r['status']=='NOT_RUN' for r in rows))
    def test_django32_not_python312(self):
        for r in self.rows:
            if r['django'].startswith('django32'):
                self.assertIn(r['python'], ['3.9','3.10'])
    def test_django61_explicit_exclusions(self):
        rows = [r for r in self.rows if r['django']=='django61-py312']
        self.assertEqual(sum(r['status']=='EXCLUDED' for r in rows), 6)
        self.assertTrue(all(r['mysql']=='8.4.13' for r in rows if r['status']!='EXCLUDED'))
    def test_three_real_runtime_suites(self):
        for suite in ['wsgi','asgi','celery']:
            self.assertEqual(sum(r['suite']==suite for r in self.rows),8)
    def test_expected_totals(self):
        self.assertEqual(len(self.rows),132)
        self.assertEqual(sum(r['status']=='NOT_RUN' for r in self.rows),126)
    def test_source_pins(self):
        for dep in self.c['native'].values(): self.assertRegex(dep['git_object'], r'^[a-f0-9]{40}$')
        for dep in self.c['upstream'].values(): self.assertRegex(dep['sha256'], r'^[a-f0-9]{64}$')
    def test_wheel_requires_exact_match(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError): wheel_for(td,'3.12')
            a=Path(td)/'mysqlclient_static-2.3.0.post2-cp312-cp312-manylinux_2_28_x86_64.whl';a.touch()
            self.assertEqual(wheel_for(td,'3.12'),a)
            (Path(td)/'other-1-cp312-cp312-manylinux_2_28_x86_64.whl').touch()
            with self.assertRaises(ValueError): wheel_for(td,'3.12')

class PackagingTests(unittest.TestCase):
    def fixture(self, td, py):
        from ci.build_wheels import stage_source
        version = upstream_for(py)["version"]
        source = Path(td)/"sources"/f"mysqlclient-{version}"
        (source/"src/MySQLdb").mkdir(parents=True)
        (source/"LICENSE").write_text("upstream license text")
        (source/"src/MySQLdb/release.py").write_text(f"__version__ = '{version}'\n")
        (source/"src/MySQLdb/_mysql.c").write_text('static PyMethodDef _mysql_methods[] = {\n};\n')
        staged = Path(td)/"staged"
        stage_source(py, staged, source_root=Path(td)/"sources")
        return staged
    def test_preserves_upstream_license(self):
        with tempfile.TemporaryDirectory() as td:
            staged=self.fixture(td,"3.13")
            self.assertEqual((staged/"LICENSES/mysqlclient-LICENSE").read_text(), "upstream license text")
    def test_runtime_version_not_spoofed(self):
        with tempfile.TemporaryDirectory() as td:
            staged=self.fixture(td,"3.13")
            self.assertIn("2.3.0", (staged/"src/MySQLdb/release.py").read_text())
            self.assertNotIn("post", (staged/"src/MySQLdb/release.py").read_text())
    def test_legacy_package_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            staged=self.fixture(td,"3.9")
            text=(staged/"pyproject.toml").read_text()
            self.assertIn('requires-python = ">=3.9,<3.10"', text)
            self.assertIn('version = "2.2.7.post3"', text)

class ClientOptionTests(unittest.TestCase):
    def arguments(self, **kwargs):
        from unittest.mock import Mock, patch
        import types
        from tests.client import db_connect
        fake=types.SimpleNamespace(connect=Mock(return_value=object()))
        env={"DB_PORT":"3306","DB_USER":"u","DB_PASSWORD":"p","DB_NAME":"d"}
        with patch.dict("sys.modules", {"MySQLdb":fake}), patch.dict("os.environ",env):
            db_connect(**kwargs)
        return fake.connect.call_args.kwargs
    def test_default_does_not_accidentally_enable_compression(self):
        self.assertNotIn("compress", self.arguments())
    def test_compression_explicitly_enabled(self):
        self.assertIs(self.arguments(compress=True)["compress"], True)
    def test_tls_identity_required(self):
        self.assertEqual(self.arguments()["ssl_mode"], "VERIFY_IDENTITY")

class FreeThreadingTests(unittest.TestCase):
    def test_regular_interpreter_does_not_require_gil_api(self):
        from unittest.mock import patch
        from tests.client import gil_check
        with patch('tests.client.sysconfig.get_config_var', return_value=None):
            self.assertIsNone(gil_check())
    def test_free_threaded_interpreter_keeps_gil_disabled(self):
        from unittest.mock import patch
        from tests.client import gil_check
        with patch('tests.client.sysconfig.get_config_var', return_value=1), \
             patch('tests.client.sys._is_gil_enabled', return_value=False, create=True):
            self.assertIs(gil_check(), False)
    def test_reenabled_gil_fails_verification(self):
        from unittest.mock import patch
        from tests.client import gil_check
        with patch('tests.client.sysconfig.get_config_var', return_value=1), \
             patch('tests.client.sys._is_gil_enabled', return_value=True, create=True):
            with self.assertRaises(AssertionError):
                gil_check()

class ElfTests(unittest.TestCase):
    def check(self, defined='000 T PyInit__mysql\n', undefined=' U PyLong_FromLong\n U memcpy@GLIBC_2.14\n',
              dynamic=' (NEEDED) Shared library: [libc.so.6]', versions='GLIBC_2.28'):
        return inspect_text(defined,undefined,dynamic,versions)['errors']
    def test_clean(self): self.assertEqual(self.check(),[])
    def test_exports(self): self.assertTrue(self.check(defined='000 T PyInit__mysql\n010 T SSL_new\n'))
    def test_weak_zstd(self): self.assertTrue(self.check(undefined=' w ZSTD_trace_decompress_end\n'))
    def test_external_openssl(self): self.assertTrue(self.check(undefined=' U SSL_new\n'))
    def test_wrong_glibc(self): self.assertTrue(self.check(versions='GLIBC_2.38'))
    def test_system_client(self): self.assertTrue(self.check(dynamic=' (NEEDED) Shared library: [libmariadb.so.3]'))
    def test_runpath(self): self.assertTrue(self.check(dynamic=' (RUNPATH) Library runpath: [/tmp]'))
    def test_unreviewed_symbol(self): self.assertTrue(self.check(undefined=' U accidental_hook\n'))
    def test_gcc_weak_hooks(self): self.assertEqual(self.check(undefined=' w __gmon_start__\n w _ITM_registerTMCloneTable\n'),[])
    def test_no_initializer(self): self.assertTrue(self.check(defined=''))

class ReportTests(unittest.TestCase):
    def test_not_run_fails(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(render(plan(),td))
            self.assertIn('NOT_RUN: 126', (Path(td)/'summary.md').read_text())
    def test_pass_requires_all_planned_cases(self):
        rows=plan()
        for r in rows:
            if r['status']=='NOT_RUN': r['status']='PASS'
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(render(rows,td))
            rows[0]['status']='FAIL'
            self.assertFalse(render(rows,td))
    def test_empty_never_green(self):
        with tempfile.TemporaryDirectory() as td: self.assertFalse(render([],td))
    def test_truncated_all_pass_still_fails(self):
        rows=plan()[:1]; rows[0]['status']='PASS'
        with tempfile.TemporaryDirectory() as td: self.assertFalse(render(rows,td))
    def test_duplicate_rows_fail(self):
        rows=plan()
        for r in rows:
            if r['status']=='NOT_RUN': r['status']='PASS'
        rows.append(rows[0].copy())
        with tempfile.TemporaryDirectory() as td: self.assertFalse(render(rows,td))
    def test_skipping_required_case_fails(self):
        rows=plan()
        for r in rows:
            if r['status']=='NOT_RUN': r['status']='PASS'
        rows[0]['status']='EXCLUDED'
        with tempfile.TemporaryDirectory() as td: self.assertFalse(render(rows,td))
    def test_html_escaped(self):
        rows=plan();rows[0]['reason']='<script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as td:
            render(rows,td)
            text=(Path(td)/'index.html').read_text()
            self.assertNotIn('<script>',text)
            self.assertIn('&lt;script&gt;',text)

class ArchiveTests(unittest.TestCase):
    def make(self,p,name):
        with tarfile.open(p,'w:gz') as t:
            m=tarfile.TarInfo(name);m.size=2;t.addfile(m,io.BytesIO(b'ok'))
    def test_regular_file(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.tar.gz';self.make(p,'src/file')
            extract(p,Path(td)/'out')
            self.assertEqual((Path(td)/'out/src/file').read_text(),'ok')
    def test_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.tar.gz';self.make(p,'../../bad')
            with self.assertRaises(ValueError): extract(p,Path(td)/'out')
    def test_absolute(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.tar.gz';self.make(p,'/tmp/bad')
            with self.assertRaises(ValueError): extract(p,Path(td)/'out')

    def test_safe_relative_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.tar.gz'
            with tarfile.open(p,'w:gz') as t:
                m=tarfile.TarInfo('src/file');m.size=2;t.addfile(m,io.BytesIO(b'ok'))
                m=tarfile.TarInfo('src/link');m.type=tarfile.SYMTYPE;m.linkname='file';t.addfile(m)
            extract(p,Path(td)/'out')
            self.assertEqual((Path(td)/'out/src/link').read_text(),'ok')
    def test_escaping_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.tar.gz'
            with tarfile.open(p,'w:gz') as t:
                m=tarfile.TarInfo('link');m.type=tarfile.SYMTYPE;m.linkname='../escape';t.addfile(m)
            with self.assertRaises(ValueError): extract(p,Path(td)/'out')

if __name__=='__main__': unittest.main()
