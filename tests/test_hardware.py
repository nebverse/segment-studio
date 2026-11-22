"""Offline tests of hardware selection; no CUDA hardware required."""
import unittest
from hardware_probe import parse_gpus, select_backend, plan


def gpu(cap, driver, vram=8):
    return {'name': 'Test NVIDIA', 'capability': cap, 'driver': driver, 'vram_gib': vram}


def machine(gpus):
    return dict(os='Windows', architecture='AMD64', python='3.12.16',
                python_64bit=True, gpus=gpus, ram_gib=16, disk_free_gib=100)


class HardwareTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_gpus('RTX 5070 Laptop GPU, 617.14, 8151, 12.0\n')[0]['capability'], '12.0')
    def test_new_gpu(self):
        self.assertEqual(select_backend(gpu('12.0','617.14'))[0], 'cu128')
    def test_driver_fallback(self):
        self.assertEqual(select_backend(gpu('8.6','565.90'))[0], 'cu126')
    def test_older_card(self):
        self.assertEqual(select_backend(gpu('6.1','580.10'))[0], 'cu126')
    def test_old_driver_cpu(self):
        self.assertEqual(select_backend(gpu('8.6','540.0'))[0], 'cpu')
    def test_missing_gpu_cpu(self):
        self.assertEqual(select_backend(None)[0], 'cpu')
    def test_override(self):
        self.assertEqual(select_backend(gpu('12.0','617.14'),'cpu')[0], 'cpu')
        with self.assertRaises(ValueError):
            select_backend(gpu('12.0','540.0'),'cu128')
    def test_sam3_requires_cu128(self):
        with self.assertRaises(ValueError):
            plan(machine([gpu('8.6','565.90')]),'auto',True)
    def test_low_vram_warning(self):
        result=plan(machine([gpu('12.0','617.14',8)]),'auto',True)
        self.assertTrue(any('SAM3' in x for x in result['warnings']))
    def test_32bit_block(self):
        info=machine([])
        info['python_64bit']=False
        with self.assertRaises(ValueError):
            plan(info,'auto',False)


if __name__ == '__main__':
    unittest.main()