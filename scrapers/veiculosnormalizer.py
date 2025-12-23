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
        Cria título elegante e uniforme
        PADRÃO: Primeira letra maiúscula, resto minúscula
        FORMATO: "Ford Ranger Xl 2014/2014"
        """
        source = item.get('source', '')
        title = item.get('title', '')
        metadata = item.get('metadata', {})
        
        # === Sodré: Usa metadata estruturado ===
        if source == 'sodre' and 'veiculo' in metadata:
            veiculo = metadata['veiculo']
            marca = (veiculo.get('marca') or '').strip()
            modelo = (veiculo.get('modelo') or '').strip()
            ano = veiculo.get('ano')
            
            if marca and modelo:
                # Title case: primeira maiúscula de cada palavra
                marca_fmt = marca.title()
                modelo_fmt = modelo.title()
                
                if ano:
                    return f"{marca_fmt} {modelo_fmt} {ano}/{ano}"
                return f"{marca_fmt} {modelo_fmt}"
        
        # === Megaleilões: Extrai do external_id ===
        if source == 'megaleiloes':
            external_id = item.get('external_id', '')
            description = item.get('description', '')
            
            # Tenta extrair da descrição primeiro (mais limpo)
            # Ex: "Caminhonete Ford Ranger XL CD4 22H - 2014/2014"
            desc_match = re.search(r'([A-Za-zÀ-ú\s]+(?:Ford|Fiat|Chevrolet|VW|Volkswagen|Renault|Honda|Toyota|Yamaha|Suzuki)[A-Za-z0-9\s\.\-]+?)\s*-?\s*(\d{4})/(\d{4})', description)
            if desc_match:
                vehicle_part = desc_match.group(1).strip()
                year1 = desc_match.group(2)
                year2 = desc_match.group(3)
                # Title case
                vehicle_fmt = vehicle_part.title()
                return f"{vehicle_fmt} {year1}/{year2}"
            
            # Fallback: extrai do external_id
            # Remove prefixo "megaleiloes_"
            clean_id = external_id.replace('megaleiloes_', '')
            
            # Padrão: "caminhonete-ford-ranger-xl-cd4-22h-20142014-lote-38-x118437"
            # Remove lote-XX-XXXXX do final
            clean_id = re.sub(r'-lote-\d+-[a-z]\d+$', '', clean_id, flags=re.IGNORECASE)
            
            # Extrai ano duplicado (20142014 → 2014/2014)
            year_match = re.search(r'(\d{4})(\d{4})$', clean_id)
            year_text = ""
            if year_match:
                y1, y2 = year_match.groups()
                year_text = f" {y1}/{y2}"
                # Remove do clean_id
                clean_id = clean_id[:year_match.start()]
            
            # Remove hífens finais soltos
            clean_id = clean_id.rstrip('-')
            
            # Substitui hífens por espaços
            clean_id = clean_id.replace('-', ' ')
            
            # Title case (primeira maiúscula de cada palavra)
            title_parts = clean_id.split()
            title_formatted = ' '.join(word.capitalize() for word in title_parts)
            
            return f"{title_formatted}{year_text}".strip()
        
        # === Superbid e outros: Limpa e formata título ===
        if title and title != "Sem título" and len(title) > 10:
            # Remove HTML tags
            clean_title = re.sub(r'<[^>]+>', '', title)
            clean_title = clean_title.strip()
            
            # Remove vírgulas, dois pontos, ponto e vírgula
            clean_title = clean_title.replace(',', '').replace(':', '').replace(';', '')
            
            # Remove "Placa FINAL X" do meio do título
            clean_title = re.sub(r'\s*Placa\s+FINAL\s+\d+\s*\([A-Z]{2}\)\s*', ' ', clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r'\s*Placa\s+FINAL\s+\d+\s*', ' ', clean_title, flags=re.IGNORECASE)
            
            # Remove espaços duplicados
            clean_title = re.sub(r'\s+', ' ', clean_title)
            
            # Title case: primeira maiúscula de cada palavra
            clean_title = clean_title.title()
            
            # Trunca se muito longo
            if len(clean_title) > 120:
                clean_title = clean_title[:117] + '...'
            
            return clean_title.strip()
        
        # === Fallback ===
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