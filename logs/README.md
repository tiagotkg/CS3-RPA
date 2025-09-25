# Logs do Sistema de Detecção de Pirataria

Este diretório contém os arquivos de log do sistema.

## Arquivos de Log

- `amazon_scraper.log` - Logs do scraper da Amazon
- `ai_classifier.log` - Logs do classificador de IA
- `pipeline.log` - Logs do pipeline integrado

## Formato dos Logs

Os logs seguem o formato:
```
YYYY-MM-DD HH:MM:SS - LEVEL - MESSAGE
```

## Níveis de Log

- **INFO**: Informações gerais sobre o funcionamento
- **WARNING**: Avisos sobre situações anômalas
- **ERROR**: Erros que não impedem o funcionamento
- **CRITICAL**: Erros críticos que impedem o funcionamento

## Rotação de Logs

Para evitar que os logs cresçam muito, considere implementar rotação de logs ou limpeza periódica.

## Monitoramento

Os logs podem ser monitorados em tempo real usando:
```bash
tail -f logs/amazon_scraper.log
tail -f logs/ai_classifier.log
tail -f logs/pipeline.log
```

