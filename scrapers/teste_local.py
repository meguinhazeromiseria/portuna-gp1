#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 TESTE LOCAL DOS SCRAPERS"""

import os
import sys


def menu():
    """Menu interativo"""
    
    print("\n" + "="*60)
    print("🧪 TESTE LOCAL DE SCRAPERS")
    print("="*60)
    
    # Verifica env vars
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        print("\n❌ Variáveis de ambiente não configuradas!")
        print("\nConfigurecliente:")
        print("  export SUPABASE_URL='sua_url'")
        print("  export SUPABASE_SERVICE_ROLE_KEY='sua_key'")
        sys.exit(1)
    
    # Testa conexão
    print("\n🔌 Testando conexão com Supabase...")
    try:
        from supabase_client import SupabaseClient
        client = SupabaseClient()
        if not client.test():
            print("❌ Falha na conexão!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("SCRAPERS DISPONÍVEIS")
    print("="*60)
    print("\n1) 🚗 Veículos")
    print("2) 💻 Tecnologia")
    print("3) 🛍️  Bens de Consumo")
    print("4) 🔌 Eletrodomésticos")
    print("5) 🚀 Todos (sequencial)")
    print("0) ❌ Sair")
    
    escolha = input("\nEscolha uma opção [0-5]: ").strip()
    
    opcoes = {
        '1': ('veiculos', '🚗'),
        '2': ('tecnologia', '💻'),
        '3': ('bens_consumo', '🛍️'),
        '4': ('eletrodomesticos', '🔌'),
    }
    
    if escolha == '0':
        print("\n👋 Até logo!")
        sys.exit(0)
    
    elif escolha == '5':
        print("\n🚀 EXECUTANDO TODOS OS SCRAPERS")
        print("="*60)
        
        for cat, emoji in opcoes.values():
            executar_scraper(cat, emoji)
            print("\n" + "-"*60 + "\n")
    
    elif escolha in opcoes:
        cat, emoji = opcoes[escolha]
        executar_scraper(cat, emoji)
    
    else:
        print("\n❌ Opção inválida!")
        sys.exit(1)


def executar_scraper(categoria: str, emoji: str):
    """Executa um scraper específico"""
    
    print(f"\n{emoji} SCRAPER: {categoria.upper()}")
    print("="*60)
    
    # Pergunta fonte
    print("\nFonte:")
    print("  1) Sodré")
    print("  2) Megaleilões")
    print("  3) Superbid")
    print("  4) Todas")
    
    fonte_escolha = input("\nEscolha [1-4, padrão=4]: ").strip() or '4'
    
    fontes_map = {
        '1': 'sodre',
        '2': 'megaleiloes',
        '3': 'superbid',
        '4': 'all'
    }
    
    fonte = fontes_map.get(fonte_escolha, 'all')
    
    print(f"\n🎯 Executando {categoria}.py --fonte {fonte}...")
    print("-"*60 + "\n")
    
    # Executa
    import subprocess
    
    try:
        result = subprocess.run(
            ['python3', f'{categoria}.py', '--fonte', fonte],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n✅ {categoria} concluído com sucesso!")
        else:
            print(f"\n❌ {categoria} falhou com código {result.returncode}")
    
    except Exception as e:
        print(f"\n❌ Erro ao executar: {e}")


def teste_rapido():
    """Teste rápido de todos os normalizadores"""
    
    print("\n" + "="*60)
    print("⚡ TESTE RÁPIDO DOS NORMALIZADORES")
    print("="*60)
    
    testes = [
        ("veiculos", "LOTE 123 CHEVROLET ONIX 1.0 2018/2019 PLACA ABC1D23"),
        ("tecnologia", "LOTE 456 NOTEBOOK DELL INSPIRON 15 I5 8GB 1TB"),
        ("bens_consumo", "LOTE 789 TENIS NIKE AIR MAX TAMANHO 42"),
        ("eletrodomesticos", "LOTE 321 GELADEIRA BRASTEMP 400L FROST FREE"),
    ]
    
    for cat, titulo_teste in testes:
        try:
            modulo = __import__(cat)
            normalizado = modulo.Normalizador.normalizar(titulo_teste)
            print(f"\n✅ {cat.upper()}")
            print(f"   Original: {titulo_teste}")
            print(f"   Normalizado: {normalizado}")
        except Exception as e:
            print(f"\n❌ {cat}: {e}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--teste-rapido', action='store_true', help='Testa apenas os normalizadores')
    args = parser.parse_args()
    
    if args.teste_rapido:
        teste_rapido()
    else:
        menu()
