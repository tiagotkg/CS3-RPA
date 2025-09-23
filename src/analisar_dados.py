import pandas as pd
import numpy as np

# Carregar os dados
print("=== ANÁLISE DOS DADOS EXISTENTES ===\n")

# Analisar base_dados.csv
print("1. ANÁLISE DA BASE DE DADOS (base_dados.csv):")
print("-" * 50)
df_base = pd.read_csv('data/base_dados.csv')
print(f"Total de registros: {len(df_base)}")
print(f"Colunas: {list(df_base.columns)}")
print(f"\nPrimeiras 3 linhas:")
print(df_base.head(3))
print(f"\nTipos de dados:")
print(df_base.dtypes)
print(f"\nValores únicos por coluna:")
for col in df_base.columns:
    unique_count = df_base[col].nunique()
    print(f"  {col}: {unique_count} valores únicos")

print(f"\nEstatísticas de preços:")
print(df_base['price'].describe())

print(f"\nDistribuição de marcas:")
print(df_base['brand'].value_counts())

print(f"\nDistribuição de tipos de cartucho:")
print(df_base['cartridge_type'].value_counts())

# Analisar catalogo.csv
print("\n\n2. ANÁLISE DO CATÁLOGO (catalogo.csv):")
print("-" * 50)
df_catalogo = pd.read_csv('data/catalogo.csv')
print(f"Total de registros: {len(df_catalogo)}")
print(f"Colunas: {list(df_catalogo.columns)}")
print(f"\nPrimeiras 5 linhas:")
print(df_catalogo.head())

print(f"\nFamílias de produtos:")
print(df_catalogo['Familia'].value_counts())

print(f"\nEstatísticas de preços sugeridos:")
# Converter preço sugerido para float (aceitando vírgula decimal)
df_catalogo['Preço_Sugerido_Float'] = pd.to_numeric(
    df_catalogo['Preço Sugerido'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
    errors='coerce'
)
print(df_catalogo['Preço_Sugerido_Float'].describe())

# Análise de compatibilidade
print(f"\n\n3. ANÁLISE DE COMPATIBILIDADE:")
print("-" * 50)

# Verificar produtos HP 667 na base de dados (model é int64 no CSV)
hp667_base = df_base[df_base['model'] == 667]
print(f"Produtos HP 667 na base de dados: {len(hp667_base)}")

# Verificar produtos HP 667 no catálogo
hp667_catalogo = df_catalogo[df_catalogo['Familia'] == 'HP 667']
print(f"Produtos HP 667 no catálogo: {len(hp667_catalogo)}")

print(f"\nProdutos HP 667 no catálogo:")
print(hp667_catalogo[['PN', 'Produto', 'Preço Sugerido']])

# Análise de preços
print(f"\n\n4. ANÁLISE DE PREÇOS:")
print("-" * 50)
hp667_prices = hp667_base['price'].astype(float)
hp667_suggested = hp667_catalogo['Preço_Sugerido_Float']

print(f"Preços HP 667 na base de dados:")
if len(hp667_prices) > 0:
    print(hp667_prices.describe())
else:
    print("(sem registros para HP 667 na base)")

print(f"\nPreços sugeridos HP 667 no catálogo:")
if len(hp667_suggested) > 0:
    print(hp667_suggested.describe())
else:
    print("(sem registros no catálogo para HP 667)")

# Identificar possíveis anomalias de preço
print(f"\n\n5. POSSÍVEIS ANOMALIAS DE PREÇO:")
print("-" * 50)

# Tornar a detecção mais sensível: abaixo de 80% do mínimo sugerido ou acima de 130% do máximo sugerido
LOW_FACTOR = 0.80
HIGH_FACTOR = 1.30

anomaly_count = 0
if len(hp667_base) > 0 and len(hp667_suggested) > 0:
    min_sugg = hp667_suggested.min()
    max_sugg = hp667_suggested.max()
    low_thr = min_sugg * LOW_FACTOR if pd.notna(min_sugg) else None
    high_thr = max_sugg * HIGH_FACTOR if pd.notna(max_sugg) else None

    for idx, row in hp667_base.iterrows():
        try:
            price = float(row['price']) if pd.notna(row['price']) else None
        except Exception:
            price = None
        if price is None:
            continue
        # Comparar com thresholds sensíveis
        if low_thr is not None and price < low_thr:
            print(f"PREÇO SUSPEITO (baixo): {row['title']} - R$ {price:.2f} (< {LOW_FACTOR*100:.0f}% do mínimo sugerido {min_sugg:.2f})")
            anomaly_count += 1
        elif high_thr is not None and price > high_thr:
            print(f"PREÇO SUSPEITO (alto): {row['title']} - R$ {price:.2f} (> {HIGH_FACTOR*100:.0f}% do máximo sugerido {max_sugg:.2f})")
            anomaly_count += 1

    if anomaly_count == 0:
        print("Nenhuma anomalia detectada com thresholds 70%/150%.")
else:
    print("(sem base suficiente para detectar anomalias de preço)")

print(f"\n\n6. ANÁLISE DE DESCRIÇÕES SUSPEITAS:")
print("-" * 50)
suspicious_keywords = ['genérico', 'cópia', 'compatível', 'recondicionado', 'usado', 'refurbished']

for idx, row in df_base.iterrows():
    description = str(row['description']).lower()
    title = str(row['title']).lower()
    
    for keyword in suspicious_keywords:
        if keyword in description or keyword in title:
            print(f"PRODUTO SUSPEITO (palavra-chave '{keyword}'): {row['title']}")
            break
