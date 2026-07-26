#!/usr/bin/env python3
"""Behavioral tests for the release preparation CLI argument contract."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCRIPT = REPO_ROOT / "scripts" / "release.sh"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
REAL_GIT = shutil.which("git")


class ReleaseCliArgumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo"
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(RELEASE_SCRIPT, scripts / "release.sh")

        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.git_state = self.root / "git-state"
        self.git_state.mkdir()
        fake_git = self.fake_bin / "git"
        fake_git.write_text(
            """#!/bin/sh
state_dir=${FAKE_GIT_STATE_DIR:?}
base_head=${FAKE_START_HEAD-base123}
release_head=${FAKE_RELEASE_COMMIT-release456}

case "$1" in
    fetch)
        if [ "${FAKE_FETCH_FAIL-0}" = "1" ]; then
            exit 1
        fi
        exit 0
        ;;
    rev-parse)
        if [ "$2" = "-q" ] && [ "$3" = "--verify" ]; then
            exit 1
        fi
        if [ "$2" = "--verify" ] && [ "$3" = "HEAD" ]; then
            count_file="$state_dir/head-count"
            count=0
            if [ -f "$count_file" ]; then count=$(cat "$count_file"); fi
            count=$((count + 1))
            printf '%s\\n' "$count" > "$count_file"
            change_on=${FAKE_HEAD_CHANGE_ON_CALL-0}
            if [ "$change_on" -gt 0 ] && [ "$count" -ge "$change_on" ]; then
                printf '%s\\n' "${FAKE_CHANGED_HEAD-race999}"
            else
                printf '%s\\n' "$base_head"
            fi
            exit 0
        fi
        if [ "$2" = "HEAD" ]; then
            if [ -f "$state_dir/current-head" ]; then
                cat "$state_dir/current-head"
            else
                printf '%s\\n' "$base_head"
            fi
            exit 0
        fi
        if [ "$2" = "$release_head^" ]; then
            printf '%s\\n' "$base_head"
            exit 0
        fi
        if [ "$2" = "refs/heads/${FAKE_BRANCH-main}" ]; then
            if [ -f "$state_dir/current-head" ]; then
                cat "$state_dir/current-head"
            else
                printf '%s\\n' "$base_head"
            fi
            exit 0
        fi
        printf 'unexpected git rev-parse: %s\\n' "$*" >&2
        exit 99
        ;;
    describe) exit 1 ;;
    log)
        printf '%s|||abc123\\n' "${FAKE_LOG_SUBJECT-fix: deterministic release test}"
        ;;
    branch)
        if [ "$2" = "--show-current" ]; then
            printf '%s\\n' "${FAKE_BRANCH-main}"
            exit 0
        fi
        ;;
    status)
        count_file="$state_dir/status-count"
        count=0
        if [ -f "$count_file" ]; then count=$(cat "$count_file"); fi
        count=$((count + 1))
        printf '%s\\n' "$count" > "$count_file"
        change_on=${FAKE_STATUS_CHANGE_ON_CALL-0}
        if [ "$change_on" -gt 0 ] && [ "$count" -ge "$change_on" ]; then
            printf ' M raced.txt\\n'
        else
            printf '%s' "${FAKE_STATUS-}"
        fi
        exit 0
        ;;
    commit)
        printf '%s\\n' "$*" > "$state_dir/commit-args"
        printf '%s\\n' "$release_head" > "$state_dir/current-head"
        exit 0
        ;;
    push)
        printf '%s\\n' "$*" > "$state_dir/push-args"
        exit 0
        ;;
    *) printf 'unexpected git command: %s\\n' "$*" >&2; exit 99 ;;
