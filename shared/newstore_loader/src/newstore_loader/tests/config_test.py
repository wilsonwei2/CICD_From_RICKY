import newstore_loader.config as config
import os
import unittest

TEST_TENANT = "testenant"
TEST_STAGE = 't'


class ConfigTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["TENANT_ROOT"] = os.path.join(os.getcwd(), "res", "tenants")
        self.cfg = config.Config(TEST_TENANT, TEST_STAGE)


class TestConfigSetup(ConfigTestCase):

    def test_tenant_property(self):
        self.assertEqual(self.cfg.tenant_property('display_price_unit_type'), 'net', 'incorrect tenant property')

    def test_read_file(self):
        count = 0
        j = self.cfg.read_file("../../../samples/multi_item.json")
        y = self.cfg.read_file("../../../samples/multi_item.yaml")
        for pair in zip(j, y):
            self.assertEqual(pair[0], pair[1], 'non-matching result')
            count += 1
        self.assertEqual(count, 2, 'incorrect count')
