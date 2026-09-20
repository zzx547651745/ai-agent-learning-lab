import unittest
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from experiment import MODES, cached_tokens, call_codex_cli, call_model, offline_preview, parse_codex_events, report_paths, request_parts, summarize


class KVCacheExperimentTests(unittest.TestCase):
    def test_all_modes_generate_five_turns(self):
        for mode in MODES:
            self.assertEqual(len(offline_preview(mode)["turns"]), 5)

    def test_stable_prefix_beats_early_mutations(self):
        correct = summarize(offline_preview("correct"))["mean_shared_prefix_percent"]
        for mode in ("dynamic_system", "dynamic_profile", "shuffled_tools"):
            damaged = summarize(offline_preview(mode))["mean_shared_prefix_percent"]
            self.assertGreater(correct, damaged, mode)

    def test_window_drops_early_history(self):
        history = []
        for turn in range(4):
            history.extend(({"role": "user", "content": f"question-{turn}"},
                            {"role": "assistant", "content": f"answer-{turn}"}))
        messages, _ = request_parts("sliding_window", 4, history, nonce="fixed")
        self.assertEqual(len(messages), 6)
        self.assertNotIn("question-0", str(messages))

    def test_missing_cache_metric_is_not_zero(self):
        self.assertIsNone(cached_tokens({"prompt_tokens": 100}))
        self.assertEqual(cached_tokens({"cached_tokens": 0}), 0)
        self.assertEqual(cached_tokens({"prompt_tokens_details": {"cached_tokens": 42}}), 42)

    def test_report_preserves_unavailable_metric(self):
        result = {"kind": "live_provider_measurement", "mode": "correct", "turns": [
            {"prompt_tokens": 100, "cached_tokens": None, "elapsed_seconds": 1.5}
        ]}
        self.assertIsNone(summarize(result)["cache_ratio_percent"])

    def test_report_rejects_unmatched_glob(self):
        with self.assertRaisesRegex(ValueError, "No result"):
            report_paths(["no-such-results-*.json"])

    def test_openai_request_uses_provider_endpoint_and_no_forced_temperature(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data)
            return io.BytesIO(b'{"choices":[{"message":{"content":"ok"}}],"usage":{}}')

        with patch("experiment.urlopen", side_effect=fake_urlopen):
            response, _ = call_model([{"role": "user", "content": "hi"}], [],
                                     key="test-only", model="gpt-4.1-mini",
                                     base_url="https://api.openai.com/v1", timeout=5,
                                     provider="openai")
        self.assertEqual(captured["url"], "https://api.openai.com/v1/chat/completions")
        self.assertNotIn("temperature", captured["payload"])
        self.assertEqual(response["choices"][0]["message"]["content"], "ok")

    def test_codex_jsonl_usage_conversion(self):
        events = '\n'.join((
            '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}',
            '{"type":"turn.completed","usage":{"input_tokens":1200,"cached_input_tokens":700,"output_tokens":9}}',
        ))
        response = parse_codex_events(events)
        self.assertEqual(response["choices"][0]["message"]["content"], "ok")
        self.assertEqual(response["usage"]["cached_tokens"], 700)
        self.assertEqual(response["usage"]["prompt_tokens"], 1200)

    def test_codex_missing_usage_is_error(self):
        with self.assertRaisesRegex(RuntimeError, "no turn.completed"):
            parse_codex_events('{"type":"turn.started"}')

    def test_codex_prompt_is_passed_via_stdin(self):
        events = '\n'.join((
            '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}',
            '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":1}}',
        ))
        fake_result = SimpleNamespace(returncode=0, stdout=events, stderr="")
        with patch("experiment.shutil.which", return_value="codex.cmd"), \
             patch("experiment.subprocess.run", return_value=fake_result) as run:
            call_codex_cli([{"role": "user", "content": "unique-task"}], [],
                           model=None, timeout=5)
        self.assertEqual(run.call_args.args[0][-1], "-")
        self.assertIn("unique-task", run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
