import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import StandardScaler
import re
import pickle
import logging
from datetime import datetime

class PiracyDetectionClassifier:
    def __init__(self):
        """
        Inicializa o classificador de detecção de pirataria
        """
        self.setup_logging()
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.scaler = StandardScaler()
        self.model = None
        self.feature_names = []
        self.is_trained = False
        
    def setup_logging(self):
        """Configura o sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/ai_classifier.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_training_data(self, df):
        """
        Cria dados de treinamento baseados em regras heurísticas
        """
        self.logger.info("Criando dados de treinamento...")
        
        # Aplicar regras heurísticas para criar labels
        df['label'] = df.apply(self.apply_heuristic_rules, axis=1)
        
        # Criar features
        df['features'] = df.apply(self.create_features, axis=1)
        
        return df
    
    def apply_heuristic_rules(self, row):
        """
        Aplica regras heurísticas para classificar produtos
        """
        title = str(row.get('title', '')).lower()
        description = str(row.get('description', '')).lower()
        seller = str(row.get('seller', '')).lower()
        price = row.get('price', 0)
        
        # Palavras-chave suspeitas
        suspicious_keywords = [
            'genérico', 'cópia', 'compatível', 'recondicionado', 'usado',
            'refurbished', 'remanufactured', 'compatible', 'generic',
            'não original', 'alternativo', 'substituto', 'imitação',
            'falso', 'fake', 'replica', 'copia', 'compativel'
        ]
        
        # Palavras-chave de originalidade
        original_keywords = [
            'original', 'oficial', 'genuíno', 'autêntico', 'lacrado',
            'novo', 'novo lacrado', 'garantia', 'nota fiscal'
        ]
        
        # Vendedores confiáveis
        trusted_sellers = [
            'amazon', 'amazon.com.br', 'hp', 'hp brasil', 'oficial'
        ]
        
        # Vendedores suspeitos
        suspicious_sellers = [
            'marketplace', 'terceiros', 'vendedor externo', 'loja genérica'
        ]
        
        score = 0
        
        # Verificar palavras-chave suspeitas
        for keyword in suspicious_keywords:
            if keyword in title or keyword in description:
                score += 2
        
        # Verificar palavras-chave de originalidade
        for keyword in original_keywords:
            if keyword in title or keyword in description:
                score -= 1
        
        # Verificar vendedor
        if any(trusted in seller for trusted in trusted_sellers):
            score -= 1
        elif any(suspicious in seller for suspicious in suspicious_sellers):
            score += 2
        
        # Verificar preço (se muito baixo, pode ser suspeito)
        if price and price < 30:  # Preço muito baixo
            score += 1
        elif price and price > 200:  # Preço muito alto
            score += 0.5
        
        # Verificar descrição vazia ou muito curta
        if len(description) < 50:
            score += 1
        
        # Classificar baseado no score
        if score >= 2:
            return 'SUSPEITO'
        elif score <= -1:
            return 'ORIGINAL'
        else:
            return 'COMPATIVEL'
    
    def create_features(self, row):
        """
        Cria features para o modelo de ML
        """
        title = str(row.get('title', ''))
        description = str(row.get('description', ''))
        seller = str(row.get('seller', ''))
        price = row.get('price', 0)
        
        # Combinar texto
        text = f"{title} {description} {seller}"
        
        # Features numéricas
        features = {
            'price': price if price else 0,
            'title_length': len(title),
            'description_length': len(description),
            'has_price': 1 if price else 0,
            'price_ratio': self.calculate_price_ratio(row),
            'word_count': len(text.split()),
            'has_suspicious_words': self.count_suspicious_words(text),
            'has_original_words': self.count_original_words(text),
            'seller_trust_score': self.calculate_seller_trust(seller)
        }
        
        return features
    
    def calculate_price_ratio(self, row):
        """
        Calcula a razão entre preço atual e preço sugerido (se disponível)
        """
        price = row.get('price', 0)
        suggested_price = row.get('suggested_price', 0)
        
        if price and suggested_price:
            return price / suggested_price
        return 1.0
    
    def count_suspicious_words(self, text):
        """
        Conta palavras suspeitas no texto
        """
        suspicious_words = [
            'genérico', 'cópia', 'compatível', 'recondicionado', 'usado',
            'refurbished', 'remanufactured', 'compatible', 'generic',
            'não original', 'alternativo', 'substituto', 'imitação'
        ]
        
        text_lower = text.lower()
        count = sum(1 for word in suspicious_words if word in text_lower)
        return count
    
    def count_original_words(self, text):
        """
        Conta palavras que indicam originalidade
        """
        original_words = [
            'original', 'oficial', 'genuíno', 'autêntico', 'lacrado',
            'novo', 'garantia', 'nota fiscal', 'certificado'
        ]
        
        text_lower = text.lower()
        count = sum(1 for word in original_words if word in text_lower)
        return count
    
    def calculate_seller_trust(self, seller):
        """
        Calcula score de confiança do vendedor
        """
        seller_lower = seller.lower()
        
        trusted_sellers = ['amazon', 'hp', 'oficial']
        suspicious_sellers = ['marketplace', 'terceiros', 'vendedor externo']
        
        if any(trusted in seller_lower for trusted in trusted_sellers):
            return 1.0
        elif any(suspicious in seller_lower for suspicious in suspicious_sellers):
            return 0.0
        else:
            return 0.5
    
    def treinar_modelo(self, df):
        """
        Treina o modelo de classificação
        """
        self.logger.info("Iniciando treinamento do modelo...")
        
        # Criar dados de treinamento
        df_training = self.create_training_data(df.copy())
        
        # Separar features e labels
        X_text = df_training.apply(lambda row: f"{row.get('title', '')} {row.get('description', '')} {row.get('seller', '')}", axis=1)
        X_numeric = pd.DataFrame([f for f in df_training['features']])
        y = df_training['label']
        
        # Vetorizar texto
        X_text_vectorized = self.vectorizer.fit_transform(X_text)
        
        # Combinar features
        X_combined = np.hstack([X_text_vectorized.toarray(), X_numeric.values])
        
        # Dividir dados
        X_train, X_test, y_train, y_test = train_test_split(
            X_combined, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Normalizar features numéricas
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Treinar modelo (usando Random Forest)
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train_scaled, y_train)
        
        # Avaliar modelo
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        self.logger.info(f"Acurácia do modelo: {accuracy:.3f}")
        self.logger.info(f"Relatório de classificação:\n{classification_report(y_test, y_pred)}")
        
        self.is_trained = True
        
        return accuracy
    
    def prever(self, df):
        """
        Faz predições em novos dados
        """
        if not self.is_trained:
            raise ValueError("Modelo não foi treinado ainda")
        
        self.logger.info("Fazendo predições...")
        
        # Criar features
        df_features = df.copy()
        df_features['features'] = df_features.apply(self.create_features, axis=1)
        
        # Separar features
        X_text = df_features.apply(lambda row: f"{row.get('title', '')} {row.get('description', '')} {row.get('seller', '')}", axis=1)
        X_numeric = pd.DataFrame([f for f in df_features['features']])
        
        # Vetorizar texto
        X_text_vectorized = self.vectorizer.transform(X_text)
        
        # Combinar features
        X_combined = np.hstack([X_text_vectorized.toarray(), X_numeric.values])
        
        # Normalizar
        X_scaled = self.scaler.transform(X_combined)
        
        # Fazer predições
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        # Adicionar resultados ao DataFrame
        df['ai_prediction'] = predictions
        df['ai_confidence'] = np.max(probabilities, axis=1)
        df['ai_probabilities'] = [prob.tolist() for prob in probabilities]
        
        return df
    
    def save_model(self, filename="resultados/modelo_deteccao_pirataria.pkl"):
        """
        Salva o modelo treinado
        """
        if not self.is_trained:
            raise ValueError("Modelo não foi treinado ainda")
        
        model_data = {
            'model': self.model,
            'vectorizer': self.vectorizer,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'trained_at': datetime.now().isoformat()
        }
        
        with open(filename, 'wb') as f:
            pickle.dump(model_data, f)
        
        self.logger.info(f"Modelo salvo em {filename}")
    
    def load_model(self, filename="resultados/modelo_deteccao_pirataria.pkl"):
        """
        Carrega um modelo treinado
        """
        try:
            with open(filename, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.vectorizer = model_data['vectorizer']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.is_trained = True
            
            self.logger.info(f"Modelo carregado de {filename}")
            
        except FileNotFoundError:
            self.logger.error(f"Arquivo {filename} não encontrado")
            raise
    
    def analyze_risk_level(self, df):
        """
        Analisa o nível de risco dos produtos
        """
        self.logger.info("Analisando níveis de risco...")
        
        def calculate_risk_score(row):
            score = 0
            
            # Baseado na predição da IA
            if row.get('ai_prediction') == 'SUSPEITO':
                score += 3
            elif row.get('ai_prediction') == 'COMPATIVEL':
                score += 1
            
            # Baseado na confiança da IA
            confidence = row.get('ai_confidence', 0)
            if confidence < 0.7:
                score += 1
            
            # Baseado no preço
            price = row.get('price', 0)
            if price and price < 30:
                score += 2
            elif price and price > 200:
                score += 1
            
            # Baseado no vendedor
            seller = str(row.get('seller', '')).lower()
            if 'marketplace' in seller:
                score += 1
            
            return score
        
        df['risk_score'] = df.apply(calculate_risk_score, axis=1)
        
        # Classificar níveis de risco
        def classify_risk(score):
            if score >= 4:
                return 'ALTO'
            elif score >= 2:
                return 'MÉDIO'
            else:
                return 'BAIXO'
        
        df['risk_level'] = df['risk_score'].apply(classify_risk)
        
        return df

def main():
    """
    Função principal para testar o classificador
    """
    # Carregar dados existentes
    try:
        df = pd.read_csv('base_dados.csv')
        print(f"Dados carregados: {len(df)} registros")
    except FileNotFoundError:
        print("Arquivo base_dados.csv não encontrado")
        return
    
    # Inicializar classificador
    classifier = PiracyDetectionClassifier()
    
    try:
        # Treinar modelo
        accuracy = classifier.treinar_modelo(df)
        print(f"Acurácia do modelo: {accuracy:.3f}")
        
        # Fazer predições
        df_with_predictions = classifier.prever(df)
        
        # Analisar riscos
        df_with_risks = classifier.analyze_risk_level(df_with_predictions)
        
        # Salvar resultados
        df_with_risks.to_csv('resultados/produtos_com_analise_ia.csv', index=False)
        print("Resultados salvos em resultados/produtos_com_analise_ia.csv")
        
        # Mostrar estatísticas
        print(f"\n=== ESTATÍSTICAS ===")
        print(f"Total de produtos: {len(df_with_risks)}")
        print(f"Predições da IA:")
        print(df_with_risks['ai_prediction'].value_counts())
        print(f"\nNíveis de risco:")
        print(df_with_risks['risk_level'].value_counts())
        
        # Mostrar produtos de alto risco
        high_risk = df_with_risks[df_with_risks['risk_level'] == 'ALTO']
        if len(high_risk) > 0:
            print(f"\n=== PRODUTOS DE ALTO RISCO ===")
            for idx, row in high_risk.iterrows():
                print(f"Título: {row['title']}")
                print(f"Preço: R$ {row['price']}")
                print(f"Vendedor: {row['seller']}")
                print(f"Predição IA: {row['ai_prediction']} (confiança: {row['ai_confidence']:.2f})")
                print(f"Score de risco: {row['risk_score']}")
                print("-" * 50)
        
        # Salvar modelo
        classifier.save_model()
        
    except Exception as e:
        print(f"Erro durante o processamento: {e}")

if __name__ == "__main__":
    main()
