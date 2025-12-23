#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER VEÍCULOS - MEGALEILÕES + SUPERBID + SODRÉ SANTORO
Versão com filtros anti-teste/demo e schema auctions correto
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

# Importa o cliente Supabase correto (com headers Content-Profile)
from supabase_client import SupabaseClient


class VeiculosScraper:
    """Scraper unificado para Megaleilões, Superbid e Sodré Santoro"""
    
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
            r'demonstra[cç][aã]o',
        ]
        
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.test_patterns]
    
    def is_test_item(self, item: dict) -> tuple[bool, str]:
        """
        Verifica se um item é de teste/demo (com proteção contra None)
        Returns: (is_test, reason)
        """
        # 1. Sem loja (store_name null/vazio) = geralmente teste
        store = item.get('store_name')
        if not store or not str(store).strip():
            return True, 'no_store'
        
        # 2. Verifica vendedor - COM PROTEÇÃO CONTRA None
        seller = item.get('store_name') or ""
        seller = seller.lower() if seller else ""
        if 'demo' in seller or 'vendedor demo' in seller:
            return True, 'demo_seller'
        
        # 3. Verifica leiloeiro - COM PROTEÇÃO CONTRA None
        auctioneer = item.get('auction_name') or ""
        auctioneer = auctioneer.lower() if auctioneer else ""
        if 'demo' in auctioneer or 'leiloeiro demo' in auctioneer or 'corretor demo' in auctioneer:
            return True, 'demo_auctioneer'
        
        # 4. Verifica título e descrição - COM PROTEÇÃO CONTRA None
        title = item.get('title') or ""
        title = title.lower() if title else ""
        
        desc = item.get('description_preview') or ""
        desc = desc.lower() if desc else ""
        
        # Verifica padrões de teste
        for pattern in self.compiled_patterns:
            if pattern.search(title) or pattern.search(desc):
                if 'deploy' in title or 'deploy' in desc:
                    return True, 'deploy_text'
                return True, 'test_text'
        
        return False, ''
    
    def setup_global_cookies(self):
        """Cria uma sessão com cookies para Megaleilões e Superbid"""
        print("🍪 CRIANDO SESSION GLOBAL (Megaleilões + Superbid)...")
        
        try:
            # Carrega as páginas principais para capturar cookies
            self.session.get('https://www.megaleiloes.com.br', timeout=15)
            time.sleep(1)
            self.session.get('https://www.superbid.net', timeout=15)
            
            cookies_count = len(self.session.cookies)
            print(f"  ✅ {cookies_count} cookies capturados")
            
        except Exception as e:
            print(f"  ⚠️ Erro ao criar sessão: {e}")
    
    def scrape_sodre(self) -> List[dict]:
        """Scrape Sodré Santoro"""
        print("🔵 SODRÉ")
        items = []
        
        try:
            print("  🍪 Obtendo cookies...")
            r1 = self.session.get('https://www.sodresantoro.com.br', timeout=15)
            cookies_count = len(self.session.cookies)
            print(f"  ✅ {cookies_count} cookies")
            
            time.sleep(2)
            
            url = 'https://www.sodresantoro.com.br/peca/proximos-leiloes'
            r = self.session.get(url, timeout=30)
            
            if r.status_code == 403:
                print(f"  ⚠️ Status 403 - proteção anti-bot detectou")
                return items
            
            r.raise_for_status()
            data = r.json()
            
            for category in data:
                cat_items = category.get('items', [])
                for item in cat_items:
                    cleaned = self._clean_sodre_item(item)
                    if cleaned:
                        items.append(cleaned)
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"  ⚠️ Bloqueado por Cloudflare/WAF")
            else:
                print(f"  ❌ Erro HTTP {e.response.status_code}")
        
        except Exception as e:
            print(f"  ❌ Erro: {e}")
        
        self.stats['sodre'] = len(items)
        return items
    
    def scrape_megaleiloes(self) -> List[dict]:
        """Scrape Megaleilões"""
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
        """Scrape Superbid usando a API que FUNCIONA (do antigo)"""
        print("🔴 SUPERBID")
        items = []
        
        # Apenas categorias de veículos
        categories = {
            'carros-motos': 'Carros & Motos',
            'caminhoes-onibus': 'Caminhões & Ônibus'
        }
        
        BASE_URL = "https://exchange.superbid.net"
        API_BASE = "https://offer-query.superbid.net"
        
        for cat_slug, cat_name in categories.items():
            print(f"  📦 {cat_name}")
            local_filtered = {'demo_seller': 0, 'demo_auctioneer': 0, 'deploy_text': 0, 'no_store': 0}
            
            page = 1
            consecutive_errors = 0
            max_retries = 3
            
            while True:
                url = f"{API_BASE}/seo/offers/"
                params = {
                    "urlSeo": f"{BASE_URL}/categorias/{cat_slug}",
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
                    r = self.session.get(url, params=params, timeout=45)
                    
                    if r.status_code == 404:
                        print(f"    ✅ Fim: página {page} retornou 404")
                        break
                    
                    if r.status_code == 200:
                        try:
                            data = r.json()
                        except:
                            print(f"    ⚠️ Erro JSON na página {page}")
                            consecutive_errors += 1
                            if consecutive_errors >= max_retries:
                                break
                            continue
                        
                        page_offers = data.get("offers", [])
                        
                        if not page_offers:
                            print(f"    ✅ Fim: página {page} vazia")
                            break
                        
                        # Filtra ofertas de teste e inativas
                        valid_count = 0
                        for offer in page_offers:
                            # Normaliza para o schema
                            cleaned = self._clean_superbid_offer(offer, cat_slug)
                            if not cleaned:
                                continue
                            
                            # Aplica filtros anti-teste
                            is_test, reason = self.is_test_item(cleaned)
                            if is_test:
                                local_filtered[reason] += 1
                                self.stats['filtered_test_items'] += 1
                                self.stats['filter_details'][reason] += 1
                                continue
                            
                            # Verifica se está ativa
                            end_date = offer.get("endDate")
                            if end_date:
                                try:
                                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                    if end_dt <= datetime.now(end_dt.tzinfo):
                                        continue  # Oferta expirada
                                except:
                                    pass
                            
                            items.append(cleaned)
                            valid_count += 1
                        
                        print(f"    Pág {page}: +{valid_count} válidos | Total: {len(items)}")
                        
                        if len(page_offers) < 10:
                            print(f"    ✅ Fim: última página com {len(page_offers)} ofertas")
                            break
                        
                        page += 1
                        consecutive_errors = 0
                        time.sleep(2)  # Delay entre páginas
                    
                    elif r.status_code == 429:
                        wait_time = 20
                        print(f"    ⚠️ Rate limit, aguardando {wait_time}s...")
                        time.sleep(wait_time)
                        consecutive_errors += 1
                        if consecutive_errors >= max_retries:
                            break
                    
                    else:
                        print(f"    ⚠️ Status {r.status_code} na página {page}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_retries:
                            break
                
                except requests.exceptions.Timeout:
                    consecutive_errors += 1
                    print(f"    ⚠️ Timeout na página {page} ({consecutive_errors}/{max_retries})")
                    if consecutive_errors >= max_retries:
                        break
                    time.sleep(10)
                
                except Exception as e:
                    consecutive_errors += 1
                    print(f"    ❌ Erro na página {page}: {e}")
                    if consecutive_errors >= max_retries:
                        break
                    time.sleep(10)
            
            # Mostra filtros da categoria
            total_filtered = sum(local_filtered.values())
            if total_filtered > 0:
                print(f"    🚫 Filtrados {total_filtered} nesta categoria:")
                if local_filtered['no_store'] > 0:
                    print(f"       • Sem loja: {local_filtered['no_store']}")
                if local_filtered['demo_seller'] > 0:
                    print(f"       • Vendedor Demo: {local_filtered['demo_seller']}")
                if local_filtered['demo_auctioneer'] > 0:
                    print(f"       • Leiloeiro Demo: {local_filtered['demo_auctioneer']}")
                if local_filtered['deploy_text'] > 0:
                    print(f"       • Texto 'deploy': {local_filtered['deploy_text']}")
            
            time.sleep(10)  # Delay entre categorias
        
        self.stats['superbid'] = len(items)
        return items
    
    def _clean_sodre_item(self, item: dict) -> Optional[dict]:
        """Limpa item do Sodré"""
        try:
            item_id = item.get('id')
            title = item.get('name', '').strip()
            
            if not item_id or not title:
                return None
            
            auction = item.get('auction', {})
            
            return {
                'source': 'sodre',
                'external_id': str(item_id),
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': item.get('description', '')[:255] if item.get('description') else None,
                'value': item.get('current_bid'),
                'value_text': f"R$ {item.get('current_bid', 0):.2f}" if item.get('current_bid') else None,
                'city': auction.get('city'),
                'state': auction.get('state'),
                'auction_date': auction.get('date'),
                'auction_type': auction.get('type', 'Leilão'),
                'auction_name': auction.get('name'),
                'lot_number': item.get('lot'),
                'link': f"https://www.sodresantoro.com.br/peca/{item_id}",
                'metadata': {
                    'images': item.get('images', []),
                    'status': item.get('status')
                }
            }
        except:
            return None
    
    def _clean_megaleiloes_item(self, item: dict) -> Optional[dict]:
        """Limpa item do Megaleilões"""
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
                'external_id': str(item_id),
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': item.get('description', '')[:255] if item.get('description') else None,
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
    
    def _clean_superbid_offer(self, offer: dict, category_slug: str) -> Optional[dict]:
        """Limpa item do Superbid (formato da API offer-query)"""
        try:
            product = offer.get("product", {})
            auction = offer.get("auction", {})
            detail = offer.get("offerDetail", {})
            seller = offer.get("seller", {})
            store = offer.get("store", {})
            
            offer_id = offer.get("id")
            title = product.get("shortDesc", "").strip()
            
            if not offer_id or not title:
                return None
            
            # Valor
            min_bid = detail.get("currentMinBid") or detail.get("initialBidValue")
            if min_bid:
                try:
                    min_bid = float(min_bid)
                except:
                    min_bid = None
            
            # Data do leilão
            auction_date = None
            end_date_str = offer.get("endDate")
            if end_date_str:
                try:
                    auction_date = datetime.fromisoformat(
                        end_date_str.replace('Z', '+00:00')
                    ).isoformat()
                except:
                    pass
            
            # Localização (extrai cidade/estado do campo city do seller)
            city = None
            state = None
            seller_city = seller.get("city", "")
            if seller_city:
                if '/' in seller_city:
                    parts = seller_city.split('/')
                    city = parts[0].strip()
                    state = parts[1].strip() if len(parts) > 1 else None
                elif ' - ' in seller_city:
                    parts = seller_city.split(' - ')
                    city = parts[0].strip()
                    state = parts[1].strip() if len(parts) > 1 else None
                else:
                    city = seller_city.strip()
                
                if state and (len(state) != 2 or not state.isupper()):
                    state = None
            
            # Descrição
            full_desc = offer.get("offerDescription", {}).get("offerDescription", "")
            desc_preview = full_desc[:255] if full_desc else title[:150]
            
            # Galeria de imagens
            gallery = product.get("galleryJson", [])
            total_fotos = len([i for i in gallery if i.get("link")]) if gallery else 0
            
            return {
                'source': 'superbid',
                'external_id': str(offer_id),
                'title': title,
                'normalized_title': self._normalize_title(title),
                'description_preview': desc_preview,
                'description': full_desc if full_desc else None,
                'value': min_bid,
                'value_text': detail.get("currentMinBidFormatted") or detail.get("initialBidValueFormatted"),
                'city': city,
                'state': state,
                'address': seller_city if seller_city else None,
                'auction_date': auction_date,
                'auction_type': auction.get("modalityDesc", "Leilão"),
                'auction_name': auction.get("desc"),
                'store_name': store.get("name"),
                'lot_number': offer.get("lotNumber"),
                'total_visits': offer.get("visits", 0),
                'total_bids': offer.get("totalBids", 0),
                'total_bidders': offer.get("totalBidders", 0),
                'link': f"https://exchange.superbid.net/oferta/{offer_id}",
                'metadata': {
                    'leiloeiro': auction.get("auctioneer"),
                    'quantidade_lote': offer.get("quantityInLot"),
                    'vendedor': {
                        'nome': seller.get("name"),
                        'empresa': seller.get("company"),
                    },
                    'preco_detalhado': {
                        'inicial': detail.get("initialBidValue"),
                        'lance_minimo': detail.get("currentMinBid"),
                        'lance_maximo': detail.get("currentMaxBid"),
                    },
                    'midia': {
                        'total_fotos': total_fotos,
                        'total_videos': product.get("videoUrlCount", 0),
                    },
                    'category': category_slug
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
    
    def upload_to_supabase(self, items: List[dict], table_name: str = 'veiculos'):
        """Faz upload para Supabase usando o cliente correto"""
        print("📤 Enviando para Supabase...")
        
        try:
            client = SupabaseClient()
            stats = client.upsert(table_name, items)
            
            print(f"  ✅ {stats['inserted']} novos, {stats['updated']} atualizados, {stats['errors']} erros")
            
            if stats['errors'] > 0:
                print(f"  ⚠️ Alguns itens falharam - verifique os logs acima")
        
        except Exception as e:
            print(f"  ❌ Erro ao enviar: {e}")
    
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
        
        # Setup cookies
        self.setup_global_cookies()
        
        # Scrape cada fonte
        sodre_items = self.scrape_sodre()
        self.items.extend(sodre_items)
        print(f"✅ sodre: {len(sodre_items)} itens")
        
        megaleiloes_items = self.scrape_megaleiloes()
        self.items.extend(megaleiloes_items)
        print(f"✅ megaleiloes: {len(megaleiloes_items)} itens")
        
        superbid_items = self.scrape_superbid()
        self.items.extend(superbid_items)
        print(f"✅ superbid: {len(superbid_items)} itens")
        
        # Mostra resumo dos filtros SUPERBID
        if self.stats['filtered_test_items'] > 0:
            print(f"  🚫 TOTAL FILTRADO (SUPERBID): {self.stats['filtered_test_items']} ofertas de teste/demo")
            details = self.stats['filter_details']
            print(f"     • Sem loja (store_name NULL): {details['no_store']}")
            print(f"     • Vendedor Demo: {details['demo_seller']}")
            print(f"     • Leiloeiro Demo: {details['demo_auctioneer']}")
            print(f"     • Texto 'deploy': {details['deploy_text']}")
        
        # Remove duplicatas
        unique_items = self.deduplicate(self.items)
        
        # Salva JSON
        filepath = self.save_json(unique_items)
        print(f"💾 Salvo: {filepath}")
        print(f"📊 Total: {len(unique_items)} itens únicos")
        
        # Upload para Supabase
        self.upload_to_supabase(unique_items)
        
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        print("="*60)
        print(f"✅ veiculos CONCLUÍDO em {minutes} minutos")
        print(f"🕐 Término: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("="*60)


if __name__ == "__main__":
    print("="*60)
    print(f"📅 Início: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"🇧🇷 Horário Brasil: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} BRT")
    print(f"📦 Fonte: all")
    print("="*60)
    
    scraper = VeiculosScraper()
    scraper.run()