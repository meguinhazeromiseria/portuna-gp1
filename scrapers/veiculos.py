#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER VEÍCULOS - VERSÃO FINAL CORRIGIDA
- Bug test_text RESOLVIDO
- Categorias expandidas (patinetes, patins, quadriciclos, etc.)
- Melhor tratamento de erros Supabase
"""

import os
import re
import json
import time
import random
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# Importa o cliente Supabase
from supabase_client import SupabaseClient


class VeiculosScraper:
    """Scraper unificado para Megaleilões, Superbid e Sodré Santoro - CATEGORIA VEÍCULOS"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        
        self.items = []
        self.stats = {
            'sodre': 0,
            'megaleiloes': 0,
            'superbid': 0,
            'superbid_oportunidades': 0,
            'filtered_test_items': 0,
            'filter_details': {
                'no_store': 0,
                'demo_seller': 0,
                'demo_auctioneer': 0,
                'deploy_text': 0,
                'test_text': 0
            }
        }
        
        # Lista de termos que indicam itens de teste/demo
        self.test_patterns = [
            r'\bdemo\b',
            r'\bteste\b',
            r'\btest\b',
            r'\bdeploy\b',
            r'^teste',
            r'demonstra[cç][aã]o',
        ]
        
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.test_patterns]
        
        # ✨ CATEGORIAS EXPANDIDAS - Qualquer meio de transporte/mobilidade
        self.vehicle_keywords = [
            # Carros e derivados
            'carro', 'celta', 'gol', 'uno', 'palio', 'corsa', 'fiesta', 'ka',
            'sedan', 'hatch', 'suv', 'crossover', 'picape', 'pickup',
            'automóvel', 'automovel', 'veículo', 'veiculo',
            
            # Motos e similares
            'moto', 'motocicleta', 'ciclomotor', 'motoneta', 'scooter', 'lambreta',
            'quadriciclo', 'quadriciclo', 'triciclo', 'moped',
            
            # Mobilidade urbana/elétrica
            'patinete', 'patins', 'skate', 'bike', 'bicicleta', 'velocípede',
            'segway', 'hoverboard', 'monowheel', 'elétrica', 'eletrica',
            'bike elétrica', 'bike eletrica', 'e-bike', 'ebike',
            'patinete elétrico', 'patinete eletrico',
            
            # Caminhões e veículos pesados
            'caminhão', 'caminhao', 'carreta', 'reboque', 'truck',
            'bitruck', 'rodotrem', 'semi-reboque', 'semi reboque',
            'caminhonete', 'camioneta',
            
            # Ônibus e vans
            'ônibus', 'onibus', 'micro-ônibus', 'micro onibus', 'microonibus',
            'van', 'kombi', 'van executiva', 'van escolar',
            'furgão', 'furgao', 'ambulância', 'ambulancia',
            
            # Utilitários
            'utilitário', 'utilitario', 'trator', 'empilhadeira',
            'retroescavadeira', 'pá carregadeira', 'pa carregadeira',
            
            # Partes e características
            'placa', 'chassi', 'chassis', 'motor', 'rodas',
            'km', 'quilometragem', 'kilometragem',
            
            # Marcas de carros
            'toyota', 'volkswagen', 'vw', 'ford', 'chevrolet', 'chevy',
            'fiat', 'renault', 'nissan', 'hyundai', 'honda', 'jeep',
            'bmw', 'mercedes', 'mercedes-benz', 'audi', 'volvo', 'peugeot',
            'citroën', 'citroen', 'mitsubishi', 'suzuki', 'kia', 'mazda',
            'subaru', 'land rover', 'porsche', 'ferrari', 'lamborghini',
            'chery', 'caoa', 'jac', 'byd', 'gwm', 'lifan',
            
            # Marcas de motos
            'yamaha', 'suzuki', 'kawasaki', 'ducati', 'harley', 'harley-davidson',
            'triumph', 'bmw motorrad', 'ktm', 'royal enfield', 'indian',
            'shineray', 'dafra', 'traxx', 'bull', 'kasinski',
            
            # Marcas de caminhões
            'scania', 'volvo', 'mercedes-benz', 'volkswagen caminhões',
            'iveco', 'man', 'daf', 'ford cargo',
            
            # Marcas de mobilidade elétrica
            'xiaomi', 'ninebot', 'segway', 'foston', 'two dogs',
            'atrio', 'multilaser', 'grin', 'yellow',
        ]
        
        # Cookies da Sodré
        self.sodre_cookies = {}
    
    def is_test_item(self, item: dict) -> tuple[bool, str]:
        """
        Verifica se um item é de teste/demo
        Returns: (is_test, reason)
        """
        # 1. Sem loja (store_name null/vazio) = geralmente teste
        store = item.get('store_name')
        if not store or not str(store).strip():
            return True, 'no_store'
        
        # 2. Verifica vendedor/leiloeiro
        seller = str(item.get('store_name', '')).lower()
        auctioneer = str(item.get('auction_name', '')).lower()
        
        if 'demo' in seller:
            return True, 'demo_seller'
        
        if 'demo' in auctioneer:
            return True, 'demo_auctioneer'
        
        # 3. Verifica título e descrição
        title = str(item.get('title', '')).lower()
        desc = str(item.get('description_preview', '')).lower()
        
        for pattern in self.compiled_patterns:
            if pattern.search(title) or pattern.search(desc):
                if 'deploy' in title or 'deploy' in desc:
                    return True, 'deploy_text'
                return True, 'test_text'
        
        return False, ''
    
    def is_vehicle(self, title: str, description: str = '') -> bool:
        """
        Verifica se um item é um veículo/meio de transporte
        """
        text = f"{title} {description}".lower()
        return any(keyword in text for keyword in self.vehicle_keywords)
    
    # ============================================================
    # SODRÉ SANTORO
    # ============================================================
    
    def get_sodre_cookies(self) -> dict:
        """Captura cookies da Sodré usando Playwright"""
        print("  🍪 Capturando cookies Sodré...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo',
                )
                
                page = context.new_page()
                
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                """)
                
                page.goto("https://www.sodresantoro.com.br", wait_until="networkidle", timeout=60000)
                time.sleep(5)

                cookies = context.cookies()
                if not cookies:
                    page.goto("https://www.sodresantoro.com.br/veiculos/lotes", wait_until="networkidle")
                    time.sleep(3)
                    cookies = context.cookies()

                browser.close()
                cookie_dict = {c["name"]: c["value"] for c in cookies}
                
                if cookie_dict:
                    print(f"     ✅ {len(cookie_dict)} cookies capturados")
                else:
                    print(f"     ⚠️ Nenhum cookie capturado")
                    
                return cookie_dict

        except Exception as e:
            print(f"     ❌ Erro ao capturar cookies: {e}")
            return {}
    
    def scrape_sodre(self) -> List[dict]:
        """Scrape Sodré Santoro"""
        print("🔵 SODRÉ SANTORO")
        items = []
        
        self.sodre_cookies = self.get_sodre_cookies()
        
        if not self.sodre_cookies:
            print("  ❌ Sem cookies - pulando Sodré")
            return items
        
        indices = ["veiculos", "judiciais-veiculos"]
        api_url = "https://www.sodresantoro.com.br/api/search-lots"
        
        headers = {
            "accept": "application/json",
            "accept-language": "pt-BR,pt;q=0.9",
            "content-type": "application/json",
            "origin": "https://www.sodresantoro.com.br",
            "referer": "https://www.sodresantoro.com.br/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            page = 0
            page_num = 1
            
            while True:
                payload = {
                    "indices": indices,
                    "query": {
                        "bool": {
                            "must": [],
                            "filter": [
                                {
                                    "terms": {
                                        "lot_status_id": [1, 2, 3]
                                    }
                                }
                            ],
                            "should": [],
                            "must_not": []
                        }
                    },
                    "from": page,
                    "size": 100,
                    "sort": [
                        {"lot_status_id_order": {"order": "asc"}},
                        {"auction_date_init": {"order": "asc"}}
                    ]
                }
                
                r = self.session.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    cookies=self.sodre_cookies,
                    timeout=30
                )
                
                r.raise_for_status()
                data = r.json()
                
                results = data.get('results', [])
                total = data.get('total', 0)
                
                if not results:
                    break
                
                for lot in results:
                    cleaned = self._clean_sodre_item(lot)
                    if cleaned:
                        items.append(cleaned)
                
                print(f"  Pág {page_num}: +{len(results)} | Total: {len(items)}/{total}")
                
                if len(items) >= total:
                    break
                
                page += 100
                page_num += 1
                time.sleep(random.uniform(1.5, 3.0))
        
        except Exception as e:
            print(f"  ❌ Erro: {e}")
        
        self.stats['sodre'] = len(items)
        return items
    
    def _clean_sodre_item(self, lot: dict) -> Optional[dict]:
        """Limpa item da Sodré"""
        try:
            lot_id = lot.get('lot_id') or lot.get('id')
            auction_id = lot.get('auction_id')
            title = (lot.get('lot_title') or '').strip()
            
            if not lot_id or not title:
                return None
            
            value_raw = lot.get('bid_actual') or lot.get('bid_initial')
            
            if isinstance(value_raw, str):
                value_raw = value_raw.replace("R$", "").replace(".", "").replace(",", ".").strip()
                try:
                    value = float(value_raw)
                except:
                    value = None
            elif isinstance(value_raw, (int, float)):
                value = float(value_raw)
            else:
                value = None
            
            if value is not None and value > 0:
                value = value / 100
            
            if value:
                value_text = f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                value_text = None
            
            location = lot.get('lot_location', '') or ''
            city = None
            state = None
            
            if '/' in location:
                parts = location.split('/')
                city = parts[0].strip() if len(parts) > 0 else None
                state = parts[1].strip() if len(parts) > 1 else None
            
            if state and (len(state) != 2 or not state.isupper()):
                state = None
            
            auction_date = None
            days_remaining = None
            
            date_str = lot.get('lot_date_end') or lot.get('auction_date_init')
            if date_str:
                try:
                    auction_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    days_remaining = max(0, (auction_date - datetime.now(auction_date.tzinfo)).days)
                except:
                    pass
            
            description = lot.get('lot_description', '')
            description_preview = description[:255] if description else title[:255]
            
            return {
                'source': 'sodre',
                'external_id': f"sodre_{lot_id}",
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': description_preview,
                'description': description,
                'value': value,
                'value_text': value_text,
                'city': city,
                'state': state,
                'address': location,
                'auction_date': auction_date.isoformat() if auction_date else None,
                'days_remaining': days_remaining,
                'auction_type': 'Leilão',
                'auction_name': lot.get('auction_name'),
                'store_name': lot.get('auctioneer_name'),
                'lot_number': lot.get('lot_number'),
                'total_visits': lot.get('lot_visits', 0),
                'total_bids': lot.get('bid_count', 0),
                'total_bidders': 0,
                'link': f"https://leilao.sodresantoro.com.br/leilao/{auction_id}/lote/{lot_id}/",
                'metadata': {
                    'leilao': {
                        'id': auction_id,
                        'nome': lot.get('auction_name'),
                        'leiloeiro': lot.get('auctioneer_name'),
                    },
                    'lote': {
                        'numero': lot.get('lot_number'),
                        'status': lot.get('lot_status'),
                        'status_id': lot.get('lot_status_id'),
                    },
                    'veiculo': {
                        'marca': lot.get('lot_brand'),
                        'modelo': lot.get('lot_model'),
                        'placa': lot.get('lot_plate'),
                        'ano': lot.get('lot_year_model'),
                    },
                    'imagens': lot.get('lot_pictures', []),
                }
            }
        except Exception as e:
            print(f"  ⚠️ Erro ao limpar item Sodré: {e}")
            return None
    
    # ============================================================
    # MEGALEILÕES
    # ============================================================
    
    def get_megaleiloes_cookies(self) -> List[dict]:
        """Captura cookies do Megaleilões"""
        print("  🍪 Capturando cookies Megaleilões...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
                )
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR'
                )
                
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                """)
                
                page = context.new_page()
                page.goto("https://www.megaleiloes.com.br", wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                
                cookies = context.cookies()
                browser.close()
                
                print(f"     ✅ {len(cookies)} cookies capturados")
                return cookies
                
        except Exception as e:
            print(f"     ⚠️ Erro ao capturar cookies: {e}")
            return []
    
    def scrape_megaleiloes(self) -> List[dict]:
        """Scrape Megaleilões"""
        print("🟢 MEGALEILÕES")
        items = []
        
        cookies_raw = self.get_megaleiloes_cookies()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR'
                )
                
                if cookies_raw:
                    context.add_cookies(cookies_raw)
                
                page = context.new_page()
                
                page_num = 1
                sem_novos = 0
                ids_vistos = set()
                
                while page_num <= 50:
                    if page_num == 1:
                        url = "https://www.megaleiloes.com.br/veiculos"
                    else:
                        url = f"https://www.megaleiloes.com.br/veiculos?pagina={page_num}"
                    
                    print(f"  Pág {page_num}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(random.uniform(3, 5))
                        
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        
                        html = page.content()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        cards = soup.select('div.card, .leilao-card, div[class*="card"]')
                        
                        if not cards:
                            print(f"    ⚪ Nenhum card")
                            sem_novos += 1
                            if sem_novos >= 3:
                                break
                            page_num += 1
                            continue
                        
                        print(f"    📦 {len(cards)} cards")
                        
                        novos = 0
                        for card in cards:
                            item = self._extract_megaleiloes_card(card)
                            if item and item['external_id'] not in ids_vistos:
                                items.append(item)
                                ids_vistos.add(item['external_id'])
                                novos += 1
                        
                        if novos > 0:
                            print(f"    ✅ +{novos} | Total: {len(items)}")
                            sem_novos = 0
                        else:
                            print(f"    ⚪ Sem novos")
                            sem_novos += 1
                            if sem_novos >= 3:
                                break
                        
                        page_num += 1
                        time.sleep(random.uniform(3, 6))
                        
                    except Exception as e:
                        print(f"    ❌ Erro: {str(e)[:100]}")
                        sem_novos += 1
                        if sem_novos >= 3:
                            break
                        page_num += 1
                
                browser.close()
        
        except Exception as e:
            print(f"  ❌ Erro geral: {e}")
        
        self.stats['megaleiloes'] = len(items)
        return items
    
    def _extract_megaleiloes_card(self, card) -> Optional[dict]:
        """Extrai dados do card do Megaleilões"""
        try:
            link_elem = card.select_one('a[href]')
            if not link_elem:
                return None
            
            link = link_elem.get('href', '')
            if not link or 'javascript' in link:
                return None
            
            if not link.startswith('http'):
                link = f"https://www.megaleiloes.com.br{link}"
            
            external_id = None
            parts = link.rstrip('/').split('/')
            for part in reversed(parts):
                if part and not part.startswith('?'):
                    external_id = f"megaleiloes_{part.split('?')[0]}"
                    break
            
            if not external_id:
                external_id = f"megaleiloes_{abs(hash(link)) % 10000000}"
            
            texto = card.get_text(separator=' ', strip=True)
            
            title = "Sem título"
            for selector in ['h1', 'h2', 'h3', 'h4', '.titulo', '.title']:
                elem = card.select_one(selector)
                if elem:
                    t = elem.get_text(strip=True)
                    if 10 < len(t) < 200:
                        title = t
                        break
            
            value = None
            value_text = None
            price_match = re.search(r'R\$\s*([\d.]+,\d{2})', texto)
            if price_match:
                value_text = f"R$ {price_match.group(1)}"
                try:
                    value = float(price_match.group(1).replace('.', '').replace(',', '.'))
                except:
                    pass
            
            state = None
            state_match = re.search(r'\b([A-Z]{2})\b', texto)
            if state_match:
                uf = state_match.group(1)
                valid_states = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
                               'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']
                if uf in valid_states:
                    state = uf
            
            city = None
            city_match = re.search(r'([A-ZÀ-Ú][a-zà-ú\s]+)\s*[-–/]\s*[A-Z]{2}', texto)
            if city_match:
                city = city_match.group(1).strip()
            
            return {
                'source': 'megaleiloes',
                'external_id': external_id,
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': texto[:200] if texto else None,
                'description': texto,
                'value': value,
                'value_text': value_text,
                'city': city,
                'state': state,
                'link': link,
                'metadata': {'categoria': 'veiculos'}
            }
            
        except Exception as e:
            return None
    
    # ============================================================
    # SUPERBID - CATEGORIAS + OPORTUNIDADES
    # ============================================================
    
    def scrape_superbid(self) -> List[dict]:
        """Scrape Superbid - Categorias específicas"""
        print("🔴 SUPERBID - Categorias")
        items = []
        
        categories = [
            ('carros-motos', 1),
            ('caminhoes-onibus', 801)
        ]
        
        headers = {
            "accept": "*/*",
            "accept-language": "pt-BR,pt;q=0.9",
            "origin": "https://exchange.superbid.net",
            "referer": "https://exchange.superbid.net/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        try:
            for cat_slug, cat_id in categories:
                print(f"  📦 {cat_slug}")
                items_before = len(items)
                
                page = 1
                consecutive_errors = 0
                
                while page <= 100:
                    url = "https://offer-query.superbid.net/seo/offers/"
                    params = {
                        "urlSeo": f"https://exchange.superbid.net/categorias/{cat_slug}",
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
                    
                    try:
                        r = self.session.get(url, params=params, headers=headers, timeout=45)
                        
                        if r.status_code == 404:
                            print(f"    ✅ Fim: página {page} retornou 404")
                            break
                        
                        if r.status_code != 200:
                            print(f"    ⚠️ Status {r.status_code}")
                            consecutive_errors += 1
                            if consecutive_errors >= 3:
                                break
                            time.sleep(5)
                            continue
                        
                        data = r.json()
                        offers = data.get("offers", [])
                        
                        if not offers:
                            print(f"    ✅ Fim: página {page} vazia")
                            break
                        
                        # ✅ FIX DEFINITIVO: Try-except INDIVIDUAL para cada oferta
                        valid_count = 0
                        for offer in offers:
                            try:
                                cleaned = self._clean_superbid_offer(offer, cat_slug)
                                if cleaned:
                                    is_test, reason = self.is_test_item(cleaned)
                                    if not is_test:
                                        items.append(cleaned)
                                        valid_count += 1
                                    else:
                                        self.stats['filtered_test_items'] += 1
                                        self.stats['filter_details'][reason] += 1
                            except Exception:
                                # Silenciosamente ignora erro individual
                                pass
                        
                        print(f"    Pág {page}: +{valid_count} | Total: {len(items)}")
                        
                        if len(offers) < 10:
                            print(f"    ✅ Última página")
                            break
                        
                        page += 1
                        consecutive_errors = 0
                        time.sleep(random.uniform(2, 5))
                        
                    except requests.exceptions.JSONDecodeError:
                        print(f"    ⚠️ Erro JSON")
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            break
                        time.sleep(5)
                    
                    except Exception as e:
                        print(f"    ❌ Erro: {str(e)[:100]}")
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            break
                        time.sleep(5)
                
                cat_items = len(items) - items_before
                print(f"    ✅ {cat_items} itens em {cat_slug}")
        
        except Exception as e:
            print(f"  ❌ Erro geral: {e}")
        
        self.stats['superbid'] = len(items)
        return items
    
    def scrape_superbid_oportunidades(self) -> List[dict]:
        """
        Scrape Superbid Oportunidades - Filtra veículos e mobilidade
        """
        print("🔴 SUPERBID - Oportunidades")
        items = []
        
        headers = {
            "accept": "*/*",
            "accept-language": "pt-BR,pt;q=0.9",
            "origin": "https://exchange.superbid.net",
            "referer": "https://exchange.superbid.net/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        try:
            page = 1
            consecutive_errors = 0
            vehicle_count = 0
            filtered_count = 0
            
            while page <= 100:
                url = "https://offer-query.superbid.net/seo/offers/"
                params = {
                    "urlSeo": "https://exchange.superbid.net/oportunidades",
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
                
                try:
                    r = self.session.get(url, params=params, headers=headers, timeout=45)
                    
                    if r.status_code == 404:
                        print(f"    ✅ Fim: página {page} retornou 404")
                        break
                    
                    if r.status_code != 200:
                        print(f"    ⚠️ Status {r.status_code}")
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            break
                        time.sleep(5)
                        continue
                    
                    data = r.json()
                    offers = data.get("offers", [])
                    
                    if not offers:
                        print(f"    ✅ Fim: página {page} vazia")
                        break
                    
                    # Processa cada oferta
                    valid_count = 0
                    for offer in offers:
                        try:
                            cleaned = self._clean_superbid_offer(offer, 'oportunidades')
                            if cleaned:
                                title = cleaned.get('title', '')
                                desc = cleaned.get('description', '')
                                
                                # Verifica se é veículo/mobilidade
                                if self.is_vehicle(title, desc):
                                    is_test, reason = self.is_test_item(cleaned)
                                    if not is_test:
                                        items.append(cleaned)
                                        valid_count += 1
                                        vehicle_count += 1
                                    else:
                                        self.stats['filtered_test_items'] += 1
                                        self.stats['filter_details'][reason] += 1
                                else:
                                    filtered_count += 1
                        except Exception:
                            pass
                    
                    if valid_count > 0 or filtered_count > 0:
                        print(f"    Pág {page}: +{valid_count} veículos ({filtered_count} outros) | Total: {len(items)}")
                    
                    if len(offers) < 10:
                        print(f"    ✅ Última página")
                        break
                    
                    page += 1
                    consecutive_errors = 0
                    time.sleep(random.uniform(2, 5))
                    
                except requests.exceptions.JSONDecodeError:
                    print(f"    ⚠️ Erro JSON")
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        break
                    time.sleep(5)
                
                except Exception as e:
                    print(f"    ❌ Erro: {str(e)[:100]}")
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        break
                    time.sleep(5)
            
            print(f"    ✅ {vehicle_count} veículos encontrados (filtrou {filtered_count} não-veículos)")
        
        except Exception as e:
            print(f"  ❌ Erro geral: {e}")
        
        self.stats['superbid_oportunidades'] = len(items)
        return items
    
    def _clean_superbid_offer(self, offer: dict, category_slug: str) -> Optional[dict]:
        """Limpa oferta do Superbid"""
        try:
            product = offer.get("product", {})
            auction = offer.get("auction", {})
            detail = offer.get("offerDetail", {})
            seller = offer.get("seller", {})
            store = offer.get("store", {})
            
            offer_id = str(offer.get("id"))
            external_id = f"superbid_{offer_id}"
            title = (product.get("shortDesc") or "Sem título").strip()
            
            value = detail.get("currentMinBid") or detail.get("initialBidValue")
            value_text = detail.get("currentMinBidFormatted") or detail.get("initialBidValueFormatted")
            
            city = None
            state = None
            seller_city = seller.get("city", "") or ""
            
            if '/' in seller_city:
                parts = seller_city.split('/')
                city = parts[0].strip()
                state = parts[1].strip() if len(parts) > 1 else None
            elif ' - ' in seller_city:
                parts = seller_city.split(' - ')
                city = parts[0].strip()
                state = parts[1].strip() if len(parts) > 1 else None
            
            if state and (len(state) != 2 or not state.isupper()):
                state = None
            
            full_desc = offer.get("offerDescription", {}).get("offerDescription", "")
            description_preview = full_desc[:150] if full_desc else title[:150]
            
            auction_date = None
            days_remaining = None
            end_date_str = offer.get("endDate")
            
            if end_date_str:
                try:
                    auction_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    days_remaining = max(0, (auction_date - datetime.now(auction_date.tzinfo)).days)
                except:
                    pass
            
            return {
                'source': 'superbid',
                'external_id': external_id,
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': description_preview,
                'description': full_desc,
                'value': value,
                'value_text': value_text,
                'city': city,
                'state': state,
                'address': seller_city,
                'auction_date': auction_date.isoformat() if auction_date else None,
                'days_remaining': days_remaining,
                'auction_type': auction.get("modalityDesc", "Leilão"),
                'auction_name': auction.get("desc"),
                'store_name': store.get("name"),
                'lot_number': offer.get("lotNumber"),
                'total_visits': offer.get("visits", 0),
                'total_bids': offer.get("totalBids", 0),
                'total_bidders': offer.get("totalBidders", 0),
                'link': f"https://exchange.superbid.net/oferta/{offer_id}",
                'metadata': {
                    'categoria': category_slug,
                    'leiloeiro': auction.get("auctioneer"),
                    'vendedor': seller.get("name"),
                }
            }
            
        except Exception as e:
            return None
    
    # ============================================================
    # MÉTODOS AUXILIARES
    # ============================================================
    
    def _normalize_title(self, title: str) -> str:
        """Normaliza título para busca"""
        if not title:
            return ''
        
        title = title.lower()
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title)
        return title.strip()
    
    def save_json(self, items: List[dict], output_dir: str = 'veiculos_data') -> str:
        """Salva dados em JSON"""
        Path(output_dir).mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f"{output_dir}/veiculos_{timestamp}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def upload_to_supabase(self, items: List[dict]):
        """Upload para Supabase com melhor tratamento de erros"""
        print("\n📤 Enviando para Supabase (auctions.veiculos)...")
        
        if not items:
            print("  ⚠️ Nenhum item para enviar")
            return
        
        try:
            client = SupabaseClient()
            table_name = 'veiculos'
            
            stats = client.upsert(table_name, items)
            
            print(f"  ✅ {stats['inserted']} novos, {stats['updated']} atualizados, {stats['errors']} erros")
            
            if stats['errors'] > 0:
                print(f"\n  ⚠️ ATENÇÃO: {stats['errors']} itens falharam")
                print(f"  💡 Se erro de permissão, execute: fix_supabase_permissions.sql")
                
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Erro ao enviar: {error_msg}")
            
            if 'permission denied' in error_msg.lower():
                print(f"\n  🔧 SOLUÇÃO:")
                print(f"     1. Execute o script: fix_supabase_permissions.sql no Supabase")
                print(f"     2. Ou execute manualmente:")
                print(f"        GRANT USAGE ON SCHEMA auctions TO anon, authenticated, service_role;")
                print(f"        GRANT ALL ON auctions.veiculos TO anon, authenticated, service_role;")
            
            import traceback
            traceback.print_exc()
    
    def deduplicate(self, items: List[dict]) -> List[dict]:
        """Remove duplicatas baseado em source + external_id"""
        seen = set()
        unique = []
        
        for item in items:
            key = (item['source'], item['external_id'])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        
        return unique
    
    def run(self):
        """Executa scraping completo"""
        print("="*60)
        print("🚗 SCRAPER: VEICULOS - VERSÃO FINAL")
        print("="*60)
        
        start_time = time.time()
        
        # Scrape cada fonte
        sodre_items = self.scrape_sodre()
        self.items.extend(sodre_items)
        print(f"✅ Sodré: {len(sodre_items)} itens\n")
        
        megaleiloes_items = self.scrape_megaleiloes()
        self.items.extend(megaleiloes_items)
        print(f"✅ Megaleilões: {len(megaleiloes_items)} itens\n")
        
        superbid_items = self.scrape_superbid()
        self.items.extend(superbid_items)
        print(f"✅ Superbid (categorias): {len(superbid_items)} itens\n")
        
        oportunidades_items = self.scrape_superbid_oportunidades()
        self.items.extend(oportunidades_items)
        print(f"✅ Superbid (oportunidades): {len(oportunidades_items)} itens\n")
        
        # Mostra resumo dos filtros
        if self.stats['filtered_test_items'] > 0:
            print(f"🚫 TOTAL FILTRADO: {self.stats['filtered_test_items']} ofertas de teste/demo")
            details = self.stats['filter_details']
            if details['no_store'] > 0:
                print(f"   • Sem loja: {details['no_store']}")
            if details['demo_seller'] > 0:
                print(f"   • Vendedor Demo: {details['demo_seller']}")
            if details['demo_auctioneer'] > 0:
                print(f"   • Leiloeiro Demo: {details['demo_auctioneer']}")
            if details['deploy_text'] > 0:
                print(f"   • Texto 'deploy': {details['deploy_text']}")
            if details['test_text'] > 0:
                print(f"   • Texto 'test/demo': {details['test_text']}")
            print()
        
        # Remove duplicatas
        unique_items = self.deduplicate(self.items)
        
        # Resumo por fonte
        print("📊 RESUMO POR FONTE:")
        print(f"   • Sodré Santoro: {self.stats['sodre']}")
        print(f"   • Megaleilões: {self.stats['megaleiloes']}")
        print(f"   • Superbid (categorias): {self.stats['superbid']}")
        print(f"   • Superbid (oportunidades): {self.stats['superbid_oportunidades']}")
        print(f"   • Total bruto: {len(self.items)}")
        print(f"   • Total único: {len(unique_items)}\n")
        
        # Salva JSON
        filepath = self.save_json(unique_items)
        print(f"💾 Salvo: {filepath}")
        
        # Upload para Supabase
        self.upload_to_supabase(unique_items)
        
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print("="*60)
        print(f"✅ CONCLUÍDO em {minutes}min {seconds}s")
        print(f"🕐 Término: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("="*60)


if __name__ == "__main__":
    print("="*60)
    print(f"📅 Início: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"🇧🇷 Horário Brasil: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} BRT")
    print("="*60)
    
    scraper = VeiculosScraper()
    scraper.run()