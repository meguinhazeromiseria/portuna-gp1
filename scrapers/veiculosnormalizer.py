#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VEÍCULOS NORMALIZER - Normalização de Dados de Veículos

Uniformiza dados de diferentes fontes (Sodré, Superbid, Megaleilões)
para apresentação elegante no front-end.
"""

import re
from typing import Dict, List, Optional


class VehicleDataNormalizer:
    """Normalizador de dados de veículos"""
    
    # Marcas conhecidas
    KNOWN_BRANDS = [
        'AUDI', 'BMW', 'BYD', 'CAOA', 'CHEVROLET', 'CHERY', 'CITROEN',
        'CITROËN', 'DAF', 'DUCATI', 'FIAT', 'FORD', 'GWM', 'HARLEY',
        'HARLEY-DAVIDSON', 'HONDA', 'HYUNDAI', 'IVECO', 'JAC', 'JEEP',
        'KAWASAKI', 'KIA', 'LAND ROVER', 'LIFAN', 'MAN', 'MAZDA',
        'MERCEDES', 'MERCEDES-BENZ', 'MITSUBISHI', 'NISSAN', 'PEUGEOT',
        'PORSCHE', 'RENAULT', 'ROYAL ENFIELD', 'SCANIA', 'SUBARU',
        'SUZUKI', 'TOYOTA', 'TRIUMPH', 'VOLKSWAGEN', 'VOLVO', 'VW',
        'YAMAHA',
    ]
    
    # UFs válidos
    VALID_STATES = [
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
        'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
        'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
    ]
    
    def normalize(self, item: dict) -> dict:
        """Normaliza um item de veículo para estrutura uniforme"""
        source = item.get('source', '')
        
        return {
            # IDs
            'id': item.get('id'),
            'source': source,
            'external_id': item.get('external_id'),
            
            # Informações principais
            'display_title': self._get_display_title(item),
            'brand': self._get_brand(item),
            'model': self._get_model(item),
            'year': self._get_year(item),
            'plate': self._get_plate(item),
            
            # Descrição
            'description': self._get_clean_description(item),
            'description_preview': item.get('description_preview'),
            
            # Valores
            'price': self._get_price(item),
            'price_formatted': item.get('value_text'),
            
            # Localização
            'location': self._get_location(item),
            'city': self._format_city(item.get('city')),
            'state': self._validate_state(item.get('state')),
            'full_address': item.get('address'),
            
            # Leilão
            'auction': self._get_auction_info(item),
            
            # Estatísticas
            'stats': {
                'visits': item.get('total_visits', 0) or 0,
                'bids': item.get('total_bids', 0) or 0,
                'bidders': item.get('total_bidders', 0) or 0,
            },
            
            # Link
            'link': item.get('link'),
            
            # Datas
            'auction_date': item.get('auction_date'),
            'days_remaining': item.get('days_remaining'),
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at'),
            
            # Metadata original
            'original_metadata': item.get('metadata'),
        }
    
    def _get_display_title(self, item: dict) -> str:
        """
        Título SIMPLES - só primeira letra da FRASE maiúscula
        
        Ex: "Moto cg fan 125 com carrocinha 2007"
            "Nissan kicks sense cvt 23/23"
            "Carro citroen jumpy furgão pk 2020/2021"
        """
        source = item.get('source', '')
        title = item.get('title', '')
        metadata = item.get('metadata', {})
        
        # ========================================
        # SODRÉ: Usa metadata (mais confiável)
        # ========================================
        if source == 'sodre' and 'veiculo' in metadata:
            veiculo = metadata['veiculo']
            marca = (veiculo.get('marca') or '').strip()
            modelo = (veiculo.get('modelo') or '').strip()
            ano = veiculo.get('ano')
            
            if marca and modelo:
                # Minúsculo + primeira maiúscula
                marca_fmt = marca.lower()
                modelo_fmt = modelo.lower()
                
                if ano:
                    # Ano curto: 2023 → 23
                    ano_curto = str(ano)[-2:]
                    result = f"{marca_fmt} {modelo_fmt} {ano_curto}/{ano_curto}"
                else:
                    result = f"{marca_fmt} {modelo_fmt}"
                
                # Primeira letra maiúscula
                return result[0].upper() + result[1:] if result else "Veículo"
        
        # ========================================
        # MEGALEILÕES: Extrai da descrição
        # ========================================
        if source == 'megaleiloes':
            description = item.get('description', '')
            
            # Padrão 1: "Carro/Caminhonete MARCA MODELO - YYYY/YYYY"
            match = re.search(r'((?:Carro|Caminhonete|Moto|Motocicleta)\s+[A-ZÀ-Ú][A-Za-zÀ-ú0-9\s]+?)\s+-\s+(\d{4})/(\d{4})', description, re.IGNORECASE)
            if match:
                vehicle_part = match.group(1).strip()
                year1 = match.group(2)
                year2 = match.group(3)
                
                # Minúsculo + primeira maiúscula
                result = f"{vehicle_part.lower()} {year1}/{year2}"
                return result[0].upper() + result[1:]
            
            # Padrão 2: Fallback - busca depois de números
            match = re.search(r'\d+\s+\d+\s+((?:Carro|Caminhonete|Moto)\s+[A-Za-zÀ-ú0-9\s-]+?)\s+[A-Z]\d+', description, re.IGNORECASE)
            if match:
                vehicle_text = match.group(1).strip().lower()
                return vehicle_text[0].upper() + vehicle_text[1:]
            
            # Padrão 3: Super fallback - marca conhecida
            brands_pattern = r'(Ford|Fiat|Chevrolet|VW|Volkswagen|Renault|Honda|Toyota|Yamaha|Nissan|Hyundai|Citroen|Peugeot)'
            match = re.search(rf'((?:Carro|Caminhonete|Moto)\s+{brands_pattern}[A-Za-zÀ-ú0-9\s]+)', description, re.IGNORECASE)
            if match:
                vehicle_text = match.group(0).strip()
                vehicle_text = re.sub(r'\s+[A-Z]\d+.*$', '', vehicle_text)
                vehicle_text = vehicle_text.lower()
                return vehicle_text[0].upper() + vehicle_text[1:]
        
        # ========================================
        # SUPERBID e outros: Limpa título
        # ========================================
        if title and title != "Sem título" and len(title) > 5:
            clean_title = title
            
            # Remove "LOTE XX" do início
            clean_title = re.sub(r'^LOTE\s+\d+\s+', '', clean_title, flags=re.IGNORECASE)
            
            # Remove HTML tags
            clean_title = re.sub(r'<[^>]+>', '', clean_title)
            
            # Remove vírgulas soltas no final
            clean_title = clean_title.rstrip(',').strip()
            
            # Remove "Placa FINAL X (UF)"
            clean_title = re.sub(r'\s*,?\s*Placa\s+FINAL\s+\d+\s*\([A-Z]{2}\)\s*,?', '', clean_title, flags=re.IGNORECASE)
            
            # Remove underscores
            clean_title = clean_title.replace('_', ' ')
            
            # Remove zeros à esquerda de números (exemplo: "03" → "3", "Fan 125" mantém)
            clean_title = re.sub(r'\b0+(\d+)\b', r'\1', clean_title)
            
            # Remove espaços duplicados
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            # Minúsculo + primeira maiúscula apenas
            clean_title = clean_title.lower()
            if clean_title:
                clean_title = clean_title[0].upper() + clean_title[1:]
            
            # Trunca se muito longo
            if len(clean_title) > 120:
                clean_title = clean_title[:117] + '...'
            
            return clean_title
        
        # ========================================
        # Fallback
        # ========================================
        return "Veículo"
    
    def _get_brand(self, item: dict) -> Optional[str]:
        """Extrai marca - title case"""
        metadata = item.get('metadata', {})
        
        if 'veiculo' in metadata:
            marca = metadata['veiculo'].get('marca')
            if marca:
                return marca.strip().title()
        
        text = f"{item.get('title', '')} {item.get('description', '')}".upper()
        
        for brand in self.KNOWN_BRANDS:
            if brand in text:
                return brand.title()
        
        return None
    
    def _get_model(self, item: dict) -> Optional[str]:
        """Extrai modelo - title case"""
        metadata = item.get('metadata', {})
        
        if 'veiculo' in metadata:
            modelo = metadata['veiculo'].get('modelo')
            if modelo:
                return modelo.strip().title()
        
        brand = self._get_brand(item)
        if brand:
            title = item.get('title', '').upper()
            model_part = title.replace(brand.upper(), '').strip()
            words = model_part.split()[:4]
            if words:
                return ' '.join(word.capitalize() for word in words)
        
        return None
    
    def _get_year(self, item: dict) -> Optional[str]:
        """Extrai ano"""
        metadata = item.get('metadata', {})
        
        if 'veiculo' in metadata:
            ano = metadata['veiculo'].get('ano')
            if ano:
                return f"{ano}/{ano}"
        
        text = f"{item.get('title', '')} {item.get('description', '')}"
        
        match = re.search(r'(\d{4})/(\d{4})', text)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        
        match = re.search(r'\b(20\d{2})\b', text)
        if match:
            year = match.group(1)
            return f"{year}/{year}"
        
        return None
    
    def _get_plate(self, item: dict) -> Optional[str]:
        """Extrai placa - formatada"""
        metadata = item.get('metadata', {})
        
        if 'veiculo' in metadata:
            placa = metadata['veiculo'].get('placa')
            if placa:
                # Formata: "FINAL 7" → "Final 7"
                return placa.strip().title()
        
        text = f"{item.get('title', '')} {item.get('description', '')}".upper()
        
        # Padrão: ABC-1234 ou ABC1D23
        match = re.search(r'\b([A-Z]{3}[-\s]?\d[A-Z0-9]\d{2})\b', text)
        if match:
            return match.group(1).replace(' ', '').upper()  # Placa fica maiúscula
        
        # Padrão: "final 7" → "Final 7"
        match = re.search(r'final\s+(\d)', text.lower())
        if match:
            return f"Final {match.group(1)}"
        
        return None
    
    def _get_clean_description(self, item: dict) -> str:
        """Limpa descrição"""
        desc = item.get('description', '') or ''
        
        if not desc:
            return item.get('description_preview', '') or ''
        
        desc = re.sub(r'<[^>]+>', '\n', desc)
        desc = re.sub(r'\n\s*\n+', '\n\n', desc)
        desc = re.sub(r'\s+', ' ', desc)
        
        if len(desc) > 3000:
            desc = desc[:2997] + '...'
        
        return desc.strip()
    
    def _get_price(self, item: dict) -> Optional[float]:
        """Normaliza preço"""
        value = item.get('value')
        
        if value is None:
            return None
        
        try:
            price = float(value)
            if price <= 0:
                return None
            return round(price, 2)
        except:
            return None
    
    def _format_city(self, city: Optional[str]) -> Optional[str]:
        """Formata cidade"""
        if not city:
            return None
        city = str(city).strip()
        if not city:
            return None
        return city.title()
    
    def _validate_state(self, state: Optional[str]) -> Optional[str]:
        """Valida UF"""
        if not state:
            return None
        state = str(state).strip().upper()
        if state in self.VALID_STATES:
            return state
        return None
    
    def _get_location(self, item: dict) -> Optional[str]:
        """Cria string de localização - Cidade/UF"""
        city = self._format_city(item.get('city'))
        state = self._validate_state(item.get('state'))
        
        if city and state:
            return f"{city}/{state}"
        elif city:
            return city
        elif state:
            return state
        
        address = item.get('address', '')
        if address:
            match = re.search(r'([^/\-,]+)[\s/\-]+([A-Z]{2})\b', address)
            if match:
                city_match = match.group(1).strip().title()
                state_match = match.group(2).upper()
                if state_match in self.VALID_STATES:
                    return f"{city_match}/{state_match}"
            return address[:50].strip()
        
        return None
    
    def _get_auction_info(self, item: dict) -> dict:
        """Info do leilão"""
        metadata = item.get('metadata', {})
        source = item.get('source', '')
        
        info = {
            'type': item.get('auction_type'),
            'name': item.get('auction_name'),
            'lot_number': item.get('lot_number'),
            'auctioneer': None,
            'seller': None,
        }
        
        if source == 'sodre':
            leilao = metadata.get('leilao', {})
            info['auctioneer'] = leilao.get('leiloeiro')
        elif source == 'superbid':
            info['auctioneer'] = metadata.get('leiloeiro')
            info['seller'] = metadata.get('vendedor')
        
        if not info['auctioneer']:
            info['auctioneer'] = item.get('store_name')
        
        return info


def normalize_vehicles(items: List[dict]) -> List[dict]:
    """Normaliza lista de veículos"""
    normalizer = VehicleDataNormalizer()
    return [normalizer.normalize(item) for item in items]