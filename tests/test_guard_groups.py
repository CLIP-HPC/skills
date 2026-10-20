"""Tests for the cbe plugin hook plugins/cbe/hooks/guard_groups.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "cbe", "hooks", "guard_groups.py")


class GuardGroups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.groups = os.path.join(base, "groups")
        self.other = os.path.join(base, "scratch")
        self.lab = os.path.join(self.groups, "lab", "alice")
        os.makedirs(os.path.join(self.lab, "experiment", "important"))
        os.makedirs(self.other)
        for p in ("experiment/a", "experiment/important/bio_data.bam", "results.txt", "old.log"):
            open(os.path.join(self.lab, p), "w").close()
        open(os.path.join(self.other, "x.tmp"), "w").close()

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, command, cwd=None, extra_env=None):
        env = dict(os.environ, CBE_PROTECTED_PATHS=self.groups, LAB=self.lab)
        env.pop("CBE_GROUPS_GUARD", None)
        env.update(extra_env or {})
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or self.lab}
        r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(event),
                           capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None

    def assertAsks(self, command, *paths, **kw):
        out = self.run_hook(command, **kw)
        self.assertIsNotNone(out, "expected ask for: %s" % command)
        self.assertEqual(out["permissionDecision"], "ask")
        for p in paths:
            self.assertIn(p, out["permissionDecisionReason"])

    def assertAllows(self, command, **kw):
        self.assertIsNone(self.run_hook(command, **kw), "expected no prompt for: %s" % command)

    # The incident that motivated the hook.
    def test_relative_rm_in_groups_cwd(self):
        self.assertAsks("cd %s && rm -r experiment && ls" % self.lab, "experiment")
        self.assertAsks("rm -r experiment", os.path.join(self.lab, "experiment"))

    def test_absolute_and_glob(self):
        self.assertAsks("rm -f %s/*.log" % self.lab, "old.log")
        self.assertAsks("sudo rm -rf %s" % self.groups)

    def test_outside_groups_allowed(self):
        self.assertAllows("rm -r %s/x.tmp" % self.other)
        self.assertAllows("cd %s && rm x.tmp" % self.other)
        self.assertAllows("rm -r experiment", cwd=self.other)

    def test_read_only_commands_allowed(self):
        self.assertAllows("ls -la experiment && du -sh experiment")
        self.assertAllows("grep -rn 'rm -r' .")
        self.assertAllows("cat results.txt | head")
        self.assertAllows("echo hi >> results.txt")
        self.assertAllows("ls nonexistent 2>/dev/null")

    def test_nonexistent_literal_target_allowed(self):
        self.assertAllows("rm -f does-not-exist.txt")

    def test_mv_and_overwrite(self):
        self.assertAsks("mv results.txt results.old", "results.txt")
        self.assertAsks("echo x > results.txt", "results.txt")
        self.assertAllows("echo x > new-file.txt")
        self.assertAsks("cp %s/x.tmp results.txt" % self.other, "results.txt")
        self.assertAsks("sort old.log | tee results.txt", "results.txt")

    def test_find_rsync_rclone(self):
        self.assertAsks("find %s -name '*.log' -delete" % self.lab)
        self.assertAsks("find . -type f -exec rm {} +")
        self.assertAsks("rsync -a --delete %s/ %s/" % (self.other, self.lab), self.lab)
        self.assertAllows("rsync -a %s/ %s/" % (self.other, self.lab))
        self.assertAllows("rsync -a --delete %s/ %s/" % (self.lab, self.other))
        self.assertAsks("rclone sync remote:bucket %s" % self.lab, self.lab)
        self.assertAllows("rclone copy remote:bucket %s" % self.lab)

    def test_variables(self):
        self.assertAsks('rm -rf "$LAB/experiment"', "experiment")
        self.assertAsks('OUT=%s/experiment; rm -r "$OUT"' % self.lab, "experiment")
        # Unset variable expands to nothing: rm -rf / would cover /groups.
        self.assertAsks('rm -rf "$UNSET_OUTDIR"/', cwd=self.other)

    def test_indirect(self):
        self.assertAsks("bash -c 'rm -r experiment'", "experiment")
        self.assertAsks("srun -n1 rm -r %s/experiment" % self.lab, "experiment")
        self.assertAsks("sbatch --wrap='rm -r %s/experiment'" % self.lab, "experiment")
        self.assertAsks("find %s -name '*.log' | xargs rm" % self.lab, self.lab)
        self.assertAsks("python3 -c 'import shutil; shutil.rmtree(\"experiment\")'")
        self.assertAsks("rm $(ls *.log)")
        self.assertAsks("for f in *.log; do rm \"$f\"; done")
        self.assertAsks("ls\nrm -r experiment", "experiment")

    def test_disable(self):
        self.assertIsNone(self.run_hook("rm -r experiment", extra_env={"CBE_GROUPS_GUARD": "off"}))

    def test_other_tools_ignored(self):
        env = dict(os.environ, CBE_PROTECTED_PATHS=self.groups)
        event = {"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": self.lab}
        r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(event),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
