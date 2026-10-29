"""ModCommands analysis must measure delivery from the candidate revision only."""
from pathlib import Path
import subprocess
import unittest
import yaml

CHART = Path(__file__).resolve().parents[2] / 'main/sky/chart'


class ModCommandsAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['helm', 'template', 'sky', str(CHART), '--namespace', 'sky',
            '-f', str(CHART / 'eu.yaml'), '-f', str(CHART / 'talos.yaml')],
            text=True, capture_output=True, check=True)
        cls.objects = {(obj['kind'], obj['metadata']['name']): obj
                       for obj in yaml.safe_load_all(result.stdout) if obj}

    def test_analysis_measures_only_latest_candidate_delivery(self):
        spec = self.objects['AnalysisTemplate', 'sky-mod-commands']['spec']
        self.assertIn({'name': 'latest-hash'}, spec['args'])
        metric = spec['metrics'][0]
        self.assertEqual(metric['provider']['prometheus']['query'].strip(),
            'sum(increase(sky_mod_sent_flips{namespace="sky",pod=~"sky-mod-commands-{{args.latest-hash}}-.*"}[5m]))')
        self.assertNotIn('sky_mod_flips_purchased', metric['provider']['prometheus']['query'])
        self.assertEqual({key: metric[key] for key in ('count', 'interval', 'failureLimit', 'successCondition')},
                         {'count': 3, 'interval': '3m', 'failureLimit': 1, 'successCondition': 'result[0] >= 1'})

    def test_rollout_passes_latest_hash_without_skipping_any_step(self):
        strategy = self.objects['Rollout', 'sky-mod-commands']['spec']['strategy']['canary']
        self.assertEqual(strategy['steps'][:-1], [{'setWeight': 30}, {'pause': {'duration': '1m'}},
            {'setWeight': 60}, {'pause': {'duration': '1m'}}, {'setWeight': 100}, {'pause': {'duration': '2m'}}])
        analysis = strategy['steps'][-1]['analysis']
        self.assertEqual(analysis['templates'], [{'templateName': 'sky-mod-commands'}])
        self.assertIn({'name': 'latest-hash', 'valueFrom': {'podTemplateHashValue': 'Latest'}}, analysis['args'])


if __name__ == '__main__':
    unittest.main()
