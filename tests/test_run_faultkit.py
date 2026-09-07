"""Unit tests for the runner's pure functions. Standard library only."""

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "faultkit" / "scripts"))

import run_faultkit as rf  # noqa: E402


class PlatformTests(unittest.TestCase):
    def test_linux_x86_64_maps_to_amd64(self):
        self.assertEqual(rf.platform_key("Linux", "x86_64"), ("linux", "amd64"))

    def test_darwin_arm64(self):
        self.assertEqual(rf.platform_key("Darwin", "arm64"), ("darwin", "arm64"))

    def test_unsupported_platform_raises_with_list(self):
        with self.assertRaises(rf.UnsupportedPlatform) as ctx:
            rf.platform_key("Windows", "AMD64")
        self.assertIn("linux/amd64", str(ctx.exception))

    def test_asset_name_strips_v(self):
        self.assertEqual(rf.asset_name("v0.1.2", "linux", "amd64"), "faultkit_0.1.2_linux_amd64.tar.gz")


class ChecksumTests(unittest.TestCase):
    NAME = "faultkit_0.1.2_linux_amd64.tar.gz"

    def test_matching_checksum_passes(self):
        data = b"binary"
        digest = hashlib.sha256(data).hexdigest()
        rf.verify_checksum(data, f"{digest}  {self.NAME}\n", self.NAME)

    def test_mismatch_raises_with_both_digests(self):
        data = b"binary"
        with self.assertRaises(rf.ChecksumMismatch) as ctx:
            rf.verify_checksum(data, "0" * 64 + f"  {self.NAME}\n", self.NAME)
        self.assertIn(hashlib.sha256(data).hexdigest(), str(ctx.exception))
        self.assertIn("0" * 64, str(ctx.exception))

    def test_missing_entry_raises(self):
        with self.assertRaises(rf.ChecksumMismatch):
            rf.verify_checksum(b"x", "abc  other.tar.gz\n", self.NAME)


class ProofTests(unittest.TestCase):
    def test_fired_count_counts_only_fired_events(self):
        report = {"events": [{"fired": True}, {"fired": False}, {"fired": True}]}
        self.assertEqual(rf.fired_count(report), 2)

    def test_fired_count_handles_missing_events(self):
        self.assertEqual(rf.fired_count({}), 0)

    def test_proof_states(self):
        self.assertEqual(rf.proof_state(3, 0), "invalid evidence: nothing was injected")
        self.assertEqual(rf.proof_state(1, 6), "silent failure confirmed")
        self.assertEqual(rf.proof_state(0, 1), "invariant proven under fault")
        self.assertEqual(rf.proof_state(2, 0), "error: faultkit exited 2")

    def test_passing_target_with_nothing_fired_is_invalid(self):
        self.assertEqual(rf.proof_state(0, 0), "invalid evidence: nothing was injected")


class ResolveTests(unittest.TestCase):
    def _resolve(self, **overrides):
        kwargs = dict(
            explicit=None, env={}, which=lambda _: None, source=None,
            cache_dir=Path("/c"), version="v0.1.2", downloader=lambda *a: Path("/d"),
        )
        kwargs.update(overrides)
        return rf.resolve_binary(**kwargs)

    def test_explicit_wins(self):
        self.assertEqual(self._resolve(explicit="/x/faultkit", env={"FAULTKIT": "/y"}, which=lambda _: "/z"), Path("/x/faultkit"))

    def test_env_beats_path(self):
        self.assertEqual(self._resolve(env={"FAULTKIT": "/y"}, which=lambda _: "/z"), Path("/y"))

    def test_path_beats_download(self):
        self.assertEqual(self._resolve(which=lambda _: "/z"), Path("/z"))

    def test_download_is_last(self):
        calls = []

        def downloader(version, cache_dir):
            calls.append((version, cache_dir))
            return Path("/d")

        self.assertEqual(self._resolve(downloader=downloader), Path("/d"))
        self.assertEqual(calls, [("v0.1.2", Path("/c"))])


class ColorTests(unittest.TestCase):
    def test_auto_follows_tty(self):
        self.assertTrue(rf.use_color("auto", isatty=True, env={}))
        self.assertFalse(rf.use_color("auto", isatty=False, env={}))

    def test_no_color_wins_over_tty(self):
        self.assertFalse(rf.use_color("auto", isatty=True, env={"NO_COLOR": "1"}))

    def test_force_color_wins_over_pipe(self):
        self.assertTrue(rf.use_color("auto", isatty=False, env={"FORCE_COLOR": "1"}))

    def test_always_and_never(self):
        self.assertTrue(rf.use_color("always", isatty=False, env={"NO_COLOR": "1"}))
        self.assertFalse(rf.use_color("never", isatty=True, env={"FORCE_COLOR": "1"}))

    def test_proof_block_keeps_state_strings_with_and_without_color(self):
        plain = rf.render_proof("s.yaml", "proxy", 1, 1, "silent failure confirmed", "r.json", color=False)
        self.assertIn("proof state:   silent failure confirmed", plain)
        self.assertNotIn("\033[", plain)
        painted = rf.render_proof("s.yaml", "proxy", 1, 0, "invariant proven under fault", "r.json", color=True)
        self.assertIn("invariant proven under fault", painted)
        self.assertIn("\033[32m", painted)  # green for proven
        invalid = rf.render_proof("s.yaml", "proxy", 0, 3, "invalid evidence: nothing was injected", "r.json", color=True)
        self.assertIn("\033[33m", invalid)  # yellow for invalid


class ArgTests(unittest.TestCase):
    def test_split_target_after_double_dash(self):
        ns, target = rf.parse_args(["--config", "s.yaml", "--report", "r.json", "--base-url", "--", "node", "--test", "t.mjs"])
        self.assertEqual(target, ["node", "--test", "t.mjs"])
        self.assertTrue(ns.base_url)

    def test_color_flag_parses(self):
        ns, _ = rf.parse_args(["--config", "s.yaml", "--report", "r.json", "--color", "always", "--", "true"])
        self.assertEqual(ns.color, "always")

    def test_missing_target_is_usage_error(self):
        with self.assertRaises(SystemExit):
            rf.parse_args(["--config", "s.yaml", "--report", "r.json"])


if __name__ == "__main__":
    unittest.main()
