import tempfile
import contextlib
import io
from figi_validation_claim_audit.audit import main
import unittest
from pathlib import Path
from figi_validation_claim_audit.audit import audit, claims, evidence
from figi_validation_claim_audit.phrases import FIGIVALIDATION, NOFIGIVALIDATION, GENERIC_NAMES


class AuditTests(unittest.TestCase):
    def test_phrases(self):
        self.assertEqual((len(set(FIGIVALIDATION)), len(set(NOFIGIVALIDATION)), len(set(GENERIC_NAMES))), (50, 24, 24))
        for phrase in FIGIVALIDATION:
            with self.subTest(phrase=phrase): self.assertEqual(claims(phrase), (True, False))
        for phrase in NOFIGIVALIDATION:
            with self.subTest(phrase=phrase): self.assertEqual(claims(phrase), (False, True))
        self.assertEqual(claims('```\nvalidate figi\n```'), (False, False))
        self.assertEqual(claims('~~~ text\nvalidate figi\n~~~'), (False, False))
        self.assertEqual(claims('`validate-figi`'), (True, False))
        self.assertEqual(claims("doesn't validate figi"), (False, True))
        self.assertEqual(claims('validate figiXYZ'), (False, False))

    def test_library_routes(self):
        for method in ('validate', 'is_valid'):
            for prefix, call in [('import stdnum.figi', 'stdnum.figi.' + method), ('import stdnum.figi as im', 'im.' + method), ('from stdnum import figi', 'figi.' + method), ('import stdnum', 'stdnum.figi.' + method), ('from stdnum.figi import ' + method, method), ('from stdnum.figi import ' + method + ' as v', 'v')]:
                with self.subTest(method=method, call=call): self.assertTrue(evidence(prefix + '\n' + call + '(x)'))

    def test_generic_routes(self):
        for name in GENERIC_NAMES:
            for source in ('obj.' + name + '(x)', 'from lib import ' + name + ' as f\nf(x)', 'obj = factory()\nobj.' + name + '(x)'):
                with self.subTest(source=source): self.assertTrue(evidence(source))

    def test_not_evidence(self):
        cases = ['import stdnum.figi', 'validate(x)', 'is_valid(x)', 'validate_figi(x)', 'obj.validate(x)', 'obj.figi(x)', 'import stdnum.figi\nstdnum.figi.compact(x)', 'import stdnum.figi\nstdnum.figi.calc_check_digit(x)', 'from stdnum import ean\nean.validate(x)', 'from stdnum import ean\nean.calc_check_digit(x)', 'from stdnum import luhn\nluhn.validate(x)', 'from stdnum import luhn\nluhn.calc_check_digit(x)', 'import re\nre.match(x,y)', 'import re\nre.search(x,y)', 'import re\nre.fullmatch(x,y)', 'len(x) == 12', 'issuer in known', 'validators.figi(x)', 'lookup.figi(x)', '"validate figi"', 'validate_figi', 'def broken(:', 'import subprocess\nsubprocess.run(["figi-check"])', 'import stdnum.figi as im\nim = x\nim.validate(x)', 'from stdnum.figi import validate\nwith x as validate:\n validate(x)', 'def validate_figi(x): pass\nobj.validate_figi(x)']
        cases += ['figi(x)', 'compact(x)', 'calc_check_digit(x)', 'obj.is_valid(x)', 'obj.compact(x)', 'obj.calc_check_digit(x)', 'import validators\nvalidators.figi(x)', 'import stdnum.figi as gr\nwith ctx() as gr:\n gr.validate(x)', 'from lib import validate_figi as v\nv = other\nv(x)', 'class C:\n def validate_figi(self): pass\nobj.validate_figi(x)', '# validate figi\nx = \"figi validation\"']
        cases += ['from stdnum import ' + n + '\n' + n + '.validate(x)' for n in ('isbn', 'issn', 'ismn', 'isan', 'isin')]
        for source in cases:
            with self.subTest(source=source): self.assertFalse(evidence(source))

    def test_findings(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'README.md').write_text('validate figi')
            self.assertEqual(audit(p)[0]['severity'], 'HIGH')
            (p/'tests').mkdir(); (p/'tests/test_a.py').write_text('obj.validate_figi(x)')
            self.assertEqual(audit(p)[0]['severity'], 'MEDIUM')
            (p/'a.py').write_text('obj.validate_figi(x)')
            self.assertEqual(audit(p), [])
            (p/'README.md').write_text('does not validate figi')
            self.assertEqual(audit(p)[0]['severity'], 'HIGH')
            (p/'a.py').unlink(); self.assertEqual(audit(p), [])
            (p/'README.md').write_text('validate figi')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit', str(p)]), 0)
                self.assertEqual(main(['audit', str(p), '--fail-on', 'medium']), 2)
                self.assertEqual(main(['audit', str(p), '--ignore', 'tests']), 2)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['audit', str(p/'missing')]), 1)

    def test_exclusions(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'README.md').write_text('validate figi')
            for folder in ('fixtures', 'docs', 'examples'):
                (p/folder).mkdir(); (p/folder/'a.py').write_text('obj.validate_figi(x)')
            (p/'link.py').symlink_to(p/'fixtures/a.py')
            self.assertEqual(audit(p)[0]['severity'], 'HIGH')
            (p/'src.py').write_text('obj.validate_figi(x)')
            self.assertEqual(audit(p, ['src.py'])[0]['severity'], 'HIGH')
