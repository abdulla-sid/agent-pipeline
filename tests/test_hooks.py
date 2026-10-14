"""Run: python3 -m unittest discover tests"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugin", "hooks")


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def sh(cwd, *cmd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


class GitGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        remote = os.path.join(self.tmp, "remote.git")
        self.repo = os.path.join(self.tmp, "repo")
        sh(self.tmp, "git", "init", "-q", "--bare", "-b", "main", remote)
        sh(self.tmp, "git", "init", "-q", "-b", "main", self.repo)
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            sh(self.repo, "git", "config", k, v)
        write(os.path.join(self.repo, "a.txt"), "a")
        sh(self.repo, "git", "add", "a.txt")
        sh(self.repo, "git", "commit", "-qm", "init")
        sh(self.repo, "git", "remote", "add", "origin", remote)
        sh(self.repo, "git", "push", "-q", "-u", "origin", "main")
        sh(self.repo, "git", "switch", "-qc", "feature/x")
        os.makedirs(os.path.join(self.repo, ".pipeline"))
        write(os.path.join(self.repo, ".pipeline", "card.md"), "x")
        write(os.path.join(self.repo, ".env"), "SECRET=1")
        write(os.path.join(self.repo, "b.txt"), "b")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_guard(self, command, config=None):
        if config is not None:
            os.makedirs(os.path.join(self.repo, ".claude"), exist_ok=True)
            write(os.path.join(self.repo, ".claude", "pipeline.json"), json.dumps(config))
        ev = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": self.repo}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.repo)
        r = subprocess.run(["python3", os.path.join(HOOKS, "git_guard.py")], input=json.dumps(ev),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if r.stdout else None

    def assertDenied(self, command, **kw):
        self.assertIsNotNone(self.run_guard(command, **kw), f"expected deny: {command}")

    def assertAllowed(self, command, **kw):
        self.assertIsNone(self.run_guard(command, **kw), f"expected allow: {command}")

    def test_add(self):
        self.assertDenied("git add .")
        self.assertDenied("git add -A")
        self.assertDenied("git add .env")
        self.assertDenied("git add -f .pipeline/card.md")
        self.assertDenied("npm test && git add b.txt .env && git commit -m x")
        self.assertAllowed("git add b.txt")
        self.assertAllowed("git status")

    def test_add_respects_config(self):
        self.assertAllowed("git add .env", config={"local_only": [".pipeline/"]})

    def test_push(self):
        self.assertDenied("git push origin main")
        self.assertDenied("git push origin HEAD:main")
        self.assertDenied("git push -u origin main")
        self.assertDenied("git push --force origin feature/x")
        self.assertDenied("git push --force-with-lease")
        self.assertDenied("git push origin +feature/x")
        self.assertAllowed("git push -u origin feature/x")
        self.assertAllowed("git push origin feature/x:refs/heads/feature/x")

    def test_bare_push_follows_upstream(self):
        sh(self.repo, "git", "branch", "--set-upstream-to=origin/main")
        self.assertDenied("git push")
        os.makedirs(os.path.join(self.repo, "sub"))
        self.assertDenied("cd sub; git push")

    def test_commit_on_protected(self):
        sh(self.repo, "git", "switch", "-q", "main")
        self.assertDenied('git commit -m "fix"')
        sh(self.repo, "git", "switch", "-q", "feature/x")
        self.assertAllowed('git commit -m "fix"')

    def test_tracking(self):
        self.assertDenied("git checkout -b feature/y origin/main")
        self.assertDenied("git switch -c feature/y origin/main")
        self.assertDenied("git branch feature/y origin/main")
        self.assertDenied("git branch --set-upstream-to=origin/main")
        self.assertAllowed("git checkout -b feature/y --no-track origin/main")
        self.assertAllowed("git checkout -b feature/y main")
        self.assertAllowed("git switch -c main origin/main")

    def test_follows_cd_and_dash_c(self):
        sh(self.repo, "git", "switch", "-q", "main")
        other = os.path.join(self.tmp, "other")
        sh(self.tmp, "git", "init", "-q", "-b", "main", other)
        os.makedirs(os.path.join(other, ".claude"))
        write(os.path.join(other, ".claude", "pipeline.json"), json.dumps({"protected_branches": []}))
        self.assertDenied('git commit -m "x"')
        self.assertAllowed(f'cd {other} && git commit -m "x"')
        self.assertAllowed(f'git -C {other} commit -m "x"')
        self.assertDenied(f'cd {other} && cd {self.repo} && git commit -m "x"')

    def test_heredoc_body_is_data(self):
        sh(self.repo, "git", "switch", "-q", "main")
        self.assertAllowed("python3 - <<'EOF'\ns = 'git commit -m x'\nEOF\necho done")
        self.assertDenied("cat > f <<EOF\ngit push origin main\nEOF\ngit commit -m x")

    def test_attribution(self):
        msg = 'git commit -m "x\n\nCo-Authored-By: Claude <noreply@anthropic.com>"'
        self.assertAllowed(msg)
        self.assertDenied(msg, config={"block_attribution": True})

    def test_escape_hatch(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}, "cwd": self.repo}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.repo, PIPELINE_GUARD="off")
        r = subprocess.run(["python3", os.path.join(HOOKS, "git_guard.py")], input=json.dumps(ev),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.stdout, "")


class CardGuardTest(unittest.TestCase):
    def run_hook(self, status, ev):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(f"# T-1\nSTATUS: {status}\n")
        env = dict(os.environ, PIPELINE_CARD=f.name)
        r = subprocess.run(["python3", os.path.join(HOOKS, "card_guard.py")], input=json.dumps(ev),
                           capture_output=True, text=True, env=env)
        os.unlink(f.name)
        return r.returncode

    def test_blocks_once(self):
        self.assertEqual(self.run_hook("IN_PROGRESS", {}), 2)
        self.assertEqual(self.run_hook("IN_PROGRESS", {"stop_hook_active": True}), 0)
        self.assertEqual(self.run_hook("COMMITTED", {}), 0)


if __name__ == "__main__":
    unittest.main()
