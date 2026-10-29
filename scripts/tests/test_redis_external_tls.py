"""Render the four external renewers without changing any existing workload."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

CHART = Path(__file__).resolve().parents[2] / 'main/sky/chart'
SERVICES = {'sky-global-redis', 'sky-mod-commands-redis', 'sky-settings-redis', 'sky-sniper-redis'}


def render(values):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as stream:
        yaml.safe_dump(values, stream)
        stream.flush()
        result = subprocess.run(['helm', 'template', 'sky', str(CHART), '--namespace', 'sky',
            '-f', str(CHART / 'eu.yaml'), '-f', str(CHART / 'talos.yaml'), '-f', stream.name],
            text=True, capture_output=True, check=True)
    return {(obj['kind'], obj['metadata']['name']): obj
            for obj in yaml.safe_load_all(result.stdout) if obj}


class ExternalRedisTLS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        active = yaml.safe_load((CHART / 'redis-optional-tls-eu.yaml').read_text())
        cls.active = render(active)
        previous = copy.deepcopy(active)
        config = previous['global']['redisOptionalTls']
        config['listenerServices'] = [name for name in config['listenerServices'] if name not in SERVICES]
        config['externalReloaderServices'] = []
        cls.previous = render(previous)

    def test_every_existing_resource_stays_identical(self):
        for key, obj in self.previous.items():
            with self.subTest(resource=key):
                self.assertEqual(self.active[key], obj)
        jobs = {name for kind, name in self.active.keys() - self.previous.keys() if kind == 'CronJob'}
        self.assertEqual(jobs, {name + '-tls-renewal' for name in SERVICES})

    def test_workers_are_bounded_and_share_only_the_matching_pvc_node(self):
        for name in SERVICES:
            job = self.active['CronJob', name + '-tls-renewal']['spec']
            self.assertEqual(job['schedule'], '*/15 * * * *')
            self.assertEqual(job['concurrencyPolicy'], 'Forbid')
            self.assertEqual(job['jobTemplate']['spec']['activeDeadlineSeconds'], 60)
            pod = job['jobTemplate']['spec']['template']['spec']
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertEqual(pod['restartPolicy'], 'Never')
            self.assertEqual(pod['volumes'][0]['persistentVolumeClaim']['claimName'], name + '-upgrade')
            affinity = pod['affinity']['podAffinity']['requiredDuringSchedulingIgnoredDuringExecution']
            self.assertEqual(affinity, [{'labelSelector': {'matchLabels': {'redis-upgrade-candidate': name}},
                                         'topologyKey': 'kubernetes.io/hostname'}])


if __name__ == '__main__':
    unittest.main()
