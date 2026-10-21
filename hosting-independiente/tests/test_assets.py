"""Comprueba assets de plantillas y salidas publicadas, incluidos modos del hero."""
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote, urlsplit
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'backend'))
from cms_content import initial_document, render_document, validate_document


class PublicAssets(unittest.TestCase):
    def test_rendered_image_and_video_modes_have_local_assets(self):
        site = BASE / 'sitio'
        doc = validate_document(initial_document(site))
        for mode in ('image', 'video'):
            doc['page']['hero_mode'] = mode
            rendered = render_document(doc, site, revision=1)
            for name in ('index.html', 'menu/index.html'):
                soup = BeautifulSoup(rendered[name], 'html.parser')
                for node in soup.find_all(True):
                    for attr in ('src', 'href', 'poster', 'data-src', 'data-mobile-src'):
                        value = node.get(attr)
                        if not isinstance(value, str):
                            continue
                        url = urlsplit(value)
                        if url.netloc and url.netloc != 'cisnenegro.mx':
                            continue
                        if url.path.startswith('/assets/'):
                            target = site / unquote(url.path.lstrip('/'))
                            self.assertTrue(target.is_file(), f'{mode}: {name}: {value}')
                        self.assertNotIn('cisnenegro.softvibes.art', value)


if __name__ == '__main__':
    unittest.main()