esac
""",
            encoding="utf-8",
        )
        fake_git.chmod(0o755)

    def run_release(
        self,
        *args: str,
        env_overrides: Optional[dict[str, str]] = None,
        input_text: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env['PATH']}"
        env["FAKE_GIT_STATE_DIR"] = str(self.git_state)
        if env_overrides is not None:
            env.update(env_overrides)
        return subprocess.run(
            ["/bin/bash", str(self.repo / "scripts" / "release.sh"), *args],
            cwd=self.repo,
            env=env,
            text=True,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_unknown_option_is_a_usage_error(self) -> None:
        result = self.run_release("--definitely-not-a-real-option", "--dry-run")

        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "Unknown option: --definitely-not-a-real-option",
            result.stderr,
        )

    def test_extra_positional_argument_is_a_usage_error(self) -> None:
        result = self.run_release(
            "v2099.01.01",
            "unexpected-extra",
            "--dry-run",
        )

        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("Unexpected extra argument: unexpected-extra", result.stderr)

    def test_invalid_explicit_versions_are_usage_errors(self) -> None:
        for version in (
            "banana",
            "v2026.7.26",
            "v2026.07.26.0",
            "v2026.07.26.01",
        ):
            with self.subTest(version=version):
                result = self.run_release(version, "--dry-run")
                self.assertEqual(
                    2,
                    result.returncode,
                    result.stdout + result.stderr,
                )
                self.assertIn(f"Invalid version: {version}", result.stderr)

    def test_impossible_calendar_dates_are_usage_errors(self) -> None:
        for version in ("v2026.99.99", "v2026.02.29"):
            with self.subTest(version=version):
                result = self.run_release(version, "--dry-run")
                self.assertEqual(
                    2,
                    result.returncode,
                    result.stdout + result.stderr,
                )
                self.assertIn(f"Invalid calendar date: {version}", result.stderr)

    def test_valid_micro_versions_are_accepted(self) -> None:
        for supplied, normalized in (
            ("v2099.01.01.1", "v2099.01.01.1"),
            ("2099.01.01.2", "v2099.01.01.2"),
        ):
            with self.subTest(supplied=supplied):
                result = self.run_release(supplied, "--dry-run")
                self.assertEqual(
                    0,
                    result.returncode,
                    result.stdout + result.stderr,
                )
                self.assertIn(f"Preparing release {normalized}", result.stdout)
                self.assertIn("Dry run", result.stdout)
                self.assertFalse((self.repo / "VERSION").exists())
                self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_valid_leap_day_is_accepted(self) -> None:
        result = self.run_release("v2028.02.29.1", "--dry-run")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Preparing release v2028.02.29.1", result.stdout)

    def test_dry_run_warns_and_uses_local_tags_when_fetch_fails(self) -> None:
        result = self.run_release(
            "v2099.01.01",
            "--dry-run",
            env_overrides={"FAKE_FETCH_FAIL": "1"},
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("dry run is using the local tag list", result.stdout)
        self.assertFalse((self.repo / "VERSION").exists())
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_real_release_refuses_when_remote_tags_cannot_be_verified(self) -> None:
        result = self.run_release(
            "v2099.01.01",
            "--yes",
            env_overrides={"FAKE_FETCH_FAIL": "1"},
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("refusing to prepare a release", result.stderr)
        self.assertFalse((self.repo / "VERSION").exists())
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_detached_head_is_refused_before_release_files_are_written(self) -> None:
        result = self.run_release(
            "v2099.01.01",
            "--yes",
            env_overrides={"FAKE_BRANCH": ""},
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("Detached HEAD", result.stdout)
        self.assertFalse((self.repo / "VERSION").exists())
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_dirty_worktree_is_refused_before_release_files_are_written(self) -> None:
        result = self.run_release(
            "v2099.01.01",
            "--yes",
            env_overrides={"FAKE_STATUS": "M unrelated.txt\n"},
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("clean worktree", result.stderr)
        self.assertFalse((self.repo / "VERSION").exists())
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_head_change_after_confirmation_is_refused_before_writes(self) -> None:
        result = self.run_release(
            "v2099.01.01",
            env_overrides={"FAKE_HEAD_CHANGE_ON_CALL": "3"},
            input_text="y",
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("changed after confirmation", result.stderr)
        self.assertFalse((self.repo / "VERSION").exists())
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_worktree_change_after_confirmation_is_refused_before_writes(
        self,
    ) -> None:
        result = self.run_release(
            "v2099.01.01",
            env_overrides={"FAKE_STATUS_CHANGE_ON_CALL": "2"},
            input_text="y",
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("clean worktree after confirmation", result.stderr)
        self.assertIn("raced.txt", result.stderr)
        self.assertFalse((self.repo / "VERSION").exists())
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_clean_attached_branch_prepares_release_files(self) -> None:
        result = self.run_release("v2099.01.01", "--yes")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            "v2099.01.01\n",
            (self.repo / "VERSION").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "## v2099.01.01",
            (self.repo / "CHANGELOG.md").read_text(encoding="utf-8"),
        )
        self.assertIn("prepared and pushed to 'main'", result.stdout)
        self.assertEqual(
            "commit --only -m chore: release v2099.01.01 -- VERSION CHANGELOG.md\n",
            (self.git_state / "commit-args").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            "push origin release456:refs/heads/main\n",
            (self.git_state / "push-args").read_text(encoding="utf-8"),
        )

    def test_backslashes_in_commit_subject_are_preserved_verbatim(self) -> None:
        subject = r"fix: preserve C:\code path and trailing text"
        result = self.run_release(
            "v2099.01.01",
            "--yes",
            env_overrides={"FAKE_LOG_SUBJECT": subject},
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        changelog = (self.repo / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(r"- preserve C:\code path and trailing text (`abc123`)", changelog)
        self.assertIn(r"preserve C:\code path and trailing text", result.stdout)

    def test_existing_changelog_entries_are_preserved_byte_for_byte(self) -> None:
        header = (
            "# Changelog\n\n"
            "All notable changes to tGD will be documented in this file.\n\n"
            "Format based on [Keep a Changelog](https://keepachangelog.com/). "
            "Versions follow [CalVer](https://calver.org/) (YYYY.MM.DD).\n\n"
        )
        existing_entries = (
            "## v2098.12.31\n\n"
            "### 🐛 Bug Fixes\n"
            "- preserve this exact historical entry (`old123`)\n"
        )
        (self.repo / "CHANGELOG.md").write_text(
            header + existing_entries,
            encoding="utf-8",
        )

        result = self.run_release("v2099.01.01", "--yes")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        changelog = (self.repo / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(changelog.endswith(existing_entries))
        self.assertIn(
            "- deterministic release test (`abc123`)\n\n## v2098.12.31",
            changelog,
        )
        self.assertNotIn("\n\n\n", changelog)

    def test_release_workflow_enforces_immutable_target_contract(self) -> None:
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            '"+refs/heads/main:refs/remotes/origin/main"',
            workflow,
        )
        self.assertIn("git log -1 --format=%H -- VERSION", workflow)
        self.assertIn("git merge-base --is-ancestor", workflow)
        self.assertIn('"$TARGET_SHA" "refs/remotes/origin/main"', workflow)
        self.assertIn('git show "${TARGET_SHA}:VERSION"', workflow)
        self.assertIn(
            'git show "${TARGET_SHA}:CHANGELOG.md"',
            workflow,
        )
        self.assertIn('git tag "$VERSION" "$TARGET_SHA"', workflow)
        self.assertIn(
            'git push origin "refs/tags/$VERSION:refs/tags/$VERSION"',
            workflow,
        )
        self.assertIn('"refs/tags/$VERSION^{commit}"', workflow)
        self.assertIn('"$CHECK_REF^{commit}"', workflow)
        self.assertIn('gh release view "$VERSION"', workflow)
        self.assertIn("--verify-tag", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertNotIn('--target "$GITHUB_SHA"', workflow)


@unittest.skipIf(REAL_GIT is None, "git is required for release target test")
class ReleaseWorkflowTargetTests(unittest.TestCase):
    def test_later_main_commit_does_not_retarget_existing_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(
                [REAL_GIT, "init", "--quiet"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [REAL_GIT, "config", "user.name", "Release Test"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [REAL_GIT, "config", "user.email", "release@example.invalid"],
                cwd=repo,
                check=True,
            )
            (repo / "VERSION").write_text("v2099.01.01\n", encoding="utf-8")
            (repo / "CHANGELOG.md").write_text(
                "# Changelog\n\n## v2099.01.01\n",
                encoding="utf-8",
            )
            subprocess.run(
                [REAL_GIT, "add", "VERSION", "CHANGELOG.md"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [REAL_GIT, "commit", "--quiet", "-m", "release"],
                cwd=repo,
                check=True,
            )
            version_commit = subprocess.check_output(
                [REAL_GIT, "rev-parse", "HEAD"],
                cwd=repo,
                text=True,
            ).strip()

            (repo / "README.md").write_text("later commit\n", encoding="utf-8")
            subprocess.run(
                [REAL_GIT, "add", "README.md"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [REAL_GIT, "commit", "--quiet", "-m", "later"],
                cwd=repo,
                check=True,
            )
            later_head = subprocess.check_output(
                [REAL_GIT, "rev-parse", "HEAD"],
                cwd=repo,
                text=True,
            ).strip()
            target = subprocess.check_output(
                [REAL_GIT, "log", "-1", "--format=%H", "--", "VERSION"],
                cwd=repo,
                text=True,
            ).strip()
            target_version = subprocess.check_output(
                [REAL_GIT, "show", f"{target}:VERSION"],
                cwd=repo,
                text=True,
            )

            self.assertNotEqual(version_commit, later_head)
            self.assertEqual(version_commit, target)
            self.assertEqual("v2099.01.01\n", target_version)

            subprocess.run(
                [
                    REAL_GIT,
                    "update-ref",
                    "refs/remotes/origin/main",
                    later_head,
                ],
                cwd=repo,
                check=True,
            )
            main_guard = subprocess.run(
                [
                    REAL_GIT,
                    "merge-base",
                    "--is-ancestor",
                    target,
                    "refs/remotes/origin/main",
                ],
                cwd=repo,
                check=False,
            )
            self.assertEqual(0, main_guard.returncode)

            subprocess.run(
                [REAL_GIT, "checkout", "--quiet", "-b", "feature-release"],
                cwd=repo,
                check=True,
            )
            (repo / "VERSION").write_text("v2099.01.02\n", encoding="utf-8")
            subprocess.run(
                [REAL_GIT, "add", "VERSION"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [REAL_GIT, "commit", "--quiet", "-m", "feature release"],
                cwd=repo,
                check=True,
            )
            feature_target = subprocess.check_output(
                [REAL_GIT, "log", "-1", "--format=%H", "--", "VERSION"],
                cwd=repo,
                text=True,
            ).strip()
            feature_guard = subprocess.run(
                [
                    REAL_GIT,
                    "merge-base",
                    "--is-ancestor",
                    feature_target,
                    "refs/remotes/origin/main",
                ],
                cwd=repo,
                check=False,
            )
            self.assertNotEqual(0, feature_guard.returncode)


if __name__ == "__main__":
    unittest.main()
