"""Exercise deployment failure gates without contacting Docker or a real host."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class DeploymentSafety(unittest.TestCase):
    def run_deploy(self, scenario):
        # Windows' system bash may be a WSL launcher and cannot run these paths.
        git_bash = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        bash = os.environ.get("BASH_EXE") or (str(git_bash) if os.name == "nt" and git_bash.exists() else shutil.which("bash"))
        self.assertTrue(bash)
        with tempfile.TemporaryDirectory(prefix="pantong-deploy-test-") as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / "deploy").mkdir()
            shutil.copy2(Path(__file__).with_name("deploy.sh"), root / "deploy" / "deploy.sh")
            (root / ".env").write_text("API_PORT=8100\n", encoding="utf-8")
            (root / "CANDIDATE_REV").write_text("a" * 40 + " test\n", encoding="utf-8")
            (root / "DEPLOYED_REV").write_text("old-release\n", encoding="utf-8")
            scripts = {
                "docker": """#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$TEST_LOG"
case "$*" in
  'compose ps --status running --services')
    [[ "$SCENARIO" != discovery_failure ]] || exit 9
    [[ "$SCENARIO" == postgres_stopped ]] || printf 'postgres\\napi\\n'
    ;;
  'compose exec -T postgres pg_dump '* )
    [[ "$SCENARIO" != dump_failure ]] || exit 7
    printf '%s\\n' '-- synthetic PostgreSQL dump'
    ;;
  'compose images -q api') printf 'sha256:old\\n';;
  'image inspect '*) printf 'sha256:new\\n';;
  'compose ps -q api') printf 'test-container\\n';;
  'inspect '* )
    if [[ "$SCENARIO" == wrong_image ]]; then printf 'sha256:old\\n'; else printf 'sha256:new\\n'; fi
    ;;
esac
""",
                "git": "#!/usr/bin/env bash\nexit 1\n",
                "curl": """#!/usr/bin/env bash
[[ "$SCENARIO" != health_failure ]] || exit 22
printf '{"ok":true}\\n'
""",
                "sleep": "#!/usr/bin/env bash\nexit 0\n",
            }
            for name, script in scripts.items():
                (bin_dir / name).write_text(script, encoding="utf-8", newline="\n")
            env = dict(os.environ, SCENARIO=scenario, TEST_LOG=(root / "commands.log").as_posix())
            command = 'testroot="$(cd "$1" && pwd)"; export PATH="$testroot/bin:$PATH"; chmod +x "$testroot"/bin/*; bash "$testroot/deploy/deploy.sh"'
            result = subprocess.run([bash, "-c", command, "test", root.as_posix()],
                                    env=env, capture_output=True, text=True, timeout=30)
            return {
                "code": result.returncode,
                "output": result.stdout + result.stderr,
                "log": (root / "commands.log").read_text() if (root / "commands.log").exists() else "",
                "rev": (root / "DEPLOYED_REV").read_text(),
                "candidate": (root / "CANDIDATE_REV").exists(),
                "image": (root / "DEPLOYED_IMAGE").read_text() if (root / "DEPLOYED_IMAGE").exists() else "",
            }

    def test_backup_failures_stop_before_build(self):
        for scenario in ("discovery_failure", "postgres_stopped", "dump_failure"):
            with self.subTest(scenario=scenario):
                result = self.run_deploy(scenario)
                self.assertNotEqual(result["code"], 0, result["output"])
                self.assertIn("compose ps --status running --services", result["log"])
                self.assertNotIn("compose build", result["log"])
                self.assertEqual(result["rev"], "old-release\n")

    def test_bad_health_does_not_publish_revision(self):
        result = self.run_deploy("health_failure")
        self.assertNotEqual(result["code"], 0, result["output"])
        self.assertEqual(result["rev"], "old-release\n")
        self.assertTrue(result["candidate"])

    def test_wrong_running_image_does_not_publish_revision(self):
        result = self.run_deploy("wrong_image")
        self.assertNotEqual(result["code"], 0, result["output"])
        self.assertEqual(result["rev"], "old-release\n")

    def test_success_records_verified_image_and_revision(self):
        result = self.run_deploy("success")
        self.assertEqual(result["code"], 0, result["output"])
        self.assertTrue(result["rev"].startswith("a" * 40 + " "))
        self.assertEqual(result["image"], "sha256:new\n")
        self.assertFalse(result["candidate"])
        self.assertIn("image tag sha256:old thaiplastic-api:before-", result["log"])
        self.assertLess(result["log"].index("pg_dump"), result["log"].index("compose build"))


if __name__ == "__main__":
    unittest.main()
