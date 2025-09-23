import time
import pandas as pd
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

class AmazonScraper:
    def __init__(self, headless=True, debug=False):
        """
        Inicializa o scraper da Amazon
        """
        self.debug = debug
        self.setup_logging()
        self.driver = None
        self.headless = headless
        self.setup_driver()
        
    def setup_logging(self):
        """Configura o sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/amazon_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_driver(self):
        """Configura o driver do Chrome"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.logger.info("Driver do Chrome configurado com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro ao configurar driver: {e}")
            raise
            
    def buscar_produtos(self, search_term, max_pages=3):
        """
        Busca produtos na Amazon
        """
        self.logger.info(f"Iniciando busca por: {search_term}")
        
        try:
            # Navegar para a Amazon Brasil
            self.driver.get("https://www.amazon.com.br")
            time.sleep(2)
            
            # Buscar o campo de pesquisa
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
            )
            
            # Inserir termo de busca
            search_box.clear()
            search_box.send_keys(search_term)
            
            # Clicar no botão de busca
            search_button = self.driver.find_element(By.ID, "nav-search-submit-button")
            search_button.click()
            
            # Aguardar carregamento dos resultados - tentar múltiplos seletores
            result_selectors = [
                "[data-asin]",  # Seletor mais confiável
                "[data-component-type='s-search-result']",
                ".s-result-item",
                ".s-search-result"
            ]
            
            results_loaded = False
            for selector in result_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    results_loaded = True
                    self.logger.info(f"Resultados carregados com seletor: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not results_loaded:
                self.logger.warning("Não foi possível carregar os resultados da busca")
                return []
            
            products = []
            
            # Coletar produtos de múltiplas páginas
            for page in range(max_pages):
                self.logger.info(f"Coletando produtos da página {page + 1}")
                
                # Aguardar carregamento dos produtos
                time.sleep(2)
                
                # Encontrar todos os produtos na página - tentar múltiplos seletores
                product_elements = []
                product_selectors = [
                    "[data-asin]",  # Seletor mais confiável
                    "[data-component-type='s-search-result']",
                    ".s-result-item",
                    ".s-search-result"
                ]
                
                for selector in product_selectors:
                    try:
                        product_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if product_elements:
                            self.logger.info(f"Encontrados {len(product_elements)} produtos com seletor: {selector}")
                            break
                    except Exception as e:
                        self.logger.warning(f"Erro ao buscar produtos com seletor {selector}: {e}")
                        continue
                
                for element in product_elements:
                    try:
                        product_data = self.extrair_dados_produto(element)
                        if product_data:
                            products.append(product_data)
                    except Exception as e:
                        self.logger.warning(f"Erro ao extrair dados do produto: {e}")
                        continue
                
                # Tentar ir para a próxima página
                if page < max_pages - 1:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "a[aria-label='Próxima página']")
                        if next_button.is_enabled():
                            next_button.click()
                            time.sleep(3)
                        else:
                            break
                    except NoSuchElementException:
                        self.logger.info("Não há mais páginas disponíveis")
                        break
            
            self.logger.info(f"Coletados {len(products)} produtos")
            return products
            
        except Exception as e:
            self.logger.error(f"Erro durante a busca: {e}")
            return []
    
    def extrair_dados_produto(self, element):
        """
        Extrai dados de um produto específico
        """
        try:
            # Título do produto - tentar múltiplos seletores
            title = None
            title_selectors = [
                "h2 a span",
                "h2 span",
                "h2 a",
                "[data-cy='title-recipe-title']",
                ".s-size-mini .s-link-style .s-color-base",
                "h2 .a-link-normal .a-text-normal",
                ".s-title-instructions-style span",
                "h2 .a-size-mini .a-link-normal",
                ".a-size-mini .a-link-normal span",
                "h2 .a-size-base-plus .a-color-base",
                ".a-size-base-plus .a-color-base",
                "h2 .a-size-medium .a-color-base",
                ".a-size-medium .a-color-base",
                "h2 .a-size-small .a-color-base",
                ".a-size-small .a-color-base",
                "h2 .a-text-normal",
                ".a-text-normal",
                "h2",
                "span[data-cy='title-recipe-title']",
                ".s-link-style span"
            ]
            
            for i, selector in enumerate(title_selectors):
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, selector)
                    title = title_element.text.strip()
                    if title and len(title) > 3:  # Título deve ter pelo menos 3 caracteres
                        self.logger.debug(f"Título extraído com seletor {i+1}: {selector}")
                        break
                except NoSuchElementException:
                    continue
            
            if not title:
                # Fallback: tentar extrair qualquer texto de h2
                try:
                    h2_elements = element.find_elements(By.TAG_NAME, "h2")
                    for h2 in h2_elements:
                        title = h2.text.strip()
                        if title and len(title) > 3:
                            self.logger.debug("Título extraído com fallback h2")
                            break
                except Exception:
                    pass
                
                if not title:
                    # Último fallback: tentar qualquer span com texto
                    try:
                        spans = element.find_elements(By.TAG_NAME, "span")
                        for span in spans:
                            text = span.text.strip()
                            if text and len(text) > 10 and len(text) < 200:  # Título razoável
                                title = text
                                self.logger.debug("Título extraído com fallback span")
                                break
                    except Exception:
                        pass
            
            if not title:
                if self.debug:
                    self.logger.warning("Não foi possível extrair o título do produto - tentando continuar sem título")
                    # Log do HTML do elemento para debug
                    try:
                        element_html = element.get_attribute('outerHTML')[:500]  # Primeiros 500 caracteres
                        self.logger.debug(f"HTML do elemento: {element_html}")
                    except Exception:
                        pass
                title = "Título não disponível"
            
            # URL do produto - tentar múltiplos seletores
            url = None
            url_selectors = [
                "h2 a",
                "a[href*='/dp/']",
                ".s-link-style",
                "h2 .a-link-normal"
            ]
            
            for selector in url_selectors:
                try:
                    url_element = element.find_element(By.CSS_SELECTOR, selector)
                    url = url_element.get_attribute("href")
                    if url and "/dp/" in url:
                        break
                except NoSuchElementException:
                    continue
            
            # Preço - tentar múltiplos seletores
            price = None
            price_selectors = [
                ".a-price-whole",
                ".a-price .a-offscreen",
                ".a-price-range .a-offscreen",
                ".a-price-symbol + .a-price-whole",
                "[data-a-color='price'] .a-offscreen",
                ".a-price .a-price-whole",
                ".a-price-range .a-price-whole",
                ".a-price .a-price-symbol + .a-price-whole",
                ".a-price .a-price-symbol + .a-price-fraction",
                ".a-price .a-price-whole + .a-price-fraction",
                ".a-price .a-price-symbol + .a-price-whole + .a-price-fraction",
                ".a-price .a-price-whole",
                ".a-price .a-price-fraction",
                ".a-price .a-price-symbol",
                ".a-price .a-price-whole + .a-price-fraction",
                ".a-price .a-price-symbol + .a-price-whole + .a-price-fraction",
                ".a-price .a-price-whole + .a-price-fraction",
                ".a-price .a-price-symbol + .a-price-whole + .a-price-fraction",
                ".a-price .a-price-whole + .a-price-fraction",
                ".a-price .a-price-symbol + .a-price-whole + .a-price-fraction"
            ]
            
            for selector in price_selectors:
                try:
                    price_element = element.find_element(By.CSS_SELECTOR, selector)
                    price_text = price_element.text if hasattr(price_element, 'text') else price_element.get_attribute("textContent")
                    price_text = price_text.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    if price_text and price_text.replace(".", "").isdigit():
                        price = float(price_text)
                        break
                except (NoSuchElementException, ValueError):
                    continue
            
            # Fallback para preço: tentar extrair qualquer texto que pareça preço
            if not price:
                try:
                    # Procurar por padrões de preço em todo o elemento
                    element_text = element.text
                    price_patterns = [
                        r'R\$\s*(\d+[,.]?\d*)',
                        r'(\d+[,.]?\d*)\s*reais',
                        r'(\d+[,.]?\d*)\s*R\$',
                        r'(\d+[,.]?\d*)\s*\$'
                    ]
                    
                    for pattern in price_patterns:
                        match = re.search(pattern, element_text, re.IGNORECASE)
                        if match:
                            price_text = match.group(1).replace(",", ".")
                            if price_text.replace(".", "").isdigit():
                                price = float(price_text)
                                break
                except (ValueError, AttributeError):
                    pass
            
            # Avaliação - tentar múltiplos seletores
            rating = None
            rating_selectors = [
                ".a-icon-alt",
                "[aria-label*='estrelas']",
                ".a-icon-star-small .a-icon-alt",
                ".a-icon-star .a-icon-alt"
            ]
            
            for selector in rating_selectors:
                try:
                    rating_element = element.find_element(By.CSS_SELECTOR, selector)
                    rating_text = rating_element.get_attribute("textContent") or rating_element.get_attribute("aria-label")
                    rating_match = re.search(r'(\d+[,.]\d+)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1).replace(",", "."))
                        break
                except (NoSuchElementException, ValueError):
                    continue
            
            # Número de avaliações - tentar múltiplos seletores
            review_count = None
            review_selectors = [
                "a[href*='reviews'] span",
                ".a-size-base",
                "[aria-label*='avaliações']",
                ".a-link-normal span"
            ]
            
            for selector in review_selectors:
                try:
                    review_element = element.find_element(By.CSS_SELECTOR, selector)
                    review_text = review_element.text.replace(".", "").replace(",", "").strip()
                    if review_text.isdigit():
                        review_count = int(review_text)
                        break
                except (NoSuchElementException, ValueError):
                    continue
            
            # Vendedor - tentar múltiplos seletores
            seller = None
            seller_selectors = [
                ".a-size-small .a-link-normal",
                ".a-size-small",
                "[data-cy='seller-name']",
                ".a-color-secondary .a-size-small"
            ]
            
            for selector in seller_selectors:
                try:
                    seller_element = element.find_element(By.CSS_SELECTOR, selector)
                    seller = seller_element.text.strip()
                    if seller and seller not in ["", "Amazon.com.br"]:
                        break
                except NoSuchElementException:
                    continue
            
            # Verificar se é produto da Amazon
            if not seller:
                seller = "Amazon.com.br"
            
            # Determinar se é produto original ou suspeito baseado em palavras-chave
            is_suspicious = self.analyze_product_suspicion(title, seller)
            
            product_data = {
                'title': title,
                'url': url,
                'price': price,
                'rating': rating,
                'review_count': review_count,
                'seller': seller,
                'search_term': getattr(self, 'current_search', ''),
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_suspicious': is_suspicious,
                'suspicion_reasons': self.get_suspicion_reasons(title, seller)
            }
            
            return product_data
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair dados do produto: {e}")
            return None
    
    def analyze_product_suspicion(self, title, seller):
        """
        Analisa se um produto é suspeito baseado em palavras-chave
        """
        title_lower = title.lower()
        seller_lower = seller.lower() if seller else ""
        
        # Palavras-chave suspeitas
        suspicious_keywords = [
            'genérico', 'cópia', 'compatível', 'recondicionado', 'usado',
            'refurbished', 'remanufactured', 'compatible', 'generic',
            'não original', 'alternativo', 'substituto'
        ]
        
        # Vendedores suspeitos (exemplos)
        suspicious_sellers = [
            'marketplace', 'terceiros', 'vendedor externo'
        ]
        
        # Verificar palavras-chave no título
        for keyword in suspicious_keywords:
            if keyword in title_lower:
                return True
        
        # Verificar vendedor suspeito
        for suspicious_seller in suspicious_sellers:
            if suspicious_seller in seller_lower:
                return True
        
        return False
    
    def get_suspicion_reasons(self, title, seller):
        """
        Retorna as razões para suspeita
        """
        reasons = []
        title_lower = title.lower()
        seller_lower = seller.lower() if seller else ""
        
        suspicious_keywords = [
            'genérico', 'cópia', 'compatível', 'recondicionado', 'usado',
            'refurbished', 'remanufactured', 'compatible', 'generic',
            'não original', 'alternativo', 'substituto'
        ]
        
        for keyword in suspicious_keywords:
            if keyword in title_lower:
                reasons.append(f"Palavra-chave suspeita: '{keyword}'")
        
        if 'marketplace' in seller_lower:
            reasons.append("Vendedor marketplace")
        
        return reasons
    
    def scrape_hp_cartridges(self):
        """
        Scraping específico para cartuchos HP
        """
        search_terms = [
            "cartucho HP 667",
            "cartucho HP 667XL",
            "cartucho HP 664",
            "cartucho HP 662"
        ]
        
        all_products = []
        
        for term in search_terms:
            self.current_search = term
            self.logger.info(f"Buscando: {term}")
            products = self.buscar_produtos(term, max_pages=2)
            all_products.extend(products)
            time.sleep(2)  # Pausa entre buscas
        
        return all_products
    
    def save_to_csv(self, products, filename="resultados/produtos_amazon.csv"):
        """
        Salva os produtos em CSV
        """
        if not products:
            self.logger.warning("Nenhum produto para salvar")
            return
        
        df = pd.DataFrame(products)
        df.to_csv(filename, index=False, encoding='utf-8')
        self.logger.info(f"Produtos salvos em {filename}")
        
        # Estatísticas
        suspicious_count = df['is_suspicious'].sum()
        self.logger.info(f"Total de produtos: {len(df)}")
        self.logger.info(f"Produtos suspeitos: {suspicious_count}")
        self.logger.info(f"Taxa de suspeita: {suspicious_count/len(df)*100:.1f}%")
    
    def close(self):
        """
        Fecha o driver
        """
        if self.driver:
            self.driver.quit()
            self.logger.info("Driver fechado")

def main():
    """
    Função principal para testar o scraper
    """
    scraper = AmazonScraper(headless=False)  # headless=False para ver o navegador
    
    try:
        # Fazer scraping de cartuchos HP
        products = scraper.scrape_hp_cartridges()
        
        # Salvar resultados
        scraper.save_to_csv(products)
        
        # Mostrar alguns resultados
        if products:
            print(f"\n=== RESULTADOS DO SCRAPING ===")
            print(f"Total de produtos encontrados: {len(products)}")
            
            suspicious_products = [p for p in products if p['is_suspicious']]
            print(f"Produtos suspeitos: {len(suspicious_products)}")
            
            if suspicious_products:
                print(f"\n=== PRODUTOS SUSPEITOS ===")
                for product in suspicious_products[:5]:  # Mostrar apenas os primeiros 5
                    print(f"Título: {product['title']}")
                    print(f"Preço: R$ {product['price']}")
                    print(f"Vendedor: {product['seller']}")
                    print(f"Razões: {', '.join(product['suspicion_reasons'])}")
                    print("-" * 50)
    
    except Exception as e:
        print(f"Erro durante o scraping: {e}")
    
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
