#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🚗 SCRAPER: VEÍCULOS"""

import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURAÇÕES
# ============================================================

CATEGORIA = "veiculos"
TABELA_DB = "veiculos"
OUTPUT_DIR = Path(f"{CATEGORIA}_data")
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# NORMALIZADOR
# ============================================================

class Normalizador:
    """Normaliza títulos de veículos"""
    
    MARCAS = {
        'AUDI', 'BMW', 'CHEVROLET', 'CHERY', 'CITROEN', 'DODGE', 'FIAT', 
        'FORD', 'HONDA', 'HYUNDAI', 'JAC', 'JEEP', 'KIA', 'LAND ROVER',
        'MERCEDES', 'MITSUBISHI', 'NISSAN', 'PEUGEOT', 'RENAULT', 
        'SUZUKI', 'TOYOTA', 'VOLKSWAGEN', 'VW', 'VOLVO'
    }
    
    @classmethod
    def normalizar(cls, titulo: str, metadata: dict = None) -> str:
        """Normaliza título de veículo"""
        if not titulo:
            return "Veículo sem título"
        
        import re
        
        # Remove lixo
        limpo = re.sub(r'(lote\s*\d+|placa\s*[a-z]{3}\d[a-z0-9]\d{2}|km\s*\d+)', '', titulo, flags=re.IGNORECASE)
        limpo = re.sub(r'\s+', ' ', limpo).strip()
        
        # Usa metadata se tiver
        if metadata:
            marca = metadata.get('marca') or metadata.get('brand', '')
            modelo = metadata.get('modelo') or metadata.get('model', '')
            ano = metadata.get('ano_modelo') or metadata.get('year', '')
            
            if marca and modelo:
                result = f"{marca.title()} {modelo.title()}"
                if ano:
                    result += f" {ano}"
                return result[:100]
        
        # Tenta extrair automaticamente
        words = limpo.upper().split()
        marca = None
        modelo = []
        
        for i, word in enumerate(words):
            if word in cls.MARCAS:
                marca = word
                modelo = words[i+1:i+4]
                break
        
        if marca:
            modelo_str = ' '.join(modelo).title()
            return f"{marca.title()} {modelo_str}".strip()[:100]
        
        return limpo[:100]


# ============================================================
# EXTRACTORS
# ============================================================

class SodreExtractor:
    """Extrai veículos do Sodré"""
    
    API = "https://www.sodresantoro.com.br/api/search-lots"
    INDICES = ["veiculos", "judiciais-veiculos"]
    
    def extrair(self):
        print("\n🔵 SODRÉ")
        
        # Cookies
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.sodresantoro.com.br", timeout=30000)
            time.sleep(2)
            cookies = {c["name"]: c["value"] for c in page.context.cookies()}
            browser.close()
        
        items = []
        pag = 0
        
        while pag < 50:  # Max 50 páginas
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
            
            items.extend(lotes)
            print(f"  Pág {pag+1}: +{len(lotes)} | Total: {len(items)}")
            
            pag += 1
            time.sleep(random.uniform(2, 4))
        
        return self._normalizar(items)
    
    def _normalizar(self, items):
        resultado = []
        
        for item in items:
            lot_id = item.get("lot_id") or item.get("id")
            if not lot_id:
                continue
            
            auction_id = item.get("auction_id")
            
            metadata = {
                "marca": item.get("lot_brand"),
                "modelo": item.get("lot_model"),
                "ano_fabricacao": item.get("lot_year_manufacture"),
                "ano_modelo": item.get("lot_year_model"),
                "placa": item.get("lot_plate"),
                "km": item.get("lot_km", 0),
                "cor": item.get("lot_color"),
            }
            
            titulo = item.get("lot_title") or f"{metadata.get('marca', '')} {metadata.get('modelo', '')}".strip()
            
            value = item.get("bid_actual") or item.get("bid_initial")
            if value:
                value = float(value) / 100
            
            location = item.get("lot_location", "")
            city, state = None, None
            if "/" in location:
                parts = location.split("/")
                city = parts[0].strip()
                state = parts[1].strip() if len(parts) > 1 else None
            
            resultado.append({
                "source": "sodre",
                "external_id": f"sodre_veiculos_{lot_id}",
                "title": titulo,
                "normalized_title": Normalizador.normalizar(titulo, metadata),
                "value": value,
                "value_text": f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if value else None,
                "city": city,
                "state": state if state and len(state) == 2 else None,
                "description": item.get("lot_description"),
                "link": f"https://leilao.sodresantoro.com.br/leilao/{auction_id}/lote/{lot_id}/",
                "metadata": metadata
            })
        
        return resultado


