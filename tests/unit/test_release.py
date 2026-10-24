from pathlib import Path
import tempfile
import unittest

from ci.release import release_notes, release_plan


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.c = dict(build_revision=2, python=["3.9", "3.12"], upstream={
            "legacy": dict(version="2.2.7", python=["3.9"]),
            "current": dict(version="2.3.0", python=["3.12"]),
        })

    def test_groups_platform_wheels_by_distribution_version(self):
        with tempfile.TemporaryDirectory() as directory:
            wheels = Path(directory) / "wheelhouse"
            wheels.mkdir()
            for version, abi in (("2.2.7.post2", "cp39"), ("2.3.0.post2", "cp312")):
                for platform in ("macosx_11_0_arm64", "manylinux_2_28_x86_64"):
                    (wheels / f"mysqlclient_static-{version}-{abi}-{abi}-{platform}.whl").touch()
            releases = release_plan(directory, self.c)
        self.assertEqual([r["tag"] for r in releases], ["v2.2.7.post2", "v2.3.0.post2"])
        self.assertEqual([r["latest"] for r in releases], [False, True])
        self.assertTrue(all("2.2.7.post2" in w.name for w in releases[0]["wheels"]))
        self.assertTrue(all("2.3.0.post2" in w.name for w in releases[1]["wheels"]))

    def test_incomplete_platform_set_prevents_release(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Incomplete wheel set"):
                release_plan(directory, self.c)

    def test_free_threaded_release_assets_and_labels(self):
        self.c['python'].append('3.14t')
        self.c['upstream']['current']['python'].append('3.14t')
        with tempfile.TemporaryDirectory() as directory:
            wheels = Path(directory) / 'wheelhouse'
            wheels.mkdir()
            for version, python, abi in [('2.2.7.post2', 'cp39', 'cp39'),
                                         ('2.3.0.post2', 'cp312', 'cp312'),
                                         ('2.3.0.post2', 'cp314', 'cp314t')]:
                for platform in ('macosx_11_0_arm64', 'manylinux_2_28_x86_64'):
                    (wheels / f'mysqlclient_static-{version}-{python}-{abi}-{platform}.whl').touch()
            release = release_plan(directory, self.c)[1]
            self.assertEqual(len(release['wheels']), 4)
            notes = release_notes(release, 'aweffr/mysqlclient-static', self.c)
            rows = [line.split('|')[1:4] for line in notes.splitlines() if line.startswith('| 3.')]
            self.assertEqual([(python.strip(), platform.strip()) for python, platform, _ in rows],
                             [('3.12', 'macOS ARM64'), ('3.12', 'Linux AMD64'),
                              ('3.14t', 'macOS ARM64'), ('3.14t', 'Linux AMD64')])
