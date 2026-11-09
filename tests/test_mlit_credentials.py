"""Only dummy credentials are used; real private configuration is never read by tests."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from japan_housing_liquidity_lab import mlit_client as m

class CredentialTests(unittest.TestCase):
    def test_env_priority_and_invalid_value_is_not_echoed(self):
        with patch.dict(os.environ,{m.KEY_NAME:'DUMMY-PRIMARY','REINFOLIB_API_KEY':'DUMMY-LEGACY'}):
            self.assertEqual(m.load_credential(Path('not-used')),'DUMMY-PRIMARY')
        with patch.dict(os.environ,{m.KEY_NAME:'DUMMY\nSECRET'}):
            with self.assertRaisesRegex(ValueError,'Invalid API credential format') as x:m.load_credential()
            self.assertNotIn('DUMMY',str(x.exception))
    def test_private_file_is_ignored_untracked_and_never_exported(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{m.KEY_NAME:'','REINFOLIB_API_KEY':''}):
            root=Path(tmp);subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)
            file=root/'.env.mlit-local';file.write_text(m.KEY_NAME+'="DUMMY-LOCAL"\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Git-ignored'):m.load_credential(file)
            (root/'.gitignore').write_text('.env.mlit-local\n',encoding='utf-8')
            self.assertEqual(m.load_credential(file),'DUMMY-LOCAL');self.assertEqual(os.environ[m.KEY_NAME],'')
            file.write_text((m.KEY_NAME+'=DUMMY\n')*2,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'exactly one'):m.load_credential(file)
            subprocess.run(['git','add','-f','.env.mlit-local'],cwd=root,check=True,capture_output=True)
            with self.assertRaisesRegex(ValueError,'untracked'):m.load_credential(file)
    def test_classifications_scopes_and_no_credential_persistence(self):
        class C:
            origin=m.ORIGIN
            def __init__(self):self.calls=[]
            def get(self,path,headers,conditional):
                self.calls.append(path)
                return 200,json.dumps(dict(status='OK',data=[dict(Type='中古マンション等',TradePrice='60000000',Area='70',Period='2023年第1四半期',MunicipalityCode='13101')])),'application/json'
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{m.KEY_NAME:'DUMMY-HTTP-KEY'}):
            c=C();root=Path(tmp)
            for classification in ['01','02']:m.fetch_quarter(c,'2023Q1',root,classification=classification,city='13101')
            self.assertEqual(len(c.calls),2)
            m.fetch_quarter(c,'2023Q1',root,classification='02',city='13101');self.assertEqual(len(c.calls),2)
            self.assertEqual(len(list(root.glob('*-manifest.json'))),2)
            self.assertNotIn('DUMMY-HTTP-KEY',''.join(p.read_text(encoding='utf-8') for p in root.iterdir()))
            c.get=lambda *a,**k:(200,'DUMMY-HTTP-KEY','application/json')
            with self.assertRaisesRegex(ValueError,'persistence refused'):m.fetch_quarter(c,'2023Q2',root)
            self.assertFalse((root/'2023Q2.json').exists())
    def test_cached_manifest_reads_utf8_with_non_utf8_locale(self):
        import hashlib
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'2023Q1.json'
            m.save(data,dict(note='日本語の取引データ'))
            manifest=dict(source=m.ORIGIN+'/ex-api/external/XIT001?year=2023&quarter=1&area=13&priceClassification=01&language=ja',
                          sha256=hashlib.sha256(data.read_bytes()).hexdigest(),note='日本語の取得記録')
            m.save(root/'2023Q1-manifest.json',manifest)
            # Simulate a locale that cannot decode Japanese if encoding is omitted.
            with patch('pathlib.io.text_encoding',side_effect=lambda encoding,stacklevel=2: encoding or 'ascii'):
                self.assertEqual(m.fetch_quarter(SimpleNamespace(origin=m.ORIGIN),'2023Q1',root),manifest)

    def test_invalid_scope_fails_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=object()
            for kwargs in [dict(classification='03'),dict(classification='02',city='99999')]:
                with self.assertRaises(ValueError):m.fetch_quarter(c,'2023Q1',tmp,**kwargs)
            with self.assertRaises(ValueError):m.fetch_quarter(c,'2020Q1',tmp,classification='02')

if __name__=='__main__':unittest.main()
