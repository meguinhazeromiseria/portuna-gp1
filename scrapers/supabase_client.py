#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SUPABASE CLIENT - CORRIGIDO PARA SCHEMA auctions"""

import os
import time
import requests
from datetime import datetime


class SupabaseClient:
    """Cliente para Supabase - Schema auctions (não public)"""
    
    def __init__(self):
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not self.url or not self.key:
            raise ValueError("❌ Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY")
        
        self.url = self.url.rstrip('/')
        
        # 🔥 FIX: Adiciona Content-Profile para schema auctions
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
            'Content-Profile': 'auctions',  # ← Define schema auctions
            'Accept-Profile': 'auctions',   # ← Define schema auctions
            'Prefer': 'resolution=merge-duplicates,return=minimal'
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def upsert(self, tabela: str, items: list) -> dict:
        """
        Faz upsert em batch na tabela especificada (schema auctions)
        
        Args:
            tabela: Nome da tabela (veiculos, tecnologia, etc)
            items: Lista de items para inserir/atualizar
        
        Returns:
            {'inserted': X, 'updated': Y, 'errors': Z}
        """
        if not items:
            return {'inserted': 0, 'updated': 0, 'errors': 0}
        
        prepared = []
        for item in items:
            try:
                db_item = self._prepare(item)
                if db_item:
                    prepared.append(db_item)
            except Exception as e:
                print(f"  ⚠️ Erro ao preparar item: {e}")
        
        if not prepared:
            print("  ⚠️ Nenhum item válido para inserir")
            return {'inserted': 0, 'updated': 0, 'errors': 0}
        
        stats = {'inserted': 0, 'updated': 0, 'errors': 0}
        batch_size = 500
        total_batches = (len(prepared) + batch_size - 1) // batch_size
        
        # 🔥 FIX: URL sem schema (usa Content-Profile header)
        url = f"{self.url}/rest/v1/{tabela}"
        
        for i in range(0, len(prepared), batch_size):
            batch = prepared[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            
            try:
                r = self.session.post(
                    url,
                    json=batch,
                    timeout=120
                )
                
                if r.status_code in (200, 201):
                    stats['inserted'] += len(batch)
                    print(f"  ✅ Batch {batch_num}/{total_batches}: {len(batch)} itens")
                
                elif r.status_code == 409:
                    stats['updated'] += len(batch)
                    print(f"  🔄 Batch {batch_num}/{total_batches}: {len(batch)} atualizados")
                
                else:
                    error_msg = r.text[:200] if r.text else 'Sem detalhes'
                    print(f"  ❌ Batch {batch_num}: HTTP {r.status_code} - {error_msg}")
                    stats['errors'] += len(batch)
            
            except requests.exceptions.Timeout:
                print(f"  ❌ Batch {batch_num}: Timeout após 120s")
                stats['errors'] += len(batch)
            
            except Exception as e:
                print(f"  ❌ Batch {batch_num}: {e}")
                stats['errors'] += len(batch)
            
            if batch_num < total_batches:
                time.sleep(0.5)
        
        return stats
    
    def _prepare(self, item: dict) -> dict:
        """Prepara item para o schema do Supabase"""
        
        source = item.get('source')
        external_id = item.get('external_id')
        title = item.get('title')
        
        if not source or not external_id:
            return None
        
        if not title or not title.strip():
            title = 'Sem título'
        
        auction_date = item.get('auction_date')
        if auction_date:
            if isinstance(auction_date, str):
                try:
                    auction_date = auction_date.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(auction_date)
                    auction_date = dt.isoformat()
                except:
                    auction_date = None
        
        state = item.get('state')
        if state:
            state = str(state).strip().upper()
            if len(state) != 2:
                state = None
        
        value = item.get('value')
        if value is not None:
            try:
                value = float(value)
                if value < 0:
                    value = None
            except:
                value = None
        
        metadata = item.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
        
        return {
            'source': str(source),
            'external_id': str(external_id),
            'title': str(title)[:255],
            'normalized_title': str(item.get('normalized_title') or title)[:255],
            'description_preview': str(item.get('description_preview', ''))[:255] if item.get('description_preview') else None,
            'description': str(item.get('description')) if item.get('description') else None,
            'value': value,
            'value_text': str(item.get('value_text')) if item.get('value_text') else None,
            'city': str(item.get('city')) if item.get('city') else None,
            'state': state,
            'address': str(item.get('address')) if item.get('address') else None,
            'auction_date': auction_date,
            'days_remaining': int(item.get('days_remaining', 0)) if item.get('days_remaining') is not None else None,
            'auction_type': str(item.get('auction_type', 'Leilão'))[:100],
            'auction_name': str(item.get('auction_name')) if item.get('auction_name') else None,
            'store_name': str(item.get('store_name')) if item.get('store_name') else None,
            'lot_number': str(item.get('lot_number')) if item.get('lot_number') else None,
            'total_visits': int(item.get('total_visits', 0)),
            'total_bids': int(item.get('total_bids', 0)),
            'total_bidders': int(item.get('total_bidders', 0)),
            'link': str(item.get('link')) if item.get('link') else None,
            'metadata': metadata,
            'is_active': True,
            'last_scraped_at': datetime.now().isoformat(),
        }
    
    def test(self) -> bool:
        """Testa conexão com Supabase"""
        try:
            # Testa acesso ao schema auctions
            url = f"{self.url}/rest/v1/"
            r = self.session.get(url, timeout=10)
            
            if r.status_code == 200:
                print("✅ Conexão com Supabase OK")
                print(f"   URL: {self.url}")
                print(f"   Schema: auctions")
                return True
            else:
                print(f"❌ Erro HTTP {r.status_code}")
                print(f"   Response: {r.text[:200]}")
                return False
        
        except requests.exceptions.Timeout:
            print("❌ Timeout ao conectar com Supabase")
            return False
        
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def get_stats(self, tabela: str) -> dict:
        """Retorna estatísticas da tabela"""
        try:
            # URL sem schema (usa Content-Profile header)
            url = f"{self.url}/rest/v1/{tabela}"
            
            r = self.session.get(
                url,
                params={'select': 'count'},
                headers={**self.headers, 'Prefer': 'count=exact'},
                timeout=30
            )
            
            if r.status_code == 200:
                total = int(r.headers.get('Content-Range', '0').split('/')[-1])
                return {
                    'total': total,
                    'table': tabela
                }
        except:
            pass
        
        return {'total': 0, 'table': tabela}
    
    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()


if __name__ == "__main__":
    print("="*60)
    print("🧪 TESTE DO SUPABASE CLIENT (SCHEMA auctions)")
    print("="*60)
    
    try:
        client = SupabaseClient()
        
        if client.test():
            print("\n📊 Testando estatísticas...")
            for tabela in ['veiculos', 'tecnologia', 'imoveis', 'eletrodomesticos']:
                stats = client.get_stats(tabela)
                print(f"  {tabela}: {stats['total']} registros")
        
        print("\n" + "="*60)
        print("✅ Testes concluídos!")
        print("="*60)
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("="*60)