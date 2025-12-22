#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🚗 SCRAPER: VEÍCULOS - GRUPO 1 - ANTI-BOT MELHORADO"""

import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

CATEGORIA = "veiculos"
TABELA_DB = "veiculos"
OUTPUT_DIR = Path(f"{CATEGORIA}_data")
OUTPUT_DIR.mkdir(exist_ok=True)


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
    """🔵 SODRÉ - Anti-bot ultra melhorado"""
    
    API = "https://www.sodresantoro.com.br/api/search-lots"
    INDICES = ["veiculos", "judiciais-veiculos"]
    ACTIVE_STATUS = [1, 2, 3]
    
    def extrair(self):
        print("\n🔵 SODRÉ (Anti-bot melhorado)")
        
        items = []
        
        try:
            with sync_playwright() as p:
                # 🔥 Browser com stealth mode completo
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process'
                    ]
                )
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo',
                    java_script_enabled=True,
                    accept_downloads=False
                )
                
                # 🔥 Scripts anti-detecção avançados
                context.add_init_script("""
                    // Remove webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Adiciona chrome object
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Mascara navigator.plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Mascara navigator.languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-BR', 'pt', 'en-US', 'en']
                    });
                    
                    // Permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                    );
                """)
                
                page = context.new_page()
                
                print("  🍪 Navegando para obter cookies...")
                
                # Navega como usuário real
                page.goto("https://www.sodresantoro.com.br", wait_until="networkidle", timeout=60000)
                time.sleep(3)
                
                # Simula comportamento humano
                page.mouse.move(100, 100)
                page.mouse.move(500, 300)
                time.sleep(1)
                
                # Vai para página de veículos
                page.goto("https://www.sodresantoro.com.br/veiculos/lotes", wait_until="networkidle", timeout=60000)
                time.sleep(4)
                
                # Scroll simulando leitura
                page.evaluate("window.scrollTo(0, 500)")
                time.sleep(1)
                page.evaluate("window.scrollTo(0, 1000)")
                time.sleep(1)
                
                # Captura cookies
                cookies_list = context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies_list}
                
                print(f"  ✅ {len(cookie_dict)} cookies capturados")
                
                browser.close()
                
                if not cookie_dict:
                    print("  ❌ Nenhum cookie capturado")
                    return []
                
                # 🔥 Faz requisições com cookies + headers realistas
                items = self._fazer_requisicoes(cookie_dict)
                
        except Exception as e:
            print(f"  ❌ Erro no browser: {e}")
            import traceback
            traceback.print_exc()
        
        return self._normalizar(items)
    
    def _fazer_requisicoes(self, cookies):
        """Faz requisições à API com cookies"""
        items = []
        page_num = 0
        max_retries = 3
        consecutive_failures = 0
        
        # Session com cookies
        session = requests.Session()
        session.cookies.update(cookies)
        
        while page_num < 50 and consecutive_failures < 5:
            payload = {
                "indices": self.INDICES,
                "query": {
                    "bool": {
                        "filter": [
                            {"terms": {"lot_status_id": self.ACTIVE_STATUS}}
                        ]
                    }
                },
                "from": page_num * 100,
                "size": 100,
                "sort": [
                    {"lot_status_id_order": {"order": "asc"}},
                    {"auction_date_init": {"order": "asc"}}
                ]
            }
            
            for attempt in range(max_retries):
                try:
                    # 🔥 Headers ultra realistas
                    headers = {
                        "accept": "application/json, text/plain, */*",
                        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                        "content-type": "application/json",
                        "origin": "https://www.sodresantoro.com.br",
                        "referer": "https://www.sodresantoro.com.br/veiculos/lotes",
                        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "same-origin",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    
                    r = session.post(
                        self.API,
                        json=payload,
                        headers=headers,
                        timeout=45
                    )
                    
                    if r.status_code == 200:
                        data = r.json()
                        lotes = data.get("results", [])
                        total = data.get("total", 0)
                        
                        if not lotes:
                            print(f"  ✅ Fim na página {page_num+1}")
                            return items
                        
                        items.extend(lotes)
                        print(f"  Pág {page_num+1}: +{len(lotes)} | Total: {len(items)}/{total}")
                        
                        consecutive_failures = 0
                        
                        if len(items) >= total:
                            return items
                        
                        break
                        
                    elif r.status_code == 403:
                        wait = random.randint(20, 40) * (attempt + 1)
                        print(f"  ⚠️ 403 Forbidden (tent. {attempt+1}), aguardando {wait}s...")
                        time.sleep(wait)
                        
                        if attempt == max_retries - 1:
                            consecutive_failures += 1
                    
                    elif r.status_code == 429:
                        wait = random.randint(30, 60)
                        print(f"  ⚠️ Rate limit, aguardando {wait}s...")
                        time.sleep(wait)
                    
                    else:
                        print(f"  ⚠️ Status {r.status_code}")
                        consecutive_failures += 1
                        break
                        
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = random.randint(15, 30)
                        print(f"  ⚠️ Erro (tent. {attempt+1}): aguardando {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"  ❌ Falha após {max_retries} tentativas")
                        consecutive_failures += 1
            
            if consecutive_failures >= 5:
                print("  ❌ Muitas falhas consecutivas, parando")
                break
            
            page_num += 1
            time.sleep(random.uniform(3, 6))  # Delay maior entre páginas
        
        return items
    
    def _normalizar(self, items):
        resultado = []
        
        for item in items:
            if not item or item.get("lot_status_id") not in self.ACTIVE_STATUS:
                continue
            
            lot_id = item.get("lot_id") or item.get("id")
            if not lot_id:
                continue
            
            auction_id = item.get("auction_id")
            
            value_raw = item.get("bid_actual") or item.get("bid_initial")
            value = None
            if value_raw:
                try:
                    value = float(value_raw) / 100
                except:
                    pass
            
            location = item.get("lot_location", "") or ""
            city, state = None, None
            if "/" in location:
                parts = location.split("/")
                city = parts[0].strip()
                state = parts[1].strip() if len(parts) > 1 else None
            
            if state and len(state) != 2:
                state = None
            
            metadata = {
                "marca": item.get("lot_brand"),
                "modelo": item.get("lot_model"),
                "ano_modelo": item.get("lot_year_model"),
                "placa": item.get("lot_plate"),
                "km": item.get("lot_km", 0),
                "cor": item.get("lot_color"),
            }
            
            titulo = item.get("lot_title") or f"{metadata.get('marca', '')} {metadata.get('modelo', '')}".strip() or "Sem título"
            
            resultado.append({
                "source": "sodre",
                "external_id": f"sodre_{lot_id}",
                "title": titulo,
                "normalized_title": Normalizador.normalizar(titulo, metadata),
                "value": value,
                "city": city,
                "state": state,
                "link": f"https://leilao.sodresantoro.com.br/leilao/{auction_id}/lote/{lot_id}/",
                "metadata": metadata
            })
        
        return resultado


class MegaleiloesExtractor:
    """🟢 MEGALEILÕES"""
    
    BASE = "https://www.megaleiloes.com.br"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
    ]
    
    def extrair(self):
        print("\n🟢 MEGALEILÕES")
        
        items = []
        ids = set()
        user_agent = random.choice(self.USER_AGENTS)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='pt-BR'
            )
            
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
            """)
            
            page = context.new_page()
            
            for pag in range(1, 31):
                url = f"{self.BASE}/veiculos" + (f"?pagina={pag}" if pag > 1 else "")
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(random.uniform(3, 6))
                    
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                    
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    
                    cards = soup.select('div.card, a[href*="/leilao/"], div[class*="card"]')
                    
                    if not cards:
                        print(f"  ⚪ Pág {pag}: sem cards")
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
                    
                    time.sleep(random.uniform(3, 6))
                    
                except Exception as e:
                    print(f"  ⚠️ Erro pág {pag}: {e}")
                    break
            
            browser.close()
        
        return items
    
    def _extrair_card(self, card):
        import re
        
        link = card.get('href') if card.name == 'a' else None
        if not link:
            link_elem = card.select_one('a[href]')
            link = link_elem.get('href') if link_elem else None
        
        if not link or link == '#' or 'javascript' in link:
            return None
        
        if not link.startswith('http'):
            link = self.BASE + link
        
        url_parts = link.rstrip('/').split('/')
        part_id = None
        for part in reversed(url_parts):
            if part and not part.startswith('?'):
                part_clean = part.split('?')[0]
                if part_clean:
                    part_id = part_clean
                    break
        
        if not part_id:
            part_id = str(abs(hash(link)) % 10000000)
        
        external_id = f"megaleiloes_{part_id}"
        
        texto = card.get_text(separator=' ', strip=True)
        
        titulo = "Sem título"
        for sel in ['h2', 'h3', 'h4', 'strong', '.titulo']:
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
        valid_states = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
                       'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']
        sm = re.search(r'\b([A-Z]{2})\b', texto)
        if sm and sm.group(1) in valid_states:
            state = sm.group(1)
        
        return {
            "source": "megaleiloes",
            "external_id": external_id,
            "title": titulo,
            "normalized_title": Normalizador.normalizar(titulo),
            "value": value,
            "state": state,
            "link": link,
            "metadata": {}
        }


class SuperbidExtractor:
    """🔴 SUPERBID - Com retry melhorado"""
    
    API = "https://offer-query.superbid.net/seo/offers/"
    BASE = "https://exchange.superbid.net"
    CATS = ["carros-motos", "caminhoes-onibus"]
    
    def extrair(self):
        print("\n🔴 SUPERBID (Retry melhorado)")
        
        items = []
        
        for cat in self.CATS:
            print(f"  📦 {cat}")
            page = 1
            consecutive_errors = 0
            
            while page <= 30 and consecutive_errors < 3:
                params = {
                    "urlSeo": f"{self.BASE}/categorias/{cat}",
                    "locale": "pt_BR",
                    "pageNumber": page,
                    "pageSize": 100,
                    "searchType": "openedAll",
                    "timeZoneId": "America/Sao_Paulo"
                }
                
                max_retries = 3
                success = False
                
                for attempt in range(max_retries):
                    try:
                        r = requests.get(
                            self.API,
                            params=params,
                            headers={
                                "accept": "*/*",
                                "accept-language": "pt-BR,pt;q=0.9",
                                "origin": self.BASE,
                                "referer": f"{self.BASE}/",
                                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                            },
                            timeout=45
                        )
                        
                        if r.status_code == 404:
                            print(f"    ✅ Fim na pág {page}")
                            success = True
                            break
                        
                        if r.status_code == 500:
                            wait = random.randint(10, 20) * (attempt + 1)
                            print(f"    ⚠️ 500 Error (tent. {attempt+1}), aguardando {wait}s...")
                            time.sleep(wait)
                            continue
                        
                        if r.status_code != 200:
                            print(f"    ⚠️ Status {r.status_code}")
                            if attempt == max_retries - 1:
                                consecutive_errors += 1
                            break
                        
                        offers = r.json().get("offers", [])
                        if not offers:
                            print(f"    ✅ Fim na pág {page}")
                            success = True
                            break
                        
                        valid = []
                        for offer in offers:
                            seller_name = (offer.get("seller", {}).get("name") or "").lower()
                            if "demo" in seller_name:
                                continue
                            
                            if not offer.get("store", {}).get("name"):
                                continue
                            
                            end_date = offer.get("endDate")
                            if end_date:
                                try:
                                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    if end_dt <= datetime.now(end_dt.tzinfo):
                                        continue
                                except:
                                    pass
                            
                            valid.append(offer)
                        
                        items.extend(valid)
                        print(f"    Pág {page}: +{len(valid)} | Total: {len(items)}")
                        
                        consecutive_errors = 0
                        success = True
                        
                        if len(offers) < 10:
                            break
                        
                        break
                        
                    except Exception as e:
                        if attempt < max_retries - 1:
                            wait = random.randint(10, 20)
                            print(f"    ⚠️ Erro (tent. {attempt+1}): aguardando {wait}s...")
                            time.sleep(wait)
                        else:
                            print(f"    ❌ Falha após {max_retries} tentativas")
                            consecutive_errors += 1
                
                if not success or consecutive_errors >= 3:
                    break
                
                page += 1
                time.sleep(random.uniform(2, 5))
        
        return self._normalizar(items)
    
    def _normalizar(self, offers):
        resultado = []
        
        for offer in offers:
            oid = offer.get("id")
            if not oid:
                continue
            
            titulo = offer.get("product", {}).get("shortDesc", "Sem título")
            
            city_text = offer.get("seller", {}).get("city", "")
            city, state = None, None
            if "/" in city_text:
                parts = city_text.split("/")
                city = parts[0].strip()
                state = parts[1].strip() if len(parts) > 1 else None
            
            if state and len(state) != 2:
                state = None
            
            resultado.append({
                "source": "superbid",
                "external_id": f"superbid_{oid}",
                "title": titulo,
                "normalized_title": Normalizador.normalizar(titulo),
                "value": offer.get("offerDetail", {}).get("currentMinBid"),
                "city": city,
                "state": state,
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
            print(f"✅ {fonte}: {len(items)} itens\n")
        except Exception as e:
            print(f"❌ {fonte}: {e}\n")
            import traceback
            traceback.print_exc()
    
    unicos = {i['external_id']: i for i in todos}
    todos = list(unicos.values())
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo = OUTPUT_DIR / f"{CATEGORIA}_{timestamp}.json"
    
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"💾 Salvo: {arquivo}")
    print(f"📊 Total: {len(todos)} itens únicos")
    
    try:
        from supabase_client import SupabaseClient
        
        client = SupabaseClient()
        result = client.upsert(TABELA_DB, todos)
        print(f"✅ Supabase: {result['inserted']} novos, {result['updated']} atualizados")
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()