#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""💻 SCRAPER: TECNOLOGIA"""

import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


CATEGORIA = "tecnologia"
TABELA_DB = "tecnologia"
OUTPUT_DIR = Path(f"{CATEGORIA}_data")
OUTPUT_DIR.mkdir(exist_ok=True)


class Normalizador:
    """Normaliza títulos de tecnologia"""
    
    @classmethod
    def normalizar(cls, titulo: str, metadata: dict = None) -> str:
        if not titulo:
            return "Sem título"
        
        import re
        
        # Remove lote
        limpo = re.sub(r'lote\s*\d+', '', titulo, flags=re.IGNORECASE)
        limpo = re.sub(r'\s+', ' ', limpo).strip()
        
        # Usa metadata
        if metadata:
            marca = metadata.get('marca', '')
            modelo = metadata.get('modelo', '')
            if marca and modelo:
                return f"{marca.title()} {modelo.title()}"[:100]
        
        return limpo[:100]


class SodreExtractor:
    API = "https://www.sodresantoro.com.br/api/search-lots"
    INDICES = ["materiais"]  # Sodré geralmente tem tech em "materiais"
    
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
        pag = 0
        
        while pag < 20:
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
            
            # Filtra apenas tecnologia
            tech_lotes = [l for l in lotes if self._is_tech(l)]
            items.extend(tech_lotes)
            
            print(f"  Pág {pag+1}: +{len(tech_lotes)} tech | Total: {len(items)}")
            
            pag += 1
            time.sleep(random.uniform(2, 4))
        
        return self._normalizar(items)
    
    def _is_tech(self, item):
        """Verifica se é tecnologia"""
        titulo = (item.get("lot_title") or "").lower()
        cat = (item.get("lot_category") or "").lower()
        
        keywords = ['notebook', 'computador', 'pc', 'monitor', 'impressora', 'tablet',
                   'celular', 'smartphone', 'iphone', 'samsung', 'dell', 'hp', 'lenovo']
        
        return any(k in titulo or k in cat for k in keywords)
    
    def _normalizar(self, items):
        resultado = []
        
        for item in items:
            lot_id = item.get("lot_id")
            if not lot_id:
                continue
            
            titulo = item.get("lot_title", "")
            value = item.get("bid_actual") or item.get("bid_initial")
            if value:
                value = float(value) / 100
            
            resultado.append({
                "source": "sodre",
                "external_id": f"sodre_tecnologia_{lot_id}",
                "title": titulo,
                "normalized_title": Normalizador.normalizar(titulo),
                "value": value,
                "link": f"https://leilao.sodresantoro.com.br/leilao/{item.get('auction_id')}/lote/{lot_id}/",
                "metadata": {}
            })
        
        return resultado


class MegaleiloesExtractor:
    BASE = "https://www.megaleiloes.com.br"
    
    def extrair(self):
        print("\n🟢 MEGALEILÕES")
        # Mega não tem categoria específica de tecnologia geralmente
        # Retorna vazio ou implementa busca genérica
        print("  ⚠️ Não implementado (categoria não encontrada)")
        return []


class SuperbidExtractor:
    API = "https://offer-query.superbid.net/seo/offers/"
    BASE = "https://exchange.superbid.net"
    
    def extrair(self):
        print("\n🔴 SUPERBID")
        
        items = []
        pag = 1
        
        while pag <= 20:
            params = {
                "urlSeo": f"{self.BASE}/categorias/tecnologia",
                "locale": "pt_BR",
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
            
            for offer in offers:
                if offer.get("store", {}).get("name"):
                    item = self._normalizar(offer)
                    if item:
                        items.append(item)
            
            print(f"  Pág {pag}: {len(offers)} | Total: {len(items)}")
            pag += 1
            time.sleep(random.uniform(2, 4))
        
        return items
    
    def _normalizar(self, offer):
        oid = offer.get("id")
        if not oid:
            return None
        
        titulo = offer.get("product", {}).get("shortDesc", "")
        
        return {
            "source": "superbid",
            "external_id": f"superbid_tecnologia_{oid}",
            "title": titulo,
            "normalized_title": Normalizador.normalizar(titulo),
            "value": offer.get("offerDetail", {}).get("currentMinBid"),
            "link": f"{self.BASE}/oferta/{oid}",
            "metadata": {}
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--fonte', choices=['sodre', 'megaleiloes', 'superbid', 'all'], default='all')
    args = parser.parse_args()
    
    print("="*60)
    print(f"💻 SCRAPER: {CATEGORIA.upper()}")
    print("="*60)
    
    extractors = {
        'sodre': SodreExtractor,
        'megaleiloes': MegaleiloesExtractor,
        'superbid': SuperbidExtractor
    }
    
    todos = []
    
    fontes = [args.fonte] if args.fonte != 'all' else list(extractors.keys())
    
    for fonte in fontes:
        try:
            ext = extractors[fonte]()
            items = ext.extrair()
            todos.extend(items)
            print(f"✅ {fonte}: {len(items)} itens")
        except Exception as e:
            print(f"❌ {fonte}: {e}")
    
    unicos = {i['external_id']: i for i in todos}
    todos = list(unicos.values())
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo = OUTPUT_DIR / f"{CATEGORIA}_{timestamp}.json"
    
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 Salvo: {arquivo}")
    print(f"📊 Total: {len(todos)} itens")
    
    try:
        from supabase_client import SupabaseClient
        client = SupabaseClient()
        result = client.upsert(TABELA_DB, todos)
        print(f"✅ Supabase: {result['inserted']} novos, {result['updated']} atualizados")
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")


if __name__ == "__main__":
    main()
