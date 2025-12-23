#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER VEÍCULOS - MEGALEILÕES + SUPERBID + SODRÉ SANTORO
Versão corrigida para schema auctions (tabelas separadas)
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

# Importa o cliente Supabase
from supabase_client import SupabaseClient


class VeiculosScraper:
    """Scraper unificado para MegaleilÃµes, Superbid e SodrÃ© Santoro"""
    
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
            'filtered_test_items': 0,
            'filter_details': {
                'no_store': 0,
                'demo_seller': 0,
                'demo_auctioneer': 0,
                'deploy_text': 0
            }
        }
        
        # Lista de termos que indicam itens de teste/demo
        self.test_patterns = [
            r'\bdemo\b',
            r'\bteste\b',
            r'\btest\b',
            r'\bdeploy\b',
            r'^teste',
            r'demonstra[cção][aã]o',
        ]
        
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.test_patterns]
        
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
    
    def get_sodre_cookies(self) -> dict:
        """Captura cookies da Sodré usando Playwright (como no antigo)"""
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
        """Scrape Sodré Santoro - MÉTODO CORRETO (usando API search-lots)"""
        print("🔵 SODRÉ SANTORO")
        items = []
        
        # Captura cookies com Playwright
        self.sodre_cookies = self.get_sodre_cookies()
        
        if not self.sodre_cookies:
            print("  ❌ Sem cookies - pulando Sodré")
            return items
        
        # Índices de veículos (como no antigo)
        indices = ["veiculos", "judiciais-veiculos"]
        
        # Configuração da API
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
                # Payload com filtro de status ATIVOS (1, 2, 3)
                payload = {
                    "indices": indices,
                    "query": {
                        "bool": {
                            "must": [],
                            "filter": [
                                {
                                    "terms": {
                                        "lot_status_id": [1, 2, 3]  # Apenas ativos
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
                
                # Delay entre páginas
                time.sleep(random.uniform(1.5, 3.0))
        
        except Exception as e:
            print(f"  ❌ Erro: {e}")
        
        self.stats['sodre'] = len(items)
        return items
    
    def scrape_megaleiloes(self) -> List[dict]:
        """Scrape MegaleilÃµes"""
        print("🟢 MEGALEILÕES")
        items = []
        
        try:
            page = 1
            while True:
                url = f'https://www.megaleiloes.com.br/api/products/search?includeImages=1&size=60&page={page}&onlyWithImage=true&sortKey=DATE_DESC&type=VEHICLE'
                
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                data = r.json()
                
                results = data.get('result', [])
                if not results:
                    break
                
                for item in results:
                    cleaned = self._clean_megaleiloes_item(item)
                    if cleaned:
                        items.append(cleaned)
                
                print(f"  Pág {page}: +{len(results)} | Total: {len(items)}")
                
                if len(results) < 60:
                    break
                
                page += 1
                time.sleep(1)
        
        except Exception as e:
            print(f"  ❌ Erro: {e}")
        
        self.stats['megaleiloes'] = len(items)
        return items
    
    def scrape_superbid(self) -> List[dict]:
        """Scrape Superbid com filtros anti-teste"""
        print("🔴 SUPERBID")
        items = []
        
        categories = [
            ('carros-motos', 1),
            ('caminhoes-onibus', 801)
        ]
        
        try:
            for cat_slug, cat_id in categories:
                print(f"  📦 {cat_slug}")
                items_before = len(items)
                
                page = 1
                while True:
                    url = f'https://www.superbid.net/api/catalog/v2/categories/{cat_id}/lots?page={page}'
                    
                    try:
                        r = self.session.get(url, timeout=30)
                        
                        if r.status_code == 404:
                            print(f"    ✅ Fim: página {page} retornou 404")
                            break
                        
                        r.raise_for_status()
                        data = r.json()
                        results = data.get('results', [])
                        
                        if not results:
                            break
                        
                        # Processa e filtra itens
                        valid_count = 0
                        for item in results:
                            cleaned = self._clean_superbid_item(item)
                            if cleaned:
                                # Aplica filtro anti-teste
                                is_test, reason = self.is_test_item(cleaned)
                                if not is_test:
                                    items.append(cleaned)
                                    valid_count += 1
                                else:
                                    self.stats['filtered_test_items'] += 1
                                    self.stats['filter_details'][reason] += 1
                        
                        print(f"    Pág {page}: +{valid_count} válidos | Total: {len(items)}")
                        
                        page += 1
                        time.sleep(1)
                    
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 404:
                            print(f"    ✅ Fim: página {page} retornou 404")
                            break
                        raise
                
                cat_items = len(items) - items_before
        
        except Exception as e:
            print(f"  ❌ Erro: {e}")
        
        # Mostra estatísticas de filtros
        if self.stats['filtered_test_items'] > 0:
            print(f"    🚫 Filtrados {self.stats['filtered_test_items']} itens de teste/demo:")
            details = self.stats['filter_details']
            if details['no_store'] > 0:
                print(f"       • Sem loja: {details['no_store']}")
            if details['demo_seller'] > 0:
                print(f"       • Vendedor Demo: {details['demo_seller']}")
            if details['demo_auctioneer'] > 0:
                print(f"       • Leiloeiro Demo: {details['demo_auctioneer']}")
            if details['deploy_text'] > 0:
                print(f"       • Texto 'deploy': {details['deploy_text']}")
        
        self.stats['superbid'] = len(items)
        return items
    
    def _clean_sodre_item(self, lot: dict) -> Optional[dict]:
        """Limpa item da Sodré (usando estrutura da API search-lots)"""
        try:
            lot_id = lot.get('lot_id') or lot.get('id')
            auction_id = lot.get('auction_id')
            title = (lot.get('lot_title') or '').strip()
            
            if not lot_id or not title:
                return None
            
            # ✅ CORREÇÃO CRÍTICA: Valor sempre dividido por 100 (centavos → reais)
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
            
            # ✅ SEMPRE divide por 100 (API retorna centavos)
            if value is not None and value > 0:
                value = value / 100
            
            # Formata texto
            if value:
                value_text = f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                value_text = None
            
            # Localização
            location = lot.get('lot_location', '') or ''
            city = None
            state = None
            
            if '/' in location:
                parts = location.split('/')
                city = parts[0].strip() if len(parts) > 0 else None
                state = parts[1].strip() if len(parts) > 1 else None
            
            # Valida UF
            if state and (len(state) != 2 or not state.isupper()):
                state = None
            
            # Data do leilão
            auction_date = None
            days_remaining = None
            
            date_str = lot.get('lot_date_end') or lot.get('auction_date_init')
            if date_str:
                try:
                    auction_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    days_remaining = max(0, (auction_date - datetime.now(auction_date.tzinfo)).days)
                except:
                    pass
            
            # Descrição
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
    
    def _clean_megaleiloes_item(self, item: dict) -> Optional[dict]:
        """Limpa item do MegaleilÃµes"""
        try:
            item_id = item.get('id')
            title = item.get('name', '').strip()
            
            if not item_id or not title:
                return None
            
            auction = item.get('auction', {})
            location = item.get('location', {})
            
            value = item.get('value')
            if value:
                try:
                    value = float(value)
                except:
                    value = None
            
            return {
                'source': 'megaleiloes',
                'external_id': f"mega_{item_id}",
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': item.get('description', '')[:255] if item.get('description') else None,
                'description': item.get('description'),
                'value': value,
                'value_text': f"R$ {value:.2f}" if value else None,
                'city': location.get('city'),
                'state': location.get('state'),
                'auction_date': auction.get('date'),
                'auction_type': auction.get('type', 'Leilão'),
                'auction_name': auction.get('name'),
                'lot_number': item.get('lot'),
                'total_visits': item.get('totalVisits', 0),
                'link': f"https://www.megaleiloes.com.br/imovel/{item_id}",
                'metadata': {
                    'images': item.get('images', []),
                    'category': item.get('category')
                }
            }
        except:
            return None
    
    def _clean_superbid_item(self, item: dict) -> Optional[dict]:
        """Limpa item do Superbid"""
        try:
            item_id = item.get('lotId')
            title = item.get('title', '').strip()
            
            if not item_id or not title:
                return None
            
            # Extrai informações
            min_bid = item.get('minimumBid')
            if min_bid:
                try:
                    min_bid = float(min_bid)
                except:
                    min_bid = None
            
            # Data do leilão
            auction_date = None
            if item.get('auctionDate'):
                try:
                    auction_date = datetime.fromisoformat(
                        item['auctionDate'].replace('Z', '+00:00')
                    ).isoformat()
                except:
                    pass
            
            # Localização
            city = None
            state = None
            address = None
            
            if item.get('city'):
                city = item['city'].get('name')
                if item['city'].get('state'):
                    state = item['city']['state'].get('initials')
            
            if item.get('address'):
                address = item['address'].get('formattedAddress')
            
            return {
                'source': 'superbid',
                'external_id': f"super_{item_id}",
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': item.get('description', '')[:255] if item.get('description') else None,
                'description': item.get('description'),
                'value': min_bid,
                'value_text': f"R$ {min_bid:.2f}" if min_bid else None,
                'city': city,
                'state': state,
                'address': address,
                'auction_date': auction_date,
                'auction_type': item.get('auctionType', 'Leilão'),
                'auction_name': item.get('auctioneerName'),
                'store_name': item.get('sellerName'),
                'lot_number': item.get('lotNumber'),
                'total_visits': item.get('totalViews', 0),
                'total_bids': item.get('totalBids', 0),
                'total_bidders': item.get('totalBidders', 0),
                'link': f"https://www.superbid.net/lote/{item_id}",
                'metadata': {
                    'images': item.get('images', []),
                    'status': item.get('status'),
                    'category': item.get('categoryName')
                }
            }
        except:
            return None
    
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
        """Upload para Supabase no schema auctions.veiculos"""
        print("\n📤 Enviando para Supabase (auctions.veiculos)...")
        
        try:
            client = SupabaseClient()
            
            # ✅ IMPORTANTE: Usa a tabela auctions.veiculos
            table_name = 'veiculos'  # O cliente deve adicionar o schema automaticamente
            
            stats = client.upsert(table_name, items)
            
            print(f"  ✅ {stats['inserted']} novos, {stats['updated']} atualizados, {stats['errors']} erros")
            
            if stats['errors'] > 0:
                print(f"  ⚠️ Alguns itens falharam - verifique os logs acima")
        
        except Exception as e:
            print(f"  ❌ Erro ao enviar: {e}")
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
        print("🚗 SCRAPER: VEICULOS - VERSÃO CORRIGIDA")
        print("="*60)
        
        start_time = time.time()
        
        # Scrape cada fonte
        sodre_items = self.scrape_sodre()
        self.items.extend(sodre_items)
        print(f"✅ sodre: {len(sodre_items)} itens\n")
        
        megaleiloes_items = self.scrape_megaleiloes()
        self.items.extend(megaleiloes_items)
        print(f"✅ megaleiloes: {len(megaleiloes_items)} itens\n")
        
        superbid_items = self.scrape_superbid()
        self.items.extend(superbid_items)
        print(f"✅ superbid: {len(superbid_items)} itens\n")
        
        # Mostra resumo dos filtros
        if self.stats['filtered_test_items'] > 0:
            print(f"🚫 TOTAL FILTRADO: {self.stats['filtered_test_items']} ofertas de teste/demo")
            details = self.stats['filter_details']
            print(f"   • Sem loja: {details['no_store']}")
            print(f"   • Vendedor Demo: {details['demo_seller']}")
            print(f"   • Leiloeiro Demo: {details['demo_auctioneer']}")
            print(f"   • Texto 'deploy': {details['deploy_text']}\n")
        
        # Remove duplicatas
        unique_items = self.deduplicate(self.items)
        
        # Salva JSON
        filepath = self.save_json(unique_items)
        print(f"💾 Salvo: {filepath}")
        print(f"📊 Total: {len(unique_items)} itens únicos\n")
        
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