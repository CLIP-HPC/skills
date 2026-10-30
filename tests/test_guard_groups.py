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

    def run_hook(self, command, cwd=None, extra_env=None, tool="Bash", tool_input=None):
        env = dict(os.environ, CBE_PROTECTED_PATHS=self.groups, LAB=self.lab)
        env.pop("CBE_GROUPS_GUARD", None)
        env.update(extra_env or {})
        event = {"tool_name": tool, "tool_input": tool_input or {"command": command}, "cwd": cwd or self.lab}
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

    # Agents on a laptop reach the cluster through ssh; remote paths can't be checked.
    def test_ssh_remote_commands(self):
        target = "%s/lab/bob/experiment" % self.groups
        self.assertAsks("ssh cbe.next 'rm -rf %s'" % target, "cbe.next:" + target)
        self.assertAsks("ssh -p 22 -o BatchMode=yes user@cbe.next rm -r %s" % target, "cbe.next:" + target)
        self.assertAsks("ssh cbe.next 'cd %s/lab/bob && rm -r experiment'" % self.groups, target)
        self.assertAsks("ssh cbe.next \"bash -lc 'find %s -delete'\"" % target, target)
        self.assertAsks("rsync -a --delete out/ cbe.next:%s/" % target, "cbe.next:" + target)
        self.assertAllows("ssh cbe.next 'ls -la %s && du -sh %s'" % (target, target))
        self.assertAllows("ssh cbe.next 'rm -rf /tmp/scratch-x'")
        self.assertAllows("ssh cbe.next rm -r old-logs")
        self.assertAllows("ssh cbe.next")
        self.assertAllows("rsync -a out/ cbe.next:%s/" % target)

    # Issue #26: false prompts for "/" from heredocs, run-time values, and dropped variables.
    def test_issue_26_false_positives(self):
        heredoc = ("cat > test.config <<'EOF'\n// m only for tasks that don't fit\nEOF\n"
                   "scp test.config cbe.next:/tmp/ && ssh cbe.next 'd=$(mktemp -d) && "
                   "mv /tmp/test.config $d/ && cd $d && nextflow run main.nf; rm -rf $d'")
        self.assertAllows(heredoc, cwd=self.other)
        self.assertAllows("ssh cbe.next 'd=$(mktemp -d) && rm -rf \"$d\"'", cwd=self.other)
        self.assertAllows('d=$(mktemp -d); rm -rf "$d"/', cwd=self.other)
        self.assertAllows("cat > notes.txt <<'EOF'\ndon't rm -rf /\nEOF", cwd=self.other)
        self.assertAllows("echo \"unbalanced && rm -rf $d/ // comment", cwd=self.other)

    def test_issue_26_still_asks(self):
        self.assertAsks('d=$(ls -d %s/lab/*); rm -rf "$d"' % self.groups, self.groups, cwd=self.other)
        self.assertAsks("bash <<'EOF'\nrm -r %s/experiment\nEOF" % self.lab, "experiment", cwd=self.other)
        self.assertAsks("ssh cbe.next <<'EOF'\nrm -rf %s/lab\nEOF" % self.groups, "cbe.next:", cwd=self.other)
        self.assertAsks("cat > /tmp/x <<'EOF'\nit's\nEOF\nrm -r experiment", "experiment")
        self.assertAsks("cat <<EOF\nrm -r experiment", "experiment")
        # An unset variable still asks, but the prompt doesn't describe the local "/".
        reason = self.run_hook('rm -rf "$UNSET_OUTDIR"/', cwd=self.other)["permissionDecisionReason"]
        self.assertNotIn("owner ", reason)
        # Paths named next to ssh in an unparseable command may be on either host.
        reason = self.run_hook("echo \"x && ssh cbe.next rm -rf %s/lab" % self.groups,
                               cwd=self.other)["permissionDecisionReason"]
        self.assertIn("may be on the ssh host", reason)

    def test_file_tools(self):
        existing = os.path.join(self.lab, "results.txt")
        self.assertIsNotNone(self.run_hook(None, tool="Write", tool_input={"file_path": existing, "content": "x"}))
        self.assertIsNotNone(self.run_hook(None, tool="Edit", tool_input={
            "file_path": existing, "old_string": "a", "new_string": "b"}))
        self.assertIsNone(self.run_hook(None, tool="Write", tool_input={
            "file_path": os.path.join(self.lab, "new.txt"), "content": "x"}))
        self.assertIsNone(self.run_hook(None, tool="Write", tool_input={
            "file_path": os.path.join(self.other, "x.tmp"), "content": "x"}))

    def test_in_place_edits(self):
        self.assertAsks("sed -i 's/a/b/' results.txt", "results.txt")
        self.assertAsks("sed -i.bak -e 's/a/b/' %s/results.txt" % self.lab, "results.txt")
        self.assertAsks("perl -pi -e 's/a/b/' results.txt", "results.txt")
        self.assertAllows("sed 's/a/b/' results.txt > %s/out.txt" % self.other)
        self.assertAllows("sed -i 's/a/b/' %s/x.tmp" % self.other)

    def test_copies_onto_existing_files(self):
        open(os.path.join(self.other, "results.txt"), "w").close()
        self.assertAsks("rsync -a %s/ %s/" % (self.other, self.lab), "results.txt")
        self.assertAllows("rsync -a --ignore-existing %s/ %s/" % (self.other, self.lab))
        self.assertAsks("cp -r %s/results.txt %s/x.tmp %s/" % (self.other, self.other, self.lab), "results.txt")
        self.assertAllows("cp -n %s/results.txt %s/" % (self.other, self.lab))
        self.assertAllows("cp %s/x.tmp %s/" % (self.other, self.lab))

    def test_archives_and_git(self):
        self.assertAsks("tar -xzf data.tar.gz -C %s" % self.lab, self.lab)
        self.assertAsks("tar xf data.tar", self.lab)
        self.assertAllows("tar -xkf data.tar -C %s" % self.lab)
        self.assertAllows("tar -czf %s/out.tgz experiment" % self.other)
        self.assertAllows("tar -xf data.tar -C %s" % self.other)
        self.assertAsks("unzip -o data.zip -d %s" % self.lab, self.lab)
        self.assertAsks("git clean -fdx", self.lab)
        self.assertAsks("git -C %s reset --hard" % self.lab, self.lab)
        self.assertAsks("git checkout -- results.txt", self.lab)
        self.assertAllows("git status && git log -1")
        self.assertAllows("git clean -n")

    def test_prompt_describes_target(self):
        reason = self.run_hook("rm -r experiment")["permissionDecisionReason"]
        self.assertIn("2 files", reason)
        self.assertIn("owner ", reason)
        self.assertNotIn("snapshot hourly", reason)
        os.makedirs(os.path.join(self.groups, ".snapshot", "hourly.2000-01-01_0000"))
        reason = self.run_hook("rm -r experiment")["permissionDecisionReason"]
        self.assertIn("changed after the latest snapshot hourly.2000-01-01_0000", reason)

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
