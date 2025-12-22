#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🚗 SCRAPER: VEÍCULOS - VERSÃO DEFINITIVA COM COOKIES PERSISTENTES"""

import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

CATEGORIA = "veiculos"
OUTPUT_DIR = Path(f"{CATEGORIA}_data")
OUTPUT_DIR.mkdir(exist_ok=True)

# 🍪 Cookies globais (capturados uma vez e reutilizados)
GLOBAL_SESSION = None


class CookieManager:
    """🍪 Gerenciador de cookies compartilhados entre todas as fontes"""
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    @classmethod
    def criar_session_global(cls):
        """Cria session com cookies capturados do Playwright"""
        global GLOBAL_SESSION
        
        if GLOBAL_SESSION is not None:
            return GLOBAL_SESSION
        
        print("\n🍪 CAPTURANDO COOKIES COM PLAYWRIGHT...")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-web-security',
                    ]
                )
                
                user_agent = random.choice(cls.USER_AGENTS)
                
                context = browser.new_context(
                    user_agent=user_agent,
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo',
                    color_scheme='light',
                )
                
                # Script anti-detecção
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']});
                    window.chrome = {runtime: {}};
                """)
                
                page = context.new_page()
                
                # Visita múltiplos sites para coletar cookies
                sites = [
                    "https://www.sodresantoro.com.br",
                    "https://www.megaleiloes.com.br",
                    "https://exchange.superbid.net",
                ]
                
                all_cookies = {}
                
                for site in sites:
                    try:
                        print(f"  🌐 Visitando {site}...")
                        page.goto(site, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(random.uniform(2, 4))
                        
                        cookies = context.cookies()
                        for cookie in cookies:
                            all_cookies[cookie['name']] = cookie['value']
                    except Exception as e:
                        print(f"  ⚠️ Erro em {site}: {e}")
                
                browser.close()
                
                print(f"  ✅ {len(all_cookies)} cookies capturados")
                
                # Cria session com os cookies
                session = requests.Session()
                session.cookies.update(all_cookies)
                
                # Headers padrão para todas as requisições
                session.headers.update({
                    "User-Agent": user_agent,
                    "Accept": "*/*",
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Cache-Control": "max-age=0",
                })
                
                GLOBAL_SESSION = session
                return session
                
        except Exception as e:
            print(f"  ❌ Erro ao capturar cookies: {e}")
            print("  ⚠️ Criando session sem cookies...")
            
            # Fallback: session básica
            session = requests.Session()
            session.headers.update({
                "User-Agent": random.choice(cls.USER_AGENTS),
                "Accept": "*/*",
                "Accept-Language": "pt-BR,pt;q=0.9",
            })
            
            GLOBAL_SESSION = session
            return session


class Normalizador:
    """Normaliza títulos de veículos"""
    
    MARCAS = {
        'AUDI', 'BMW', 'CHEVROLET', 'CHERY', 'CITROEN', 'DODGE', 'FIAT', 
        'FORD', 'HONDA', 'HYUNDAI', 'JAC', 'JEEP', 'KIA', 'LAND ROVER',
        'MERCEDES', 'MITSUBISHI', 'NISSAN', 'PEUGEOT', 'RENAULT', 
        'SUZUKI', 'TOYOTA', 'VOLKSWAGEN', 'VW', 'VOLVO', 'YAMAHA',
        'SCANIA', 'VOLKS', 'MERCEDES-BENZ'
    }
    
    @classmethod
    def normalizar(cls, titulo: str, metadata: dict = None) -> str:
        if not titulo:
            return "Veículo sem título"
        
        import re
        limpo = re.sub(r'(lote\s*\d+|placa\s*[a-z]{3}\d[a-z0-9]\d{2}|km\s*\d+)', '', titulo, flags=re.IGNORECASE)
        limpo = re.sub(r'\s+', ' ', limpo).strip()
        
        if metadata:
            marca = metadata.get('marca') or metadata.get('brand', '')
            modelo = metadata.get('modelo') or metadata.get('model', '')
            ano = metadata.get('ano_modelo') or metadata.get('year', '')
            
            if marca and modelo:
                result = f"{marca.title()} {modelo.title()}"
                if ano:
                    result += f" {ano}"
                return result[:100]
        
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


class SodreExtractor:
    """🔵 SODRÉ - USA COOKIES GLOBAIS"""
    
    API = "https://www.sodresantoro.com.br/api/search-lots"
    INDICES = ["veiculos", "judiciais-veiculos"]
    ACTIVE_STATUS = [1, 2, 3]
    
    def extrair(self):
        print("\n🔵 SODRÉ")
        
        session = GLOBAL_SESSION
        if not session:
            print("  ❌ Session global não inicializada")
            return []
        
        items = []
        page_num = 0
        max_pages = 50
        
        while page_num < max_pages:
            payload = {
                "indices": self.INDICES,
                "query": {"bool": {"filter": [{"terms": {"lot_status_id": self.ACTIVE_STATUS}}]}},
                "from": page_num * 100,
                "size": 100,
                "sort": [
                    {"lot_status_id_order": {"order": "asc"}},
                    {"auction_date_init": {"order": "asc"}}
                ]
            }
            
            try:
                headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "origin": "https://www.sodresantoro.com.br",
                    "referer": "https://www.sodresantoro.com.br/veiculos/lotes",
                }
                
                r = session.post(self.API, json=payload, headers=headers, timeout=45)
                
                if r.status_code == 200:
                    data = r.json()
                    lotes = data.get("results", [])
                    total = data.get("total", 0)
                    
                    if not lotes:
                        break
                    
                    items.extend(lotes)
                    print(f"  Pág {page_num+1}: +{len(lotes)} | Total: {len(items)}/{total}")
                    
                    if len(items) >= total:
                        break
                elif r.status_code == 403:
                    print(f"  ⚠️ Status 403 - proteção anti-bot detectou")
                    break
                else:
                    print(f"  ⚠️ Status {r.status_code}")
                    break
                    
            except Exception as e:
                print(f"  ❌ Erro: {e}")
                break
            
            page_num += 1
            time.sleep(random.uniform(3, 6))
        
        return self._normalizar(items)
    
    def _normalizar(self, items):
        resultado = []
        
        for item in items:
            if item.get("lot_status_id") not in self.ACTIVE_STATUS:
                continue
            
            lot_id = item.get("lot_id")
            if not lot_id:
                continue
            
            value_raw = item.get("bid_actual") or item.get("bid_initial")
            value = float(value_raw) / 100 if value_raw else None
            
            location = item.get("lot_location", "") or ""
            city, state = None, None
            if "/" in location:
                parts = location.split("/")
                city = parts[0].strip()
                state = parts[1].strip() if len(parts) > 1 else None
            
            metadata = {
                "marca": item.get("lot_brand"),
                "modelo": item.get("lot_model"),
                "ano_modelo": item.get("lot_year_model"),
            }
            
            titulo = item.get("lot_title") or "Sem título"
            
            resultado.append({
                "source": "sodre",
                "external_id": f"sodre_{lot_id}",
                "title": titulo,
                "normalized_title": Normalizador.normalizar(titulo, metadata),
                "value": value,
                "city": city,
                "state": state,
                "link": f"https://leilao.sodresantoro.com.br/leilao/{item.get('auction_id')}/lote/{lot_id}/",
                "metadata": metadata
            })
        
        return resultado


class MegaleiloesExtractor:
    """🟢 MEGALEILÕES - USA COOKIES GLOBAIS"""
    
    BASE = "https://www.megaleiloes.com.br"
    
    def extrair(self):
        print("\n🟢 MEGALEILÕES")
        
        session = GLOBAL_SESSION
        if not session:
            print("  ❌ Session global não inicializada")
            return []
        
        items = []
        ids = set()
        
        for pag in range(1, 10):
            url = f"{self.BASE}/veiculos" + (f"?pagina={pag}" if pag > 1 else "")
            
            try:
                headers = {
                    "referer": self.BASE,
                    "origin": self.BASE,
                }
                
                r = session.get(url, headers=headers, timeout=30)
                
                if r.status_code != 200:
                    print(f"  ⚠️ Status {r.status_code}")
                    break
                
                soup = BeautifulSoup(r.content, 'html.parser')
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
                
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"  ⚠️ Erro pág {pag}: {e}")
                break
        
        return items
    
    def _extrair_card(self, card):
        import re
        
        link = card.get('href') if card.name == 'a' else None
        if not link:
            link_elem = card.select_one('a[href]')
            link = link_elem.get('href') if link_elem else None
        
        if not link or 'javascript' in link:
            return None
        
        if not link.startswith('http'):
            link = self.BASE + link
        
        part_id = link.rstrip('/').split('/')[-1].split('?')[0]
        if not part_id:
            part_id = str(abs(hash(link)) % 10000000)
        
        texto = card.get_text(separator=' ', strip=True)
        
        titulo = "Sem título"
        for sel in ['h2', 'h3', 'strong']:
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
        
        return {
            "source": "megaleiloes",
            "external_id": f"megaleiloes_{part_id}",
            "title": titulo,
            "normalized_title": Normalizador.normalizar(titulo),
            "value": value,
            "link": link,
            "metadata": {}
        }


class SuperbidExtractor:
    """🔴 SUPERBID - USA COOKIES GLOBAIS"""
    
    API = "https://offer-query.superbid.net/seo/offers/"
    BASE = "https://exchange.superbid.net"
    CATS = ["carros-motos", "caminhoes-onibus"]
    
    def __init__(self):
        self.filtered_stats = {
            'demo_seller': 0,
            'demo_auctioneer': 0,
            'deploy_text': 0,
            'no_store': 0
        }
    
    def is_test_offer(self, offer: dict) -> tuple:
        """Verifica se a oferta é de teste/demo"""
        seller = offer.get("seller", {})
        auction = offer.get("auction", {})
        product = offer.get("product", {})
        store = offer.get("store", {})
        
        store_name = store.get("name")
        if not store_name:
            return True, "no_store"
        
        seller_name = seller.get("name") or ""
        seller_name = seller_name.lower() if seller_name else ""
        if "vendedor demo" in seller_name or "demo" in seller_name:
            return True, "demo_seller"
        
        auctioneer = auction.get("auctioneer") or ""
        auctioneer = auctioneer.lower() if auctioneer else ""
        if "demo" in auctioneer or "corretor demo" in auctioneer or "leiloeiro demo" in auctioneer:
            return True, "demo_auctioneer"
        
        title = product.get("shortDesc") or ""
        title = title.lower() if title else ""
        
        description = offer.get("offerDescription", {}).get("offerDescription") or ""
        description = description.lower() if description else ""
        
        if "deploy" in title or "deploy" in description:
            return True, "deploy_text"
        
        return False, ""
    
    def extrair(self):
        print("\n🔴 SUPERBID")
        
        session = GLOBAL_SESSION
        if not session:
            print("  ❌ Session global não inicializada")
            return []
        
        items = []
        
        for cat in self.CATS:
            print(f"  📦 {cat}")
            page = 1
            consecutive_errors = 0
            local_filtered = {'demo_seller': 0, 'demo_auctioneer': 0, 'deploy_text': 0, 'no_store': 0}
            
            while page <= 20 and consecutive_errors < 5:
                try:
                    params = {
                        "urlSeo": f"{self.BASE}/categorias/{cat}",
                        "locale": "pt_BR",
                        "orderBy": "offerDetail.percentDiffReservedPriceOverFipePrice:asc",
                        "pageNumber": page,
                        "pageSize": 100,
                        "portalId": "[2,15]",
                        "preOrderBy": "orderByFirstOpenedOffersAndSecondHasPhoto",
                        "requestOrigin": "marketplace",
                        "searchType": "openedAll",
                        "timeZoneId": "America/Sao_Paulo",
                    }
                    
                    headers = {
                        "accept": "*/*",
                        "accept-language": "pt-BR,pt;q=0.9",
                        "origin": self.BASE,
                        "referer": f"{self.BASE}/",
                    }
                    
                    r = session.get(
                        self.API, 
                        params=params, 
                        headers=headers,
                        timeout=45
                    )
                    
                    if r.status_code == 404:
                        print(f"    ✅ Fim: página {page} retornou 404")
                        break
                    
                    if r.status_code == 500:
                        consecutive_errors += 1
                        wait = 20 * consecutive_errors
                        print(f"    ⚠️ 500 Error (tentativa {consecutive_errors}/5), aguardando {wait}s...")
                        time.sleep(wait)
                        continue
                    
                    if r.status_code != 200:
                        print(f"    ⚠️ Status {r.status_code}")
                        consecutive_errors += 1
                        if consecutive_errors >= 5:
                            break
                        time.sleep(10)
                        continue
                    
                    try:
                        offers = r.json().get("offers", [])
                    except json.JSONDecodeError:
                        print(f"    ⚠️ Erro JSON na página {page}")
                        consecutive_errors += 1
                        continue
                    
                    if not offers or len(offers) == 0:
                        print(f"    ✅ Fim: página {page} vazia")
                        break
                    
                    valid = []
                    for offer in offers:
                        is_test, reason = self.is_test_offer(offer)
                        if is_test:
                            local_filtered[reason] += 1
                            self.filtered_stats[reason] += 1
                            continue
                        valid.append(offer)
                    
                    items.extend(valid)
                    print(f"    Pág {page}: +{len(valid)} válidos | Total: {len(items)}")
                    
                    if len(offers) < 10:
                        print(f"    ✅ Fim: Última página com {len(offers)} ofertas")
                        break
                    
                    page += 1
                    consecutive_errors = 0
                    time.sleep(random.uniform(2, 5))
                    
                except requests.exceptions.Timeout:
                    print(f"    ⚠️ Timeout na página {page}")
                    consecutive_errors += 1
                    time.sleep(10)
                except Exception as e:
                    print(f"    ⚠️ Erro: {e}")
                    consecutive_errors += 1
                    time.sleep(10)
            
            total_filtered_cat = sum(local_filtered.values())
            if total_filtered_cat > 0:
                print(f"    🚫 Filtrados {total_filtered_cat} itens de teste/demo:")
                if local_filtered['no_store'] > 0:
                    print(f"       • Sem loja: {local_filtered['no_store']}")
                if local_filtered['demo_seller'] > 0:
                    print(f"       • Vendedor Demo: {local_filtered['demo_seller']}")
                if local_filtered['demo_auctioneer'] > 0:
                    print(f"       • Leiloeiro Demo: {local_filtered['demo_auctioneer']}")
                if local_filtered['deploy_text'] > 0:
                    print(f"       • Texto 'deploy': {local_filtered['deploy_text']}")
            
            if cat != self.CATS[-1]:
                time.sleep(random.uniform(10, 20))
        
        total_filtered = sum(self.filtered_stats.values())
        if total_filtered > 0:
            print(f"\n  🚫 TOTAL FILTRADO: {total_filtered} ofertas de teste/demo")
            print(f"     • Sem loja (store_name NULL): {self.filtered_stats['no_store']}")
            print(f"     • Vendedor Demo: {self.filtered_stats['demo_seller']}")
            print(f"     • Leiloeiro Demo: {self.filtered_stats['demo_auctioneer']}")
            print(f"     • Texto 'deploy': {self.filtered_stats['deploy_text']}")
        
        return self._normalizar(items)
    
    def _normalizar(self, offers):
        resultado = []
        
        for offer in offers:
            oid = offer.get("id")
            if not oid:
                continue
            
            titulo = offer.get("product", {}).get("shortDesc", "Sem título")
            
            resultado.append({
                "source": "superbid",
                "external_id": f"superbid_{oid}",
                "title": titulo,
                "normalized_title": Normalizador.normalizar(titulo),
                "value": offer.get("offerDetail", {}).get("currentMinBid"),
                "link": f"{self.BASE}/oferta/{oid}",
                "metadata": {}
            })
        
        return resultado


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--fonte', choices=['sodre', 'megaleiloes', 'superbid', 'all'], default='all')
    args = parser.parse_args()
    
    print("="*60)
    print(f"🚗 SCRAPER: {CATEGORIA.upper()} - VERSÃO DEFINITIVA")
    print("="*60)
    
    # 🍪 Cria session global com cookies
    CookieManager.criar_session_global()
    
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
            print(f"✅ {fonte}: {len(items)} itens\n")
        except Exception as e:
            print(f"❌ {fonte}: {e}\n")
    
    unicos = {i['external_id']: i for i in todos}
    todos = list(unicos.values())
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo = OUTPUT_DIR / f"{CATEGORIA}_{timestamp}.json"
    
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"💾 Salvo: {arquivo}")
    print(f"📊 Total: {len(todos)} itens únicos")
    
    # 🔥 CORREÇÃO DEFINITIVA DO SUPABASE
    try:
        from supabase_client import SupabaseClient
        
        print("\n📤 Enviando para Supabase...")
        client = SupabaseClient()
        
        # Verifica qual método está disponível
        if hasattr(client, 'upsert_normalized'):
            # Versão otimizada (nova)
            print("  ℹ️ Usando método: upsert_normalized()")
            result = client.upsert_normalized(todos)
            print(f"  ✅ {result['inserted']} novos, {result['updated']} atualizados, {result['errors']} erros")
            
        elif hasattr(client, 'upsert'):
            # Versão com tabelas separadas (antiga)
            print("  ℹ️ Usando método: upsert('veiculos', items)")
            result = client.upsert('veiculos', todos)
            print(f"  ✅ {result['inserted']} novos, {result['updated']} atualizados, {result['errors']} erros")
            
        elif hasattr(client, 'insert_normalized'):
            # Fallback para método antigo
            print("  ℹ️ Usando método: insert_normalized()")
            inserted = client.insert_normalized(todos)
            print(f"  ✅ {inserted} itens processados")
            
        else:
            print("  ⚠️ Nenhum método de upsert encontrado no SupabaseClient")
            print("  📋 Métodos disponíveis:", [m for m in dir(client) if not m.startswith('_')])
            
    except ImportError:
        print("\n⚠️ supabase_client.py não encontrado")
        print("  ℹ️ Os dados foram salvos localmente em:", arquivo)
        
    except Exception as e:
        print(f"\n❌ Erro Supabase: {e}")
        print("  ℹ️ Os dados foram salvos localmente em:", arquivo)
        
        # Debug: mostra informações do erro
        import traceback
        print("\n🔍 Detalhes do erro:")
        traceback.print_exc()


if __name__ == "__main__":
    main()