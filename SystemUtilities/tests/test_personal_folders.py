"""Clean-up: an AI "safe" verdict must never apply inside personal folders, wherever Windows keeps them.

The model here answers "safe" for every folder - the worst case - so each test shows what the code allows.
"""

import ntpath
import os
import sys
import types
import unittest
from unittest import mock

import _support

cleanup = _support.load("cleanup")

DOWNLOADS = "{374DE290-123F-4565-9164-39C4925E467B}"


class SaysSafe:
    model = "test"

    def chat_json(self, system, user, max_tokens=None):
        return {"items": [{"id": i + 1, "what": "stuff", "verdict": "safe", "action": "delete it"} for i in range(5)]}


class Node:
    size = 500 * 1024 ** 2


def fake_registry(values):
    """Stands in for winreg, holding what Windows records under "User Shell Folders"."""
    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    def query(key, name):
        if name not in values:
            raise OSError(2, "not found")
        return values[name], 2
    return types.SimpleNamespace(HKEY_CURRENT_USER=1, OpenKey=lambda *a: Key(), QueryValueEx=query)


class PersonalFolders(unittest.TestCase):
    def setUp(self):
        # Windows path rules and no registry by default, so the tests give the same answers on any system.
        for target, name, value in ((cleanup, "rel_path", lambda p: ntpath.splitdrive(p)[1].strip("\\").lower()),
                                    (cleanup, "describe_folder", lambda node, path: f"path: {path}"),
                                    (os.path, "expandvars", ntpath.expandvars)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.use_registry(None)

    def use_registry(self, values):
        patcher = mock.patch.dict(sys.modules, {"winreg": fake_registry(values) if values is not None else None})
        patcher.start()
        self.addCleanup(patcher.stop)

    def verdicts(self, paths):
        out = {}
        for i in range(0, len(paths), 5):
            cat = cleanup.ai_review_folders(SaysSafe(), [(Node(), p) for p in paths[i:i + 5]])
            out.update({item["path"]: item for item in cat.items})
        return out

    def check(self, expected):
        got = self.verdicts(list(expected))
        for path, want in expected.items():
            with self.subTest(path=path):
                self.assertEqual(got[path]["risk"], want)
        return got

    def test_user_folders_are_review_only(self):
        got = self.check({
            r"C:\Users\sekar\Pictures\2019": cleanup.REVIEW,
            r"C:\Users\sekar\Documents\Taxes": cleanup.REVIEW,
            r"C:\Users\sekar\Desktop\stuff": cleanup.REVIEW,
            r"C:\Users\sekar\Videos": cleanup.REVIEW,
            r"C:\Users\sekar\Music\Albums": cleanup.REVIEW,
            r"C:\Users\sekar\Downloads\SomeApp-unzipped": cleanup.REVIEW,
            r"C:\Users\sekar\Projects\site\node_modules": cleanup.REVIEW,     # no exception for build leftovers
            r"C:\Users\sekar\Documents\code\build": cleanup.REVIEW,
            r"C:\Users\Public\Documents\shared": cleanup.REVIEW,
            r"C:\Users\sekar\OneDrive\Pictures": cleanup.REVIEW,
        })
        self.assertIn(cleanup.PERSONAL_NOTE, got[r"C:\Users\sekar\Pictures\2019"]["action"])

    def test_existing_rules_are_unchanged(self):
        self.check({
            r"C:\Users\sekar\AppData\Local\SomeApp\Cache": cleanup.SAFE,
            r"C:\Users\sekar\AppData\Local\SomeApp\Data": cleanup.REVIEW,
            r"C:\Windows\Installer": cleanup.KEEP,
            r"C:\Program Files\Game": cleanup.REVIEW,
            r"D:\Scratch\render-tmp": cleanup.SAFE,
        })

    def test_no_registry_means_no_extra_folders_and_no_error(self):
        self.assertEqual(cleanup.personal_roots(), [])

    def test_folders_moved_to_another_drive(self):
        self.use_registry({"Personal": r"D:\Documents", "My Pictures": "E:\\Media\\Photos\\", DOWNLOADS: r"D:\Downloads",
                           "Desktop": r"%USERPROFILE%\Desktop", "My Video": r"%NO_SUCH_VARIABLE%\Videos"})
        with mock.patch.dict(os.environ, {"USERPROFILE": r"C:\Users\sekar"}):
            self.assertEqual(sorted(cleanup.personal_roots()),
                             [r"c:\users\sekar\desktop", r"d:\documents", r"d:\downloads", r"e:\media\photos"])
            self.check({
                r"D:\Documents\Taxes\2021": cleanup.REVIEW,
                r"D:\Documents": cleanup.REVIEW,
                r"d:\DOCUMENTS\Old": cleanup.REVIEW,
                r"E:\Media\Photos\Trip": cleanup.REVIEW,
                r"D:\Downloads\SomeApp-unzipped": cleanup.REVIEW,
                r"D:\Documents-backup\tmp": cleanup.SAFE,          # a similar name is a different folder
                r"E:\Media\Renders\cache": cleanup.SAFE,
                r"D:\Scratch": cleanup.SAFE,
            })


if __name__ == "__main__":
    unittest.main()
