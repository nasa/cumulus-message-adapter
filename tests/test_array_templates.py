"""Array templates must remove only their own enclosing brackets."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonpath_ng.exceptions import JsonPathParserError

from message_adapter.cumulus_message import resolve_path_str
from message_adapter.message_adapter import MessageAdapter


class TestArrayTemplates(unittest.TestCase):
    """Test actual JSONPath evaluation and the public adapter entry points."""

    def setUp(self):
        self.event = {
            'payload': {'values': [10, 20, 30], 'rows': [[1, 2], [3, 4]]},
            'meta': {'name': 'sample'},
        }
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {'LAMBDA_TASK_ROOT': directory.name})
        environment.start()
        self.addCleanup(environment.stop)

    def test_trailing_wildcard(self):
        """Keep the wildcard's closing bracket and preserve source data."""
        original = copy.deepcopy(self.event)
        self.assertEqual(resolve_path_str(
            self.event, '{[$.payload.values[*]]}'), [10, 20, 30])
        self.assertEqual(self.event, original)

    def test_trailing_indices_and_slices(self):
        """Accept both element selectors and array slices."""
        for selector, expected in [('[0]', [10]), ('[-1]', [30]),
                                   ('[1:3]', [20, 30]), ('[99]', [])]:
            with self.subTest(selector=selector):
                self.assertEqual(resolve_path_str(
                    self.event, '{[$.payload.values' + selector + ']}'), expected)

    def test_quoted_keys_and_nested_subscripts(self):
        """Retain closing brackets belonging to keys or nested arrays."""
        for expression, expected in [
            ("$['payload']['values'][*]", [10, 20, 30]),
            ("$.payload['values']", [[10, 20, 30]]),
            ('$.payload.rows[*][0]', [1, 3]),
        ]:
            with self.subTest(expression=expression):
                self.assertEqual(resolve_path_str(
                    self.event, '{[' + expression + ']}'), expected)

    def test_root_array(self):
        """Apply the same wrapper rule to an array at the document root."""
        self.assertEqual(resolve_path_str([1, 2, 3], '{[$[*]]}'), [1, 2, 3])

    def test_empty_array(self):
        """No matching elements still yield an empty list."""
        self.assertEqual(resolve_path_str({'values': []}, '{[$.values[*]]}'), [])

    def test_existing_template_forms(self):
        """Preserve field-only arrays, typed values and inline strings."""
        for template, expected in [
            ('{[$.meta.name]}', ['sample']),
            ('{[$.missing]}', []),
            ('{$.payload.values[0]}', 10),
            ('{{$.payload.values[0]}}', 10),
            ('prefix{$.meta.name}suffix', 'prefixsamplesuffix'),
            ('literal', 'literal'),
        ]:
            with self.subTest(template=template):
                self.assertEqual(resolve_path_str(self.event, template), expected)

    def test_invalid_jsonpath_still_raises(self):
        """Do not turn an invalid expression into an empty match."""
        with self.assertRaises(JsonPathParserError):
            resolve_path_str(self.event, '{[$.payload.values[0]}')

    def test_nested_input_and_configuration(self):
        """Resolve selectors through the actual input and config paths."""
        self.event['task_config'] = {
            'selected': '{[$.payload.rows[*][1]]}',
            'cumulus_message': {'input': '{[$.payload.values[1:3]]}'},
        }
        original = copy.deepcopy(self.event)
        result = MessageAdapter().load_nested_event(self.event)
        self.assertEqual(result['input'], [20, 30])
        self.assertEqual(result['config'], {'selected': [2, 4]})
        self.assertEqual(self.event, original)

    def test_output_source_selector(self):
        """Output source templates also retain their selector brackets."""
        response = {'values': [10, 20]}
        message_config = {'outputs': [{
            'source': '{[$.values[*]]}',
            'destination': '{$.payload.selected}',
        }]}
        result = MessageAdapter().create_next_event(
            response, self.event, message_config)
        self.assertEqual(result['payload'], {'selected': [10, 20]})
        self.assertEqual(response, {'values': [10, 20]})

    def test_single_command_entry_point(self):
        """Exercise the CLI JSON input and output without network access."""
        self.event['task_config'] = {
            'cumulus_message': {'input': '{[$.payload.values[*]]}'}}
        command = Path(__file__).resolve().parents[1] / '__main__.py'
        result = subprocess.run(
            [sys.executable, str(command), 'loadNestedEvent'],
            input=json.dumps({'event': self.event}) + '\n',
            text=True, capture_output=True, check=False, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['input'], [10, 20, 30])
