import unittest
from foundation.browser_network import check_destination,check_resolved_addresses
class BrowserNetworkTests(unittest.TestCase):
    def test_exact_reviewed_host(self):self.assertEqual(check_destination('https://portal.example.com/form',['portal.example.com']),'portal.example.com')
    def test_unreviewed_redirect_destination_blocked(self):
        with self.assertRaises(ValueError):check_destination('https://other.example.com',['portal.example.com'])
    def test_local_and_ambiguous_urls_blocked_even_if_allowlisted(self):
        for host in ['127.0.0.1','169.254.169.254','localhost','service.internal','portal.example.com.']:
            with self.subTest(host=host):
                with self.assertRaises(ValueError):check_destination('https://'+host,[host])
    def test_private_dns_answer_blocks_entire_connection(self):
        for addresses in [['8.8.8.8','10.0.0.1'],['::1'],['169.254.169.254'],[]]:
            with self.assertRaises(ValueError):check_resolved_addresses(addresses)
    def test_public_addresses_pass(self):check_resolved_addresses(['8.8.8.8','2606:4700:4700::1111'])
