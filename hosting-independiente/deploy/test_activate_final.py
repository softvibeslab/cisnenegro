import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('activate_final', Path(__file__).with_name('activate_final.py'))
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


def dns_answer(record_type, addresses=(), cname=False, status='NOERROR'):
    header = f';; ->>HEADER<<- opcode: QUERY, status: {status}, id: 1\n'
    if cname:
        header += 'www.cisnenegro.mx. 300 IN CNAME cisnenegro.mx.\n'
    return header + ''.join(f'cisnenegro.mx. 300 IN {record_type} {ip}\n' for ip in addresses)


class ActivateFinalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vhost = self.root / 'cisne-final'
        self.placeholder = (activation.MARKER + '\nserver { listen 80; }\n').encode()
        self.vhost.write_bytes(self.placeholder)
        self.certificate = self.root / 'certificate'
        self.certificate.mkdir()
        self.calls = []
        self.address = activation.TARGET_IP
        self.ipv6 = []
        self.fail_nginx_check = 0
        self.nginx_checks = 0
        self.fail_reload = False
        self.fail_certbot = False

    def command(self, args, **kwargs):
        self.calls.append(args)
        output = ''
        if args[0] == 'dig':
            record_type = args[3]
            addresses = [self.address] if record_type == 'A' else self.ipv6
            output = dns_answer(record_type, addresses, cname=args[2].startswith('www.'))
        elif args[:2] == ['nginx', '-t']:
            self.nginx_checks += 1
            if self.nginx_checks == self.fail_nginx_check:
                raise subprocess.CalledProcessError(1, args, stderr='private configuration')
        elif args[0] == 'certbot':
            if self.fail_certbot:
                raise subprocess.CalledProcessError(1, args)
            for name in ('fullchain.pem', 'privkey.pem'):
                (self.certificate / name).write_text('test certificate')
        elif args == ['systemctl', 'reload', 'nginx'] and self.fail_reload:
            self.fail_reload = False
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, stdout=output)

    def activate(self):
        return activation.activate(self.vhost, self.certificate, self.root / 'lock', self.command)

    def test_waits_for_old_dns_without_certbot_or_nginx_changes(self):
        self.address = '198.49.23.145'
        self.assertEqual(self.activate()['status'], 'waiting_for_dns')
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)
        self.assertTrue(all(args[0] == 'dig' for args in self.calls))

    def test_active_ipv6_prevents_cutover(self):
        self.ipv6 = ['2001:db8::1']
        self.assertEqual(self.activate()['status'], 'waiting_for_dns')
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)

    def test_activates_both_names_after_both_resolvers_agree_and_is_idempotent(self):
        self.assertEqual(self.activate()['status'], 'activated')
        dns_calls = [args for args in self.calls if args[0] == 'dig']
        self.assertEqual(len(dns_calls), 8)
        self.assertEqual({args[1] for args in dns_calls}, {'@1.1.1.1', '@8.8.8.8'})
        self.assertEqual(self.vhost.read_text(), activation.final_config())
        certbot = next(args for args in self.calls if args[0] == 'certbot')
        self.assertIn('--non-interactive', certbot)
        self.assertIn('www.cisnenegro.mx', certbot)
        self.assertIn('cisnenegro.mx', certbot)
        self.assertEqual(self.calls[-1], ['systemctl', 'reload', 'nginx'])
        self.calls.clear()
        self.assertEqual(self.activate()['status'], 'already_active')
        self.assertEqual(self.calls, [])

    def test_apex_serves_application_and_www_redirects_preserving_request_uri(self):
        config = activation.final_config()
        blocks = re.split(r'(?m)^server \{', config)[1:]
        self.assertEqual(len(blocks), 3)
        self.assertIn('return 301 https://cisnenegro.mx$request_uri;', blocks[0])
        self.assertIn('server_name www.cisnenegro.mx;', blocks[1])
        self.assertIn('return 301 https://cisnenegro.mx$request_uri;', blocks[1])
        self.assertNotIn('proxy_pass', blocks[1])
        self.assertIn('server_name cisnenegro.mx;', blocks[2])
        self.assertIn('proxy_pass http://127.0.0.1:8888;', blocks[2])
        self.assertNotIn('return 301', blocks[2])

    def test_invalid_existing_nginx_prevents_certificate_request(self):
        self.fail_nginx_check = 1
        with self.assertRaises(subprocess.CalledProcessError):
            self.activate()
        self.assertFalse(any(args[0] == 'certbot' for args in self.calls))
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)

    def test_certificate_failure_preserves_placeholder(self):
        self.fail_certbot = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.activate()
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)
        self.assertFalse(any(args[0] == 'systemctl' for args in self.calls))

    def test_failed_certificate_waits_before_retrying_acme(self):
        self.fail_certbot = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.activate()
        self.calls.clear()
        self.assertEqual(self.activate()['status'], 'waiting_for_certificate_retry')
        self.assertTrue(all(args[0] == 'dig' for args in self.calls))
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)

    def test_invalid_generated_nginx_rolls_back_without_reload(self):
        self.fail_nginx_check = 2
        with self.assertRaises(subprocess.CalledProcessError):
            self.activate()
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)
        self.assertFalse(any(args[0] == 'systemctl' for args in self.calls))

    def test_reload_failure_restores_and_reloads_previous_config(self):
        self.fail_reload = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.activate()
        self.assertEqual(self.vhost.read_bytes(), self.placeholder)
        self.assertEqual(self.nginx_checks, 3)
        self.assertEqual(sum(args[0] == 'systemctl' for args in self.calls), 2)

    def test_never_overwrites_unowned_file_or_symlink(self):
        self.vhost.write_text('server { # another project\n }')
        with self.assertRaises(ValueError):
            self.activate()
        self.assertEqual(self.calls, [])
        self.vhost.unlink()
        other = self.root / 'other'
        other.write_bytes(self.placeholder)
        self.vhost.symlink_to(other)
        with self.assertRaises(ValueError):
            self.activate()
        self.assertEqual(other.read_bytes(), self.placeholder)

    def test_dns_parser_handles_cname_and_rejects_errors_or_extra_ips(self):
        self.assertEqual(activation.answer_addresses(dns_answer('A', [activation.TARGET_IP], True), 'A'),
                         {activation.TARGET_IP})
        self.assertEqual(activation.answer_addresses(dns_answer('AAAA', [], True), 'AAAA'), set())
        for output in (dns_answer('A', [], status='NXDOMAIN'),
                       dns_answer('A', [], status='SERVFAIL'),
                       dns_answer('A', ['invalid']),
                       dns_answer('AAAA', ['2001:db8::1'])):
            with self.subTest(output=output), self.assertRaises(ValueError):
                activation.answer_addresses(output, 'A')

    def test_resolver_disagreement_and_timeouts_wait_without_mutations(self):
        for scenario in ('disagreement', 'multiple', 'timeout'):
            self.calls.clear()
            def command(args, **kwargs):
                if scenario == 'timeout':
                    raise subprocess.TimeoutExpired(args, 8)
                if args[1] == '@8.8.8.8' and args[3] == 'A':
                    addresses = ['192.0.2.1']
                    if scenario == 'multiple':
                        addresses.append(activation.TARGET_IP)
                    return subprocess.CompletedProcess(args, 0, stdout=dns_answer('A', addresses))
                return self.command(args, **kwargs)
            with self.subTest(scenario=scenario):
                result = activation.activate(self.vhost, self.certificate, self.root / 'lock', command)
                self.assertEqual(result['status'], 'waiting_for_dns')
                self.assertEqual(self.vhost.read_bytes(), self.placeholder)
                self.assertTrue(all(args[0] == 'dig' for args in self.calls))


if __name__ == '__main__':
    unittest.main()
