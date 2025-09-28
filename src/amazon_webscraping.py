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
from urllib.parse import urljoin, urlparse

class AmazonScraperV2:
    def __init__(self, headless=True, debug=False):
        """
        Inicializa o scraper da Amazon versão 2
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
                logging.FileHandler('logs/amazon_scraper_v2.log'),
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
    
    def scrape_product_listing(self, search_url, max_pages=3):
        """
        Extrai a listagem de produtos da página de busca
        """
        self.logger.info(f"Iniciando scraping da listagem: {search_url}")
        
        try:
            # Navegar para a página de busca
            self.driver.get(search_url)
            time.sleep(2)  # Aguardar carregamento inicial
            
            # Aguardar carregamento dos resultados
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-asin]"))
            )
            
            products = []
            
            for page in range(max_pages):
                self.logger.info(f"Processando página {page + 1}")
                
                # Aguardar carregamento dos produtos
                time.sleep(1)
                
                # Encontrar todos os produtos na página
                product_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-asin]")
                
                for element in product_elements:
                    try:
                        # Verificar se tem ASIN válido
                        asin = element.get_attribute("data-asin")
                        if not asin or asin.strip() == "":
                            continue
                        
                        # Extrair dados básicos do produto
                        product_data = self.extract_basic_product_info(element)
                        if product_data:
                            products.append(product_data)
                            
                    except Exception as e:
                        self.logger.warning(f"Erro ao extrair produto: {e}")
                        continue
                
                # Tentar ir para próxima página
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
            
            self.logger.info(f"Coletados {len(products)} produtos da listagem")
            return products
            
        except Exception as e:
            self.logger.error(f"Erro durante scraping da listagem: {e}")
            return []
    
    def extract_basic_product_info(self, element):
        """
        Extrai informações básicas do produto na listagem
        """
        try:
            # ASIN
            asin = element.get_attribute("data-asin")
            if not asin:
                return None
            
            # Título
            title = self.extract_title(element)
            if not title:
                return None
            
            # URL do produto
            product_url = self.extract_product_url(element)
            
            # Preço
            price = self.extract_price(element)
            
            # Avaliação
            rating = self.extract_rating(element)
            
            # Número de avaliações
            review_count = self.extract_review_count(element)
            
            # Vendedor (básico da listagem)
            seller = self.extract_seller_from_listing(element)
            
            return {
                'asin': asin,
                'title': title,
                'url': product_url,
                'price': price,
                'rating': rating,
                'review_count': review_count,
                'seller': seller,
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair informações básicas: {e}")
            return None
    
    def extract_title(self, element):
        """Extrai o título do produto"""
        title_selectors = [
            "h2 a span",
            "h2 span",
            "h2 a",
            ".s-size-mini .s-link-style .s-color-base",
            "h2 .a-link-normal .a-text-normal"
        ]
        
        for selector in title_selectors:
            try:
                title_element = element.find_element(By.CSS_SELECTOR, selector)
                title = title_element.text.strip()
                if title and len(title) > 3:
                    return title
            except NoSuchElementException:
                continue
        
        return None
    
    def extract_product_url(self, element):
        """Extrai a URL do produto"""
        try:
            link_element = element.find_element(By.CSS_SELECTOR, "h2 a")
            url = link_element.get_attribute("href")
            if self.debug:
                self.logger.info(f"URL extraída: {url}")
            return url
        except NoSuchElementException:
            if self.debug:
                self.logger.warning("Link h2 a não encontrado, tentando seletores alternativos")
            # Tentar seletores alternativos
            alternative_selectors = [
                "a[href*='/dp/']",
                "a[href*='/product/']",
                ".s-link-style a",
                "a[data-csa-c-content-id]"
            ]
            for selector in alternative_selectors:
                try:
                    link_element = element.find_element(By.CSS_SELECTOR, selector)
                    url = link_element.get_attribute("href")
                    if url and "/dp/" in url:
                        if self.debug:
                            self.logger.info(f"URL encontrada via seletor alternativo '{selector}': {url}")
                        return url
                except NoSuchElementException:
                    continue
            return None
    
    def extract_price(self, element):
        """Extrai o preço do produto"""
        price_selectors = [
            ".a-price-whole",
            ".a-price .a-offscreen",
            ".a-price-range .a-offscreen"
        ]
        
        for selector in price_selectors:
            try:
                price_element = element.find_element(By.CSS_SELECTOR, selector)
                price_text = price_element.text.replace("R$", "").replace(".", "").replace(",", ".").strip()
                if price_text and price_text.replace(".", "").isdigit():
                    return float(price_text)
            except (NoSuchElementException, ValueError):
                continue
        
        return None
    
    def extract_rating(self, element):
        """Extrai a avaliação do produto"""
        try:
            rating_element = element.find_element(By.CSS_SELECTOR, ".a-icon-alt")
            rating_text = rating_element.get_attribute("textContent")
            rating_match = re.search(r'(\d+[,.]\d+)', rating_text)
            if rating_match:
                return float(rating_match.group(1).replace(",", "."))
        except (NoSuchElementException, ValueError):
            pass
        
        return None
    
    def extract_review_count(self, element):
        """Extrai o número de avaliações"""
        try:
            review_element = element.find_element(By.CSS_SELECTOR, "a[href*='reviews'] span")
            review_text = review_element.text.replace(".", "").replace(",", "").strip()
            if review_text.isdigit():
                return int(review_text)
        except (NoSuchElementException, ValueError):
            pass
        
        return None
    
    def extract_seller_from_listing(self, element):
        """Extrai o vendedor da listagem (básico)"""
        try:
            # Procurar por texto "Vendido por" ou "Enviado por"
            element_text = element.text
            
            if self.debug:
                self.logger.info(f"Texto do elemento para análise de vendedor: {element_text[:200]}...")
            
            # Padrão: "Vendido por [Nome do Vendedor]"
            vendido_por_match = re.search(r'Vendido por\s+([^\n\r]+)', element_text, re.IGNORECASE)
            if vendido_por_match:
                seller_name = vendido_por_match.group(1).strip()
                if self.debug:
                    self.logger.info(f"Vendedor encontrado via 'Vendido por': {seller_name}")
                if self.is_valid_seller_name(seller_name):
                    return seller_name
            
            # Padrão: "Enviado por [Nome] / Vendido por [Nome]"
            enviado_vendido_match = re.search(r'Enviado por\s+([^/]+)\s*/\s*Vendido por\s+([^\n\r]+)', element_text, re.IGNORECASE)
            if enviado_vendido_match:
                seller_name = enviado_vendido_match.group(2).strip()
                if self.debug:
                    self.logger.info(f"Vendedor encontrado via 'Enviado/Vendido por': {seller_name}")
                if self.is_valid_seller_name(seller_name):
                    return seller_name
            
            # Procurar por indicadores de que é vendido pela Amazon
            amazon_indicators = [
                "Vendido por Amazon.com.br",
                "Vendido por Amazon",
                "Amazon.com.br"
            ]
            
            for indicator in amazon_indicators:
                if indicator in element_text:
                    if self.debug:
                        self.logger.info(f"Vendedor Amazon detectado: {indicator}")
                    return "Amazon.com.br"
            
            # Fallback: procurar por qualquer texto que possa ser vendedor
            if self.debug:
                self.logger.warning("Nenhum padrão de vendedor encontrado na listagem")
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair vendedor da listagem: {e}")
            return ""
    
    def scrape_product_details(self, product_url):
        """
        Acessa a página individual do produto para extrair mais detalhes
        """
        self.logger.info(f"Acessando página do produto: {product_url}")
        
        try:
            # Abrir nova aba
            original_window = self.driver.current_window_handle
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            try:
                # Navegar para a página do produto
                self.driver.get(product_url)
                time.sleep(2)  # Aguardar carregamento
                
                # Extrair informações detalhadas
                details = {
                    'seller_detailed': self.extract_detailed_seller(),
                    'price_detailed': self.extract_detailed_price(),
                    'description': self.extract_description(),
                    'specifications': self.extract_specifications(),
                    'availability': self.extract_availability(),
                    'shipping_info': self.extract_shipping_info()
                }
                
                return details
                
            finally:
                # Fechar aba e voltar para a original
                self.driver.close()
                self.driver.switch_to.window(original_window)
                
        except Exception as e:
            self.logger.error(f"Erro ao acessar página do produto: {e}")
            return {}
    
    def extract_detailed_seller(self):
        """Extrai informações detalhadas do vendedor"""
        try:
            if self.debug:
                self.logger.info("Iniciando extração detalhada do vendedor...")
            
            # 1. PRIMEIRO: Verificar se é vendido pela Amazon
            amazon_indicators = [
                "#merchant-info a[href*='amazon.com.br']",
                "#merchant-info a[href*='amazon.com']", 
                "#sellerProfileTriggerId[href*='amazon']",
                ".tabular-buybox-text a[href*='amazon']",
                "#shipsFromSoldByMessage_feature_div a[href*='amazon']",
                "[data-cel-widget='desktop-merchant-info'] a[href*='amazon']"
            ]
            
            for selector in amazon_indicators:
                try:
                    amazon_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in amazon_elements:
                        href = element.get_attribute("href")
                        text = element.text.strip()
                        if "amazon" in href.lower() or "amazon" in text.lower():
                            if self.debug:
                                self.logger.info(f"Amazon detectado via seletor '{selector}': {text}")
                            return "Amazon.com.br"
                except Exception:
                    continue
            
            # 2. SEGUNDO: Procurar por vendedores específicos com seletores expandidos
            seller_selectors = [
                "#sellerProfileTriggerId",
                "#merchant-info a",
                "#shipsFromSoldByMessage_feature_div a",
                ".tabular-buybox-text a",
                "[data-cel-widget='desktop-merchant-info'] a",
                "a[href*='seller']",
                "a[href*='merchant']",
                "a[href*='storefront']",
                ".a-size-small .a-link-normal[href*='seller']",
                ".a-size-small .a-link-normal[href*='merchant']",
                "a[data-csa-c-content-id='odf-desktop-merchant-info']",
                "a[data-csa-c-slot-id='odf-desktop-merchant-info-anchor-text']"
            ]
            
            # 2.1. PRIMEIRO: Tentar os seletores XPath específicos sugeridos
            xpath_selectors = [
                "//*[@id='merchantInfoFeature_feature_div']/div[2]",
                "//*[@id='fulfillerInfoFeature_feature_div']/div[2]"
            ]
            
            for xpath_selector in xpath_selectors:
                try:
                    merchant_element = self.driver.find_element(By.XPATH, xpath_selector)
                    merchant_text = merchant_element.text.strip()
                    if self.debug:
                        self.logger.info(f"Seletor XPath '{xpath_selector}' encontrou: '{merchant_text}'")
                    if self.is_valid_seller_name(merchant_text):
                        if self.debug:
                            self.logger.info(f"Vendedor válido encontrado via XPath: {merchant_text}")
                        return merchant_text
                except NoSuchElementException:
                    if self.debug:
                        self.logger.info(f"Seletor XPath '{xpath_selector}' não encontrou elementos")
                except Exception as e:
                    if self.debug:
                        self.logger.warning(f"Erro no seletor XPath '{xpath_selector}': {e}")
            
            for selector in seller_selectors:
                try:
                    seller_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for seller_element in seller_elements:
                        seller_text = seller_element.text.strip()
                        href = seller_element.get_attribute("href")
                        
                        # Pular se for link da Amazon
                        if href and "amazon" in href.lower():
                            continue
                            
                        if self.debug:
                            self.logger.info(f"Seletor '{selector}' encontrou: '{seller_text}' (href: {href})")
                        
                        if self.is_valid_seller_name(seller_text):
                            if self.debug:
                                self.logger.info(f"Vendedor válido encontrado: {seller_text}")
                            return seller_text
                except NoSuchElementException:
                    continue
            
            # 3. TERCEIRO: Procurar por padrões no texto da página (mais específicos)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            if self.debug:
                self.logger.info(f"Texto da página para análise: {page_text[:500]}...")
            
            # Padrões mais específicos e robustos
            patterns = [
                r'Vendido por\s+([^\n\r,]+?)(?:\s*$|\s*\(|\s*\|)',
                r'Enviado por\s+([^/]+?)\s*/\s*Vendido por\s+([^\n\r,]+?)(?:\s*$|\s*\(|\s*\|)',
                r'Sold by\s+([^\n\r,]+?)(?:\s*$|\s*\(|\s*\|)',
                r'Shipped by\s+([^/]+?)\s*/\s*Sold by\s+([^\n\r,]+?)(?:\s*$|\s*\(|\s*\|)',
                r'Vendedor:\s*([^\n\r,]+?)(?:\s*$|\s*\(|\s*\|)',
                r'Seller:\s*([^\n\r,]+?)(?:\s*$|\s*\(|\s*\|)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    if len(match.groups()) == 2:
                        seller_name = match.group(2).strip()
                    else:
                        seller_name = match.group(1).strip()
                    
                    # Limpar caracteres indesejados
                    seller_name = re.sub(r'[^\w\s\-\.]', '', seller_name).strip()
                    
                    if self.debug:
                        self.logger.info(f"Padrão regex encontrou: '{seller_name}'")
                    
                    if self.is_valid_seller_name(seller_name):
                        if self.debug:
                            self.logger.info(f"Vendedor válido via regex: {seller_name}")
                        return seller_name
            
            # 4. QUARTO: Procurar por indicadores específicos da Amazon no texto
            amazon_text_indicators = [
                "Vendido por Amazon.com.br",
                "Vendido por Amazon",
                "Sold by Amazon.com.br", 
                "Sold by Amazon",
                "Amazon.com.br",
                "Amazon"
            ]
            
            for indicator in amazon_text_indicators:
                if indicator in page_text:
                    if self.debug:
                        self.logger.info(f"Indicador Amazon encontrado no texto: {indicator}")
                    return "Amazon.com.br"
            
            # 5. QUINTO: Fallback - procurar qualquer link que não seja Amazon
            try:
                all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='seller'], a[href*='merchant'], a[href*='storefront']")
                for link in all_links:
                    href = link.get_attribute("href")
                    text = link.text.strip()
                    if href and "amazon" not in href.lower() and self.is_valid_seller_name(text):
                        if self.debug:
                            self.logger.info(f"Fallback encontrou vendedor: {text}")
                        return text
            except Exception:
                pass
            
            if self.debug:
                self.logger.warning("Nenhum vendedor identificado na página individual")
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair vendedor detalhado: {e}")
            return ""
    
    def extract_detailed_price(self):
        """Extrai preço detalhado da página individual do produto"""
        try:
            if self.debug:
                self.logger.info("Iniciando extração detalhada do preço...")
            
            # 1. PRIMEIRO: Tentar o seletor XPath específico sugerido
            try:
                price_element = self.driver.find_element(By.XPATH, "//*[@id='corePrice_feature_div']/div/div/div/div/span[1]/span[1]")
                price_text = price_element.text.strip()
                if self.debug:
                    self.logger.info(f"Seletor XPath específico encontrou preço: '{price_text}'")
                
                # Limpar e converter preço
                cleaned_price = price_text.replace("R$", "").replace(".", "").replace(",", ".").strip()
                if cleaned_price and cleaned_price.replace(".", "").isdigit():
                    price_value = float(cleaned_price)
                    if self.debug:
                        self.logger.info(f"Preço válido extraído via XPath: {price_value}")
                    return price_value
                    
            except NoSuchElementException:
                if self.debug:
                    self.logger.info("Seletor XPath específico não encontrou preço")
            except Exception as e:
                if self.debug:
                    self.logger.warning(f"Erro no seletor XPath específico: {e}")
            
            # 2. SEGUNDO: Tentar seletores CSS alternativos
            price_selectors = [
                "#corePrice_feature_div .a-price-whole",
                "#corePrice_feature_div .a-offscreen",
                ".a-price-whole",
                ".a-price .a-offscreen",
                ".a-price-range .a-offscreen",
                "#apex_desktop .a-price-whole",
                "#apex_desktop .a-offscreen"
            ]
            
            for selector in price_selectors:
                try:
                    price_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    price_text = price_element.text.strip()
                    if self.debug:
                        self.logger.info(f"Seletor CSS '{selector}' encontrou: '{price_text}'")
                    
                    # Limpar e converter preço
                    cleaned_price = price_text.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    if cleaned_price and cleaned_price.replace(".", "").isdigit():
                        price_value = float(cleaned_price)
                        if self.debug:
                            self.logger.info(f"Preço válido extraído via CSS: {price_value}")
                        return price_value
                        
                except NoSuchElementException:
                    continue
                except Exception as e:
                    if self.debug:
                        self.logger.warning(f"Erro no seletor CSS '{selector}': {e}")
                    continue
            
            # 3. TERCEIRO: Procurar por padrões no texto da página
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                if self.debug:
                    self.logger.info(f"Texto da página para análise de preço: {page_text[:500]}...")
                
                patterns = [
                    r'R\$\s*(\d+[,.]?\d*)',
                    r'(\d+[,.]?\d*)\s*reais',
                    r'Preço:\s*R\$\s*(\d+[,.]?\d*)',
                    r'Valor:\s*R\$\s*(\d+[,.]?\d*)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        price_text = match.group(1).replace(",", ".")
                        if price_text.replace(".", "").isdigit():
                            price_value = float(price_text)
                            if self.debug:
                                self.logger.info(f"Preço encontrado via regex: {price_value}")
                            return price_value
                            
            except Exception as e:
                if self.debug:
                    self.logger.warning(f"Erro na busca por padrões de preço: {e}")
            
            if self.debug:
                self.logger.warning("Nenhum preço identificado na página individual")
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair preço detalhado: {e}")
            return None
    
    def extract_description(self):
        """Extrai a descrição do produto"""
        try:
            description_selectors = [
                "#feature-bullets ul",
                ".a-unordered-list .a-list-item",
                "[data-feature-name='featureList']"
            ]
            
            for selector in description_selectors:
                try:
                    desc_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return desc_element.text.strip()
                except NoSuchElementException:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair descrição: {e}")
            return None
    
    def extract_specifications(self):
        """Extrai especificações do produto"""
        try:
            specs = {}
            
            # Procurar por tabela de especificações
            spec_selectors = [
                "#productDetails_techSpec_section_1 tr",
                ".a-keyvalue tr",
                "[data-feature-name='productDetails'] tr"
            ]
            
            for selector in spec_selectors:
                try:
                    spec_rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for row in spec_rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value = cells[1].text.strip()
                            if key and value:
                                specs[key] = value
                    break
                except NoSuchElementException:
                    continue
            
            return specs
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair especificações: {e}")
            return {}
    
    def extract_availability(self):
        """Extrai informações de disponibilidade"""
        try:
            availability_selectors = [
                "#availability span",
                ".a-size-medium.a-color-success",
                ".a-size-medium.a-color-price"
            ]
            
            for selector in availability_selectors:
                try:
                    avail_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return avail_element.text.strip()
                except NoSuchElementException:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair disponibilidade: {e}")
            return None
    
    def extract_shipping_info(self):
        """Extrai informações de frete"""
        try:
            shipping_selectors = [
                "#delivery-block .a-size-base",
                ".a-size-base.a-color-secondary"
            ]
            
            for selector in shipping_selectors:
                try:
                    shipping_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return shipping_element.text.strip()
                except NoSuchElementException:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair informações de frete: {e}")
            return None
    
    def is_valid_seller_name(self, text):
        """Valida se o texto é um nome de vendedor válido"""
        if not text or text.strip() == "":
            return False
        
        text = text.strip()
        
        if self.debug:
            self.logger.info(f"Validando nome de vendedor: '{text}'")
        
        # Filtrar textos que claramente não são nomes de vendedores
        invalid_keywords = [
            'avaliação', 'review', 'rating', 'estrela', 'star',
            'avaliações', 'reviews', 'disponível', 'available',
            'preço', 'price', 'frete', 'shipping', 'entrega', 'delivery',
            'mais vendidos', 'best sellers', 'escolha da amazon',
            'amazon choice', 'patrocinado', 'sponsored',
            'pesquisas relacionadas', 'related searches',
            'anterior', 'próximo', 'next', 'previous',
            'departamentos', 'departments', 'categoria', 'category',
            'ver mais', 'see more', 'ver ofertas', 'see offers',
            'produtos similares', 'similar products',
            'outras opções', 'other options',
            # Termos genéricos que não são nomes
            'vendido por', 'enviado por', 'sold by', 'shipped by'
        ]
        
        text_lower = text.lower()
        for keyword in invalid_keywords:
            if keyword in text_lower:
                if self.debug:
                    self.logger.info(f"Nome rejeitado por palavra-chave: '{keyword}'")
                return False
        
        # Verificar se tem pelo menos 2 caracteres
        if len(text) < 2:
            if self.debug:
                self.logger.info("Nome rejeitado por ser muito curto")
            return False
        
        # Verificar se não é um número puro
        try:
            float(text.replace(',', '.'))
            if self.debug:
                self.logger.info("Nome rejeitado por ser apenas número")
            return False
        except ValueError:
            pass
        
        # Verificar se não contém apenas caracteres especiais
        if not any(c.isalnum() for c in text):
            if self.debug:
                self.logger.info("Nome rejeitado por não conter caracteres alfanuméricos")
            return False
        
        # Verificar se não é muito longo (provavelmente não é nome de vendedor)
        if len(text) > 100:
            if self.debug:
                self.logger.info("Nome rejeitado por ser muito longo")
            return False
        
        if self.debug:
            self.logger.info(f"Nome de vendedor válido: '{text}'")
        
        return True
    
    def scrape_complete_products(self, search_url, max_pages=3):
        """
        Scraping completo: listagem + detalhes de cada produto
        """
        self.logger.info("Iniciando scraping completo")
        
        # 1. Extrair listagem de produtos
        products = self.scrape_product_listing(search_url, max_pages)
        
        # 2. Para cada produto, acessar página individual
        complete_products = []
        
        for i, product in enumerate(products):
            self.logger.info(f"Processando produto {i+1}/{len(products)}: {product['title'][:50]}...")
            
            if product['url']:
                # Extrair detalhes da página individual
                details = self.scrape_product_details(product['url'])
                
                if self.debug:
                    self.logger.info(f"Detalhes extraídos: {details}")
                
                # Combinar dados básicos com detalhes
                complete_product = {**product, **details}
                complete_products.append(complete_product)
                
                # Pausa entre produtos para evitar bloqueio
                time.sleep(2)
            else:
                if self.debug:
                    self.logger.warning(f"Produto sem URL: {product['title'][:50]}")
                complete_products.append(product)
        
        return complete_products
    
    def save_to_csv(self, products, filename="resultados/produtos_amazon_v2.csv"):
        """Salva os produtos em CSV"""
        if not products:
            self.logger.warning("Nenhum produto para salvar")
            return
        
        df = pd.DataFrame(products)
        df.to_csv(filename, index=False, encoding='utf-8')
        self.logger.info(f"Produtos salvos em {filename}")
        
        # Estatísticas
        self.logger.info(f"Total de produtos: {len(df)}")
        if 'seller_detailed' in df.columns:
            identified_sellers = df['seller_detailed'].notna().sum()
            self.logger.info(f"Vendedores identificados: {identified_sellers}")
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Driver fechado")

def main():
    """Função principal para testar o scraper"""
    scraper = AmazonScraperV2(headless=False, debug=True)
    
    try:
        # URL de busca fornecida
        search_url = "https://www.amazon.com.br/s?k=cartucho+hp+667&crid=1U2CLTC8YJUQ3&sprefix=cartu%2Caps%2C601&ref=nb_sb_ss_ts-doa-p_1_5"
        
        # Fazer scraping completo
        products = scraper.scrape_complete_products(search_url, max_pages=2)
        
        # Salvar resultados
        scraper.save_to_csv(products)
        
        # Mostrar resultados
        if products:
            print(f"\n=== RESULTADOS DO SCRAPING ===")
            print(f"Total de produtos: {len(products)}")
            
            for i, product in enumerate(products[:5]):  # Mostrar apenas os primeiros 5
                print(f"\n--- Produto {i+1} ---")
                print(f"Título: {product.get('title', 'N/A')}")
                print(f"Preço: R$ {product.get('price', 'N/A')}")
                print(f"Vendedor (listagem): {product.get('seller', 'N/A')}")
                print(f"Vendedor (detalhado): {product.get('seller_detailed', 'N/A')}")
                print(f"URL: {product.get('url', 'N/A')}")
    
    except Exception as e:
        print(f"Erro durante o scraping: {e}")
    
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