class MegaleiloesExtractor:
    """Extrai veículos do Megaleilões"""
    
    BASE = "https://www.megaleiloes.com.br"
    
    def extrair(self):
        print("\n🟢 MEGALEILÕES")
        
        items = []
        ids = set()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for pag in range(1, 31):  # Max 30 páginas
                url = f"{self.BASE}/veiculos" + (f"?pagina={pag}" if pag > 1 else "")
                
                page.goto(url, timeout=60000)
                time.sleep(random.uniform(3, 5))
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                cards = soup.select('div.card, a[href*="/leilao/"]')
                
                if not cards:
                    break
                
                novos = 0
                for card in cards:
                    item = self._extrair_card(card)
                    if item and item['external_id'] not in ids:
                        items.append(item)
                        ids.add(item['external_id'])
                        novos += 1
                
                print(f"  Pág {pag}: +{novos} | Total: {len(items)}")
                
                if novos == 0:
                    break
                
                time.sleep(random.uniform(3, 5))
            
            browser.close()
        
        return items
    
    def _extrair_card(self, card):
        import re
        
        link = card.get('href') if card.name == 'a' else (card.select_one('a[href]') or {}).get('href', '')
        if not link or link == '#':
            return None
        
        if not link.startswith('http'):
            link = self.BASE + link
        
        texto = card.get_text(separator=' ', strip=True)
        
        titulo = "Sem título"
        for sel in ['h2', 'h3', 'h4', 'strong']:
            elem = card.select_one(sel)
            if elem:
                t = elem.get_text(strip=True)
                if 10 < len(t) < 200:
                    titulo = t
                    break
        
        value = None
        match = re.search(r'R\$\s*([\d.]+,\d{2})', texto)
        if match:
            try:
                value = float(match.group(1).replace('.', '').replace(',', '.'))
            except:
                pass
        
        state = None
        sm = re.search(r'\b([A-Z]{2})\b', texto)
        if sm:
            state = sm.group(1)
        
        return {
            "source": "megaleiloes",
            "external_id": f"megaleiloes_veiculos_{abs(hash(link)) % 10000000}",
            "title": titulo,
            "normalized_title": Normalizador.normalizar(titulo),
            "value": value,
            "state": state,
            "link": link,
            "metadata": {}
        }


class SuperbidExtractor:
    """Extrai veículos do Superbid"""
    
    API = "https://offer-query.superbid.net/seo/offers/"
    BASE = "https://exchange.superbid.net"
    CATS = ["carros-motos", "caminhoes-onibus"]
    
    def extrair(self):
        print("\n🔴 SUPERBID")
        
        items = []
        
        for cat in self.CATS:
            pag = 1
            
            while pag <= 30:  # Max 30 páginas por categoria
                params = {
                    "urlSeo": f"{self.BASE}/categorias/{cat}",
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
                    if self._valido(offer):
                        item = self._normalizar(offer)
                        if item:
                            items.append(item)
                
                print(f"  {cat} pág {pag}: {len(offers)} | Total: {len(items)}")
                
                pag += 1
                time.sleep(random.uniform(2, 4))
        
        return items
    
    def _valido(self, offer):
        store = offer.get("store", {}).get("name")
        seller = (offer.get("seller", {}).get("name") or "").lower()
        
        if not store or "demo" in seller:
            return False
        return True
    
    def _normalizar(self, offer):
        oid = offer.get("id")
        if not oid:
            return None
        
        titulo = offer.get("product", {}).get("shortDesc", "Sem título")
        
        city_text = offer.get("seller", {}).get("city", "")
        city, state = None, None
        if "/" in city_text:
            parts = city_text.split("/")
            city = parts[0].strip()
            state = parts[1].strip() if len(parts) > 1 else None
        
        return {
            "source": "superbid",
            "external_id": f"superbid_veiculos_{oid}",
            "title": titulo,
            "normalized_title": Normalizador.normalizar(titulo),
            "value": offer.get("offerDetail", {}).get("currentMinBid"),
            "city": city,
            "state": state if state and len(state) == 2 else None,
            "link": f"{self.BASE}/oferta/{oid}",
            "store_name": offer.get("store", {}).get("name"),
            "metadata": {}
        }


# ============================================================
# MAIN
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--fonte', choices=['sodre', 'megaleiloes', 'superbid', 'all'], default='all')
    args = parser.parse_args()
    
    print("="*60)
    print(f"🚗 SCRAPER: {CATEGORIA.upper()}")
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
    
    # Remove duplicatas
    unicos = {i['external_id']: i for i in todos}
    todos = list(unicos.values())
    
    # Salva JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo = OUTPUT_DIR / f"{CATEGORIA}_{timestamp}.json"
    
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 Salvo: {arquivo}")
    print(f"📊 Total: {len(todos)} itens")
    
    # Upload Supabase
    try:
        from supabase_client import SupabaseClient
        
        client = SupabaseClient()
        result = client.upsert(TABELA_DB, todos)
        print(f"✅ Supabase: {result['inserted']} novos, {result['updated']} atualizados")
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")


if __name__ == "__main__":
    main()
