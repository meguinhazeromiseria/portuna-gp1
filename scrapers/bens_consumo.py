# ============================================================
# bens_consumo.py
# ============================================================

#!/usr/bin/env python3
"""🛍️ SCRAPER: BENS DE CONSUMO"""

import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

CATEGORIA = "bens_consumo"
TABELA_DB = "bens_consumo"
OUTPUT_DIR = Path(f"{CATEGORIA}_data")
OUTPUT_DIR.mkdir(exist_ok=True)


class Normalizador:
    @classmethod
    def normalizar(cls, titulo: str, metadata: dict = None) -> str:
        if not titulo:
            return "Sem título"
        import re
        limpo = re.sub(r'lote\s*\d+', '', titulo, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', limpo).strip()[:100]


class SodreExtractor:
    API = "https://www.sodresantoro.com.br/api/search-lots"
    INDICES = ["materiais"]
    
    def extrair(self):
        print("\n🔵 SODRÉ")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.sodresantoro.com.br", timeout=30000)
            time.sleep(2)
            cookies = {c["name"]: c["value"] for c in page.context.cookies()}
            browser.close()
        
        items = []
        for pag in range(15):
            payload = {
                "indices": self.INDICES,
                "query": {"bool": {"filter": [{"terms": {"lot_status_id": [1, 2, 3]}}]}},
                "from": pag * 100,
                "size": 100
            }
            
            r = requests.post(self.API, json=payload, cookies=cookies, timeout=60)
            if r.status_code != 200:
                break
            
            lotes = r.json().get("results", [])
            if not lotes:
                break
            
            # Filtra bens de consumo (roupas, calçados, acessórios, etc)
            bens = [l for l in lotes if self._is_bem_consumo(l)]
            items.extend(bens)
            
            print(f"  Pág {pag+1}: +{len(bens)} | Total: {len(items)}")
            time.sleep(random.uniform(2, 4))
        
        return self._normalizar(items)
    
    def _is_bem_consumo(self, item):
        titulo = (item.get("lot_title") or "").lower()
        keywords = ['roupa', 'calcado', 'tenis', 'sapato', 'bolsa', 'relogio', 'joia', 'acessorio']
        return any(k in titulo for k in keywords)
    
    def _normalizar(self, items):
        return [{
            "source": "sodre",
            "external_id": f"sodre_bens_{i.get('lot_id')}",
            "title": i.get("lot_title", ""),
            "normalized_title": Normalizador.normalizar(i.get("lot_title")),
            "value": float(i.get("bid_actual") or i.get("bid_initial") or 0) / 100,
            "link": f"https://leilao.sodresantoro.com.br/leilao/{i.get('auction_id')}/lote/{i.get('lot_id')}/",
            "metadata": {}
        } for i in items if i.get("lot_id")]


class MegaleiloesExtractor:
    def extrair(self):
        print("\n🟢 MEGALEILÕES")
        print("  ⚠️ Não implementado")
        return []


class SuperbidExtractor:
    API = "https://offer-query.superbid.net/seo/offers/"
    BASE = "https://exchange.superbid.net"
    
    def extrair(self):
        print("\n🔴 SUPERBID")
        
        items = []
        for pag in range(1, 15):
            params = {
                "urlSeo": f"{self.BASE}/categorias/bolsas-canetas-joias-e-relogios",
                "pageNumber": pag,
                "pageSize": 100,
                "searchType": "openedAll"
            }
            
            r = requests.get(self.API, params=params, timeout=60)
            if r.status_code != 200:
                break
            
            offers = r.json().get("offers", [])
            if not offers:
                break
            
            for o in offers:
                if o.get("store", {}).get("name"):
                    items.append({
                        "source": "superbid",
                        "external_id": f"superbid_bens_{o.get('id')}",
                        "title": o.get("product", {}).get("shortDesc", ""),
                        "normalized_title": Normalizador.normalizar(o.get("product", {}).get("shortDesc")),
                        "value": o.get("offerDetail", {}).get("currentMinBid"),
                        "link": f"{self.BASE}/oferta/{o.get('id')}",
                        "metadata": {}
                    })
            
            print(f"  Pág {pag}: {len(offers)} | Total: {len(items)}")
            time.sleep(random.uniform(2, 4))
        
        return items


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fonte', choices=['sodre', 'megaleiloes', 'superbid', 'all'], default='all')
    args = parser.parse_args()
    
    print("="*60)
    print(f"🛍️ SCRAPER: {CATEGORIA.upper()}")
    print("="*60)
    
    extractors = {'sodre': SodreExtractor, 'megaleiloes': MegaleiloesExtractor, 'superbid': SuperbidExtractor}
    todos = []
    
    for fonte in ([args.fonte] if args.fonte != 'all' else list(extractors.keys())):
        try:
            items = extractors[fonte]().extrair()
            todos.extend(items)
            print(f"✅ {fonte}: {len(items)}")
        except Exception as e:
            print(f"❌ {fonte}: {e}")
    
    unicos = {i['external_id']: i for i in todos}
    todos = list(unicos.values())
    
    arquivo = OUTPUT_DIR / f"{CATEGORIA}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 {arquivo}")
    print(f"📊 Total: {len(todos)}")
    
    try:
        from supabase_client import SupabaseClient
        result = SupabaseClient().upsert(TABELA_DB, todos)
        print(f"✅ Supabase: {result['inserted']} novos")
    except Exception as e:
        print(f"❌ {e}")


if __name__ == "__main__":
    main()