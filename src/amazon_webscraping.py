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
                        # Filtrar banners/cabeçalhos/itens sem ASIN
                        try:
                            asin_value = element.get_attribute("data-asin")
                        except Exception:
                            asin_value = None
                        if asin_value is not None and asin_value.strip() == "":
                            if self.debug:
                                self.logger.info("Elemento sem ASIN (provável banner/cabeçalho) ignorado")
                            continue
                        
                        # Filtrar blocos claramente não-produto (ex.: Patrocinado/cabeçalhos)
                        try:
                            element_text_head = (element.text or "").strip().lower()[:60]
                        except Exception:
                            element_text_head = ""
                        if any(flag in element_text_head for flag in [
                            "patrocinado", "pesquisas relacionadas", "impressoras e acessórios",
                            "anterior", "próximo", "resultados", "escolha da amazon"
                        ]):
                            if self.debug:
                                self.logger.info(f"Bloco não-produto ignorado: {element_text_head}")
                            continue
                        
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
            # Validar ASIN do elemento (evita pegar banners/paginação)
            try:
                asin_value = element.get_attribute("data-asin")
            except Exception:
                asin_value = None
            if not asin_value or not re.match(r"^[A-Z0-9]{10}$", asin_value.strip(), re.IGNORECASE):
                if self.debug:
                    self.logger.info(f"Ignorado por ASIN inválido: '{asin_value}'")
                return None
            
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
            
            # Validar se é um produto real (não um texto genérico da Amazon)
            if not self.is_valid_product(title):
                if self.debug:
                    self.logger.info(f"Produto inválido filtrado: {title}")
                return None
            
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
            
            # Vendedor - extrair nome correto do vendedor
            seller = self.extract_seller_name(element)
            
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
    
    def extract_seller_name(self, element):
        """
        Extrai o nome do vendedor de um elemento de produto
        """
        # Primeiro, tentar extrair o vendedor da página de resultados
        seller = self.extract_seller_from_search_results(element)
        if seller and seller != "Não identificado":
            return seller
        
        # Se não encontrou na página de resultados, tentar acessar a página do produto
        return self.extract_seller_from_product_page(element)
    
    def extract_seller_from_search_results(self, element):
        """
        Extrai o nome do vendedor da página de resultados de busca
        """
        seller_selectors = [
            # Seletores para links de vendedor
            "a[href*='seller']",
            "a[href*='merchant']", 
            "a[href*='storefront']",
            # Seletores por atributos data
            "[data-cy='seller-name']",
            "[data-asin] a[href*='seller']",
            # Tag específica para informações de vendedor
            "a[data-csa-c-content-id='odf-desktop-merchant-info']",
            "a[data-csa-c-slot-id='odf-desktop-merchant-info-anchor-text']",
            ".offer-display-feature-text-message",
            "span.offer-display-feature-text-message",
            # Seletores por classes específicas
            ".a-size-small .a-link-normal[href*='seller']",
            ".a-size-small .a-link-normal[href*='merchant']",
            ".a-size-small .a-link-normal[href*='storefront']",
            ".a-color-secondary .a-size-small .a-link-normal",
            ".a-color-secondary .a-size-small",
            ".a-size-small .a-link-normal",
            ".a-size-small",
            # Seletores alternativos
            ".a-link-normal[href*='seller']",
            ".a-link-normal[href*='merchant']",
            ".a-link-normal[href*='storefront']"
        ]
        
        for selector in seller_selectors:
            try:
                seller_elements = element.find_elements(By.CSS_SELECTOR, selector)
                if self.debug:
                    self.logger.info(f"Seletor '{selector}' encontrou {len(seller_elements)} elementos")
                
                for seller_element in seller_elements:
                    # Para o seletor específico da Amazon, procurar pelo texto do vendedor
                    if "desktop-merchant-info" in selector:
                        # Procurar pelo texto do vendedor após "Enviado / Vendido"
                        try:
                            # Procurar pelo próximo elemento que contenha o nome do vendedor
                            parent = seller_element.find_element(By.XPATH, "./..")
                            all_text = parent.text
                            
                            if self.debug:
                                self.logger.info(f"Texto do elemento desktop-merchant-info: {all_text}")
                            
                            # Procurar por padrões como "Enviado por X / Vendido por Y"
                            import re
                            patterns = [
                                r'Enviado\s+por\s+([^/]+)\s*/\s*Vendido\s+por\s+([^\n\r]+)',
                                r'Vendido\s+por\s+([^\n\r]+)',
                                r'Enviado\s+por\s+([^\n\r]+)'
                            ]
                            
                            for pattern in patterns:
                                match = re.search(pattern, all_text, re.IGNORECASE)
                                if match:
                                    if len(match.groups()) == 2:
                                        # "Enviado por X / Vendido por Y" - pegar o vendedor
                                        seller_name = match.group(2).strip()
                                    else:
                                        # "Vendido por X" ou "Enviado por X"
                                        seller_name = match.group(1).strip()
                                    
                                    if self.is_valid_seller_name(seller_name):
                                        if self.debug:
                                            self.logger.info(f"Vendedor extraído via desktop-merchant-info: {seller_name}")
                                        return seller_name
                        except Exception as e:
                            if self.debug:
                                self.logger.warning(f"Erro ao processar desktop-merchant-info: {e}")
                            continue
                    else:
                        # Para outros seletores, usar a lógica original
                        seller_text = seller_element.text.strip()
                        if self.debug:
                            self.logger.info(f"Texto encontrado: '{seller_text}'")
                        
                        # Validar se é um nome de vendedor válido
                        if self.is_valid_seller_name(seller_text):
                            if self.debug:
                                self.logger.info(f"Vendedor extraído com seletor '{selector}': {seller_text}")
                            return seller_text
                        
            except NoSuchElementException:
                continue
        
        # Procurar por texto "Vendido por" ou "Enviado por" no elemento
        try:
            element_text = element.text
            if self.debug:
                self.logger.info(f"Texto do elemento: {element_text[:500]}...")
            
            # Procurar por padrões específicos da Amazon
            import re
            
            # Padrão: "Vendido por [Nome do Vendedor]"
            vendido_por_match = re.search(r'Vendido por\s+([^\n\r]+)', element_text, re.IGNORECASE)
            if vendido_por_match:
                seller_name = vendido_por_match.group(1).strip()
                if self.is_valid_seller_name(seller_name):
                    if self.debug:
                        self.logger.info(f"Vendedor encontrado via 'Vendido por': {seller_name}")
                    return seller_name
            
            # Padrão: "Enviado por [Nome] / Vendido por [Nome]"
            enviado_vendido_match = re.search(r'Enviado por\s+([^/]+)\s*/\s*Vendido por\s+([^\n\r]+)', element_text, re.IGNORECASE)
            if enviado_vendido_match:
                seller_name = enviado_vendido_match.group(2).strip()
                if self.is_valid_seller_name(seller_name):
                    if self.debug:
                        self.logger.info(f"Vendedor encontrado via 'Enviado/Vendido por': {seller_name}")
                    return seller_name
            
            # Procurar por indicadores de que é vendido pela Amazon
            amazon_indicators = [
                "Vendido por Amazon.com.br",
                "Vendido por Amazon"
            ]
            
            for indicator in amazon_indicators:
                if indicator in element_text:
                    return "Amazon.com.br"
                    
        except Exception as e:
            if self.debug:
                self.logger.warning(f"Erro ao processar texto do elemento: {e}")
            pass
        
        # Fallback: tentar extrair qualquer texto que possa ser vendedor
        try:
            # Procurar por qualquer texto que possa ser nome de vendedor
            element_text = element.text
            if self.debug:
                self.logger.info(f"Fallback - Texto completo: {element_text[:500]}...")
            
            # Procurar por padrões mais genéricos
            import re
            
            # Procurar por qualquer texto após "por" ou "by"
            generic_patterns = [
                r'Vendido\s+por\s+([A-Za-z][A-Za-z0-9\s\.\-]+)',
                r'Sold\s+by\s+([A-Za-z][A-Za-z0-9\s\.\-]+)',
                r'por\s+([A-Za-z][A-Za-z0-9\s\.\-]+)',
                r'by\s+([A-Za-z][A-Za-z0-9\s\.\-]+)',
                r'Enviado\s+por\s+([A-Za-z][A-Za-z0-9\s\.\-]+)',
                r'Shipped\s+by\s+([A-Za-z][A-Za-z0-9\s\.\-]+)'
            ]
            
            for pattern in generic_patterns:
                match = re.search(pattern, element_text, re.IGNORECASE)
                if match:
                    potential_seller = match.group(1).strip()
                    # Limpar o texto extraído
                    potential_seller = re.sub(r'\s+', ' ', potential_seller)  # Múltiplos espaços
                    potential_seller = potential_seller.strip()
                    
                    if self.is_valid_seller_name(potential_seller):
                        if self.debug:
                            self.logger.info(f"Vendedor encontrado via fallback: {potential_seller}")
                        return potential_seller
            
            # Tentar extrair apenas vendedores específicos conhecidos
            known_sellers = [
                'Amazon.com.br', 'Amazon', 'Microjet', 'TECKKIN', 'WISETA', 
                'Valuetoner', 'GPC Image', 'YATUNINK', 'ASANSH', 'Zencoma',
                'Supreme Quality', 'HP', 'Epson', 'Canon', 'Brother'
            ]
            
            for seller in known_sellers:
                if seller.lower() in element_text.lower():
                    if self.debug:
                        self.logger.info(f"Vendedor conhecido encontrado: {seller}")
                    return seller
            
            # Se não encontrar nada, retornar "Não identificado"
            if self.debug:
                self.logger.warning("Nenhum vendedor identificado, retornando 'Não identificado'")
            return "Não identificado"
            
        except Exception as e:
            if self.debug:
                self.logger.warning(f"Erro no fallback: {e}")
            return "Não identificado"
    
    def is_valid_seller_name(self, text):
        """
        Valida se o texto é um nome de vendedor válido
        """
        if not text or text.strip() == "":
            return False
        
        text = text.strip()
        
        # Filtrar textos que claramente não são nomes de vendedores
        invalid_patterns = [
            r'^\([0-9,\.\s]+\)$',  # Formato (número)
            r'^[0-9,\.\s]+$',      # Só números
            r'^\d+$',              # Apenas dígitos
            r'^\([0-9]+\)$',       # (número)
            r'^\d+[,\.]\d*$',      # Números com vírgula/ponto
            r'^\d+[,\.]\d*\s*(mil|thousand|k)$',  # Números com mil
            r'^\([0-9,\.\s]+\s*(mil|thousand|k)\)$',  # (número mil)
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return False
        
        # Filtrar palavras-chave que indicam que não é nome de vendedor
        invalid_keywords = [
            'avaliação', 'review', 'rating', 'estrela', 'star',
            'avaliações', 'reviews',
            'disponível', 'available',
            'preço', 'price', 'frete', 'shipping', 'entrega', 'delivery'
        ]
        
        text_lower = text.lower()
        for keyword in invalid_keywords:
            if keyword in text_lower:
                return False
        
        # Verificar se tem pelo menos 2 caracteres e não é só números
        if len(text) < 2:
            return False
        
        # Verificar se não começa ou termina com parênteses
        if text.startswith('(') or text.endswith(')'):
            return False
        
        # Verificar se não é um número puro
        try:
            float(text.replace(',', '.'))
            return False
        except ValueError:
            pass
        
        return True

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
    
    def is_valid_product(self, title):
        """
        Valida se o título representa um produto real
        """
        if not title or title == "Título não disponível":
            return False
        
        # Textos genéricos da Amazon que devem ser filtrados
        invalid_texts = [
            "Consulte as páginas dos produtos para ver outras opções de compra",
            "Consulte as páginas dos produtos para ver",
            "Ver outras opções de compra",
            "Outras opções de compra",
            "Ver mais opções",
            "Mais opções",
            "Ver produtos similares",
            "Produtos similares",
            "Ver ofertas",
            "Ofertas disponíveis",
            "Ver detalhes",
            "Detalhes do produto",
            "Ver informações",
            "Informações do produto",
            # Novos filtros: paginação, patrocinado e cabeçalhos de seções
            "Pesquisas relacionadas",
            "Patrocinado",
            "Impressoras e Acessórios",
            "Anterior",
            "Próximo",
            "Escolha da Amazon",
            "Mais vendidos",
            "Departamentos",
            "Categoria",
        ]
        
        title_lower = title.lower().strip()
        
        # Verificar se contém textos inválidos (match por substring)
        for invalid_text in invalid_texts:
            if invalid_text.lower() in title_lower:
                return False
        
        # Padrões específicos (regex) para paginação e seções
        invalid_regex = [
            r"^anterior\d+próximo$",
            r"^pesquisas\s+relacionadas$",
            r"^patrocinado$",
            r"^impressoras\s+e\s+acessórios$",
        ]
        for pattern in invalid_regex:
            if re.match(pattern, title_lower, re.IGNORECASE):
                return False
        
        # Verificar se é muito curto (menos de 10 caracteres)
        if len(title.strip()) < 10:
            return False
        
        # Verificar se contém apenas números ou caracteres especiais
        if title.strip().replace(" ", "").replace("-", "").replace("_", "").isalnum() == False and len(title.strip()) < 20:
            return False
        
        return True
    
    def extract_seller_from_product_page(self, element):
        """
        Extrai o nome do vendedor acessando a página individual do produto
        """
        try:
            # Encontrar o link do produto
            product_link = None
            try:
                # Tentar encontrar o link do produto
                link_element = element.find_element(By.CSS_SELECTOR, "h2 a, .a-link-normal[href*='/dp/']")
                product_link = link_element.get_attribute('href')
            except:
                try:
                    # Tentar encontrar por data-asin
                    asin_element = element.find_element(By.CSS_SELECTOR, "[data-asin]")
                    asin = asin_element.get_attribute('data-asin')
                    if asin:
                        product_link = f"https://www.amazon.com.br/dp/{asin}"
                except:
                    pass
            
            if not product_link:
                if self.debug:
                    self.logger.warning("Não foi possível encontrar o link do produto")
                return "Não identificado"
            
            if self.debug:
                self.logger.info(f"Acessando página do produto: {product_link}")
            
            # Abrir nova aba e acessar a página do produto
            original_window = self.driver.current_window_handle
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            try:
                self.driver.get(product_link)
                time.sleep(2)  # Aguardar carregamento
                
                # Procurar pelo vendedor usando o ID sellerProfileTriggerId
                seller_name = None
                
                # Tentar encontrar o elemento com ID sellerProfileTriggerId
                try:
                    seller_element = self.driver.find_element(By.ID, "sellerProfileTriggerId")
                    seller_name = seller_element.text.strip()
                    if self.debug:
                        self.logger.info(f"Vendedor encontrado via sellerProfileTriggerId: {seller_name}")
                except:
                    # Tentar outros seletores na página do produto
                    seller_selectors = [
                        "[data-cel-widget='desktop-merchant-info']",
                        "[offer-display-feature-name='desktop-merchant-info']",
                        ".offer-display-feature-label[data-cel-widget='desktop-merchant-info']",
                        "div[data-cel-widget='desktop-merchant-info']",
                        "div[offer-display-feature-name='desktop-merchant-info']",
                        "div.offer-display-feature-label[data-cel-widget='desktop-merchant-info']",
                        "#sellerProfileTriggerId",
                        "[data-cy='seller-name']",
                        "a[href*='seller']",
                        "a[href*='merchant']",
                        # Tag específica para informações de vendedor
                        "a[data-csa-c-content-id='odf-desktop-merchant-info']",
                        "a[data-csa-c-slot-id='odf-desktop-merchant-info-anchor-text']",
                        ".offer-display-feature-text-message",
                        "span.offer-display-feature-text-message"
                    ]
                    
                    for selector in seller_selectors:
                        try:
                            seller_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for seller_element in seller_elements:
                                seller_text = seller_element.text.strip()
                                if self.is_valid_seller_name(seller_text):
                                    seller_name = seller_text
                                    if self.debug:
                                        self.logger.info(f"Vendedor encontrado via seletor '{selector}': {seller_name}")
                                    break
                            if seller_name:
                                break
                        except:
                            continue
                
                # Se não encontrou, tentar extrair do texto da página
                if not seller_name:
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    import re
                    
                    patterns = [
                        r'Vendido\s+por\s+([^\n\r]+)',
                        r'Enviado\s+por\s+([^/]+)\s*/\s*Vendido\s+por\s+([^\n\r]+)',
                        r'Sold\s+by\s+([^\n\r]+)',
                        r'Shipped\s+by\s+([^/]+)\s*/\s*Sold\s+by\s+([^\n\r]+)'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, page_text, re.IGNORECASE)
                        if match:
                            if len(match.groups()) == 2:
                                seller_name = match.group(2).strip()
                            else:
                                seller_name = match.group(1).strip()
                            
                            if self.is_valid_seller_name(seller_name):
                                if self.debug:
                                    self.logger.info(f"Vendedor encontrado via regex: {seller_name}")
                                break
                
                return seller_name if seller_name and self.is_valid_seller_name(seller_name) else "Não identificado"
                
            finally:
                # Fechar a aba e voltar para a aba original
                self.driver.close()
                self.driver.switch_to.window(original_window)
                
        except Exception as e:
            if self.debug:
                self.logger.warning(f"Erro ao extrair vendedor da página do produto: {e}")
            return "Não identificado"

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
